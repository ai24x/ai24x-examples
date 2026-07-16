from __future__ import annotations

import csv
import glob as _glob
import io
import logging
import os as _os
import random
import re
import string
import time
from typing import Optional
from urllib.parse import quote

# v1.09: startup pycache + signal cache cleaner (prevent stale bytecode on Windows)
def _startup_clean():
    base = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    # 1) clear all __pycache__ in api/server tree
    for root, dirs, files in _os.walk(base):
        if root.endswith("__pycache__"):
            for f in files:
                if f.endswith(".pyc"):
                    try: _os.remove(_os.path.join(root, f))
                    except: pass
    # 2) clear stale signal caches
    sd = _os.path.join(base, "data", "signal_cache")
    if _os.path.isdir(sd):
        for f in _glob.glob(_os.path.join(sd, "*.json")):
            try: _os.remove(f)
            except: pass
_startup_clean()

import httpx
from fastapi import Cookie, Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, Response

from . import alipay_wap, db, wechat_v3
from .admin_baseline import log_admin_security_baseline
from .admin_auth import COOKIE_NAME, SESSION_TTL_S, admin_key_matches, issue_admin_session, verify_admin_session
from .admin_otp import (
    admin_browser_otp_feature_enabled,
    admin_browser_otp_required,
    admin_otp_generate,
    admin_otp_put,
    admin_otp_verify_and_consume,
    dev_admin_otp_bypass_code,
    is_phone_allowed_for_admin_otp,
    normalize_admin_phone,
)
from .billing_runtime import identity_configured, resolve_alipay, resolve_billing, resolve_identity, resolve_wechat_pay
from .auth import create_token, get_current_user_id, get_optional_user_id, parse_token
from .config import settings
from .admin_ui import admin_app_html, admin_login_html
from .providers import (
    fetch_em_suggest,
    fetch_ths_suggest,
    fetch_tx_kline,
    debug_10jqka_funds_tail_losers,
    debug_ths_daily_day,
  hotspots_ths_daily_grid,
    hotspots_ths_pct_change_top,
    market_data_status,
)
from .signals import build_signals_v3, candles_from_tencent_like_pack
from .schemas import (
    AdminLoginIn,
    AdminOtpSendIn,
    FeedbackCreateIn,
    InviteBindIn,
    LoginIn,
    LoginOut,
    PasswordChangeIn,
    PasswordResetIn,
    PayNativeIn,
    PayNativeOut,
    PayH5Out,
    PayWapIn,
    PayWapOut,
    QuotaConsumeIn,
    QuotaConsumeOut,
    RegisterIn,
    RequestCodeIn,
    RequestCodeOut,
    SmsSendProxyIn,
)


app = FastAPI(
    title="AI24X 股票查询助手 API",
    version="0.1.0",
    docs_url=None if str(settings.env or "").strip().lower() in ("prod", "production") else "/docs",
    redoc_url=None if str(settings.env or "").strip().lower() in ("prod", "production") else "/redoc",
    openapi_url=None if str(settings.env or "").strip().lower() in ("prod", "production") else "/openapi.json",
)

def _is_prod() -> bool:
    try:
        return str(settings.env or "").strip().lower() in ("prod", "production")
    except Exception:
        return False


@app.middleware("http")
async def _collapse_duplicate_path_slashes(request: Request, call_next):
    """将 //admin… 规范为 /admin…，避免端口后多打一个 / 导致 404。"""
    path = request.scope.get("path") or ""
    if "//" in path:
        fixed = re.sub(r"/{2,}", "/", path)
        if fixed != path:
            request.scope["path"] = fixed
            raw = request.scope.get("raw_path")
            if isinstance(raw, (bytes, bytearray)):
                request.scope["raw_path"] = fixed.encode()
    return await call_next(request)

@app.middleware("http")
async def _security_headers_mw(request: Request, call_next):
    """Defense-in-depth security headers (prod should also set at Nginx)."""
    resp = await call_next(request)
    try:
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        resp.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    except Exception:
        pass
    try:
        # Only force HSTS when we are actually behind HTTPS (usually via Nginx).
        if _is_prod():
            xfp = str(request.headers.get("x-forwarded-proto") or "").lower()
            if xfp == "https" or str(request.url.scheme or "").lower() == "https":
                resp.headers.setdefault("Strict-Transport-Security", "max-age=63072000; includeSubDomains; preload")
    except Exception:
        pass
    return resp


# in-memory rate limit buckets (single-process MVP)
_RL: dict[str, tuple[int, int]] = {}

# Anonymous whitelist: allow a few demo/sample symbols without login to improve onboarding.
_ANON_KLINE_WHITELIST: set[str] = {
    "1.000001",  # 上证指数
    "0.399001",  # 深证成指
    "0.399006",  # 创业板指
    "0.899050",  # 北证50
    "0.000977",  # 浪潮信息（示例）
    "1.300059",  # 东方财富
    "0.300059",  # 东方财富（深）
    "1.300033",  # 同花顺
    "1.600519",  # 贵州茅台
    "1.688981",  # 中芯国际
    "1.601398",  # 工商银行
    "0.300750",  # 宁德时代
}

# Anonymous extra trial quota (non-whitelist): allow a few self-selected queries per day.
# This complements the frontend guest counter but must be enforced server-side too.
_ANON_DAILY: dict[str, tuple[str, int]] = {}
_ANON_DAILY_MAX: int = 3


def _anon_day_key() -> str:
    return time.strftime("%Y-%m-%d", time.localtime())


def _anon_id_from_request(request: "Request") -> str:
    try:
        host = (request.client.host if request and request.client else "") or ""
        host = str(host).strip()
        return host or "unknown"
    except Exception:
        return "unknown"


def _anon_daily_can_consume(request: "Request") -> bool:
    k = f"{_anon_id_from_request(request)}"
    day = _anon_day_key()
    cur_day, cur_cnt = _ANON_DAILY.get(k, (day, 0))
    if cur_day != day:
        cur_cnt = 0
        cur_day = day
    return cur_cnt < int(getattr(settings, "anon_daily_max", 0) or _ANON_DAILY_MAX)


def _anon_daily_consume(request: "Request") -> None:
    k = f"{_anon_id_from_request(request)}"
    day = _anon_day_key()
    cur_day, cur_cnt = _ANON_DAILY.get(k, (day, 0))
    if cur_day != day:
        cur_cnt = 0
        cur_day = day
    _ANON_DAILY[k] = (cur_day, int(cur_cnt) + 1)


def _rate_limit(key: str, limit: int, window_s: int = 60) -> None:
    now = int(time.time())
    win = now // window_s
    k = f"{key}:{win}"
    cur_win, cnt = _RL.get(k, (win, 0))
    if cur_win != win:
        cnt = 0
    cnt += 1
    _RL[k] = (win, cnt)
    if limit > 0 and cnt > limit:
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")


def _client_ip(request: "Request") -> str:
    """Extract real client IP (respect X-Forwarded-For)."""
    xff = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if xff:
        return xff
    try:
        return (request.client.host if request and request.client else "") or "unknown"
    except Exception:
        return "unknown"


# Per-IP rate limit for authenticated endpoints (anti-scraping).
_AUTH_IP_RL: dict[str, tuple[int, int]] = {}


def _auth_ip_rate_limit(request: "Request", limit: int = 30, window_s: int = 60) -> None:
    """Rate-limit authenticated requests by client IP (defense against scraping with valid tokens).
    
    Default 30/min is conservative enough to catch multi-account scraping but won't
    block normal browsing (~2s per stock = 30/min theoretical max).
    """
    ip = _client_ip(request)
    now = int(time.time())
    win = now // window_s
    k = f"auth_ip:{ip}:{win}"
    cur_win, cnt = _AUTH_IP_RL.get(k, (win, 0))
    if cur_win != win:
        cnt = 0
    cnt += 1
    _AUTH_IP_RL[k] = (win, cnt)
    if limit > 0 and cnt > limit:
        raise HTTPException(
            status_code=429,
            detail="同一设备请求过于频繁，请稍后再试",
        )


def _identity_post(path: str, json_body: dict, *, extra_headers: dict[str, str] | None = None) -> dict:
    cfg = resolve_identity()
    base = (cfg.identity_api_base or "").strip().rstrip("/")
    if not base:
        raise HTTPException(status_code=503, detail="服务暂未就绪，请稍后再试")
    url = f"{base}{path}"
    headers: dict[str, str] = {}
    if cfg.sms_internal_key and (
        path.endswith("/sms/send") or "/internal/sms/verify-consume" in path
    ):
        headers["X-SMS-Internal-Key"] = cfg.sms_internal_key
    if extra_headers:
        headers.update(extra_headers)
    try:
        with httpx.Client(timeout=30.0) as client:
            r = client.post(url, json=json_body, headers=headers or None)
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail="身份服务暂时不可用，请稍后重试") from e
    ct = (r.headers.get("content-type") or "").lower()
    if r.status_code >= 400:
        detail = r.text[:4000]
        if "json" in ct:
            try:
                err = r.json()
                if isinstance(err, dict):
                    detail = str(err.get("error") or err.get("detail") or err.get("message") or "")
                if not detail:
                    detail = str(err)
            except Exception:
                pass
        raise HTTPException(status_code=r.status_code, detail=detail)
    if "json" not in ct:
        raise HTTPException(status_code=502, detail="身份服务响应异常，请稍后重试")
    return r.json()


def _identity_verify_sms_consume(phone_norm: str, purpose: str, code: str) -> bool:
    """与主站短信 OTP 一致：校验并消费（须 AI24X_IDENTITY_API_BASE + AI24X_SMS_INTERNAL_KEY 与主站对齐）。"""
    try:
        data = _identity_post(
            "/v1/internal/sms/verify-consume",
            {
                "mobile": phone_norm,
                "purpose": (purpose or "login").strip() or "login",
                "code": (code or "").strip(),
            },
        )
        return bool(data.get("ok"))
    except HTTPException:
        return False


def _sms_forward_json(mobile: str, purpose: str) -> dict:
    """发往主站的短信 JSON：含手机号/用途；若管理端配置了 106 项则一并带上（非空才覆盖主站 .env）。"""
    cfg = resolve_identity()
    payload: dict[str, str] = {"mobile": mobile, "purpose": purpose}
    if (cfg.sms_106_endpoint or "").strip():
        payload["sms_106_endpoint"] = cfg.sms_106_endpoint.strip()
    if (cfg.sms_106_account or "").strip():
        payload["sms_106_account"] = cfg.sms_106_account.strip()
    if (cfg.sms_106_password or "").strip():
        payload["sms_106_password"] = cfg.sms_106_password.strip()
    if (cfg.sms_106_sign_name or "").strip():
        payload["sms_106_sign_name"] = cfg.sms_106_sign_name.strip()
    if (cfg.sms_106_template or "").strip():
        payload["sms_106_template"] = cfg.sms_106_template.strip()
    # Forward provider selection and juhe config
    prov = (cfg.sms_active_provider or "identity_proxy").strip()
    if prov in ("juhe", "tencent"):
        payload["sms_provider"] = prov
    if prov == "juhe":
        if (cfg.sms_juhe_key or "").strip():
            payload["sms_juhe_key"] = cfg.sms_juhe_key.strip()
        if (cfg.sms_juhe_template_id or "").strip():
            payload["sms_juhe_tpl_id"] = cfg.sms_juhe_template_id.strip()
    if prov == "tencent":
        if (cfg.sms_tencent_secret_id or "").strip():
            payload["sms_tencent_secret_id"] = cfg.sms_tencent_secret_id.strip()
        if (cfg.sms_tencent_secret_key or "").strip():
            payload["sms_tencent_secret_key"] = cfg.sms_tencent_secret_key.strip()
        if (cfg.sms_tencent_sdk_app_id or "").strip():
            payload["sms_tencent_sdk_app_id"] = cfg.sms_tencent_sdk_app_id.strip()
        if (cfg.sms_tencent_sign or "").strip():
            payload["sms_tencent_sign"] = cfg.sms_tencent_sign.strip()
        if (cfg.sms_tencent_template_id or "").strip():
            payload["sms_tencent_template_id"] = cfg.sms_tencent_template_id.strip()
        if (cfg.sms_tencent_region or "").strip():
            payload["sms_tencent_region"] = cfg.sms_tencent_region.strip()
    return payload


def _turnstile_verify(token: str, remote_ip: str | None) -> tuple[bool, str | None]:
    """Verify Cloudflare Turnstile token. Reserved anti-abuse switch (default off)."""
    cfg = resolve_identity()
    secret = (cfg.sms_captcha_turnstile_secret_key or "").strip()
    if not secret:
        return False, "未配置 turnstile secret key"
    t = (token or "").strip()
    if not t:
        return False, "缺少图形码 token"
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.post(
                "https://challenges.cloudflare.com/turnstile/v0/siteverify",
                data={"secret": secret, "response": t, "remoteip": (remote_ip or "").strip() or None},
            )
    except httpx.RequestError:
        return False, "图形码校验服务不可用"
    try:
        data = r.json()
    except Exception:
        return False, "图形码校验失败"
    if bool(data.get("success")):
        return True, None
    # Don't leak detailed error codes to end-users; keep it simple.
    return False, "图形码校验未通过"


def _identity_get(path: str) -> dict:
    cfg = resolve_identity()
    base = (cfg.identity_api_base or "").strip().rstrip("/")
    if not base:
        raise HTTPException(
            status_code=503,
            detail="服务暂未就绪，请稍后再试",
        )
    url = f"{base}{path}"
    headers: dict[str, str] = {}
    p = path.rstrip("/") or "/"
    if (
        p.endswith("/sms/diagnostics")
        or p.startswith("/v1/admin/sms/")
        or p.startswith("/v1/admin/users/")
    ) and cfg.sms_internal_key:
        headers["X-SMS-Internal-Key"] = cfg.sms_internal_key
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.get(url, headers=headers or None)
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail="身份服务暂时不可用，请稍后重试") from e
    ct = (r.headers.get("content-type") or "").lower()
    if r.status_code >= 400:
        detail = r.text[:4000]
        if "json" in ct:
            try:
                err = r.json()
                if isinstance(err, dict):
                    detail = str(err.get("error") or err.get("detail") or err.get("message") or "")
                if not detail:
                    detail = str(err)
            except Exception:
                pass
        raise HTTPException(status_code=r.status_code, detail=detail)
    if "json" not in ct:
        raise HTTPException(status_code=502, detail="身份服务响应异常，请稍后重试")
    return r.json()


def _identity_lookup_user_id(*, phone: str = "", email: str = "") -> int | None:
    """Best-effort lookup identity auth_users.id for admin sync."""
    cfg = resolve_identity()
    if not identity_configured():
        return None
    if not (cfg.sms_internal_key or "").strip():
        return None
    p = (phone or "").strip()
    e = (email or "").strip().lower()
    if not p and not e:
        return None
    try:
        data = _identity_get(f"/v1/admin/users/lookup?phone={quote(p)}&email={quote(e)}")
        u = data.get("user") if isinstance(data, dict) else None
        uid = int((u or {}).get("id") or 0)
        return uid if uid > 0 else None
    except Exception:
        return None


def _cors_list(v: str) -> list[str]:
    vv = (v or "").strip()
    if not vv or vv == "*":
        # Default narrow: only allow our own domains + localhost dev ports.
        # Override via AI24X_CORS_ORIGINS if you need additional origins.
        return [
            "https://a.ai24x.com",
            "https://www.ai24x.com",
            "https://api.ai24x.com",
            "http://localhost:18001",
            "http://127.0.0.1:18001",
            "http://localhost:18003",
            "http://127.0.0.1:18003",
        ]
    return [x.strip() for x in vv.split(",") if x.strip()]


# CORS 在外层；内层会先经上方路径折叠，再匹配路由
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_list(settings.cors_origins),
    # We use Authorization: Bearer token (not cookies). Disabling credentials keeps wildcard origins working
    # and avoids confusing CORS behavior on Windows browsers.
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    db.init_db()
    try:
        log_admin_security_baseline(settings)
    except Exception:
        logging.getLogger(__name__).exception("admin security baseline check failed")


@app.get("/health")
def health() -> dict:
    return {"ok": True, "ts": int(time.time())}


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(status_code=204)


def _client_ip(request: Request) -> str:
    xff = (request.headers.get("x-forwarded-for") or "").strip()
    if xff:
        return xff.split(",")[0].strip()[:128] or "unknown"
    if request.client:
        return str(request.client.host or "unknown")[:128]
    return "unknown"


def require_admin(
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
    admin_session: Optional[str] = Cookie(default=None, alias=COOKIE_NAME),
) -> bool:
    k = (x_admin_key or "").strip()
    if k and admin_key_matches(k, str(settings.admin_key)):
        return True
    if verify_admin_session(admin_session):
        return True
    raise HTTPException(status_code=401, detail="Invalid admin key")


_NO_STORE = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}

# 浏览器管理台挂载路径（默认 /admin20260501，对齐宣发 2026-05-01）；见 AI24X_ADMIN_MOUNT_PATH
_ADMIN_BASE = str(settings.admin_mount_path)


@app.get("/", include_in_schema=False)
def root_landing() -> dict:
    """Root endpoint: do not leak admin mount path or security posture."""
    return {"ok": True, "service": "ai24x-p-a-api"}


def _public_origin(request: Request) -> str:
    """
    Determine origin for share cards behind reverse proxy.
    Prefer forwarded headers; fall back to request.url.
    """
    try:
        xf_proto = str(request.headers.get("x-forwarded-proto") or "").strip().lower()
        xf_host = str(request.headers.get("x-forwarded-host") or "").strip()
        if xf_host:
            proto = xf_proto or str(request.url.scheme or "http")
            return f"{proto}://{xf_host}"
    except Exception:
        pass
    try:
        return str(request.url.scheme or "http") + "://" + str(request.url.netloc)
    except Exception:
        return ""


@app.get("/i/{code}", response_class=HTMLResponse, include_in_schema=False)
def share_landing(
    request: Request,
    code: str,
    secid: str | None = None,
    period: str | None = None,
    view: str | None = None,
    utm: str | None = None,
    scene: str | None = None,
) -> HTMLResponse:
    """
    Share landing page for WeChat link previews.
    - Server-rendered OG meta so WeChat crawler can build a nice card.
    - Body shows a lightweight "复盘卡" and a CTA to open demo.html.
    """
    c = (code or "").strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{4,32}", c or ""):
        # Keep it simple: avoid reflecting arbitrary strings into HTML/meta.
        raise HTTPException(status_code=404, detail="not found")

    sid = (secid or "").strip()
    per = (period or "").strip().lower()
    if per not in ("day", "week", "month"):
        per = "day"
    origin = _public_origin(request) or ""

    # Build canonical URL (what is being shared). Preserve query for tracking.
    try:
        u = request.url
        canonical = str(u)
    except Exception:
        canonical = f"{origin}/i/{quote(c)}"

    # Build "open in app" url (web demo) with state.
    open_url = f"{origin}/demo.html"
    try:
        qs = []
        if sid:
            qs.append("secid=" + quote(sid))
        if per:
            qs.append("period=" + quote(per))
        qs.append("i=" + quote(c))
        qs.append("view=" + quote((view or "lite").strip() or "lite"))
        if utm:
            qs.append("utm=" + quote(str(utm)[:64]))
        if scene:
            qs.append("scene=" + quote(str(scene)[:64]))
        open_url = open_url + ("?" + "&".join(qs) if qs else "")
    except Exception:
        pass

    # Title/desc: compliant and tool-oriented.
    title = "AI24X 复盘卡"
    if sid:
        title = f"AI24X 复盘卡 · {sid}"
    desc = "结构要点 / 关键位 / 风险提示（仅供参考）。打开即可查看简版，注册后解锁完整。"
    og_img = f"{origin}/img/share-preview.svg" if origin else "/img/share-preview.svg"

    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
  <meta name="description" content="{desc}" />
  <meta property="og:type" content="website" />
  <meta property="og:title" content="{title}" />
  <meta property="og:description" content="{desc}" />
  <meta property="og:image" content="{og_img}" />
  <meta property="og:url" content="{canonical}" />
  <meta name="robots" content="index,follow" />
  <style>
    body{{margin:0;font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial;color:#0b1220;background:#0b1220}}
    .wrap{{max-width:720px;margin:0 auto;padding:18px}}
    .card{{background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.10);border-radius:16px;padding:16px;color:rgba(255,255,255,0.92)}}
    .t{{font-weight:800;font-size:18px}}
    .sub{{margin-top:6px;color:rgba(255,255,255,0.70);font-size:13px;line-height:1.5}}
    .grid{{display:grid;grid-template-columns:1fr;gap:10px;margin-top:12px}}
    .pill{{background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.10);border-radius:12px;padding:10px}}
    .pill b{{color:rgba(251,191,36,0.95)}}
    .btn{{display:inline-block;margin-top:14px;background:rgba(251,191,36,0.92);color:rgba(24,18,6,.98);font-weight:900;text-decoration:none;padding:10px 14px;border-radius:12px}}
    .muted{{margin-top:10px;color:rgba(255,255,255,0.60);font-size:12px}}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <div class="t">复盘卡 · 结构要点速览</div>
      <div class="sub">{desc}</div>
      <div class="grid">
        <div class="pill"><b>结构</b>：上行 / 震荡 / 下行（偏结构观察）</div>
        <div class="pill"><b>关键位</b>：支撑区 / 压力区（区间表达）</div>
        <div class="pill"><b>风险</b>：关注风险提示（复盘用）</div>
      </div>
      <a class="btn" href="{open_url}">打开查看</a>
      <div class="muted">参考码：{c} · 仅供参考</div>
    </div>
  </div>
</body>
</html>
"""
    return HTMLResponse(html, headers=_NO_STORE)


def _admin_login_html_response(browser_base: str, otp_required: bool | None = None) -> HTMLResponse:
    if otp_required is None:
        otp_required = admin_browser_otp_required()
    return HTMLResponse(admin_login_html(browser_base, otp_required=otp_required), headers=_NO_STORE)


def _admin_app_html_response(browser_base: str) -> HTMLResponse:
    return HTMLResponse(admin_app_html(browser_base), headers=_NO_STORE)


# 与 AI24X_ADMIN_MOUNT_PATH 并列保留 /admin（旧书签、PM2 未拉新代码时常见）；HTML 内链按各自 browser_base 生成
if _ADMIN_BASE.rstrip("/") != "/admin":

    @app.get("/admin/login", response_class=HTMLResponse, include_in_schema=False)
    def admin_login_page_compat_admin() -> HTMLResponse:
        return _admin_login_html_response("/admin", admin_browser_otp_required())

    @app.get("/admin", response_class=HTMLResponse, include_in_schema=False)
    def admin_page_compat_admin() -> HTMLResponse:
        return _admin_app_html_response("/admin")


@app.get(f"{_ADMIN_BASE}/login", response_class=HTMLResponse)
def admin_login_page() -> HTMLResponse:
    return _admin_login_html_response(_ADMIN_BASE, admin_browser_otp_required())


@app.get(_ADMIN_BASE, response_class=HTMLResponse)
def admin_page() -> HTMLResponse:
    # 浏览器工作台；鉴权为 Cookie 会话或 X-Admin-Key（脚本/ curl）。未登录时由前端跳转到 {mount}/login。
    return _admin_app_html_response(_ADMIN_BASE)


@app.post("/api/admin/otp/send")
def admin_otp_send(request: Request, body: AdminOtpSendIn) -> dict:
    if not admin_browser_otp_required():
        if not admin_browser_otp_feature_enabled():
            raise HTTPException(
                status_code=400,
                detail="管理登录短信 OTP 未开启：请登录后在「系统配置」中开启（admin_browser_otp_enabled），并配置白名单手机号。",
            )
        raise HTTPException(
            status_code=400,
            detail="未配置管理 OTP 白名单：请在环境变量 AI24X_ADMIN_OTP_PHONES 或库表 admin_operators 中登记手机号。",
        )
    if not is_phone_allowed_for_admin_otp(body.phone):
        raise HTTPException(status_code=403, detail="当前号码不可用于管理后台验证")
    pnorm = normalize_admin_phone(body.phone)
    _rate_limit(
        f"admin_otp_send_ip:{_client_ip(request)}",
        limit=max(1, int(settings.admin_otp_send_per_15m)),
        window_s=900,
    )
    _rate_limit(
        f"admin_otp_send_phone:{pnorm}",
        limit=max(1, int(settings.admin_otp_send_per_15m) // 2 + 1),
        window_s=900,
    )
    ttl = int(settings.admin_otp_ttl_s)
    # 仅当系统配置未开启管理 OTP 时，才允许固定验证码；线上应使用短信验证。
    dc = dev_admin_otp_bypass_code()
    if dc and not admin_browser_otp_feature_enabled():
        admin_otp_put(pnorm, dc, ttl)
        return {
            "ok": True,
            "ttl_s": ttl,
            "dev_code": dc,
            "message": "已生成验证码。",
        }
    if identity_configured():
        _identity_post("/v1/auth/sms/send", _sms_forward_json(pnorm, "login"))
        return {"ok": True, "ttl_s": ttl}
    if str(settings.env or "").lower() in ("prod", "production"):
        raise HTTPException(status_code=503, detail="短信服务暂未就绪，请稍后再试")
    code = admin_otp_generate()
    admin_otp_put(pnorm, code, ttl)
    return {"ok": True, "ttl_s": ttl, "dev_code": code, "message": "验证码已生成。"}


@app.post("/api/admin/login")
def admin_login(request: Request, body: AdminLoginIn, response: Response) -> dict:
    _rate_limit(
        f"admin_login:{_client_ip(request)}",
        limit=int(settings.admin_login_max_per_15m),
        window_s=900,
    )
    need_otp = admin_browser_otp_required()
    phone_norm = ""
    role = "super"
    perm_flags = 0x7FFFFFFF
    if need_otp:
        phone_norm = normalize_admin_phone(body.phone or "")
        otp = (body.otp or "").strip()
        if not phone_norm or not otp:
            raise HTTPException(status_code=400, detail="请填写手机号与短信验证码")
        if not is_phone_allowed_for_admin_otp(phone_norm):
            raise HTTPException(status_code=403, detail="凭据无效")
        # 开关开启时已强制主站发码：只走主站验码；未配主站时走本机内存表（仅非 identity 联调路径）
        if identity_configured():
            otp_ok = _identity_verify_sms_consume(phone_norm, "login", otp)
        else:
            otp_ok = admin_otp_verify_and_consume(phone_norm, otp)
        if not otp_ok:
            raise HTTPException(status_code=401, detail="凭据无效")
        role, perm_flags = db.admin_operator_role_for_phone(phone_norm)
    if not admin_key_matches(body.key, str(settings.admin_key)):
        raise HTTPException(status_code=401, detail="凭据无效")
    tok = issue_admin_session(phone=phone_norm, role=role, perm_flags=perm_flags)
    env = str(settings.env or "").lower()
    secure = env in ("prod", "production")
    response.set_cookie(
        key=COOKIE_NAME,
        value=tok,
        max_age=SESSION_TTL_S,
        httponly=True,
        samesite="lax",
        path="/",
        secure=secure,
    )
    return {"ok": True}


@app.post("/api/admin/logout")
def admin_logout(response: Response) -> dict:
    env = str(settings.env or "").lower()
    secure = env in ("prod", "production")
    response.delete_cookie(COOKIE_NAME, path="/", secure=secure, httponly=True, samesite="lax")
    return {"ok": True}


@app.get("/api/admin/ping")
def admin_ping(_: bool = Depends(require_admin)) -> dict:
    return {"ok": True, "ts": int(time.time())}


@app.get("/api/admin/users")
def admin_users(q: str = "", limit: int = 50, offset: int = 0, _: bool = Depends(require_admin)) -> dict:
    return db.admin_list_users(q=q, limit=limit, offset=offset)


@app.get("/api/admin/feedback")
def admin_feedback_list(
    status: str = "",
    category: str = "",
    q: str = "",
    limit: int = 50,
    offset: int = 0,
    _: bool = Depends(require_admin),
) -> dict:
    return db.admin_list_feedback(status=status, category=category, q=q, limit=limit, offset=offset)


@app.post("/api/admin/feedback/reply")
def admin_feedback_reply_route(body: dict, _: bool = Depends(require_admin)) -> dict:
    try:
        fid = int(body.get("id") or 0)
        reply = str(body.get("reply") if body.get("reply") is not None else "")
        status = str(body.get("status") or "replied")
        replied_by = str(body.get("replied_by") or "")
        return db.admin_feedback_reply(fid, reply=reply, status=status, replied_by=replied_by)
    except ValueError as e:
        code = str(e)
        msg = {
            "invalid_id": "工单 ID 无效",
            "not_found": "工单不存在",
            "invalid_status": "状态仅支持 replied / closed",
            "reply_required": "「已回复」须填写回复内容",
            "reply_too_long": "回复过长",
        }.get(code, code)
        raise HTTPException(status_code=400, detail=msg)


@app.get("/api/admin/pay_orders")
def admin_pay_orders(
    user_id: int = 0,
    status: str = "",
    plan: str = "",
    q: str = "",
    limit: int = 50,
    offset: int = 0,
    _: bool = Depends(require_admin),
) -> dict:
    """VIP/微信支付订单列表（pay_orders）；q 支持商户单号 / 微信单号片段、纯数字 user_id。"""
    return db.admin_list_pay_orders(
        user_id=user_id, status=status, plan=plan, q=q, limit=limit, offset=offset
    )


@app.get("/api/admin/pay_orders_export")
def admin_pay_orders_export(
    user_id: int = 0,
    status: str = "",
    plan: str = "",
    q: str = "",
    cap: int = 5000,
    _: bool = Depends(require_admin),
) -> Response:
    """同筛选条件导出 CSV（UTF-8 BOM，便于 Excel）；最多 cap 条，默认 5000。"""
    rows = db.admin_export_pay_orders_rows(user_id=user_id, status=status, plan=plan, q=q, cap=cap)
    fieldnames = [
        "id",
        "user_id",
        "plan",
        "amount_fen",
        "channel",
        "status",
        "has_code_url",
        "created_at",
        "updated_at",
        "out_trade_no",
        "transaction_id",
    ]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        line = {k: r.get(k, "") for k in fieldnames}
        line["has_code_url"] = "1" if r.get("has_code_url") else "0"
        w.writerow(line)
    body = "\ufeff" + buf.getvalue()
    return Response(
        content=body.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="pay_orders_export.csv"',
            "Cache-Control": "no-store",
        },
    )


@app.get("/api/admin/payout_requests_export_alipay")
def admin_payout_requests_export_alipay(
    status: str = "",
    cap: int = 5000,
    mark: int = 1,
    mark_note: str = "alipay_batch",
    _: bool = Depends(require_admin),
) -> Response:
    """导出「提现申请」为支付宝批量转账 CSV（UTF-8 BOM，便于 Excel）；默认导出 approved。"""
    rows = db.admin_export_payout_requests_alipay_rows(
        status=status,
        cap=cap,
        mark_exported=bool(int(mark or 0) == 1),
        exported_note=str(mark_note or "alipay_batch"),
    )
    # Fieldnames order matters for finance copy/paste.
    fieldnames = [
        "收款方账号",
        "收款方姓名",
        "转账金额(元)",
        "备注",
        "手机号",
        "申请ID",
        "用户ID",
        "渠道",
        "申请时间",
        "打款流水",
    ]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow({k: r.get(k, "") for k in fieldnames})
    body = "\ufeff" + buf.getvalue()
    return Response(
        content=body.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="alipay_batch.csv"',
            "Cache-Control": "no-store",
        },
    )


@app.get("/api/admin/commissions")
def admin_commissions(
    status: str = "",
    agent_user_id: int = 0,
    q: str = "",
    eligible_only: int = 0,
    limit: int = 50,
    offset: int = 0,
    _: bool = Depends(require_admin),
) -> dict:
    return db.admin_list_commissions(
        status=status,
        agent_user_id=int(agent_user_id or 0),
        q=q,
        eligible_only=bool(int(eligible_only or 0) == 1),
        limit=limit,
        offset=offset,
    )


@app.post("/api/admin/commissions/mark_paid")
def admin_commissions_mark_paid(body: dict, _: bool = Depends(require_admin)) -> dict:
    agent_user_id = int(body.get("agent_user_id") or 0)
    note = str(body.get("note") or "")
    try:
        return db.admin_mark_commissions_paid(agent_user_id, note=note)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/admin/commissions/generate_for_order")
def admin_commissions_generate_for_order(body: dict, _: bool = Depends(require_admin)) -> dict:
    out_trade_no = str(body.get("out_trade_no") or "")
    try:
        return db.commission_generate_for_order(out_trade_no)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/agent/overview")
def agent_overview(user_id: int = Depends(get_current_user_id)) -> dict:
    try:
        return db.agent_commission_overview(int(user_id))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/agent/commissions")
def agent_commissions(
    status: str = "",
    limit: int = 50,
    offset: int = 0,
    user_id: int = Depends(get_current_user_id),
) -> dict:
    try:
        return db.agent_list_commissions(int(user_id), status=status, limit=limit, offset=offset)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/agent/payout_account")
def agent_payout_account(body: dict, user_id: int = Depends(get_current_user_id)) -> dict:
    try:
        return db.agent_set_payout_account(
            user_id=int(user_id),
            channel=str(body.get("channel") or ""),
            account_name=str(body.get("account_name") or ""),
            account_no=str(body.get("account_no") or ""),
            phone=str(body.get("phone") or ""),
            qr_image=str(body.get("qr_image") or ""),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/agent/payout_account")
def agent_payout_account_get(user_id: int = Depends(get_current_user_id)) -> dict:
    return db.agent_get_payout_account_full(int(user_id))


@app.post("/api/agent/payout/request")
def agent_payout_request(body: dict, user_id: int = Depends(get_current_user_id)) -> dict:
    try:
        amount = body.get("amount_fen", None)
        amount2 = None if amount is None else int(amount)
        return db.agent_create_payout_request(int(user_id), amount_fen=amount2, note=str(body.get("note") or ""))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/admin/payout_requests")
def admin_payout_requests(
    status: str = "",
    user_id: int = 0,
    limit: int = 50,
    offset: int = 0,
    _: bool = Depends(require_admin),
) -> dict:
    return db.admin_list_payout_requests(status=status, user_id=int(user_id or 0), limit=limit, offset=offset)


@app.post("/api/admin/payout_requests/set_status")
def admin_payout_requests_set_status(body: dict, _: bool = Depends(require_admin)) -> dict:
    try:
        rid = int(body.get("id") or 0)
        st = str(body.get("status") or "")
        note = str(body.get("note") or "")
        tref = str(body.get("transfer_ref") or "")
        return db.admin_payout_request_set_status(rid, status=st, note=note, transfer_ref=tref)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/admin/hotspots/test")
async def admin_hotspots_test(
    sample: int = 80,
    topk: int = 10,
    lookback_days: int = 30,
    concurrency: int = 6,
    gate_funds: int = 1,
    include_regions: int = 0,
    allow_88xx: int = 1,
    _: bool = Depends(require_admin),
) -> dict:
    """
    Hotspot ranking test page backend (admin only).
    Hard limited in providers to avoid hitting TuShare per-minute QPS.
    """
    return await hotspots_ths_pct_change_top(
        sample=sample,
        topk=topk,
        lookback_days=lookback_days,
        concurrency=concurrency,
        timeout_s=10.0,
        gate_by_ths_funds_pages=bool(int(gate_funds or 0)),
        include_regions=bool(int(include_regions or 0)),
        allow_code_prefix_88xx=bool(int(allow_88xx or 0)),
    )


@app.get("/api/admin/hotspots/compare")
async def admin_hotspots_compare(
    sample: int = 120,
    topk: int = 10,
    lookback_long: int = 30,
    lookback_short: int = 10,
    concurrency: int = 6,
    gate_funds: int = 1,
    _: bool = Depends(require_admin),
) -> dict:
    """Return two hotspot lists for side-by-side comparison (admin only)."""
    long_res = await hotspots_ths_pct_change_top(
        sample=sample,
        topk=topk,
        lookback_days=lookback_long,
        concurrency=concurrency,
        timeout_s=10.0,
        gate_by_ths_funds_pages=bool(int(gate_funds or 0)),
    )
    short_res = await hotspots_ths_pct_change_top(
        sample=sample,
        topk=topk,
        lookback_days=lookback_short,
        concurrency=concurrency,
        timeout_s=10.0,
        gate_by_ths_funds_pages=bool(int(gate_funds or 0)),
    )
    if not (long_res and long_res.get("ok")):
        return {"ok": False, "error": "long_failed", "long": long_res, "short": short_res}
    if not (short_res and short_res.get("ok")):
        return {"ok": False, "error": "short_failed", "long": long_res, "short": short_res}
    return {"ok": True, "long": long_res, "short": short_res}


@app.get("/api/admin/hotspots/grid")
async def admin_hotspots_grid(
    sample: int = 160,
    topk: int = 10,
    long_days: int = 30,
    daily_days: int = 10,
    concurrency: int = 6,
    gate_funds: int = 1,
    include_regions: int = 0,
    allow_88xx: int = 1,
    losers_mode: str = "ths_daily",
    _: bool = Depends(require_admin),
) -> dict:
    """Hotspot heatmap grid (admin only): long window + daily columns."""
    # Winner list comes from ths_daily pct_change; loser list can optionally use THS funds tail pages
    # to align with THS app "跌榜尾页" behavior.
    return await hotspots_ths_daily_grid(
        sample=sample,
        topk=topk,
        long_days=long_days,
        daily_days=daily_days,
        concurrency=concurrency,
        timeout_s=10.0,
        gate_by_ths_funds_pages=bool(int(gate_funds or 0)),
        include_regions=bool(int(include_regions or 0)),
        allow_code_prefix_88xx=bool(int(allow_88xx or 0)),
        losers_from_10jqka_funds_tails=str(losers_mode or "").strip().lower() in ("funds_tail", "funds", "tail"),
    )


@app.get("/api/admin/hotspots/losers_tail_debug")
async def admin_hotspots_losers_tail_debug(topk: int = 10, _: bool = Depends(require_admin)) -> dict:
    """Debug: parse 10jqka tail pages and compute worst(net) losers."""
    return await debug_10jqka_funds_tail_losers(topk=int(topk or 10))


@app.get("/api/admin/hotspots/pct_day_debug")
async def admin_hotspots_pct_day_debug(
    trade_date: str,
    sample: int = 600,
    topk: int = 10,
    gate_funds: int = 1,
    include_regions: int = 0,
    allow_88xx: int = 1,
    concurrency: int = 6,
    _: bool = Depends(require_admin),
) -> dict:
    """Debug: what ths_daily pct_change looks like for a specific trade_date."""
    return await debug_ths_daily_day(
        trade_date=trade_date,
        sample=sample,
        topk=topk,
        gate_by_ths_funds_pages=bool(int(gate_funds or 0)),
        include_regions=bool(int(include_regions or 0)),
        allow_code_prefix_88xx=bool(int(allow_88xx or 0)),
        concurrency=concurrency,
    )


@app.get("/api/admin/user/{user_id}")
def admin_user(user_id: int, _: bool = Depends(require_admin)) -> dict:
    try:
        return db.admin_get_user(user_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="User not found")


@app.post("/api/admin/user/{user_id}/basic_update")
def admin_user_basic_update(user_id: int, body: dict, _: bool = Depends(require_admin)) -> dict:
    """
    Admin update for user basic contact fields.
    Body:
    - email: string (optional; empty to clear)
    - phone: string (optional; empty to clear)
    """
    try:
        cfg = resolve_identity()
        # Sync to identity first (source of truth for login), then update local users.
        if identity_configured():
            email = body.get("email")
            phone = body.get("phone")
            if (cfg.sms_internal_key or "").strip():
                # Resolve identity user_id by current local contact (best-effort).
                cur = db.admin_get_user(int(user_id))
                cur_u = (cur or {}).get("user") if isinstance(cur, dict) else None
                id_uid = _identity_lookup_user_id(
                    phone=str((cur_u or {}).get("phone") or ""),
                    email=str((cur_u or {}).get("email") or ""),
                )
                if id_uid:
                    # Identity 侧要求「手机号/邮箱二选一」；但管理台允许两者都维护，所以这里拆成两次同步。
                    has_email = bool(str(email or "").strip())
                    has_phone = bool(str(phone or "").strip())
                    if has_phone:
                        _identity_post(
                            "/v1/admin/users/contact/set",
                            {"user_id": int(id_uid), "phone": phone},
                            extra_headers={"X-SMS-Internal-Key": cfg.sms_internal_key},
                        )
                    if has_email:
                        _identity_post(
                            "/v1/admin/users/contact/set",
                            {"user_id": int(id_uid), "email": email},
                            extra_headers={"X-SMS-Internal-Key": cfg.sms_internal_key},
                        )
        return db.admin_update_user_basic(int(user_id), email=body.get("email"), phone=body.get("phone"))
    except ValueError as e:
        # keep user-friendly; do not leak DB error details
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        # Bubble up identity sync errors (404/403/etc) instead of hiding them.
        raise
    except Exception as e:
        logging.getLogger(__name__).exception("admin_user_basic_update failed")
        env = str(settings.env or "").strip().lower()
        if env not in ("prod", "production"):
            raise HTTPException(status_code=400, detail=f"{type(e).__name__}: {e}")
        raise HTTPException(status_code=400, detail="Invalid request")


@app.post("/api/admin/user/{user_id}/password_set")
def admin_user_password_set(user_id: int, body: dict, _: bool = Depends(require_admin)) -> dict:
    """
    Super admin: force set user password (no OTP).
    This calls the identity service internal admin endpoint and requires sms_internal_key configured.
    Body:
    - new_password: string (>=6)
    """
    npw = str(body.get("new_password") or "")
    if len(npw.strip()) < 6:
        raise HTTPException(status_code=400, detail="新密码至少 6 位")
    cfg = resolve_identity()
    if not (cfg.sms_internal_key or "").strip():
        raise HTTPException(status_code=503, detail="未配置 sms_internal_key，无法执行管理员强制改密")
    try:
        cur = db.admin_get_user(int(user_id))
        cur_u = (cur or {}).get("user") if isinstance(cur, dict) else None
        cur_phone = str((cur_u or {}).get("phone") or "")
        cur_email = str((cur_u or {}).get("email") or "")
        id_uid = _identity_lookup_user_id(phone=cur_phone, email=cur_email)
        if not id_uid:
            # Local/dev: the account may exist only in p/a1 DB. Bootstrap it into identity, then set password.
            _identity_post(
                "/v1/admin/users/bootstrap",
                (
                    {"phone": cur_phone, "new_password": npw}
                    if (cur_phone or "").strip()
                    else {"email": (cur_email or "").strip().lower(), "new_password": npw}
                ),
                extra_headers={"X-SMS-Internal-Key": cfg.sms_internal_key},
            )
            id_uid = _identity_lookup_user_id(phone=cur_phone, email=cur_email)
        if not id_uid:
            raise HTTPException(status_code=404, detail="Identity 用户不存在：请先让该用户在主站完成一次注册/登录后再改密")
        data = _identity_post(
            "/v1/admin/users/password/set",
            {"user_id": int(id_uid), "new_password": npw},
            extra_headers={"X-SMS-Internal-Key": cfg.sms_internal_key},
        )
    except HTTPException as e:
        # Most common local/dev footgun: p/a1 uses one DB, identity(core) uses another DB,
        # so the same numeric user_id doesn't exist upstream.
        d = str(getattr(e, "detail", "") or "")
        if (
            e.status_code in (400, 404)
            and ("用户不存在" in d or "user not found" in d.lower())
            and not d.startswith("Identity 用户不存在：")
        ):
            base = (cfg.identity_api_base or "").strip()
            raise HTTPException(
                status_code=404,
                detail=f"Identity 用户不存在：p/a1 的 user_id={int(user_id)} 与 Identity 用户表不一致。请检查 AI24X_IDENTITY_API_BASE={base!r} 指向的主站是否使用同一套数据库/同一批用户数据。",
            )
        raise
    # Do not return token to admin UI; only indicate success.
    return {"ok": True, "user": data.get("user", {})}

@app.post("/api/admin/user/{user_id}/quota_set_remaining")
def admin_user_set_remaining(user_id: int, body: dict, _: bool = Depends(require_admin)) -> dict:
    remaining = body.get("remaining")
    if remaining is None:
        raise HTTPException(status_code=400, detail="Missing remaining")
    try:
        return db.admin_set_remaining(user_id, int(remaining))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid remaining")


@app.post("/api/admin/user/{user_id}/quota_adjust")
def admin_user_quota_adjust(user_id: int, body: dict, _: bool = Depends(require_admin)) -> dict:
    """
    Admin quota/plan adjustments (with audit log).
    Body fields:
    - set_remaining_day / set_remaining_week: absolute set remaining (>=0)
    - delta_day / delta_week: relative adjust remaining (can be negative)
    - plan: free / vip_month / vip_year_999 / vip_trial_99
    - note: short text for audit
    """
    try:
        return db.admin_quota_adjust(
            int(user_id),
            actor="admin",
            set_remaining_day=body.get("set_remaining_day"),
            set_remaining_week=body.get("set_remaining_week"),
            delta_day=body.get("delta_day"),
            delta_week=body.get("delta_week"),
            plan=body.get("plan"),
            note=str(body.get("note") or ""),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid request")


@app.post("/api/admin/user/{user_id}/reset")
def admin_user_reset(user_id: int, body: dict, _: bool = Depends(require_admin)) -> dict:
    """
    测试用：重置账号数据（保留 user_id），用于重复走邀请码/激活/支付/返佣链路。
    生产环境默认禁止；可通过 admin_config 显式开启。
    """
    env = str(getattr(settings, "env", "") or "").strip().lower()
    if env == "prod":
        v = (db.admin_config_get("admin_user_reset_enabled") or "").strip().lower()
        if v not in ("1", "true", "yes", "on"):
            raise HTTPException(status_code=403, detail="生产环境禁止重置账号（admin_user_reset_enabled 未开启）")

    try:
        return db.admin_user_reset(
            int(user_id),
            actor="admin",
            invite_binding=bool(body.get("invite_binding")),
            quota_reset=bool(body.get("quota_reset")),
            quota_ledger=bool(body.get("quota_ledger")),
            pay_orders=bool(body.get("pay_orders")),
            reward_ledger=bool(body.get("reward_ledger")),
            commission_ledger=bool(body.get("commission_ledger")),
            note=str(body.get("note") or ""),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)[:200])


@app.get("/api/admin/quota_ledger")
def admin_quota_ledger(user_id: int, limit: int = 50, _: bool = Depends(require_admin)) -> dict:
    return db.admin_list_quota_ledger(user_id=user_id, limit=limit)


@app.get("/api/admin/invite/tree")
def admin_invite_tree(
    root_user_id: int,
    depth: int = 2,
    limit: int = 200,
    _: bool = Depends(require_admin),
) -> dict:
    try:
        return db.admin_invite_tree(int(root_user_id), depth=int(depth), limit=int(limit))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)[:200])


@app.get("/api/admin/agent/rank")
def admin_agent_rank(
    metric: str = "direct_invites",
    limit: int = 50,
    offset: int = 0,
    _: bool = Depends(require_admin),
) -> dict:
    try:
        return {"ok": True, **db.admin_agent_rank(metric=str(metric or ""), limit=int(limit), offset=int(offset))}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)[:200])


@app.get("/api/admin/agent/detail")
def admin_agent_detail(
    user_id: int,
    depth: int = 3,
    limit: int = 300,
    _: bool = Depends(require_admin),
) -> dict:
    try:
        return db.admin_agent_detail(user_id=int(user_id), depth=int(depth), limit=int(limit))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)[:200])


@app.post("/api/admin/agent/tier_set")
def admin_agent_tier_set(body: dict, _: bool = Depends(require_admin)) -> dict:
    try:
        uid = int(body.get("user_id") or 0)
        level = body.get("level", None)
        locked = body.get("locked", None)
        note = str(body.get("note") or "")
        return db.admin_agent_tier_set(user_id=uid, level=level, locked=locked, note=note)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)[:200])


@app.get("/api/admin/agent/rank")
def admin_agent_rank(
    metric: str = "direct_invites",
    limit: int = 50,
    offset: int = 0,
    _: bool = Depends(require_admin),
) -> dict:
    try:
        return {"ok": True, **db.admin_agent_rank(metric=str(metric or ""), limit=int(limit), offset=int(offset))}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)[:200])


@app.get("/api/admin/ops_ledger")
def admin_ops_ledger(user_id: int, limit: int = 50, _: bool = Depends(require_admin)) -> dict:
    return db.admin_list_ops_ledger(user_id=user_id, limit=limit)


@app.get("/api/admin/config")
def admin_config_get(_: bool = Depends(require_admin)) -> dict:
    items = db.admin_config_get_all()
    # Do not leak secrets to browser/admin UI.
    sensitive = {
        "tushare_token",
        "wechat_api_v3_key",
        "wechat_mch_private_key_pem",
        "alipay_merchant_private_key_pem",
        "sms_internal_key",
        "sms_captcha_turnstile_secret_key",
        "sms_tencent_secret_id",
        "sms_tencent_secret_key",
        "sms_106_password",
    }
    safe: dict = {}
    for k, v in (items or {}).items():
        if str(k) in sensitive and str(v or "").strip():
            safe[str(k)] = "***"
        else:
            safe[str(k)] = v
    return {"items": safe}


@app.get("/api/admin/sms_effective")
def admin_sms_effective(_: bool = Depends(require_admin)) -> dict:
    """管理端读取短信/统一身份“当前生效值”（DB 优先，否则 .env）。敏感字段仅返回是否已配置。"""
    cfg = resolve_identity()
    def _mask(s: str, keep_tail: int = 4) -> str:
        v = str(s or "").strip()
        if not v:
            return ""
        if len(v) <= keep_tail:
            return "*" * len(v)
        return ("*" * max(4, len(v) - keep_tail)) + v[-keep_tail:]
    out = {
        "identity_api_base": (cfg.identity_api_base or "").strip() or "",
        "sms_active_provider": (cfg.sms_active_provider or "identity_proxy").strip() or "identity_proxy",
        "sms_internal_key_set": bool((cfg.sms_internal_key or "").strip()),
        "sms_internal_key_masked": _mask(cfg.sms_internal_key, keep_tail=4),
        # anti-abuse (reserved)
        "sms_captcha_enabled": "1" if bool(cfg.sms_captcha_enabled) else "0",
        "sms_captcha_provider": (cfg.sms_captcha_provider or "turnstile").strip() or "turnstile",
        "sms_captcha_turnstile_site_key": (cfg.sms_captcha_turnstile_site_key or "").strip() or "",
        "sms_captcha_turnstile_secret_key_set": bool((cfg.sms_captcha_turnstile_secret_key or "").strip()),
        "sms_captcha_turnstile_secret_key_masked": _mask(cfg.sms_captcha_turnstile_secret_key, keep_tail=4),
        # 106 gateway overrides
        "sms_106_endpoint": (cfg.sms_106_endpoint or "").strip() or "",
        "sms_106_account": (cfg.sms_106_account or "").strip() or "",
        "sms_106_password_set": bool((cfg.sms_106_password or "").strip()),
        "sms_106_password_masked": _mask(cfg.sms_106_password, keep_tail=4),
        "sms_106_sign_name": (cfg.sms_106_sign_name or "").strip() or "",
        "sms_106_template": (cfg.sms_106_template or "").strip() or "",
        # tencent (reserved)
        "sms_tencent_secret_id": (cfg.sms_tencent_secret_id or "").strip() or "",
        "sms_tencent_secret_key_set": bool((cfg.sms_tencent_secret_key or "").strip()),
        "sms_tencent_secret_key_masked": _mask(cfg.sms_tencent_secret_key, keep_tail=4),
        "sms_tencent_sdk_app_id": (cfg.sms_tencent_sdk_app_id or "").strip() or "",
        "sms_tencent_sign": (cfg.sms_tencent_sign or "").strip() or "",
        "sms_tencent_template_id": (cfg.sms_tencent_template_id or "").strip() or "",
        "sms_tencent_region": (cfg.sms_tencent_region or "").strip() or "ap-guangzhou",
        # juhe（聚合数据，预留）
        "sms_juhe_key": (cfg.sms_juhe_key or "").strip() or "",
        "sms_juhe_template_id": (cfg.sms_juhe_template_id or "").strip() or "",
        "sms_juhe_sign": (cfg.sms_juhe_sign or "").strip() or "",
        "sms_juhe_template": (cfg.sms_juhe_template or "").strip() or "",
    }
    # If subsite didn't override 106 fields, pull main-site effective config for reference.
    try:
        base = (cfg.identity_api_base or "").strip()
        if base and (cfg.sms_internal_key or "").strip():
            main = _identity_get("/v1/admin/sms/effective") or {}
            if bool(main.get("ok")):
                if not out.get("sms_106_endpoint"):
                    out["sms_106_endpoint"] = str(main.get("sms_106_endpoint") or "").strip()
                if not out.get("sms_106_account"):
                    out["sms_106_account"] = str(main.get("sms_106_account") or "").strip()
                if not out.get("sms_106_sign_name"):
                    out["sms_106_sign_name"] = str(main.get("sms_106_sign_name") or "").strip()
                if not out.get("sms_106_template"):
                    out["sms_106_template"] = str(main.get("sms_106_template") or "").strip()
                out["sms_106_password_masked"] = str(main.get("sms_106_password_masked") or out.get("sms_106_password_masked") or "")
                out["sms_106_password_set"] = bool(str(out.get("sms_106_password_masked") or "").strip())
    except Exception:
        pass
    return out


@app.get("/api/admin/sms_logs")
def admin_sms_logs(
    phone: str = "",
    purpose: str = "",
    status: str = "",
    limit: int = 50,
    offset: int = 0,
    _: bool = Depends(require_admin),
) -> dict:
    """代理查询主站短信发送记录。"""
    cfg = resolve_identity()
    params = f"limit={min(limit,200)}&offset={offset}"
    if phone:
        params += f"&phone={phone}"
    if purpose:
        params += f"&purpose={purpose}"
    if status:
        params += f"&status={status}"
    data = _identity_get(f"/v1/admin/sms/logs?{params}")
    return data


@app.get("/api/public/sms_captcha")
def public_sms_captcha() -> dict:
    """Public config for reserved SMS captcha feature (default disabled)."""
    cfg = resolve_identity()
    if not bool(cfg.sms_captcha_enabled):
        return {"enabled": False}
    prov = (cfg.sms_captcha_provider or "turnstile").strip().lower()
    if prov != "turnstile":
        return {"enabled": False}
    site_key = (cfg.sms_captcha_turnstile_site_key or "").strip()
    if not site_key:
        return {"enabled": False}
    return {"enabled": True, "provider": "turnstile", "turnstile_site_key": site_key}


@app.post("/api/admin/config")
def admin_config_set(body: dict, _: bool = Depends(require_admin)) -> dict:
    key = str(body.get("key") or "").strip()
    value = str(body.get("value") if body.get("value") is not None else "").strip()
    if not key:
        raise HTTPException(status_code=400, detail="Missing key")
    try:
        out = db.admin_config_set(key, value)
        # Invalidate providers admin_config cache so paid switches take effect immediately.
        try:
            from . import providers as _providers

            try:
                _providers._ADMIN_CONF = None  # type: ignore[attr-defined]
                _providers._ADMIN_CONF_EXP = 0.0  # type: ignore[attr-defined]
            except Exception:
                pass
        except Exception:
            pass
        return out
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/admin/sms_106_config")
def admin_sms_106_config(_: bool = Depends(require_admin)) -> dict:
    """管理端读取 106 核心配置（明文，仅管理员）；存于 admin_config，保存后随短信转发提交主站。"""
    cfg = resolve_identity()
    return {
        "sms_106_endpoint": cfg.sms_106_endpoint,
        "sms_106_account": cfg.sms_106_account,
        "sms_106_password": cfg.sms_106_password,
        "sms_106_sign_name": cfg.sms_106_sign_name,
        "sms_106_template": cfg.sms_106_template,
        "note": "须与主站 SMS_INTERNAL_KEY 一致；模板须含 {code}；留空并保存可删除库内该项以回退主站 .env。",
    }


@app.get("/api/admin/sms_diagnostics")
def admin_sms_diagnostics(_: bool = Depends(require_admin)) -> dict:
    """经主站 `GET /v1/auth/sms/diagnostics` 拉取 106 网关脱敏参数（须主站已部署该路由且密钥一致）。"""
    cfg = resolve_identity()
    base = (cfg.identity_api_base or "").strip().rstrip("/")
    prov = (cfg.sms_active_provider or "identity_proxy").strip().lower()
    out: dict = {
        "ok": True,
        "sms_active_provider": prov,
        "default_provider": "identity_proxy",
        "default_note": "未配置 sms_active_provider 时默认为 identity_proxy：子站请求主站 API，主站再调 106接口网。",
        "identity_api_base": base or None,
        "subsite_admin_106": {
            "endpoint_set": bool((cfg.sms_106_endpoint or "").strip()),
            "account_set": bool((cfg.sms_106_account or "").strip()),
            "password_set": bool((cfg.sms_106_password or "").strip()),
            "sign_name_set": bool((cfg.sms_106_sign_name or "").strip()),
            "template_set": bool((cfg.sms_106_template or "").strip()),
        },
        "main_api_diagnostics": None,
        "fetch_error": None,
    }
    if prov == "tencent":
        out["note"] = "当前为腾讯短信预留通道，未请求主站 106 诊断。"
        return out
    if not base:
        out["ok"] = False
        out["fetch_error"] = "未配置 identity_api_base"
        return out
    try:
        out["main_api_diagnostics"] = _identity_get("/v1/auth/sms/diagnostics")
    except HTTPException as e:
        out["ok"] = False
        out["fetch_error"] = {"status_code": e.status_code, "detail": e.detail}
    return out


@app.post("/api/auth/sms/send")
def proxy_sms_send(body: SmsSendProxyIn, request: Request) -> dict:
    """转发至主站 `POST /v1/auth/sms/send`：带 X-SMS-Internal-Key；若管理端配置了 sms_106_* 则一并提交以覆盖主站 .env。"""
    cfg = resolve_identity()
    prov = (cfg.sms_active_provider or "identity_proxy").strip().lower()
    # Reserved: captcha gate for SMS anti-abuse (default off).
    if bool(cfg.sms_captcha_enabled):
        prov2 = (cfg.sms_captcha_provider or "turnstile").strip().lower()
        if prov2 == "turnstile":
            ok, err = _turnstile_verify(
                token=(body.captcha_token or "").strip(),
                remote_ip=str(getattr(request.client, "host", "") or "").strip() or None,
            )
            if not ok:
                raise HTTPException(status_code=400, detail=str(err or "图形码校验失败"))
    return _identity_post("/v1/auth/sms/send", _sms_forward_json(body.mobile, body.purpose))


@app.post("/api/auth/request_code", response_model=RequestCodeOut)
def request_code(body: RequestCodeIn) -> RequestCodeOut:
    if identity_configured():
        data = _identity_post(
            "/v1/auth/email/send",
            {"email": (body.email or "").strip().lower(), "purpose": (body.purpose or "register").strip()},
        )
        return RequestCodeOut(
            ok=bool(data.get("ok", True)),
            dev_code=data.get("dev_code"),
            message=data.get("message"),
        )
    dev_code = "1234" if settings.env != "prod" else None
    return RequestCodeOut(ok=True, dev_code=dev_code, message="验证码已生成。")


@app.post("/api/auth/register", response_model=LoginOut)
def register(body: RegisterIn) -> LoginOut:
    if not identity_configured():
        raise HTTPException(status_code=503, detail="注册需配置主站身份 API（环境变量或管理后台 identity_api_base）")
    payload: dict = {"password": body.password}
    if body.phone:
        payload["phone"] = body.phone
        payload["sms_code"] = (body.sms_code or "").strip()
    else:
        payload["email"] = body.email
        payload["email_code"] = (body.email_code or "").strip()
    data = _identity_post("/v1/auth/register", payload)
    return LoginOut(token=data["token"], user=data.get("user", {}))


@app.post("/api/auth/login", response_model=LoginOut)
def login(body: LoginIn) -> LoginOut:
    if identity_configured() and (body.password or "").strip():
        if not body.phone and not body.email:
            raise HTTPException(status_code=400, detail="请填写手机号或邮箱")
        payload: dict = {"password": (body.password or "").strip()}
        if body.phone:
            payload["phone"] = (body.phone or "").strip()
        else:
            payload["email"] = (body.email or "").strip().lower()
        data = _identity_post("/v1/auth/login", payload)
        return LoginOut(token=data["token"], user=data.get("user", {}))

    if not body.email or not body.code:
        raise HTTPException(
            status_code=400,
            detail="手机号或邮箱不存在，或密码错误。",
        )
    if settings.env != "prod":
        if body.code != "1234":
            raise HTTPException(status_code=400, detail="验证码错误")
        u = db.get_or_create_user_by_email(body.email, phone=body.phone)
        token = create_token(u.id, u.email, u.phone)
        return LoginOut(token=token, user={"id": u.id, "email": u.email, "phone": u.phone or ""})
    raise HTTPException(status_code=503, detail="服务暂未就绪，请稍后再试")


@app.post("/api/auth/password/change", response_model=LoginOut)
def password_change(request: Request, body: PasswordChangeIn) -> LoginOut:
    if not identity_configured():
        raise HTTPException(status_code=503, detail="未配置主站身份 API（环境变量或管理后台）")
    auth = (request.headers.get("Authorization") or "").strip()
    if not auth:
        raise HTTPException(status_code=401, detail="需要登录")
    data = _identity_post(
        "/v1/auth/password/change",
        {"old_password": body.old_password, "new_password": body.new_password},
        extra_headers={"Authorization": auth},
    )
    return LoginOut(token=data["token"], user=data.get("user", {}))


@app.post("/api/auth/password/reset", response_model=LoginOut)
def password_reset(body: PasswordResetIn) -> LoginOut:
    if not identity_configured():
        raise HTTPException(status_code=503, detail="未配置主站身份 API（环境变量或管理后台）")
    payload: dict = {"new_password": body.new_password}
    if body.phone:
        payload["phone"] = body.phone
        payload["sms_code"] = (body.sms_code or "").strip()
    else:
        payload["email"] = body.email
        payload["email_code"] = (body.email_code or "").strip()
    data = _identity_post("/v1/auth/password/reset", payload)
    return LoginOut(token=data["token"], user=data.get("user", {}))


@app.post("/api/auth/phone/bind", response_model=LoginOut)
def bind_phone(request: Request, body: dict) -> LoginOut:
    """Bind phone to current user (requires bearer token + sms code)."""
    if not identity_configured():
        raise HTTPException(status_code=503, detail="未配置主站身份 API（环境变量或管理后台）")
    auth = (request.headers.get("Authorization") or "").strip()
    if not auth:
        raise HTTPException(status_code=401, detail="需要登录")
    phone = str(body.get("phone") or "").strip()
    code = str(body.get("sms_code") or "").strip()
    if not phone or not code:
        raise HTTPException(status_code=400, detail="请填写手机号与短信验证码")
    data = _identity_post(
        "/v1/auth/phone/bind",
        {"phone": phone, "sms_code": code},
        extra_headers={"Authorization": auth},
    )
    try:
        tok = str(data.get("token") or "")
        if tok:
            payload = parse_token(tok)
            uid = int(payload.get("sub") or 0)
            if uid > 0:
                db.ensure_platform_user(uid, payload.get("email") or None, payload.get("phone") or None)
    except Exception:
        # best-effort: do not break bind flow if sync fails
        pass
    return LoginOut(token=data["token"], user=data.get("user", {}))


@app.post("/api/auth/email/bind", response_model=LoginOut)
def bind_email(request: Request, body: dict) -> LoginOut:
    """Bind email to current user (requires bearer token + email code)."""
    if not identity_configured():
        raise HTTPException(status_code=503, detail="未配置主站身份 API（环境变量或管理后台）")
    auth = (request.headers.get("Authorization") or "").strip()
    if not auth:
        raise HTTPException(status_code=401, detail="需要登录")
    email = str(body.get("email") or "").strip().lower()
    code = str(body.get("email_code") or "").strip()
    if not email or not code:
        raise HTTPException(status_code=400, detail="请填写邮箱与邮箱验证码")
    data = _identity_post(
        "/v1/auth/email/bind",
        {"email": email, "email_code": code},
        extra_headers={"Authorization": auth},
    )
    try:
        tok = str(data.get("token") or "")
        if tok:
            payload = parse_token(tok)
            uid = int(payload.get("sub") or 0)
            if uid > 0:
                db.ensure_platform_user(uid, payload.get("email") or None, payload.get("phone") or None)
    except Exception:
        pass
    return LoginOut(token=data["token"], user=data.get("user", {}))


@app.get("/api/feedback/categories")
def feedback_categories() -> dict:
    """反馈分类（前端与公开接口共用，无需登录）。"""
    return {"items": db.feedback_category_labels()}


@app.post("/api/feedback")
def feedback_submit(
    request: Request,
    body: FeedbackCreateIn,
    user_id: int = Depends(get_current_user_id),
) -> dict:
    # 内存桶：单进程内先挡 burst；跨进程以 DB 计数为准
    _rate_limit(
        f"feedback_submit_ip:{_client_ip(request)}",
        limit=80,
        window_s=3600,
    )
    _rate_limit(f"feedback_submit:{user_id}", limit=6, window_s=3600)
    try:
        return db.feedback_create(
            int(user_id),
            category=body.category,
            title=body.title,
            body=body.body,
            contact=body.contact,
        )
    except ValueError as e:
        code = str(e)
        msg = {
            "invalid_user": "用户无效",
            "invalid_category": "请选择有效的反馈类型",
            "body_too_short": "请至少填写 5 个字的详细描述",
            "body_too_long": "正文过长，请精简后重试",
            "feedback_hourly_cap": "本小时反馈次数已达上限，请稍后再试",
            "feedback_daily_cap": "今日反馈次数已达上限，请明天再试或合并为一条描述",
            "feedback_new_hourly_cap": "新账号本小时反馈次数已达上限，请稍后再试",
            "feedback_new_daily_cap": "新账号今日反馈次数已达上限，请明天再试",
        }.get(code, code)
        if code in (
            "feedback_hourly_cap",
            "feedback_daily_cap",
            "feedback_new_hourly_cap",
            "feedback_new_daily_cap",
        ):
            raise HTTPException(status_code=429, detail=msg)
        raise HTTPException(status_code=400, detail=msg)


@app.get("/api/feedback/mine")
def feedback_mine(
    request: Request,
    limit: int = 30,
    offset: int = 0,
    user_id: int = Depends(get_current_user_id),
) -> dict:
    _rate_limit(f"feedback_mine:{user_id}", limit=120, window_s=60)
    _rate_limit(f"feedback_mine_ip:{_client_ip(request)}", limit=200, window_s=60)
    return db.feedback_list_for_user(int(user_id), limit=limit, offset=offset)


@app.get("/api/notices")
def notices_list(
    limit: int = 20,
    offset: int = 0,
    unread_only: int = 0,
    user_id: int = Depends(get_current_user_id),
) -> dict:
    try:
        return db.notices_list_for_user(int(user_id), limit=int(limit), offset=int(offset), unread_only=bool(int(unread_only or 0) == 1))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)[:200])


@app.post("/api/notices/read")
def notices_mark_read(body: dict, user_id: int = Depends(get_current_user_id)) -> dict:
    try:
        nid = int(body.get("notice_id") or 0)
        return db.notice_mark_read(int(user_id), int(nid))
    except ValueError as e:
        code = str(e)
        msg = {"invalid_notice_id": "通告 ID 无效"}.get(code, code)
        raise HTTPException(status_code=400, detail=msg)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)[:200])


@app.get("/api/admin/notices")
def admin_notices(status: str = "", limit: int = 50, offset: int = 0, _: bool = Depends(require_admin)) -> dict:
    return db.admin_notice_list(status=status, limit=int(limit), offset=int(offset))


@app.post("/api/admin/notices/create")
def admin_notices_create(body: dict, _: bool = Depends(require_admin)) -> dict:
    try:
        return db.admin_notice_create(
            title=str(body.get("title") or ""),
            body=str(body.get("body") or ""),
            scope=str(body.get("scope") or "all"),
            target_user_id=(int(body.get("target_user_id")) if body.get("target_user_id") not in (None, "", 0, "0") else None),
            target_agent_level=str(body.get("target_agent_level") or ""),
            pinned=bool(body.get("pinned")),
            starts_at=(int(body.get("starts_at")) if body.get("starts_at") not in (None, "", 0, "0") else None),
            ends_at=(int(body.get("ends_at")) if body.get("ends_at") not in (None, "", 0, "0") else None),
            created_by="admin",
        )
    except ValueError as e:
        code = str(e)
        msg = {
            "title_body_required": "请填写标题与正文",
            "invalid_scope": "scope 仅支持 all / user / agent_level",
            "target_user_required": "scope=user 需要 target_user_id",
            "target_agent_level_required": "scope=agent_level 需要 target_agent_level=starter/growth/pro",
        }.get(code, code)
        raise HTTPException(status_code=400, detail=msg)


@app.post("/api/admin/notices/set_status")
def admin_notices_set_status(body: dict, _: bool = Depends(require_admin)) -> dict:
    try:
        nid = int(body.get("notice_id") or 0)
        st = str(body.get("status") or "")
        return db.admin_notice_set_status(int(nid), st)
    except ValueError as e:
        code = str(e)
        msg = {"invalid_notice_id": "通告 ID 无效", "invalid_status": "status 仅支持 active/archived"}.get(code, code)
        raise HTTPException(status_code=400, detail=msg)


@app.post("/api/admin/notices/pin")
def admin_notices_pin(body: dict, _: bool = Depends(require_admin)) -> dict:
    try:
        nid = int(body.get("notice_id") or 0)
        pinned = bool(int(body.get("pinned") or 0) == 1) if body.get("pinned") is not None else bool(body.get("pinned"))
        return db.admin_notice_pin(int(nid), bool(pinned))
    except ValueError as e:
        code = str(e)
        msg = {"invalid_notice_id": "通告 ID 无效"}.get(code, code)
        raise HTTPException(status_code=400, detail=msg)


@app.post("/api/admin/notices/update")
def admin_notices_update(body: dict, _: bool = Depends(require_admin)) -> dict:
    try:
        nid = int(body.get("notice_id") or 0)
        return db.admin_notice_update(
            int(nid),
            title=str(body.get("title") or ""),
            body=str(body.get("body") or ""),
            scope=str(body.get("scope") or "all"),
            target_user_id=(int(body.get("target_user_id")) if body.get("target_user_id") not in (None, "", 0, "0") else None),
            target_agent_level=str(body.get("target_agent_level") or ""),
            pinned=bool(body.get("pinned")),
            starts_at=(int(body.get("starts_at")) if body.get("starts_at") not in (None, "", 0, "0") else None),
            ends_at=(int(body.get("ends_at")) if body.get("ends_at") not in (None, "", 0, "0") else None),
        )
    except ValueError as e:
        code = str(e)
        msg = {
            "invalid_notice_id": "通告 ID 无效",
            "title_body_required": "请填写标题与正文",
            "invalid_scope": "scope 仅支持 all / user / agent_level",
            "target_user_required": "scope=user 需要 target_user_id",
            "target_agent_level_required": "scope=agent_level 需要 target_agent_level=starter/growth/pro",
        }.get(code, code)
        raise HTTPException(status_code=400, detail=msg)


@app.get("/api/me")
def me(user_id: int = Depends(get_current_user_id)) -> dict:
    db.downgrade_expired_vip_plan(int(user_id))
    try:
        u = db.get_user_basic(int(user_id))
    except Exception:
        u = {"id": int(user_id)}
    return {"user": u, "quota": db.get_quota_status(user_id)}


@app.get("/api/quota/status")
def quota_status(user_id: int = Depends(get_current_user_id)) -> dict:
    db.downgrade_expired_vip_plan(int(user_id))
    return db.get_quota_status(user_id)


@app.post("/api/quota/consume", response_model=QuotaConsumeOut)
def quota_consume(body: QuotaConsumeIn, user_id: int = Depends(get_current_user_id)) -> QuotaConsumeOut:
    # 推荐 idempotency_key = f"{secid}:{period}:{floor(now/dedupe_seconds)}"
    r = db.consume_quota(user_id, body.secid, body.period, body.idempotency_key, ok=bool(body.ok))
    return QuotaConsumeOut(
        result=str(r["result"]),
        deduped=bool(r["deduped"]),
        consumed_at=int(r["consumed_at"]),
        quota=r.get("quota"),
    )


def _rand_code(n: int = 8) -> str:
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choice(chars) for _ in range(n))


@app.get("/api/invite/my_code")
def invite_my_code(user_id: int = Depends(get_current_user_id)) -> dict:
    now = int(time.time())
    with db.connect() as conn:
        row = conn.execute("SELECT code FROM invite_codes WHERE user_id=?", (user_id,)).fetchone()
        if row:
            return {"code": str(row["code"])}
        # generate unique
        code = _rand_code(8)
        for _ in range(5):
            try:
                conn.execute(
                    "INSERT INTO invite_codes(user_id, code, created_at) VALUES (?, ?, ?)",
                    (user_id, code, now),
                )
                return {"code": code}
            except Exception:
                code = _rand_code(8)
        raise HTTPException(status_code=500, detail="生成邀请码失败，请稍后重试")


@app.post("/api/invite/bind")
def invite_bind(body: InviteBindIn, user_id: int = Depends(get_current_user_id)) -> dict:
    code = body.code.strip().upper()
    now = int(time.time())
    with db.connect() as conn:
        existing = conn.execute("SELECT inviter_id FROM invite_relations WHERE invitee_id=?", (user_id,)).fetchone()
        if existing:
            return {"ok": True, "bound": True}
        inviter = conn.execute("SELECT user_id FROM invite_codes WHERE code=?", (code,)).fetchone()
        if not inviter:
            raise HTTPException(status_code=400, detail="邀请码无效，请检查后重试")
        inviter_id = int(inviter["user_id"])
        if inviter_id == user_id:
            raise HTTPException(status_code=400, detail="不能绑定自己的邀请码")
        # Cache up to 3-level ancestor chain at bind-time to keep paid-order attribution stable and fast.
        l1 = inviter_id
        l2 = None
        l3 = None
        try:
            chain = db._invite_chain_for_user_in_conn(conn, inviter_id)  # type: ignore[attr-defined]
            # chain returns (l1,l2,l3) for inviter as an invitee; shift it up by one.
            l2 = chain[0]
            l3 = chain[1]
        except Exception:
            l2 = None
            l3 = None
        depth = 1 + (1 if l2 else 0) + (1 if l3 else 0)
        try:
            conn.execute(
                "INSERT INTO invite_relations(invitee_id, inviter_id, inviter_l1_id, inviter_l2_id, inviter_l3_id, depth, updated_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (user_id, inviter_id, l1, l2, l3, int(depth), now, now),
            )
        except Exception:
            # Fallback for very old schema: keep minimal relation.
            conn.execute(
                "INSERT INTO invite_relations(invitee_id, inviter_id, created_at) VALUES (?, ?, ?)",
                (user_id, inviter_id, now),
            )
        # MVP 发奖策略：绑定成功后不直接发，等“首次有效查询”触发更抗刷（阶段1先留接口位）
        return {"ok": True, "bound": True}


@app.get("/api/invite/summary")
def invite_summary(user_id: int = Depends(get_current_user_id)) -> dict:
    return {"summary": db.invite_summary_for_user(user_id)}


@app.get("/api/invite/list")
def invite_list(limit: int = 50, user_id: int = Depends(get_current_user_id)) -> dict:
    return {"items": db.invite_list_for_user(user_id, limit=limit)}


@app.get("/api/suggest")
async def api_suggest(
    q: str,
    include_plates: int = 0,
    user_id: Optional[int] = Depends(get_optional_user_id),
) -> dict:
    # MVP：不扣次数（扣次数放在真正加载 kline 前）
    _rate_limit(f"suggest:{user_id or 'anon'}", settings.suggest_per_minute)
    em = await fetch_em_suggest(q, include_plates=bool(int(include_plates or 0)))
    ths = await fetch_ths_suggest(q)
    try:
        d1 = (((em or {}).get("QuotationCodeTable") or {}).get("Data")) if isinstance(em, dict) else None
        d2 = (((ths or {}).get("QuotationCodeTable") or {}).get("Data")) if isinstance(ths, dict) else None
        # If Eastmoney returns empty but THS has results, return THS directly.
        if isinstance(d2, list) and d2 and (not isinstance(d1, list) or not d1):
            return ths
        if isinstance(d1, list) and isinstance(d2, list) and d2:
            # append THS items after Eastmoney items
            merged = d1 + d2
            out = dict(em)
            tbl = dict(out.get("QuotationCodeTable") or {})
            tbl["Data"] = merged
            tbl["TotalCount"] = int(len(merged))
            out["QuotationCodeTable"] = tbl
            return out
    except Exception:
        pass
    return em


@app.get("/api/kline")
async def api_kline(
    secid: str,
    period: str = "day",
    count: int = 500,
    request: "Request" = None,  # type: ignore[assignment]
    user_id: Optional[int] = Depends(get_optional_user_id),
) -> dict:
    _rate_limit(f"kline:{user_id or 'anon'}", settings.kline_per_minute)
    if user_id is not None:
        _auth_ip_rate_limit(request)
    if period not in ("day", "week", "month"):
        raise HTTPException(status_code=400, detail="Invalid period")
    if count < 50:
        count = 50
    # For week/month signals we may need multi-year history. Allow a higher cap for these periods.
    if period in ("week", "month"):
        if count > 3000:
            count = 3000
    else:
        if count > 1000:
            count = 1000
    try:
        if user_id is None:
            secid0 = str(secid or "").strip()
            # THS 概念板块（ths:886108）只能通过 tushare 付费源获取K线，
            # 对游客开放板块查询权限，提升体验。
            is_ths_plate = secid0.lower().startswith("ths:")
            # Force public sources only; do not allow paid provider for anonymous traffic.
            md = market_data_status()
            base_pri = str((md.get("paid") or {}).get("priority") or "").strip().lower()
            if not base_pri:
                base_pri = "tencent,eastmoney,sina,paid"
            if is_ths_plate:
                # 板块查K线：保留 paid（tushare 是唯一数据源）
                priority_override = base_pri
            else:
                priority_override = ",".join([x for x in base_pri.split(",") if x.strip() and x.strip() != "paid"])

            if secid0 in _ANON_KLINE_WHITELIST:
                # Whitelist: always allowed (onboarding + demo stability).
                count_anon = min(int(count), 800)
                return await fetch_tx_kline(
                    secid0,
                    period,
                    count=count_anon,
                    variant="anon",
                    priority_override=priority_override,
                    allow_paid=is_ths_plate,
                )

            # Extra anon trial quota for self-selected symbols (3/day per IP).
            # Only check availability here; actual consume happens in kline_with_signals.
            if request is not None and _anon_daily_can_consume(request):
                count_anon = min(int(count), 800)
                payload = await fetch_tx_kline(
                    secid0,
                    period,
                    count=count_anon,
                    variant="anon",
                    priority_override=priority_override,
                    allow_paid=is_ths_plate,
                )
                return payload

            return {"code": -401, "msg": "游客今日体验次数已用完，请登录继续", "data": {}}

        db.downgrade_expired_vip_plan(int(user_id))
        quota = db.get_quota_status(int(user_id)) if user_id is not None else {"plan": "anon"}
        plan = str(quota.get("plan") or "anon").strip().lower()
        is_vip = plan not in ("", "free", "anon")

        # C方案：默认 VIP 优先 paid；免费优先公共源；公共源不稳时再回落 paid
        # 但如果后台把优先级显式配置为 `paid,...`，视为“强制付费优先”（所有用户都优先 paid），方便应急切流。
        md = market_data_status()
        base_pri = str((md.get("paid") or {}).get("priority") or "").strip().lower()
        if not base_pri:
            base_pri = "tencent,eastmoney,sina,paid"

        # If vip_only enabled, forbid non-vip to use paid.
        vip_only = bool((md.get("paid") or {}).get("vip_only"))
        allow_paid = (is_vip or not vip_only)

        def reorder(priority: str, paid_first: bool) -> str:
            items = [x.strip() for x in (priority or "").split(",") if x.strip()]
            # ensure paid exists for paid_first and allow_paid cases
            items2 = []
            for it in items:
                if it not in items2:
                    items2.append(it)
            if "paid" in items2:
                items2 = [x for x in items2 if x != "paid"]
            if paid_first:
                items2 = ["paid"] + items2
            else:
                items2 = items2 + ["paid"]
            return ",".join(items2)

        first = (base_pri.split(",")[0].strip() if base_pri else "")
        force_paid_first = first == "paid"
        paid_first = bool(force_paid_first or is_vip)
        priority_override = reorder(base_pri, paid_first=paid_first) if allow_paid else ",".join([x for x in base_pri.split(",") if x.strip() != "paid"])
        data = await fetch_tx_kline(
            secid,
            period,
            count=count,
            variant=("vip" if is_vip else "free"),
            priority_override=priority_override,
            allow_paid=allow_paid,
        )
        return data
    except HTTPException:
        raise
    except Exception as e:
        # Keep HTTP 200 so frontend can show a stable "code/msg" error without surfacing "Failed to fetch".
        return {"code": -1, "msg": f"K线数据源请求失败，请稍后重试（{type(e).__name__}）", "data": {}}


@app.get("/api/signals")
async def api_signals(
    secid: str,
    period: str = "day",
    count: int = 500,
    user_id: Optional[int] = Depends(get_optional_user_id),
) -> dict:
    """
    Signals/markers computed on server (B-plan MVP).

    Return shape:
    - code: 0 ok
    - data: { markers: [...], version: "a2-v1" }
    """
    _rate_limit(f"signals:{user_id or 'anon'}", settings.kline_per_minute)
    if user_id is not None:
        _auth_ip_rate_limit(request)
    if period not in ("day", "week", "month"):
        raise HTTPException(status_code=400, detail="Invalid period")
    if count < 50:
        count = 50
    if period in ("week", "month"):
        if count > 3000:
            count = 3000
    else:
        if count > 1000:
            count = 1000

    try:
        # Keep the same anon policy as /api/kline.
        if user_id is None:
            secid0 = str(secid or "").strip()
            is_ths_plate = secid0.lower().startswith("ths:")
            if secid0 in _ANON_KLINE_WHITELIST or is_ths_plate:
                md = market_data_status()
                base_pri = str((md.get("paid") or {}).get("priority") or "").strip().lower()
                if not base_pri:
                    base_pri = "tencent,eastmoney,sina,paid"
                if is_ths_plate:
                    priority_override = base_pri
                else:
                    priority_override = ",".join([x for x in base_pri.split(",") if x.strip() and x.strip() != "paid"])
                count_anon = min(int(count), 800)
                payload = await fetch_tx_kline(
                    secid0,
                    period,
                    count=count_anon,
                    variant="anon",
                    priority_override=priority_override,
                    allow_paid=is_ths_plate,
                )
            else:
                return {"code": -401, "msg": "请先登录后再查询", "data": {}}
        else:
            db.downgrade_expired_vip_plan(int(user_id))
            quota = db.get_quota_status(int(user_id))
            plan = str(quota.get("plan") or "anon").strip().lower()
            is_vip = plan not in ("", "free", "anon")
            md = market_data_status()
            base_pri = str((md.get("paid") or {}).get("priority") or "").strip().lower()
            if not base_pri:
                base_pri = "tencent,eastmoney,sina,paid"
            vip_only = bool((md.get("paid") or {}).get("vip_only"))
            allow_paid = (is_vip or not vip_only)

            def reorder(priority: str, paid_first: bool) -> str:
                items = [x.strip() for x in (priority or "").split(",") if x.strip()]
                items2 = []
                for it in items:
                    if it not in items2:
                        items2.append(it)
                if "paid" in items2:
                    items2 = [x for x in items2 if x != "paid"]
                if paid_first:
                    items2 = ["paid"] + items2
                else:
                    items2 = items2 + ["paid"]
                return ",".join(items2)

            first = (base_pri.split(",")[0].strip() if base_pri else "")
            force_paid_first = first == "paid"
            paid_first = bool(force_paid_first or is_vip)
            priority_override = (
                reorder(base_pri, paid_first=paid_first)
                if allow_paid
                else ",".join([x for x in base_pri.split(",") if x.strip() != "paid"])
            )
            payload = await fetch_tx_kline(
                secid,
                period,
                count=count,
                variant=("vip" if is_vip else "free"),
                priority_override=priority_override,
                allow_paid=allow_paid,
            )

        if not isinstance(payload, dict) or int(payload.get("code") or 0) != 0:
            return {"code": int((payload or {}).get("code") or -1), "msg": str((payload or {}).get("msg") or "signals failed"), "data": {}}
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict) or not data:
            return {"code": -1, "msg": "signals: empty data", "data": {}}
        # pick first pack (same as frontend key selection)
        pack = next(iter(data.values()))
        if not isinstance(pack, dict):
            return {"code": -1, "msg": "signals: bad pack", "data": {}}
        candles = candles_from_tencent_like_pack(pack, period=period)  # type: ignore[arg-type]
        # Week/month may be rendered on frontend by aggregating daily bars when provider
        # doesn't return week/month rows. Keep backend behavior aligned so markers show up.
        try:
            if period in ("week", "month") and len(candles) < 60:
                # Pull daily history and aggregate.
                day_count = int(count)
                if period == "week":
                    day_count = max(day_count * 8, 1200)
                else:
                    day_count = max(day_count * 25, 1500)
                day_count = min(day_count, 3000)
                payload_day = await fetch_tx_kline(
                    secid,
                    "day",
                    count=day_count,
                    variant=("vip" if user_id is not None and is_vip else "free") if user_id is not None else "anon",
                    priority_override=priority_override,
                    allow_paid=allow_paid if user_id is not None else False,
                )
                if isinstance(payload_day, dict) and int(payload_day.get("code") or 0) == 0:
                    data_day = payload_day.get("data") if isinstance(payload_day, dict) else None
                    if isinstance(data_day, dict) and data_day:
                        pack_day = next(iter(data_day.values()))
                        if isinstance(pack_day, dict):
                            day_candles = candles_from_tencent_like_pack(pack_day, period="day")
                            if period == "week":
                                from .signals import aggregate_daily_to_week
                                candles = aggregate_daily_to_week(day_candles)
                            else:
                                from .signals import aggregate_daily_to_month
                                candles = aggregate_daily_to_month(day_candles)
        except Exception:
            pass
        sig = build_signals_v3(candles, cache_key=f"{secid0}_{period}")
        return {
            "code": 0,
            "msg": "ok",
            "data": {
                "version": "a2-v3",
                "markers": sig.get("markers") or [],
                "bar_labels": sig.get("bar_labels") or [],
                "macd": sig.get("macd") or [],
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        return {"code": -1, "msg": f"signals failed ({type(e).__name__})", "data": {}}


@app.get("/api/kline_with_signals")
async def api_kline_with_signals(
    secid: str,
    period: str = "day",
    count: int = 500,
    request: "Request" = None,  # type: ignore[assignment]
    user_id: Optional[int] = Depends(get_optional_user_id),
) -> dict:
    """
    One-shot endpoint: fetch kline pack + compute signals in one request.
    This avoids the frontend doing /api/kline + /api/signals separately (2 RTT + duplicated upstream pulls).
    """
    _rate_limit(f"kline2:{user_id or 'anon'}", settings.kline_per_minute)
    if user_id is not None:
        _auth_ip_rate_limit(request)
    if period not in ("day", "week", "month"):
        raise HTTPException(status_code=400, detail="Invalid period")
    if count < 50:
        count = 50
    if period in ("week", "month"):
        if count > 3000:
            count = 3000
    else:
        if count > 1000:
            count = 1000

    # Resolve the same paid/public policy as /api/kline and /api/signals.
    secid0 = str(secid or "").strip()
    md = market_data_status()
    base_pri = str((md.get("paid") or {}).get("priority") or "").strip().lower()
    if not base_pri:
        base_pri = "tencent,eastmoney,sina,paid"
    vip_only = bool((md.get("paid") or {}).get("vip_only"))

    is_vip = False
    allow_paid = False
    variant = "free"
    priority_override = base_pri

    def reorder(priority: str, paid_first: bool) -> str:
        items = [x.strip() for x in (priority or "").split(",") if x.strip()]
        items2: list[str] = []
        for it in items:
            if it not in items2:
                items2.append(it)
        if "paid" in items2:
            items2 = [x for x in items2 if x != "paid"]
        if paid_first:
            items2 = ["paid"] + items2
        else:
            items2 = items2 + ["paid"]
        return ",".join(items2)

    is_ths_plate = secid0.lower().startswith("ths:")
    if user_id is None:
        priority_override = ",".join([x for x in base_pri.split(",") if x.strip() and x.strip() != "paid"])
        allow_paid = False
        variant = "anon"
        count = min(int(count), 800)

        # THS 概念板块只能通过 tushare 付费源获取K线，对游客开放
        if is_ths_plate:
            allow_paid = True
            priority_override = base_pri
        elif secid0 not in _ANON_KLINE_WHITELIST:
            if request is None or not _anon_daily_can_consume(request):
                return {"code": -401, "msg": "游客今日体验次数已用完，请登录继续", "data": {}, "signals": {}}
    else:
        db.downgrade_expired_vip_plan(int(user_id))
        quota = db.get_quota_status(int(user_id))
        plan = str(quota.get("plan") or "anon").strip().lower()
        is_vip = plan not in ("", "free", "anon")
        allow_paid = (is_vip or not vip_only)
        first = (base_pri.split(",")[0].strip() if base_pri else "")
        paid_first = bool(first == "paid" or is_vip)
        priority_override = (
            reorder(base_pri, paid_first=paid_first)
            if allow_paid
            else ",".join([x for x in base_pri.split(",") if x.strip() != "paid"])
        )
        variant = "vip" if is_vip else "free"

    # Fetch kline ONCE.
    payload = await fetch_tx_kline(
        secid0,
        period,
        count=int(count),
        variant=variant,
        priority_override=priority_override,
        allow_paid=allow_paid,
    )
    # Consume anon daily trial only for non-whitelist success.
    try:
        if user_id is None and secid0 not in _ANON_KLINE_WHITELIST and request is not None:
            if isinstance(payload, dict) and int(payload.get("code") or 0) == 0:
                _anon_daily_consume(request)
    except Exception:
        pass
    if not isinstance(payload, dict) or int(payload.get("code") or 0) != 0:
        return {
            "code": int((payload or {}).get("code") or -1),
            "msg": str((payload or {}).get("msg") or "kline failed"),
            "data": (payload or {}).get("data") if isinstance(payload, dict) else {},
            "signals": {},
        }
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict) or not data:
        return {"code": -1, "msg": "kline: empty data", "data": {}, "signals": {}}
    pack = next(iter(data.values()))
    if not isinstance(pack, dict):
        return {"code": -1, "msg": "kline: bad pack", "data": data, "signals": {}}

    # Compute signals based on the same candles (avoid divergence).
    try:
        from .signals import (
            candles_from_tencent_like_pack,
            aggregate_daily_to_week,
            aggregate_daily_to_month,
            rows_from_candles,
        )
        candles = candles_from_tencent_like_pack(pack, period=period)  # type: ignore[arg-type]
        # If provider doesn't have week/month rows, derive from daily in the SAME endpoint.
        if period in ("week", "month") and len(candles) < 60:
            day_count = int(count)
            if period == "week":
                day_count = max(day_count * 8, 1200)
            else:
                day_count = max(day_count * 25, 1500)
            day_count = min(day_count, 3000)
            payload_day = await fetch_tx_kline(
                secid0,
                "day",
                count=day_count,
                variant=variant,
                priority_override=priority_override,
                allow_paid=allow_paid,
            )
            if isinstance(payload_day, dict) and int(payload_day.get("code") or 0) == 0:
                data_day = payload_day.get("data")
                if isinstance(data_day, dict) and data_day:
                    pack_day = next(iter(data_day.values()))
                    if isinstance(pack_day, dict):
                        day_candles = candles_from_tencent_like_pack(pack_day, period="day")
                        if period == "week":
                            agg = aggregate_daily_to_week(day_candles)
                            candles = agg
                            rows = rows_from_candles(agg)
                            pack["qfqweek"] = rows
                            pack["week"] = rows
                        else:
                            agg = aggregate_daily_to_month(day_candles)
                            candles = agg
                            rows = rows_from_candles(agg)
                            pack["qfqmonth"] = rows
                            pack["month"] = rows
        sig = build_signals_v3(candles, cache_key=f"{secid0}_{period}")
        payload["data"] = data  # ensure pack mutations are returned
        payload["signals"] = {
            "version": "a2-v3",
            "markers": sig.get("markers") or [],
            "bar_labels": sig.get("bar_labels") or [],
            "macd": sig.get("macd") or [],
        }
        return payload
    except Exception as e:
        payload["signals"] = {"code": -1, "msg": f"signals failed ({type(e).__name__})"}
        return payload


@app.get("/api/status/market-data")
def api_market_data_status(_: bool = Depends(require_admin)) -> dict:
    return market_data_status()


@app.get("/api/public/billing/plans")
def public_billing_plans() -> dict:
    """
    给静态前端展示用的套餐信息（名称/标价）。

    注意：这不是支付接口；真实下单金额仍由后端下单时计算并校验。
    """
    b = resolve_billing()
    return {
        "ok": True,
        "pay_methods": {
            "wechat_enabled": bool(getattr(b, "billing_pay_wechat_enabled", True)),
            "alipay_enabled": bool(getattr(b, "billing_pay_alipay_enabled", True)),
        },
        "plans": {
            "vip_trial_99": {
                "title": str(getattr(b, "vip_title_trial", "AI24X VIP体验卡") or "AI24X VIP体验卡"),
                "price_fen": int(getattr(b, "price_vip_trial_fen", settings.price_vip_trial_fen)),
            },
            "vip_month": {
                "title": str(getattr(b, "vip_title_month", "AI24X VIP月会员") or "AI24X VIP月会员"),
                "price_fen": int(getattr(b, "price_vip_month_fen", settings.price_vip_month_fen)),
            },
            "vip_year_999": {
                "title": str(getattr(b, "vip_title_year", "AI24X VIP年会员") or "AI24X VIP年会员"),
                "price_fen": int(getattr(b, "price_vip_year_fen", settings.price_vip_year_fen)),
            },
            **(
                {
                    "agent_growth": {
                        "title": str(getattr(b, "agent_title_growth", "伙伴计划 · 成长档") or "伙伴计划 · 成长档"),
                        "price_fen": int(getattr(b, "price_agent_growth_fen", 29900)),
                    }
                }
                if bool(getattr(b, "agent_upgrade_growth_enabled", True))
                else {}
            ),
            **(
                {
                    "agent_pro": {
                        "title": str(getattr(b, "agent_title_pro", "伙伴计划 · 专业档") or "伙伴计划 · 专业档"),
                        "price_fen": int(getattr(b, "price_agent_pro_fen", 99900)),
                    }
                }
                if bool(getattr(b, "agent_upgrade_pro_enabled", True))
                else {}
            ),
        },
    }


@app.get("/api/public/invite/config")
def public_invite_config() -> dict:
    """Public invite reward config for frontend display (no auth)."""
    try:
        return {"ok": True, **(db.invite_cfg_effective() or {})}
    except Exception:
        return {"ok": True, "invite_reward_inviter_weekly": 0, "invite_reward_invitee_weekly": 0, "invite_weekly_cap": 0}


def _billing_normalize_plan(plan: str) -> tuple[str, int]:
    b = resolve_billing()
    p = (plan or "").strip().lower()
    if p in ("vip_month", "month", "monthly", "vip"):
        return "vip_month", int(getattr(b, "price_vip_month_fen", settings.price_vip_month_fen))
    if p in ("vip_year_999", "vip_year", "year", "yearly"):
        return "vip_year_999", int(getattr(b, "price_vip_year_fen", settings.price_vip_year_fen))
    if p in ("vip_trial_99", "vip_trial", "trial", "trial_99"):
        return "vip_trial_99", int(getattr(b, "price_vip_trial_fen", settings.price_vip_trial_fen))
    if p in ("agent_growth", "growth", "agent_g"):
        if not bool(getattr(b, "agent_upgrade_growth_enabled", True)):
            raise HTTPException(status_code=503, detail="成长档升级暂未开放")
        return "agent_growth", int(getattr(b, "price_agent_growth_fen", 29900))
    if p in ("agent_pro", "pro", "agent_p"):
        if not bool(getattr(b, "agent_upgrade_pro_enabled", True)):
            raise HTTPException(status_code=503, detail="专业档升级暂未开放")
        return "agent_pro", int(getattr(b, "price_agent_pro_fen", 99900))
    raise HTTPException(
        status_code=400,
        detail="不支持的套餐：vip_trial_99 / vip_month / vip_year_999 / agent_growth / agent_pro",
    )


def _billing_charge_amount_fen(catalog_fen: int) -> int:
    """非 prod 可开启真实小额扣款用于联调。"""
    b = resolve_billing()
    if bool(getattr(b, "billing_dev_real_pay", False)):
        return max(1, int(getattr(b, "billing_dev_amount_fen", settings.billing_dev_amount_fen)))
    return int(catalog_fen)


def _fen_to_yuan_display(fen: int) -> str:
    try:
        return f"{(int(fen) / 100.0):.2f}"
    except Exception:
        return "0.00"


def _yuan_str_from_fen(fen: int) -> str:
    try:
        return f"{(int(fen) / 100.0):.2f}"
    except Exception:
        return "0.00"


@app.post("/api/billing/wechat/native", response_model=PayNativeOut)
async def billing_wechat_native(body: PayNativeIn, user_id: int = Depends(get_current_user_id)) -> PayNativeOut:
    wx_cfg = resolve_wechat_pay()
    b = resolve_billing()
    if not bool(getattr(b, "billing_pay_wechat_enabled", True)):
        raise HTTPException(status_code=503, detail="微信支付已关闭")
    if not wechat_v3.wechat_pay_configured(wx_cfg):
        raise HTTPException(
            status_code=503,
            detail="微信支付未配置：请设置 AI24X_WECHAT_MCH_ID / APP_ID / MCH_SERIAL_NO / MCH_PRIVATE_KEY_PATH / API_V3_KEY / NOTIFY_URL",
        )
    plan_norm, priced_fen = _billing_normalize_plan(body.plan)
    if plan_norm == "vip_trial_99" and db.pay_user_has_paid_trial(int(user_id)):
        raise HTTPException(
            status_code=400,
            detail="体验卡每位用户限购 1 次，您已购买过。如需更高额度请选择月卡或年卡。",
        )
    charge_fen = _billing_charge_amount_fen(priced_fen)
    out_trade_no = db.pay_mk_out_trade_no(int(user_id))
    if plan_norm == "vip_month":
        desc = str(getattr(b, "vip_title_month", "AI24X VIP月会员") or "AI24X VIP月会员")
    elif plan_norm == "vip_year_999":
        desc = str(getattr(b, "vip_title_year", "AI24X VIP年会员") or "AI24X VIP年会员")
    elif plan_norm == "vip_trial_99":
        desc = str(getattr(b, "vip_title_trial", "AI24X VIP体验卡") or "AI24X VIP体验卡")
    elif plan_norm == "agent_growth":
        desc = str(getattr(b, "agent_title_growth", "伙伴计划 · 成长档") or "伙伴计划 · 成长档")
    else:
        desc = str(getattr(b, "agent_title_pro", "伙伴计划 · 专业档") or "伙伴计划 · 专业档")
    db.pay_order_create(
        int(user_id),
        out_trade_no=out_trade_no,
        plan=plan_norm,
        amount_fen=charge_fen,
        channel="wechat",
        code_url=None,
    )
    try:
        wx = await wechat_v3.native_create_order(
            wx_cfg,
            out_trade_no=out_trade_no,
            description=desc,
            amount_fen=charge_fen,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)[:800]) from e
    code_url = str(wx.get("code_url") or "")
    if not code_url:
        raise HTTPException(status_code=502, detail=f"微信下单未返回 code_url: {wx!r}")
    db.pay_order_attach_code_url(out_trade_no, code_url)
    return PayNativeOut(
        out_trade_no=out_trade_no,
        code_url=code_url,
        amount_fen=charge_fen,
        priced_amount_fen=priced_fen,
        amount_yuan_display=_fen_to_yuan_display(charge_fen),
        priced_amount_yuan_display=_fen_to_yuan_display(priced_fen),
        plan=plan_norm,
    )


@app.post("/api/billing/wechat/h5", response_model=PayH5Out)
async def billing_wechat_h5(request: Request, body: PayNativeIn, user_id: int = Depends(get_current_user_id)) -> PayH5Out:
    """
    微信 H5（MWEB）下单：用于微信内置浏览器，避免“长按识别二维码被拦截”。
    前端拿到 h5_url 后应直接跳转；支付完成会回跳 return_url。
    """
    wx_cfg = resolve_wechat_pay()
    b = resolve_billing()
    if not bool(getattr(b, "billing_pay_wechat_enabled", True)):
        raise HTTPException(status_code=503, detail="微信支付已关闭")
    if not wechat_v3.wechat_pay_configured(wx_cfg):
        raise HTTPException(status_code=503, detail="微信支付未配置")

    plan_norm, priced_fen = _billing_normalize_plan(body.plan)
    if plan_norm == "vip_trial_99" and db.pay_user_has_paid_trial(int(user_id)):
        raise HTTPException(status_code=400, detail="体验卡每位用户限购 1 次，您已购买过。")
    charge_fen = _billing_charge_amount_fen(priced_fen)
    out_trade_no = db.pay_mk_out_trade_no(int(user_id))
    if plan_norm == "vip_month":
        desc = str(getattr(b, "vip_title_month", "AI24X VIP月会员") or "AI24X VIP月会员")
    elif plan_norm == "vip_year_999":
        desc = str(getattr(b, "vip_title_year", "AI24X VIP年会员") or "AI24X VIP年会员")
    elif plan_norm == "vip_trial_99":
        desc = str(getattr(b, "vip_title_trial", "AI24X VIP体验卡") or "AI24X VIP体验卡")
    elif plan_norm == "agent_growth":
        desc = str(getattr(b, "agent_title_growth", "伙伴计划 · 成长档") or "伙伴计划 · 成长档")
    else:
        desc = str(getattr(b, "agent_title_pro", "伙伴计划 · 专业档") or "伙伴计划 · 专业档")

    # Build redirect_url from forwarded headers (behind Nginx).
    try:
        proto = str(request.headers.get("x-forwarded-proto") or request.url.scheme or "https").split(",")[0].strip()
        host = str(request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc or "").split(",")[0].strip()
        origin = f"{proto}://{host}" if host else str(request.base_url).rstrip("/")
    except Exception:
        origin = str(request.base_url).rstrip("/")
    redirect_url = f"{origin}/account.html?otn={quote(out_trade_no)}&ch=wechat"

    db.pay_order_create(
        int(user_id),
        out_trade_no=out_trade_no,
        plan=plan_norm,
        amount_fen=charge_fen,
        channel="wechat_h5",
        code_url=None,
    )
    try:
        wx = await wechat_v3.h5_create_order(
            wx_cfg,
            out_trade_no=out_trade_no,
            description=desc,
            amount_fen=charge_fen,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)[:800]) from e
    h5_url = str(wx.get("h5_url") or "")
    if not h5_url:
        raise HTTPException(status_code=502, detail=f"微信下单未返回 h5_url: {wx!r}")
    # WeChat H5 requires appending redirect_url when navigating to h5_url.
    try:
        sep = "&" if "?" in h5_url else "?"
        h5_url = h5_url + sep + "redirect_url=" + quote(redirect_url, safe="")
    except Exception:
        pass
    # store for ops/debug (reuse code_url field)
    try:
        db.pay_order_attach_code_url(out_trade_no, h5_url)
    except Exception:
        pass
    return PayH5Out(
        out_trade_no=out_trade_no,
        h5_url=h5_url,
        amount_fen=charge_fen,
        priced_amount_fen=priced_fen,
        amount_yuan_display=_fen_to_yuan_display(charge_fen),
        priced_amount_yuan_display=_fen_to_yuan_display(priced_fen),
        plan=plan_norm,
    )


@app.post("/api/billing/wechat/notify")
async def billing_wechat_notify(request: Request) -> JSONResponse:
    wx_cfg = resolve_wechat_pay()
    body_str = (await request.body()).decode("utf-8")
    headers = {str(k): str(v) for k, v in request.headers.items()}
    try:
        txn = await wechat_v3.parse_payment_notify(wx_cfg, headers=headers, body_str=body_str)
    except Exception as e:
        return JSONResponse(status_code=200, content={"code": "FAIL", "message": str(e)[:200]})
    if str(txn.get("trade_state") or "") != "SUCCESS":
        return JSONResponse(status_code=200, content={"code": "FAIL", "message": "trade_state not SUCCESS"})
    out_trade_no = str(txn.get("out_trade_no") or "")
    transaction_id = str(txn.get("transaction_id") or "")
    amount = txn.get("amount") if isinstance(txn.get("amount"), dict) else {}
    total = int((amount or {}).get("total") or 0)
    r = db.pay_order_try_fulfill_wechat(out_trade_no, transaction_id, total)
    if not r.get("ok"):
        return JSONResponse(status_code=200, content={"code": "FAIL", "message": str(r.get("error") or "fulfill_failed")})
    return JSONResponse(status_code=200, content={"code": "SUCCESS", "message": "成功"})


@app.post("/api/billing/wechat/query_and_fulfill")
async def billing_wechat_query_and_fulfill(body: dict, user_id: int = Depends(get_current_user_id)) -> dict:
    """
    兜底：当微信 notify 因网络/配置原因未到达时，前端可带 out_trade_no 主动查询并补发开通。
    - 仅允许查询自己的订单
    - 若 trade_state=SUCCESS 则尝试 fulfill（幂等）
    """
    wx_cfg = resolve_wechat_pay()
    otn = str((body or {}).get("out_trade_no") or "").strip()
    if not otn:
        raise HTTPException(status_code=400, detail="missing out_trade_no")

    row = db.pay_order_get_by_out_trade_no(otn)
    if not row:
        raise HTTPException(status_code=404, detail="order_not_found")
    if int(row.get("user_id") or 0) != int(user_id):
        raise HTTPException(status_code=403, detail="forbidden")
    if str(row.get("channel") or "") != "wechat":
        raise HTTPException(status_code=400, detail="not_wechat_order")

    if str(row.get("status") or "") == "paid":
        return {"ok": True, "status": "paid", "duplicate": True}

    try:
        txn = await wechat_v3.query_transaction_by_out_trade_no(wx_cfg, out_trade_no=otn)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)[:400]) from e

    trade_state = str(txn.get("trade_state") or "").strip()
    if trade_state != "SUCCESS":
        return {"ok": True, "status": "pending", "trade_state": trade_state}

    transaction_id = str(txn.get("transaction_id") or "").strip()
    amount = txn.get("amount") if isinstance(txn.get("amount"), dict) else {}
    total = int((amount or {}).get("total") or 0)
    r = db.pay_order_try_fulfill_wechat(otn, transaction_id, total)
    if not r.get("ok"):
        raise HTTPException(status_code=409, detail=str(r.get("error") or "fulfill_failed"))
    return {"ok": True, "status": "paid", "duplicate": bool(r.get("duplicate"))}


@app.post("/api/billing/alipay/wap", response_model=PayWapOut)
async def billing_alipay_wap(body: PayWapIn, user_id: int = Depends(get_current_user_id)) -> PayWapOut:
    ali_cfg = resolve_alipay()
    b = resolve_billing()
    if not bool(getattr(b, "billing_pay_alipay_enabled", True)):
        raise HTTPException(status_code=503, detail="支付宝支付已关闭")
    if not alipay_wap.alipay_configured(ali_cfg):
        raise HTTPException(
            status_code=503,
            detail="支付宝未配置：请设置 ALIPAY_APP_ID / 公钥 / 商户私钥 / NOTIFY_URL（及可选 RETURN_URL）",
        )

    plan_norm, priced_fen = _billing_normalize_plan(body.plan)
    if plan_norm == "vip_trial_99" and db.pay_user_has_paid_trial(int(user_id)):
        raise HTTPException(status_code=400, detail="体验卡每位用户限购 1 次，您已购买过。")

    charge_fen = _billing_charge_amount_fen(priced_fen)
    out_trade_no = db.pay_mk_out_trade_no(int(user_id))
    if plan_norm == "vip_month":
        subj = str(getattr(b, "vip_title_month", "AI24X VIP月会员") or "AI24X VIP月会员")
    elif plan_norm == "vip_year_999":
        subj = str(getattr(b, "vip_title_year", "AI24X VIP年会员") or "AI24X VIP年会员")
    elif plan_norm == "vip_trial_99":
        subj = str(getattr(b, "vip_title_trial", "AI24X VIP体验卡") or "AI24X VIP体验卡")
    elif plan_norm == "agent_growth":
        subj = str(getattr(b, "agent_title_growth", "伙伴计划 · 成长档") or "伙伴计划 · 成长档")
    else:
        subj = str(getattr(b, "agent_title_pro", "伙伴计划 · 专业档") or "伙伴计划 · 专业档")

    db.pay_order_create(
        int(user_id),
        out_trade_no=out_trade_no,
        plan=plan_norm,
        amount_fen=charge_fen,
        channel="alipay_wap",
        code_url=None,
    )

    try:
        pay_url = alipay_wap.build_wap_pay_url(
            ali_cfg,
            out_trade_no=out_trade_no,
            subject=subj,
            total_amount_yuan=_yuan_str_from_fen(charge_fen),
            return_url=(str(getattr(ali_cfg, "alipay_return_url", "") or "").strip() or None),
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)[:800]) from e

    db.pay_order_attach_code_url(out_trade_no, pay_url)
    return PayWapOut(
        out_trade_no=out_trade_no,
        pay_url=pay_url,
        amount_fen=charge_fen,
        priced_amount_fen=priced_fen,
        amount_yuan_display=_fen_to_yuan_display(charge_fen),
        priced_amount_yuan_display=_fen_to_yuan_display(priced_fen),
        plan=plan_norm,
    )


@app.post("/api/billing/alipay/notify")
async def billing_alipay_notify(request: Request) -> PlainTextResponse:
    ali_cfg = resolve_alipay()
    form = await request.form()
    data = {str(k): str(v) for k, v in form.items()}

    ok, _err = alipay_wap.verify_notify(ali_cfg, form=data)
    if not ok:
        return PlainTextResponse("fail", status_code=200)

    trade_status = (data.get("trade_status") or "").strip()
    if trade_status not in ("TRADE_SUCCESS", "TRADE_FINISHED"):
        return PlainTextResponse("success", status_code=200)

    out_trade_no = (data.get("out_trade_no") or "").strip()
    trade_no = (data.get("trade_no") or "").strip()
    total_amount = (data.get("total_amount") or "").strip()
    try:
        fen = int(round(float(total_amount) * 100.0))
    except Exception:
        return PlainTextResponse("fail", status_code=200)

    r = db.pay_order_try_fulfill_alipay(out_trade_no, trade_no, fen)
    if not r.get("ok"):
        if r.get("error") in ("order_already_paid",):
            return PlainTextResponse("success", status_code=200)
        return PlainTextResponse("fail", status_code=200)
    return PlainTextResponse("success", status_code=200)


@app.post("/api/billing/alipay/query_and_fulfill")
async def billing_alipay_query_and_fulfill(body: dict, user_id: int = Depends(get_current_user_id)) -> dict:
    """
    兜底：当支付宝 notify 因网络/配置原因未到达时，前端可带 out_trade_no 主动查询并补发开通。
    - 仅允许查询自己的订单
    - 若 trade_status=TRADE_SUCCESS/TRADE_FINISHED 则尝试 fulfill（幂等）
    """
    ali_cfg = resolve_alipay()
    otn = str((body or {}).get("out_trade_no") or "").strip()
    if not otn:
        raise HTTPException(status_code=400, detail="missing out_trade_no")

    row = db.pay_order_get_by_out_trade_no(otn)
    if not row:
        raise HTTPException(status_code=404, detail="order_not_found")
    if int(row.get("user_id") or 0) != int(user_id):
        raise HTTPException(status_code=403, detail="forbidden")
    if str(row.get("status") or "") == "paid":
        return {"ok": True, "status": "paid", "duplicate": True}

    try:
        txn = alipay_wap.query_trade(ali_cfg, out_trade_no=otn)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)[:400]) from e

    trade_status = str(txn.get("trade_status") or "").strip()
    if trade_status not in ("TRADE_SUCCESS", "TRADE_FINISHED"):
        return {"ok": True, "status": "pending", "trade_status": trade_status}

    trade_no = str(txn.get("trade_no") or "").strip()
    total_amount = str(txn.get("total_amount") or "").strip()
    try:
        fen = int(round(float(total_amount) * 100.0))
    except Exception:
        raise HTTPException(status_code=502, detail="invalid_total_amount")

    r = db.pay_order_try_fulfill_alipay(otn, trade_no, fen)
    if not r.get("ok"):
        raise HTTPException(status_code=409, detail=str(r.get("error") or "fulfill_failed"))
    return {"ok": True, "status": "paid", "duplicate": bool(r.get("duplicate"))}


@app.get("/api/admin/user/{user_id}/quota_status")
def admin_user_quota_status(user_id: int, _: bool = Depends(require_admin)) -> dict:
    """
    后台兜底：即使用户未出现在 admin 列表/未同步 contacts，也能按 user_id 查询 quota/VIP 状态。
    """
    try:
        db.downgrade_expired_vip_plan(int(user_id))
    except Exception:
        pass
    return {"ok": True, "user_id": int(user_id), "quota": db.get_quota_status(int(user_id))}

