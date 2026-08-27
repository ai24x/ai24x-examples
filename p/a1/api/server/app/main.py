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
import uuid
import asyncio
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
    # 2) clear stale signal caches (incl. legacy NTFS ADS host 'ths' from ths:XXXX keys)
    sd = _os.path.join(base, "data", "signal_cache")
    if _os.path.isdir(sd):
        for f in _glob.glob(_os.path.join(sd, "*.json")):
            try: _os.remove(f)
            except: pass
        # Windows ADS host file created by cache keys containing ':'
        try:
            ads_host = _os.path.join(sd, "ths")
            if _os.path.isfile(ads_host):
                _os.remove(ads_host)
        except: pass
_startup_clean()

import httpx
from fastapi import Cookie, Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response

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
from .billing_runtime import (
    auth_local_enabled,
    identity_configured,
    partner_payout_mode,
    resolve_alipay,
    resolve_billing,
    resolve_identity,
    resolve_wechat_pay,
)
from .sms_local import send_local_sms, send_local_sms_code, verify_and_consume_otp as verify_local_otp
from .auth import create_token, get_current_user_id, get_optional_user_id, parse_token
from . import auth_local
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
from . import providers as _prov
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


def _session_from_identity_payload(data: dict) -> LoginOut:
    """
    主站 identity 校验通过后，用本站 AI24X_JWT_SECRET 重签会话。

    避免生产上 core SECRET_KEY 与 a1 AI24X_JWT_SECRET 漂移时：
    登录成功 → /api/me Invalid token →「登录已失效」。
    """
    user = data.get("user") if isinstance(data, dict) else None
    if not isinstance(user, dict):
        user = {}
    uid = 0
    try:
        uid = int(user.get("id") or 0)
    except Exception:
        uid = 0
    if uid <= 0:
        # 兜底：从主站 token 读 sub（不验签；仅在 identity 刚返回后使用）
        try:
            from jose import jwt as _jwt

            raw = str((data or {}).get("token") or "")
            if raw:
                claims = _jwt.get_unverified_claims(raw)
                uid = int(claims.get("sub") or 0)
                if not user.get("email"):
                    user["email"] = claims.get("email") or ""
                if not user.get("phone"):
                    user["phone"] = claims.get("phone") or ""
        except Exception:
            uid = 0
    if uid <= 0:
        return LoginOut(token=str((data or {}).get("token") or ""), user=user)
    email = (user.get("email") or "") or None
    phone = (user.get("phone") or "") or None
    try:
        db.ensure_platform_user(uid, email, phone)
    except Exception:
        pass
    token = create_token(uid, email, phone)
    return LoginOut(
        token=token,
        user={"id": uid, "email": email or "", "phone": phone or ""},
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
    "1.000300",  # 沪深300
    "1.000688",  # 科创50
    "1.000852",  # 中证1000
    "0.000977",  # 浪潮信息（示例）
    "1.300059",  # 东方财富
    "0.300059",  # 东方财富（深）
    "0.300033",  # 同花顺（深市创业板）
    "1.600519",  # 贵州茅台
    "1.688981",  # 中芯国际
    "1.601398",  # 工商银行
    "0.300750",  # 宁德时代
    "0.002371",  # 北方华创（半导体设备，深市中小板）
    "1.688256",  # 寒武纪（AI芯片）
    "0.002463",  # 沪电股份（PCB）
    "0.300308",  # 中际旭创（光模块）
    "1.601899",  # 紫金矿业（有色）
}

# Anonymous extra trial quota (non-whitelist): allow a few self-selected queries per day.
# This complements the frontend guest counter but must be enforced server-side too.
_ANON_DAILY: dict[str, tuple[str, int]] = {}
_ANON_DAILY_MAX: int = 10


def _anon_day_key() -> str:
    return time.strftime("%Y-%m-%d", time.localtime())


def _anon_id_from_request(request: "Request") -> str:
    # 用真实客户端 IP（识别 X-Forwarded-For），避免 Nginx 反代后所有游客共享同一额度
    try:
        return _client_ip(request) or "unknown"
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

def _anon_priority(base_pri: str) -> str:
    """匿名/免费：仅 public 源；同花顺（盘中当日实时）提前，paid 排除。"""
    items = [x.strip() for x in (base_pri or "").split(",") if x.strip() and x.strip() != "paid"]
    if "ths" in items:
        items = ["ths"] + [x for x in items if x != "ths"]
    if not items:
        items = ["tencent", "eastmoney", "sina"]
    return ",".join(items)


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


def _scrub_user_facing_detail(msg: str) -> str:
    """Strip ops/env leakage from messages that may reach the browser."""
    s = (msg or "").strip()
    if not s:
        return "请求失败，请稍后重试。"
    s = re.sub(r"(?i)^value error[,:\s]+", "", s).strip() or s
    leak = re.search(
        r"(?i)(SMS_|AI24X_|ALIPAY_|TOKEN_|APP_ENV|identity_api|INTERNAL_KEY|NOTIFY_URL|"
        r"环境变量|\.env\b|X-SMS-|admin_browser_otp|admin_user_reset|sms_internal_key|"
        r"Identity|user_id=)",
        s,
    )
    if leak:
        return "服务暂不可用，请稍后再试。"
    return s


def _detail_from_upstream_body(err: object) -> str:
    """Normalize FastAPI/Pydantic error JSON into a short user-facing string."""
    if not isinstance(err, dict):
        return _scrub_user_facing_detail(str(err))
    detail = err.get("error")
    if detail is None:
        detail = err.get("detail")
    if detail is None:
        detail = err.get("message")
    if isinstance(detail, list) and detail:
        first = detail[0]
        if isinstance(first, dict):
            msg = str(first.get("msg") or first.get("message") or first.get("error") or "")
            return _scrub_user_facing_detail(msg)
        return _scrub_user_facing_detail(str(first))
    if isinstance(detail, dict):
        return _scrub_user_facing_detail(
            str(detail.get("msg") or detail.get("message") or detail.get("error") or "")
        )
    if detail is not None and str(detail).strip():
        return _scrub_user_facing_detail(str(detail))
    return "请求失败，请稍后重试。"


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
        raise HTTPException(status_code=503, detail="服务暂时不可用，请稍后重试") from e
    ct = (r.headers.get("content-type") or "").lower()
    if r.status_code >= 400:
        detail = r.text[:4000]
        if "json" in ct:
            try:
                err = r.json()
                detail = _detail_from_upstream_body(err)
            except Exception:
                detail = _scrub_user_facing_detail(detail)
        else:
            detail = _scrub_user_facing_detail(detail)
        raise HTTPException(status_code=r.status_code, detail=detail)
    if "json" not in ct:
        raise HTTPException(status_code=502, detail="服务响应异常，请稍后重试")
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
        raise HTTPException(status_code=503, detail="服务暂时不可用，请稍后重试") from e
    ct = (r.headers.get("content-type") or "").lower()
    if r.status_code >= 400:
        detail = r.text[:4000]
        if "json" in ct:
            try:
                err = r.json()
                detail = _detail_from_upstream_body(err)
            except Exception:
                detail = _scrub_user_facing_detail(detail)
        else:
            detail = _scrub_user_facing_detail(detail)
        raise HTTPException(status_code=r.status_code, detail=detail)
    if "json" not in ct:
        raise HTTPException(status_code=502, detail="服务响应异常，请稍后重试")
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
    try:
        from .bj_screener import start_bj_auto_scan
        start_bj_auto_scan()
    except Exception:
        logging.getLogger(__name__).exception("bj auto scan task start failed")


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
                detail="管理登录短信验证未开启，请先在系统配置中开启并登记白名单手机号。",
            )
        raise HTTPException(
            status_code=400,
            detail="管理登录短信验证未就绪，请先登记白名单手机号。",
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
    # 本站本地短信通道直发（tencent/106/juhe）
    code = admin_otp_generate()
    cfg = resolve_identity()
    ok, msg = send_local_sms_code(cfg=cfg, mobile=pnorm, code=code)
    if not ok:
        raise HTTPException(status_code=503, detail="短信服务暂不可用，请稍后再试。")
    admin_otp_put(pnorm, code, ttl)
    return {"ok": True, "ttl_s": ttl, "message": "验证码已发送。"}


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
        code = str(e)
        msg = {
            "missing out_trade_no": "请填写支付订单号",
            "order_not_found": "未找到该订单号，请到「订单支付」面板核对后再填",
            "order_not_paid": "该订单不是已支付状态，无法补单",
        }.get(code, code)
        raise HTTPException(status_code=400, detail=msg)


def _partner_cash_eligible(user_id: int) -> bool:
    """现金提现资格：全局模式=现金 且 该用户为签约城市合伙人。"""
    if partner_payout_mode() != "cash":
        return False
    try:
        cp = db.agent_city_partner_info(int(user_id))
        return bool(cp and cp.get("city_partner"))
    except Exception:
        return False


@app.get("/api/agent/overview")
def agent_overview(user_id: int = Depends(get_current_user_id)) -> dict:
    try:
        out = db.agent_commission_overview(int(user_id))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    cp = out.get("city_partner") or {}
    cash_pilot = partner_payout_mode() == "cash"
    out["payout_mode"] = partner_payout_mode()
    out["payout_enabled"] = bool(cash_pilot and cp.get("city_partner"))
    return out


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
    if not _partner_cash_eligible(int(user_id)):
        raise HTTPException(status_code=403, detail="当前为权益回馈模式：仅签约城市合伙人可配置收款与现金提现")
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
    if not _partner_cash_eligible(int(user_id)):
        raise HTTPException(status_code=403, detail="当前为权益回馈模式：仅签约城市合伙人可申请现金提现")
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
    Local (auth_local_enabled): write users.password_hash directly; otherwise calls the
    identity service internal admin endpoint and requires sms_internal_key configured.
    Body:
    - new_password: string (>=8)
    """
    npw = str(body.get("new_password") or "")
    if len(npw.strip()) < 8:
        raise HTTPException(status_code=400, detail="新密码至少 8 位")
    # P1: 数据库已独立——本地身份直接写 users.password_hash，不再依赖主站 identity
    if auth_local_enabled():
        try:
            db.admin_get_user(int(user_id))
        except ValueError:
            raise HTTPException(status_code=404, detail="用户不存在")
        db.set_user_password_hash(int(user_id), auth_local.hash_password(npw))
        return {"ok": True}
    cfg = resolve_identity()
    if not (cfg.sms_internal_key or "").strip():
        raise HTTPException(status_code=503, detail="改密服务暂未就绪，请稍后再试")
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
            raise HTTPException(status_code=404, detail="该用户尚未在主站建立账号，请先让用户完成一次注册或登录后再改密")
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
            and "尚未在主站建立账号" not in d
        ):
            raise HTTPException(
                status_code=404,
                detail="账号数据不一致，请确认主站与行情官指向同一套用户库后再改密。",
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
            raise HTTPException(status_code=403, detail="当前不可重置账号，请联系运维开启后再试。")

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


@app.get("/api/admin/invite/activity")
def admin_invite_activity_get(_: bool = Depends(require_admin)) -> dict:
    """裂变活动：全部活动配置 + 最近发放记录。"""
    return {
        "ok": True,
        "activities": db.invite_activity_get_all(),
        "rewards": db.activity_rewards_list(limit=100),
    }


@app.post("/api/admin/invite/activity")
def admin_invite_activity_save(body: dict, _: bool = Depends(require_admin)) -> dict:
    """新增/更新裂变活动配置。body: id(可选) enabled/name/description/start_at/end_at/
    target_invites/require_activated/reward_plan/reward_days/reward_weekly/reward_daily。"""
    try:
        item = db.invite_activity_save(body)
        return {"ok": True, "item": item}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)[:200])


@app.post("/api/admin/invite/activity/backfill")
def admin_invite_activity_backfill(body: dict, _: bool = Depends(require_admin)) -> dict:
    """补扫：把当前生效活动下「已达标但未发放」的邀请人自动补发。"""
    try:
        out = db.backfill_invite_activity_rewards(limit=int(body.get("limit") or 200))
        return {"ok": True, **out}
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
        "auth_local_enabled": "1" if bool(getattr(cfg, "auth_local_enabled", False)) else "0",
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


@app.get("/api/public/build_stamp")
def public_build_stamp() -> dict:
    """部署探针：确认公网 a-api 是否已加载登录重签等热修（无密钥）。"""
    return {
        "ok": True,
        "stamp": "20260727-resign-v2",
        "session_resign": True,
        "identity_jwt_env": "AI24X_IDENTITY_JWT_SECRET",
    }


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


@app.post("/api/admin/auth_import")
def admin_auth_import(body: dict, _: bool = Depends(require_admin)) -> dict:
    """
    导入主站 auth_users 切片（按 id 写入 password_hash）。
    body: { "rows": [ {"id":1,"phone":"...","email":"...","password_hash":"..."}, ... ] }
    """
    rows = body.get("rows")
    if not isinstance(rows, list) or not rows:
        raise HTTPException(status_code=400, detail="请提供 rows 数组")
    if len(rows) > 20000:
        raise HTTPException(status_code=400, detail="单次最多 20000 行")
    stats = auth_local.import_password_rows(rows)
    return {"ok": True, **stats}


@app.post("/api/admin/agent/city_partner")
def admin_agent_city_partner_set(body: dict, _: bool = Depends(require_admin)) -> dict:
    """后台签约/解约城市合伙人（区域 + 协议编号）。"""
    try:
        uid = int(body.get("user_id") or 0)
    except Exception:
        uid = 0
    if uid <= 0:
        raise HTTPException(status_code=400, detail="请提供有效的 user_id")
    raw = str(body.get("city_partner") if body.get("city_partner") is not None else "").strip().lower()
    enabled = raw in ("1", "true", "yes", "on")
    try:
        return db.admin_set_city_partner(
            user_id=uid,
            city_partner=enabled,
            city_region=str(body.get("city_region") or ""),
            city_agreement_no=str(body.get("city_agreement_no") or ""),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/admin/agent/city_partners")
def admin_agent_city_partners(q: str = "", limit: int = 50, offset: int = 0, _: bool = Depends(require_admin)) -> dict:
    """后台列出已签约城市合伙人。"""
    return db.admin_list_city_partners(q=q, limit=limit, offset=offset)


@app.post("/api/agent/city_partner/apply")
def agent_city_partner_apply(body: dict, user_id: int = Depends(get_current_user_id)) -> dict:
    """前台申请城市合伙人（需已支付成长档/合作伙伴，支付后人工审核）。"""
    try:
        return db.create_city_partner_application(
            user_id=user_id,
            region=str(body.get("region") or ""),
            contact_name=str(body.get("contact_name") or ""),
            id_no=str(body.get("id_no") or ""),
            phone=str(body.get("phone") or ""),
            note=str(body.get("note") or ""),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/agent/city_partner/application")
def agent_city_partner_application_get(user_id: int = Depends(get_current_user_id)) -> dict:
    """查询本人城市合伙人申请状态与签约状态。"""
    return {
        "ok": True,
        "application": db.get_city_partner_application_by_user(user_id),
        "partner": db.agent_city_partner_info(user_id),
    }


@app.get("/api/admin/agent/city_partner/applications")
def admin_agent_city_partner_applications(status: str = "", q: str = "", limit: int = 50, offset: int = 0, _: bool = Depends(require_admin)) -> dict:
    """后台列出城市合伙人申请（默认待审核优先）。"""
    return db.admin_list_city_partner_applications(status=status, q=q, limit=limit, offset=offset)


@app.post("/api/admin/agent/city_partner/review")
def admin_agent_city_partner_review(body: dict, _: bool = Depends(require_admin)) -> dict:
    """后台审核城市合伙人申请：通过=签约（可改区域/协议编号），驳回=记录原因。"""
    try:
        return db.admin_review_city_partner_application(
            application_id=int(body.get("application_id") or 0),
            approve=bool(body.get("approve")),
            admin_note=str(body.get("admin_note") or ""),
            region_override=str(body.get("region") or ""),
            agreement_no=str(body.get("agreement_no") or ""),
        )
    except (ValueError, TypeError) as e:
        raise HTTPException(status_code=400, detail=str(e))


_CONTRACT_FILE_TYPES = {
    ".pdf": (b"%PDF", "application/pdf"),
    ".jpg": (b"\xff\xd8\xff", "image/jpeg"),
    ".jpeg": (b"\xff\xd8\xff", "image/jpeg"),
    ".png": (b"\x89PNG\r\n\x1a\n", "image/png"),
}
_CONTRACT_FILE_MAX = 10 * 1024 * 1024  # 10MB


def _validate_contract_file(filename: str, content: bytes) -> tuple[str, str]:
    """校验合同附件：扩展名白名单 + magic bytes。返回 (ext, mime)。"""
    name = str(filename or "").strip()
    ext = (name.rsplit(".", 1)[-1].lower() if "." in name else "")
    ext = "." + ext if ext else ""
    if ext not in _CONTRACT_FILE_TYPES:
        raise ValueError("unsupported_file_type")
    magic, mime = _CONTRACT_FILE_TYPES[ext]
    if len(content) < len(magic) or not content.startswith(magic):
        raise ValueError("file_content_mismatch")
    return ext, mime


def _contract_file_response(row: dict) -> Response:
    """按 stored_name 安全构造下载响应（防目录穿越）。"""
    d = db.partner_contract_upload_dir()
    stored = str(row.get("stored_name") or "")
    if not stored or "/" in stored or "\\" in stored or ".." in stored:
        raise HTTPException(status_code=404, detail="file_not_found")
    path = _os.path.realpath(_os.path.join(d, stored))
    if not path.startswith(_os.path.realpath(d) + _os.sep):
        raise HTTPException(status_code=404, detail="file_not_found")
    if not _os.path.isfile(path):
        raise HTTPException(status_code=404, detail="file_not_found")
    fname = quote(str(row.get("original_name") or "download"))
    return FileResponse(path, media_type=str(row.get("mime") or "application/octet-stream"), filename=fname)


def _unlink_contract_file(stored_name: str) -> None:
    if not stored_name or "/" in stored_name or "\\" in stored_name or ".." in stored_name:
        return
    try:
        d = db.partner_contract_upload_dir()
        p = _os.path.realpath(_os.path.join(d, stored_name))
        if p.startswith(_os.path.realpath(d) + _os.sep) and _os.path.isfile(p):
            _os.remove(p)
    except Exception:
        pass


@app.post("/api/agent/city_partner/upload")
async def agent_city_partner_upload(
    request: Request,
    file: UploadFile = File(...),
    kind: str = Form("material"),
    note: str = Form(""),
    user_id: int = Depends(get_current_user_id),
) -> dict:
    """用户上传城市合伙人申请材料（身份证/营业执照/意向书/已签合同扫描件等）。"""
    _rate_limit(f"cp_upload:{user_id}", limit=20, window_s=3600)
    _rate_limit(f"cp_upload_ip:{_client_ip(request)}", limit=60, window_s=3600)
    try:
        content = await file.read()
        if not content:
            raise ValueError("empty_file")
        if len(content) > _CONTRACT_FILE_MAX:
            raise ValueError("file_too_large")
        ext, mime = _validate_contract_file(file.filename or "", content)
        app = db.get_city_partner_application_by_user(int(user_id))
        if not app:
            raise ValueError("application_required")
        if app.get("status") not in ("pending", "rejected"):
            raise ValueError("upload_not_allowed")
        existing = db.list_partner_contract_files(application_id=int(app["id"]), side="user")
        if len(existing) >= 4:
            raise ValueError("too_many_files")
        stored = uuid.uuid4().hex + ext
        d = db.partner_contract_upload_dir()
        with open(_os.path.join(d, stored), "wb") as f:
            f.write(content)
        r = db.save_partner_contract_file(
            application_id=int(app["id"]),
            user_id=int(user_id),
            side="user",
            kind=str(kind or "material").strip()[:32] or "material",
            original_name=str(file.filename or "")[:255],
            stored_name=stored,
            size_bytes=len(content),
            mime=mime,
            note=str(note or "").strip()[:300],
        )
        return r
    except ValueError as e:
        code = str(e)
        msg = {
            "unsupported_file_type": "仅支持 PDF/JPG/PNG 格式",
            "file_content_mismatch": "文件内容与扩展名不符，请上传有效文件",
            "file_too_large": "文件过大，请控制在 10MB 以内",
            "empty_file": "文件为空",
            "application_required": "请先提交城市合伙人申请",
            "upload_not_allowed": "当前状态无需上传材料",
            "too_many_files": "材料数量已达上限（4 份），请先删除旧材料",
        }.get(code, code)
        raise HTTPException(status_code=400, detail=msg)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)[:200])


@app.get("/api/agent/city_partner/attachments")
def agent_city_partner_attachments(user_id: int = Depends(get_current_user_id)) -> dict:
    """本人城市合伙人相关附件（材料 + 正式合同）。"""
    return {"ok": True, "items": db.list_partner_contract_files(user_id=int(user_id))}


@app.get("/api/agent/city_partner/attachments/{file_id}/download")
def agent_city_partner_attachment_download(file_id: int, user_id: int = Depends(get_current_user_id)) -> Response:
    row = db.get_partner_contract_file(int(file_id))
    if not row:
        raise HTTPException(status_code=404, detail="file_not_found")
    if int(row["user_id"]) != int(user_id):
        raise HTTPException(status_code=403, detail="forbidden")
    return _contract_file_response(row)


@app.post("/api/agent/city_partner/attachments/{file_id}/delete")
def agent_city_partner_attachment_delete(file_id: int, user_id: int = Depends(get_current_user_id)) -> dict:
    try:
        r = db.delete_partner_contract_file(int(file_id), user_id=int(user_id))
    except ValueError as e:
        code = str(e)
        msg = {"file_not_found": "文件不存在", "no_permission": "无权删除该文件"}.get(code, code)
        raise HTTPException(status_code=400, detail=msg)
    _unlink_contract_file(r.get("stored_name") or "")
    return {"ok": True}


@app.get("/api/admin/agent/city_partner/attachments")
def admin_agent_city_partner_attachments(application_id: int = 0, user_id: int = 0, _: bool = Depends(require_admin)) -> dict:
    return {"ok": True, "items": db.list_partner_contract_files(application_id=int(application_id), user_id=int(user_id))}


@app.post("/api/admin/agent/city_partner/upload")
async def admin_agent_city_partner_upload(
    file: UploadFile = File(...),
    application_id: int = Form(0),
    note: str = Form(""),
    _: bool = Depends(require_admin),
) -> dict:
    """后台上传/归档正式《城市合伙人合作协议》，自动站内通知用户。"""
    try:
        content = await file.read()
        if not content:
            raise ValueError("empty_file")
        if len(content) > _CONTRACT_FILE_MAX:
            raise ValueError("file_too_large")
        ext, mime = _validate_contract_file(file.filename or "", content)
        app_row = db.get_city_partner_application_by_id(int(application_id))
        if not app_row:
            raise ValueError("application_required")
        stored = uuid.uuid4().hex + ext
        d = db.partner_contract_upload_dir()
        with open(_os.path.join(d, stored), "wb") as f:
            f.write(content)
        r = db.save_partner_contract_file(
            application_id=int(application_id),
            user_id=int(app_row["user_id"]),
            side="admin",
            kind="agreement",
            original_name=str(file.filename or "")[:255],
            stored_name=stored,
            size_bytes=len(content),
            mime=mime,
            note=str(note or "").strip()[:300],
        )
        return r
    except ValueError as e:
        code = str(e)
        msg = {
            "unsupported_file_type": "仅支持 PDF/JPG/PNG 格式",
            "file_content_mismatch": "文件内容与扩展名不符，请上传有效文件",
            "file_too_large": "文件过大，请控制在 10MB 以内",
            "empty_file": "文件为空",
            "application_required": "申请不存在",
        }.get(code, code)
        raise HTTPException(status_code=400, detail=msg)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)[:200])


@app.get("/api/admin/agent/city_partner/attachments/{file_id}/download")
def admin_agent_city_partner_attachment_download(file_id: int, _: bool = Depends(require_admin)) -> Response:
    row = db.get_partner_contract_file(int(file_id))
    if not row:
        raise HTTPException(status_code=404, detail="file_not_found")
    return _contract_file_response(row)


@app.post("/api/admin/agent/city_partner/attachments/{file_id}/delete")
def admin_agent_city_partner_attachment_delete(file_id: int, _: bool = Depends(require_admin)) -> dict:
    try:
        r = db.delete_partner_contract_file(int(file_id), is_admin=True)
    except ValueError as e:
        code = str(e)
        msg = {"file_not_found": "文件不存在"}.get(code, code)
        raise HTTPException(status_code=400, detail=msg)
    _unlink_contract_file(r.get("stored_name") or "")
    return {"ok": True}


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
        "default_note": "正式：local=本站直发106；临时：tencent（移动签名未过）；勿用 juhe（备案中）；identity_proxy=经主站（主站关短信会挂）。",
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
    """本地直发（juhe/tencent/local）或转发主站 identity_proxy。"""
    _rate_limit(f"sms_ip:{_client_ip(request)}", 20, 900)
    _mob = str(body.mobile or "").strip()
    if _mob:
        _rate_limit(f"sms_phone:{_mob}", 6, 900)
    cfg = resolve_identity()
    _local_providers = ("local", "juhe", "tencent")
    if (cfg.sms_active_provider or "identity_proxy").strip().lower() in _local_providers:
        ok, msg, _dev = send_local_sms(
            cfg=cfg,
            mobile=body.mobile,
            purpose=(body.purpose or "login").strip() or "login",
        )
        if not ok:
            raise HTTPException(status_code=503, detail="短信服务暂不可用，请稍后再试。")
        return {"ok": True, "message": "验证码已发送。", "ttl_s": 300}
    if not (cfg.sms_internal_key or "").strip():
        # 主站若已设 SMS_INTERNAL_KEY，无此头会 403；先在本站明确提示运维配齐密钥
        raise HTTPException(
            status_code=503,
            detail="短信服务暂时不可用，请稍后再试。",
        )
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
def request_code(body: RequestCodeIn, request: Request) -> RequestCodeOut:
    _rate_limit(f"email_code_ip:{_client_ip(request)}", 10, 900)
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


def _session_from_local_user(u: db.User) -> LoginOut:
    token = create_token(int(u.id), u.email or None, u.phone)
    return LoginOut(
        token=token,
        user={"id": int(u.id), "email": u.email or "", "phone": u.phone or ""},
    )


@app.post("/api/auth/register", response_model=LoginOut)
def register(body: RegisterIn, request: Request) -> LoginOut:
    _rate_limit(f"reg_ip:{_client_ip(request)}", 10, 60)
    # P1：本地身份——不写主站 auth_users
    if auth_local_enabled():
        try:
            if body.phone:
                u = auth_local.register_phone(
                    phone=body.phone or "",
                    password=body.password,
                    sms_code=body.sms_code or "",
                )
            else:
                raise HTTPException(status_code=400, detail="本地身份模式请使用手机号注册")
        except HTTPException:
            raise
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e) or "注册失败") from e
        except Exception as e:
            logging.getLogger(__name__).exception("local register failed: %s", e)
            raise HTTPException(status_code=500, detail="注册暂时失败，请稍后重试。") from e
        return _session_from_local_user(u)

    if not identity_configured():
        raise HTTPException(status_code=503, detail="注册服务暂未就绪，请稍后再试")
    cfg = resolve_identity()
    local_sms = (cfg.sms_active_provider or "identity_proxy").strip().lower() in ("local", "juhe", "tencent")
    payload: dict = {"password": body.password}
    extra = None
    if body.phone:
        payload["phone"] = body.phone
        payload["sms_code"] = (body.sms_code or "").strip()
        if local_sms:
            # 本地已验码；带内部密钥让主站跳过短信开关与 OTP（账号仍写入主站 auth_users）
            from .sms_local import normalize_mobile as _nm

            if not verify_local_otp(_nm(body.phone), "register", body.sms_code or ""):
                raise HTTPException(status_code=400, detail="验证码错误或已过期，请重新获取验证码")
            _ikey = (cfg.sms_internal_key or "").strip()
            if not _ikey:
                raise HTTPException(status_code=503, detail="注册服务暂未就绪，请稍后再试")
            extra = {"X-SMS-Internal-Key": _ikey}
    else:
        payload["email"] = body.email
        payload["email_code"] = (body.email_code or "").strip()
    data = _identity_post("/v1/auth/register", payload, extra_headers=extra)
    return _session_from_identity_payload(data)


@app.post("/api/auth/login", response_model=LoginOut)
def login(body: LoginIn, request: Request) -> LoginOut:
    _rate_limit(f"login_ip:{_client_ip(request)}", 30, 60)
    _lp = str(body.phone or "").strip()
    if _lp:
        _rate_limit(f"login_phone:{_lp}", 10, 300)
    if auth_local_enabled() and (body.password or "").strip():
        if not body.phone and not body.email:
            raise HTTPException(status_code=400, detail="请填写手机号或邮箱")
        try:
            u = auth_local.login_password(
                phone=(body.phone or "").strip() or None,
                email=(body.email or "").strip() or None,
                password=(body.password or "").strip(),
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e) or "手机号或密码错误") from e
        return _session_from_local_user(u)

    if identity_configured() and (body.password or "").strip():
        if not body.phone and not body.email:
            raise HTTPException(status_code=400, detail="请填写手机号或邮箱")
        payload: dict = {"password": (body.password or "").strip()}
        if body.phone:
            payload["phone"] = (body.phone or "").strip()
        else:
            payload["email"] = (body.email or "").strip().lower()
        data = _identity_post("/v1/auth/login", payload)
        return _session_from_identity_payload(data)

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
def password_change(
    request: Request,
    body: PasswordChangeIn,
    user_id: int = Depends(get_current_user_id),
) -> LoginOut:
    if auth_local_enabled():
        try:
            u = auth_local.change_password(
                user_id=int(user_id),
                old_password=body.old_password,
                new_password=body.new_password,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e) or "改密失败") from e
        return _session_from_local_user(u)

    if not identity_configured():
        raise HTTPException(status_code=503, detail="服务暂未就绪，请稍后再试")
    auth = (request.headers.get("Authorization") or "").strip()
    if not auth:
        raise HTTPException(status_code=401, detail="需要登录")
    data = _identity_post(
        "/v1/auth/password/change",
        {"old_password": body.old_password, "new_password": body.new_password},
        extra_headers={"Authorization": auth},
    )
    return _session_from_identity_payload(data)


@app.post("/api/auth/password/reset", response_model=LoginOut)
def password_reset(body: PasswordResetIn, request: Request) -> LoginOut:
    _rate_limit(f"reset_ip:{_client_ip(request)}", 10, 60)
    _rp = str(body.phone or "").strip()
    if _rp:
        _rate_limit(f"reset_phone:{_rp}", 5, 300)
    if auth_local_enabled():
        if not body.phone:
            raise HTTPException(status_code=400, detail="本地身份模式请使用手机号重置密码")
        try:
            u = auth_local.reset_password_phone(
                phone=body.phone or "",
                sms_code=body.sms_code or "",
                new_password=body.new_password,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e) or "重置失败") from e
        return _session_from_local_user(u)

    if not identity_configured():
        raise HTTPException(status_code=503, detail="服务暂未就绪，请稍后再试")
    payload: dict = {"new_password": body.new_password}
    if body.phone:
        payload["phone"] = body.phone
        payload["sms_code"] = (body.sms_code or "").strip()
    else:
        payload["email"] = body.email
        payload["email_code"] = (body.email_code or "").strip()
    data = _identity_post("/v1/auth/password/reset", payload)
    return _session_from_identity_payload(data)


@app.post("/api/auth/phone/bind", response_model=LoginOut)
def bind_phone(request: Request, body: dict) -> LoginOut:
    """Bind phone to current user (requires bearer token + sms code)."""
    auth = (request.headers.get("Authorization") or "").strip()
    if not auth:
        raise HTTPException(status_code=401, detail="需要登录")
    phone = str(body.get("phone") or "").strip()
    code = str(body.get("sms_code") or "").strip()
    if not phone or not code:
        raise HTTPException(status_code=400, detail="请填写手机号与短信验证码")
    # P1: 数据库已独立——本地验 OTP 后直接写 users.phone
    if auth_local_enabled():
        from .sms_local import normalize_mobile as _nm
        mob = _nm(phone)
        if len(mob) != 11 or not mob.isdigit():
            raise HTTPException(status_code=400, detail="请填写 11 位手机号")
        if not verify_local_otp(mob, "bind", code):
            raise HTTPException(status_code=400, detail="验证码错误或已过期，请重新获取验证码")
        try:
            uid = int((parse_token(auth[7:] if auth[:7].lower() == "bearer " else auth)).get("sub") or 0)
        except (TypeError, ValueError):
            uid = 0
        if uid <= 0:
            raise HTTPException(status_code=401, detail="需要登录")
        exist = db.get_user_auth_by_phone(mob)
        if exist and int(exist.id) != uid:
            raise HTTPException(status_code=400, detail="该手机号已被其他账号绑定")
        try:
            db.set_user_phone(int(uid), mob)
        except ValueError as e:
            if str(e) == "user not found":
                raise HTTPException(status_code=404, detail="用户不存在")
            raise HTTPException(status_code=400, detail="该手机号已被其他账号绑定")
        u = db.get_user_auth_by_id(int(uid))
        if not u:
            raise HTTPException(status_code=404, detail="用户不存在")
        return _session_from_local_user(u)
    if not identity_configured():
        raise HTTPException(status_code=503, detail="服务暂未就绪，请稍后再试")
    data = _identity_post(
        "/v1/auth/phone/bind",
        {"phone": phone, "sms_code": code},
        extra_headers={"Authorization": auth},
    )
    return _session_from_identity_payload(data)


@app.post("/api/auth/email/bind", response_model=LoginOut)
def bind_email(request: Request, body: dict) -> LoginOut:
    """Bind email to current user (requires bearer token + email code)."""
    auth = (request.headers.get("Authorization") or "").strip()
    if not auth:
        raise HTTPException(status_code=401, detail="需要登录")
    email = str(body.get("email") or "").strip().lower()
    code = str(body.get("email_code") or "").strip()
    if not email or not code:
        raise HTTPException(status_code=400, detail="请填写邮箱与邮箱验证码")
    # P1: 数据库已独立——本地身份暂未接邮箱 OTP，非生产仅放行开发码
    if auth_local_enabled():
        if "@" not in email or len(email) < 6:
            raise HTTPException(status_code=400, detail="邮箱格式不正确")
        dev_ok = (str(settings.env or "").strip().lower() != "prod") and code == "1234"
        if not dev_ok:
            raise HTTPException(status_code=503, detail="邮箱绑定服务暂未就绪，请稍后再试")
        try:
            uid = int((parse_token(auth[7:] if auth[:7].lower() == "bearer " else auth)).get("sub") or 0)
        except (TypeError, ValueError):
            uid = 0
        if uid <= 0:
            raise HTTPException(status_code=401, detail="需要登录")
        exist = db.get_user_auth_by_email(email)
        if exist and int(exist.id) != uid:
            raise HTTPException(status_code=400, detail="该邮箱已被其他账号绑定")
        try:
            db.set_user_email(int(uid), email)
        except ValueError as e:
            if str(e) == "user not found":
                raise HTTPException(status_code=404, detail="用户不存在")
            raise HTTPException(status_code=400, detail="该邮箱已被其他账号绑定")
        u = db.get_user_auth_by_id(int(uid))
        if not u:
            raise HTTPException(status_code=404, detail="用户不存在")
        return _session_from_local_user(u)
    if not identity_configured():
        raise HTTPException(status_code=503, detail="服务暂未就绪，请稍后再试")
    data = _identity_post(
        "/v1/auth/email/bind",
        {"email": email, "email_code": code},
        extra_headers={"Authorization": auth},
    )
    return _session_from_identity_payload(data)


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


@app.get("/api/invite/activity")
def invite_activity_status(user_id: int = Depends(get_current_user_id)) -> dict:
    """当前裂变活动 + 我的进度（已激活邀请数 / 是否已领取奖励）。"""
    act = db.invite_activity_effective()
    if not act:
        return {"ok": True, "activity": None, "progress": None}
    progress = db.invite_activity_progress_for_user(int(user_id), act)
    return {"ok": True, "activity": act, "progress": progress}


# ============ 自选股 watchlist（登录态，跨设备同步） ============


@app.get("/api/watchlist")
def api_watchlist(user_id: int = Depends(get_current_user_id)) -> dict:
    _rate_limit(f"wl-list:{user_id}", 30)
    return db.watchlist_list(int(user_id))


@app.post("/api/watchlist")
async def api_watchlist_add(body: dict, user_id: int = Depends(get_current_user_id)) -> dict:
    _rate_limit(f"wl-add:{user_id}", 30)
    secid = str(body.get("secid") or "").strip()
    if not secid:
        raise HTTPException(status_code=400, detail="缺少 secid")
    code = str(body.get("code") or "").strip()
    name = str(body.get("name") or "").strip()
    if not code:
        code = _wl_code_from_secid(secid)
    if _wl_name_is_missing(name, code) and code:
        try:
            name = await _wl_resolve_name(secid, code)
        except Exception:
            name = ""
    if _wl_name_is_missing(name, code):
        name = ""
    return db.watchlist_add(
        int(user_id),
        secid,
        code,
        name,
        str(body.get("note") or ""),
    )


@app.post("/api/watchlist/remove")
async def api_watchlist_remove(body: dict, user_id: int = Depends(get_current_user_id)) -> dict:
    _rate_limit(f"wl-rm:{user_id}", 60)
    return db.watchlist_remove(int(user_id), str(body.get("secid") or ""))


# 自选评分榜结果缓存：同用户、同自选池、5 分钟内重复进入/刷新直接秒出
# （K 线内存缓存仅 30s，冷启动需逐票拉日线较慢，故加一层评分结果缓存）
_WL_SCORE_CACHE: dict[tuple, tuple[float, dict]] = {}
_WL_SCORE_TTL_S = 300.0
_WL_NAME_CACHE: dict[str, tuple[float, str]] = {}
_WL_NAME_TTL_S = 3600.0


def _wl_code_from_secid(secid: str) -> str:
    m = re.search(r"(\d{6})$", str(secid or "").strip())
    return m.group(1) if m else ""


def _wl_normalize_ident(secid: str, code: str, name: str) -> tuple[str, str]:
    code = str(code or "").strip()
    name = str(name or "").strip()
    if not code:
        code = _wl_code_from_secid(secid)
    return code, name


def _wl_name_is_missing(name: str, code: str) -> bool:
    """自选名称是否缺失/占位（空、纯代码、secid 形态）——此时应触发 suggest 补名。"""
    name = str(name or "").strip()
    if not name:
        return True
    code = str(code or "").strip()
    if code and name == code:
        return True
    return bool(re.fullmatch(r"\d{4,8}", name))


_WL_NAME_SEM = None  # asyncio.Semaphore，懒初始化（评分榜多只缺名并发补名时限制上游并发）


async def _wl_resolve_name(secid: str, code: str) -> str:
    """按代码解析标的名称（suggest 补名，带缓存与超时；仅用于自选缺名回填）。"""
    import asyncio
    secid = str(secid or "").strip()
    code = str(code or "").strip()
    if not code:
        code = _wl_code_from_secid(secid)
    if not code:
        return ""
    now = time.time()
    hit = _WL_NAME_CACHE.get(secid) or _WL_NAME_CACHE.get(code)
    if hit and now - hit[0] < _WL_NAME_TTL_S:
        return hit[1]

    async def _lookup() -> str:
        from .providers import fetch_em_suggest, fetch_ths_suggest
        for payload in (await fetch_em_suggest(code), await fetch_ths_suggest(code)):
            try:
                arr = ((payload or {}).get("QuotationCodeTable") or {}).get("Data") or []
                for it in arr:
                    if not isinstance(it, dict):
                        continue
                    if str(it.get("Code") or "") == code and str(it.get("Name") or "").strip():
                        return str(it["Name"]).strip()
            except Exception:
                continue
        return ""

    global _WL_NAME_SEM
    if _WL_NAME_SEM is None:
        _WL_NAME_SEM = asyncio.Semaphore(2)
    try:
        async with _WL_NAME_SEM:
            name = await asyncio.wait_for(_lookup(), timeout=4.0)
    except Exception:
        name = ""
    if name:
        if len(_WL_NAME_CACHE) > 1024:
            _WL_NAME_CACHE.clear()
        _WL_NAME_CACHE[secid] = (time.time(), name)
        _WL_NAME_CACHE[code] = (time.time(), name)
    return name


async def _wl_fetch_snapshot(secid: str, code: str, name: str, variant: str, priority_override: str, allow_paid: bool) -> dict:
    """单票技术指标快照：拉日线120根 → 技术面量化（与自选评分榜同口径，不含大盘调整）。"""
    from .scoring import score_candles
    from .signals import candles_from_tencent_like_pack

    secid = str(secid or "").strip()
    code, name = _wl_normalize_ident(secid, code, name)
    if _wl_name_is_missing(name, code):
        name = await _wl_resolve_name(secid, code)
    base = {"secid": secid, "code": code, "name": name}
    try:
        payload = await fetch_tx_kline(secid, "day", count=120, timeout=6.0, variant=variant, priority_override=priority_override, allow_paid=allow_paid)
    except Exception as e:
        base["error"] = "fetch:%s" % type(e).__name__
        return base
    if not isinstance(payload, dict) or int(payload.get("code") or 0) != 0:
        base["error"] = str((payload or {}).get("msg") or "kline failed")
        return base
    data = payload.get("data")
    if not isinstance(data, dict) or not data:
        base["error"] = "empty data"
        return base
    pack = next(iter(data.values()))
    candles = candles_from_tencent_like_pack(pack, period="day")
    if len(candles) < 60:
        base["error"] = "insufficient history"
        return base
    res = score_candles(candles, name=base["name"] or base["code"])
    base.update(res)
    return base


async def _wl_market_env(variant: str, priority_override: str, allow_paid: bool) -> dict:
    """大盘环境（上证指数）：MACD 首根红柱天数 + 均线信号，作为各标的统一加减分项。"""
    from .scoring import _red_days, _ma, _slope_ratio
    from .signals import _compute_macd_arrays, candles_from_tencent_like_pack

    try:
        payload = await fetch_tx_kline("1.000001", "day", count=120, timeout=6.0, variant=variant, priority_override=priority_override, allow_paid=allow_paid)
        if not isinstance(payload, dict) or int(payload.get("code") or 0) != 0:
            return {}
        data = payload.get("data")
        if not isinstance(data, dict) or not data:
            return {}
        pack = next(iter(data.values()))
        candles = candles_from_tencent_like_pack(pack, period="day")
        if len(candles) < 60:
            return {}
        closes = [float(c.close) for c in candles]
        dif, dea, bar, golden, dead = _compute_macd_arrays(closes)
        ma5 = _ma(closes, 5)
        ma10 = _ma(closes, 10)
        ma20 = _ma(closes, 20)
        rd = _red_days(bar)
        cur = closes[-1]
        macd_red = rd >= 1
        ma_bull = ma5[-1] > ma10[-1] > ma20[-1]
        ma20_up = _slope_ratio(ma20, 5) > 0.001
        above_ma20 = cur > ma20[-1]
        weak = (not above_ma20) and (not ma20_up)
        pts = 0.0
        if macd_red:
            pts += 3.0
        if ma_bull:
            pts += 3.0
        if above_ma20 and ma20_up:
            pts += 2.0
        if weak:
            pts -= 3.0
        tags = []
        tags.append("大盘MACD翻红·第%d天" % rd if macd_red else "大盘MACD绿柱")
        if ma_bull:
            tags.append("大盘均线多头")
        elif above_ma20:
            tags.append("大盘站上MA20")
        else:
            tags.append("大盘跌破MA20")
        return {
            "secid": "1.000001",
            "name": "上证指数",
            "pts": round(max(-3.0, min(8.0, pts)), 1),
            "red_days": rd,
            "ma_bull": bool(ma_bull),
            "above_ma20": bool(above_ma20),
            "weak": bool(weak),
            "tags": tags,
            "latest_time": str(candles[-1].time),
        }
    except Exception:
        return {}


@app.get("/api/watchlist/scores")
async def api_watchlist_scores(
    request: Request,
    user_id: int = Depends(get_current_user_id),
) -> dict:
    """
    自选评分榜：对自选池逐票取日线 → 技术面评分 → 综合分降序。
    扣次：复用自然日同票去重，同日重复刷新不重复扣。
    """
    _rate_limit(f"wl-scores:{user_id}", 6)
    wl = db.watchlist_list(int(user_id))
    items = wl.get("items") or []
    db.downgrade_expired_vip_plan(int(user_id))
    quota = db.get_quota_status(int(user_id))
    plan = str(quota.get("plan") or "anon").strip().lower()
    is_vip = plan not in ("", "free", "anon")
    caps = db.watchlist_score_caps()
    max_n = int(caps.get("vip") if is_vip else caps.get("free")) or 0
    vip_cap = int(caps.get("vip") or 0)
    if not items:
        return {"ok": True, "items": [], "count": 0, "updated_at": int(time.time()),
                "is_vip": is_vip, "score_max": max_n, "vip_cap": vip_cap,
                "watchlist_total": 0, "truncated": False}
    truncated = False
    watchlist_total = len(items)
    if max_n > 0 and watchlist_total > max_n:
        items = items[:max_n]
        truncated = True

    _ckey = (int(user_id), int(time.time() // _WL_SCORE_TTL_S), int(max_n),
             ",".join(sorted(str(it.get("secid") or "") for it in items)))
    _chit = _WL_SCORE_CACHE.get(_ckey)
    if _chit is not None and time.time() - _chit[0] < _WL_SCORE_TTL_S:
        return _chit[1]
    md = market_data_status()
    base_pri = str((md.get("paid") or {}).get("priority") or "").strip().lower()
    if not base_pri:
        base_pri = "tencent,eastmoney,sina,paid"
    vip_only = bool((md.get("paid") or {}).get("vip_only"))
    allow_paid = bool(is_vip or not vip_only)
    priority_override = base_pri if allow_paid else ",".join(
        [x for x in base_pri.split(",") if x.strip() and x.strip() != "paid"]
    )
    variant = "vip" if is_vip else "free"

    import asyncio

    async def _score_one(it: dict) -> dict:
        secid = str(it.get("secid") or "")
        base = await _wl_fetch_snapshot(secid, it.get("code"), it.get("name"), variant, priority_override, allow_paid)
        if str(base.get("code") or "") != str(it.get("code") or "") or str(base.get("name") or "") != str(it.get("name") or ""):
            try:
                db.watchlist_patch_ident(int(user_id), secid, str(base.get("code") or ""), str(base.get("name") or ""))
            except Exception:
                pass
        base["created_at"] = int(it.get("created_at") or 0)
        if not base.get("error"):
            try:
                db.consume_quota(
                    int(user_id),
                    secid,
                    "day",
                    "wl:%s:day:%d" % (secid, int(time.time() // 86400)),
                    ok=True,
                )
            except Exception:
                pass
        return base

    async def _fetch_market() -> dict:
        return await _wl_market_env(variant, priority_override, allow_paid)

    # 整体 12 秒上限：外部数据源偶发慢/挂时，先出已算完的标的，其余标记超时，避免整榜一直转圈
    fs = [asyncio.ensure_future(_score_one(it)) for it in items]
    mkt_task = asyncio.ensure_future(_fetch_market())
    fs.append(mkt_task)
    done, pending = await asyncio.wait(fs, timeout=12.0)
    for t in pending:
        t.cancel()
    scored = []
    for i, t in enumerate(fs):
        if t is mkt_task:
            continue
        it = items[i]
        if not t.cancelled() and t in done:
            try:
                r = t.result()
            except Exception:
                r = None
            if r:
                scored.append(r)
            continue
        scored.append({
            "secid": str(it.get("secid") or ""),
            "code": _wl_code_from_secid(str(it.get("secid") or "")) or str(it.get("code") or ""),
            "name": str(it.get("name") or ""),
            "created_at": int(it.get("created_at") or 0),
            "error": "fetch:timeout",
        })
    market = {}
    if not mkt_task.cancelled() and mkt_task in done:
        try:
            market = mkt_task.result() or {}
        except Exception:
            market = {}
    mpts = float(market.get("pts") or 0.0)
    for sc in scored:
        if sc.get("error"):
            continue
        f = sc.setdefault("factors", {})
        f["market"] = mpts
        sc["score"] = round(max(0.0, min(100.0, float(sc.get("score") or 0.0) + mpts)), 1)
        if market.get("weak"):
            rks = sc.setdefault("risks", [])
            if "大盘弱势" not in rks:
                rks.append("大盘弱势")
    scored.sort(key=lambda x: float(x.get("score") or -1), reverse=True)
    result = {"ok": True, "items": scored, "count": len(scored), "updated_at": int(time.time()),
              "market": market if market.get("name") else None,
              "is_vip": is_vip, "score_max": max_n, "vip_cap": vip_cap,
              "watchlist_total": watchlist_total, "truncated": truncated}
    if len(_WL_SCORE_CACHE) > 256:
        _now = time.time()
        for _k in [k for k, v in _WL_SCORE_CACHE.items() if _now - v[0] > _WL_SCORE_TTL_S * 2]:
            _WL_SCORE_CACHE.pop(_k, None)
    _WL_SCORE_CACHE[_ckey] = (time.time(), result)
    return result


@app.get("/api/quote/snapshot")
async def api_quote_snapshot(
    secid: str = "",
    code: str = "",
    name: str = "",
    request: "Request" = None,  # type: ignore[assignment]
    user_id: Optional[int] = Depends(get_optional_user_id),
) -> dict:
    """单票「技术指标快照」：综合分/关键信号/风险 + 大盘环境，与自选评分榜同口径（仅统计，非推荐）。

    匿名策略与 /api/kline 一致：白名单（含 ths: 板块）可直接查；非白名单需在游客每日试用额度内。
    """
    secid = str(secid or "").strip()
    if not secid:
        raise HTTPException(status_code=400, detail="missing secid")
    if user_id is None:
        secid0 = str(secid).strip()
        is_ths_plate = secid0.lower().startswith("ths:")
        if request is not None:
            _rate_limit(f"quote-snap-ip:{_client_ip(request)}", 10)
        md = market_data_status()
        base_pri = str((md.get("paid") or {}).get("priority") or "").strip().lower()
        if not base_pri:
            base_pri = "tencent,eastmoney,sina,paid"
        if is_ths_plate:
            priority_override = base_pri
            allow_paid = True
        else:
            priority_override = _anon_priority(base_pri)
            allow_paid = False
        if secid0 not in _ANON_KLINE_WHITELIST and not is_ths_plate:
            if request is None or not _anon_daily_can_consume(request):
                return {"ok": False, "error": "游客今日体验次数已用完，请登录继续", "secid": secid, "code": str(code or ""), "name": str(name or "")}
        snap = await _wl_fetch_snapshot(secid, code, name, "anon", priority_override, allow_paid)
        if snap.get("error"):
            return {"ok": False, "error": snap["error"], "secid": secid, "code": str(code or ""), "name": str(name or "")}
        mkt = await _wl_market_env("anon", priority_override, allow_paid)
        snap["market"] = mkt if mkt.get("name") else None
        snap["is_vip"] = False
        return {"ok": True, **snap}
    _rate_limit(f"quote-snap:{user_id}", 10)
    db.downgrade_expired_vip_plan(int(user_id))
    quota = db.get_quota_status(int(user_id))
    plan = str(quota.get("plan") or "anon").strip().lower()
    is_vip = plan not in ("", "free", "anon")
    md = market_data_status()
    base_pri = str((md.get("paid") or {}).get("priority") or "").strip().lower()
    if not base_pri:
        base_pri = "tencent,eastmoney,sina,paid"
    vip_only = bool((md.get("paid") or {}).get("vip_only"))
    allow_paid = bool(is_vip or not vip_only)
    priority_override = base_pri if allow_paid else ",".join(
        [x for x in base_pri.split(",") if x.strip() and x.strip() != "paid"]
    )
    variant = "vip" if is_vip else "free"
    snap = await _wl_fetch_snapshot(secid, code, name, variant, priority_override, allow_paid)
    if snap.get("error"):
        return {"ok": False, "error": snap["error"], "secid": secid, "code": str(code or ""), "name": str(name or "")}
    try:
        db.consume_quota(int(user_id), secid, "day", "wl:%s:day:%d" % (secid, int(time.time() // 86400)), ok=True)
    except Exception:
        pass
    mkt = await _wl_market_env(variant, priority_override, allow_paid)
    snap["market"] = mkt if mkt.get("name") else None
    snap["is_vip"] = is_vip
    return {"ok": True, **snap}


async def _bj_ensure_scan_or_fast(
    user_id: int, market: str, force: bool = False,
    cfg_override: dict | None = None, boards_only: bool = False,
    column: str = "",
) -> dict | None:
    """掘金防 504：能秒回（缓存/归档）返回 None 走正常同步路径；否则后台启动扫描并返回 scanning 提示。
    绝不在 HTTP 请求内同步等待完整扫描（生产 nginx 60s 网关超时会 504）。
    """
    from .bj_screener import (
        scan_progress, run_scan_dedup, mark_scan_failed,
        _RUNNING_SCAN, _SCAN_CACHE, _BOARDS_CACHE,
        _today_off_market, _market_closed, _latest_history, _reattach_ths,
    )
    p = scan_progress(market)
    if p.get("running") or (_RUNNING_SCAN.get(market) is not None and not _RUNNING_SCAN[market].done()):
        return {"ok": True, "scanning": True, "msg": "今日掘金数据正在生成中，请稍候…"}
    today8 = time.strftime("%Y%m%d", time.localtime())
    full_key = f"{market}-scan:{today8}"
    boards_key = f"{market}-boards:{today8}"
    if not force:
        hit = _SCAN_CACHE.get(full_key)
        if hit and time.time() - hit[0] < 6 * 3600:
            return None
        if boards_only:
            bh = _BOARDS_CACHE.get(boards_key)
            if bh and time.time() - bh[0] < 6 * 3600:
                return None
        # 非交易日或盘中未收盘：run_scan 会秒回最近归档，不触发长扫
        if _today_off_market() or not _market_closed():
            if _latest_history(market):
                return None
        # 交易日已收盘但内存无今日扫描缓存：
        # - 若磁盘已有「今日」归档 → 不算 missing，交回 run_scan 正常加载（避免重启后误报「今日尚未生成」）
        # - 仅当最近归档早于今日 → 标记 today_missing，绝不在进页时自动开扫（防"进页就扫描"）
        _stale = _latest_history(market)
        if _stale:
            _arch_day = str(_stale.get("date") or _stale.get("asof") or "").replace("-", "")[:8]
            if _arch_day == today8:
                return None
            _out = dict(_stale)
            _out["cached"] = True
            _out["stale"] = True
            _out["today_missing"] = True
            _out["stale_from"] = _stale.get("asof") or _stale.get("date") or ""
            _out["market_code"] = market
            _out["date"] = _stale.get("date") or _stale.get("asof") or ""
            _out = _reattach_ths(_out)
            if boards_only:
                # 非 VIP 板块视图：剥离个股分析（重建对象防污染共享缓存）
                _out = dict(_out)
                _out["vip_required"] = True
                _out.pop("picks", None)
                _out.pop("runners", None)
                _out.pop("prev_track", None)
                _out.pop("prev_date", None)
                _out["board_rank"] = [dict(_b) for _b in (_out.get("board_rank") or []) if isinstance(_b, dict)]
                for _br in _out["board_rank"]:
                    _br.pop("mainline", None)
                _out["mainlines"] = []
            return _out

    async def _bg() -> None:
        try:
            await run_scan_dedup(int(user_id), force=True, cfg_override=cfg_override,
                                 boards_only=boards_only, market=market, column=column)
        except Exception as e:
            try:
                mark_scan_failed(market, f"\u626b\u63cf\u5931\u8d25: {type(e).__name__}: {str(e)[:120]}")
            except Exception:
                pass

    try:
        asyncio.create_task(_bg())
    except Exception:
        pass
    return {"ok": True, "scanning": True, "msg": "正在生成今日掘金数据（约1-2分钟），请稍候…"}


@app.get("/api/bj/screener")
async def api_bj_screener(
    request: Request,
    force: int = 0,
    top_n: int = 5,
    mcap_min: float = 0,
    mcap_max: float = 0,
    amount_min: float = 0,
    pos_max: float = 0,
    cap: int = 0,
    market: str = "bj",
    user_id: int = Depends(get_current_user_id),
) -> dict:
    """掘金（VIP 专属）：北证全市场 / 沪深京全市场扫描 -> 板块先行+主线反推 -> 主推 3 只。

    market=hs 沪深主线、kc 科创主线（板块先行两阶段）；market=bj 北证主线、bj_all 北证全市场（纯评分）。
    每栏主推 2 只（王者1⭐ + 重点1），宁缺毋滥；小市值底部异动进备选池。
    算法全部在服务端执行（bj_screener.py），前端仅展示接口返回；非 VIP 一律 403。
    结果按自然日缓存，force=1 强制重扫。不扣查次（VIP 权益功能），仅做频率限制。
    """
    market = str(market or "bj").strip().lower()
    macd_mode = market == "macd"
    pb_mode = market == "pb"
    low10_mode = market == "low10"
    if market not in ("bj", "all", "hs", "kc", "bj_all", "macd", "pb", "low10"):
        market = "bj"
    scan_market = "all" if (macd_mode or low10_mode) else ("hs" if pb_mode else market)
    _rate_limit(f"bj-screener:{user_id}", 24)
    try:
        _auth_ip_rate_limit(request)
    except Exception:
        pass
    db.downgrade_expired_vip_plan(int(user_id))
    quota = db.get_quota_status(int(user_id))
    plan = str(quota.get("plan") or "anon").strip().lower()
    is_vip = plan not in ("", "free", "anon")
    from .bj_screener import run_scan_dedup, macd_view, pb_view, low10_view, _backfill_leader_quotes
    _col = "low10" if low10_mode else ("pb" if pb_mode else ("macd" if macd_mode else ""))
    if not is_vip:
        # 非 VIP：开放“异动板块”视图（复用当日缓存或轻量扫描），个股分析保持 VIP 专属
        early = await _bj_ensure_scan_or_fast(int(user_id), scan_market, force=False, boards_only=True, column=_col)
        if early is not None:
            return await _backfill_leader_quotes(early)
        try:
            out = await run_scan_dedup(int(user_id), force=False, cfg_override=None,
                                       boards_only=True, market=scan_market, column=_col)
        except HTTPException:
            raise
        except Exception as e:
            from .bj_screener import mark_scan_failed
            mark_scan_failed(scan_market, f"\u626b\u63cf\u5931\u8d25: {type(e).__name__}")
            return {"ok": False, "error": "scan_failed", "message": f"{type(e).__name__}: {str(e)[:160]}"}
        # 统一剥离（路由级收敛）：无论命中哪条缓存路径，非 VIP 只保留板块排行与市场概览
        # 注意重建 dict/list，不原地修改共享缓存对象（防污染 _SCAN_CACHE/_BOARDS_CACHE）
        if isinstance(out, dict):
            out = dict(out)
            out["vip_required"] = True
            out.pop("picks", None)
            out.pop("runners", None)
            out.pop("macd_reds", None)
            out.pop("prev_track", None)
            out.pop("prev_date", None)
            out["board_rank"] = [dict(_b) for _b in (out.get("board_rank") or []) if isinstance(_b, dict)]
            for _br in out["board_rank"]:
                _br.pop("mainline", None)
            out["mainlines"] = []
        return await _backfill_leader_quotes(out)

    cfg_override: dict = {}
    if mcap_min > 0:
        cfg_override["mcapMin"] = float(mcap_min)
    if mcap_max > 0:
        cfg_override["mcapMax"] = float(mcap_max)
    if amount_min > 0:
        cfg_override["amountMin"] = float(amount_min)
    if pos_max > 0:
        cfg_override["posMax"] = float(pos_max)
    if top_n > 0:
        cfg_override["topN"] = int(max(3, min(5, top_n)))
    if cap > 0:
        cfg_override["cap"] = int(max(30, min(120, cap)))
    early = await _bj_ensure_scan_or_fast(int(user_id), scan_market, force=bool(force),
                                          cfg_override=cfg_override or None, column=_col)
    if early is not None:
        _early = macd_view(early) if macd_mode else (
            pb_view(early) if pb_mode else (low10_view(early) if low10_mode else early))
        return await _backfill_leader_quotes(_early)

    try:
        out = await run_scan_dedup(int(user_id), force=bool(force), cfg_override=cfg_override or None,
                                   market=scan_market, column=_col)
        _out = macd_view(out) if macd_mode else (
            pb_view(out) if pb_mode else (low10_view(out) if low10_mode else out))
        return await _backfill_leader_quotes(_out)
    except HTTPException:
        raise
    except Exception as e:
        from .bj_screener import mark_scan_failed
        mark_scan_failed(scan_market, f"\u626b\u63cf\u5931\u8d25: {type(e).__name__}")
        return {"ok": False, "error": "scan_failed", "message": f"{type(e).__name__}: {str(e)[:160]}"}


@app.get("/api/bj/screener/start")
async def api_bj_screener_start(
    request: Request,
    market: str = "bj",
    user_id: int = Depends(get_current_user_id),
) -> dict:
    """掘金异步重扫启动：立即返回，后台任务执行扫描（避免 nginx 60s 网关超时 504）。

    用法：GET /api/bj/screener/start?market=bj → {ok, running} → 前端轮询 /api/bj/screener/progress
    → running=false 后 GET /api/bj/screener?market=bj（命中缓存返回最新结果）。
    """
    market = str(market or "bj").strip().lower()
    macd_mode = market == "macd"
    pb_mode = market == "pb"
    if market not in ("bj", "all", "hs", "kc", "bj_all", "macd", "pb"):
        market = "bj"
    scan_market = "all" if macd_mode else ("hs" if pb_mode else market)
    _rate_limit(f"bj-screener:{user_id}", 24)
    try:
        _auth_ip_rate_limit(request)
    except Exception:
        pass
    db.downgrade_expired_vip_plan(int(user_id))
    quota = db.get_quota_status(int(user_id))
    plan = str(quota.get("plan") or "anon").strip().lower()
    is_vip = plan not in ("", "free", "anon")
    if not is_vip:
        return {"ok": False, "error": "vip_required", "message": "掘金扫描为 VIP 专属，请先开通 VIP。"}
    from .bj_screener import scan_progress, run_scan_dedup, mark_scan_failed, _RUNNING_SCAN
    _col = "pb" if pb_mode else ("macd" if macd_mode else "")
    p = scan_progress(scan_market)
    if p.get("running") or (_RUNNING_SCAN.get(scan_market) is not None and not _RUNNING_SCAN[scan_market].done()):
        return {"ok": True, "running": True, "msg": "扫描进行中，请稍候…"}

    async def _bg_scan() -> None:
        try:
            await run_scan_dedup(int(user_id), force=True, market=scan_market, column=_col)
        except Exception as e:
            try:
                mark_scan_failed(scan_market, f"扫描失败: {type(e).__name__}: {str(e)[:120]}")
            except Exception:
                pass

    try:
        asyncio.create_task(_bg_scan())
    except Exception as e:
        return {"ok": False, "error": "start_failed", "message": f"扫描启动失败，请重试：{type(e).__name__}"}
    return {"ok": True, "running": True, "msg": "扫描已启动"}


@app.get("/api/bj/screener/partial")
async def api_bj_screener_partial(request: Request, market: str = "bj", user_id: int = Depends(get_current_user_id)) -> dict:
    market = str(market or "bj").strip().lower()
    if market == "macd":
        market = "all"
    if market == "pb":
        market = "hs"
    if market not in ("bj", "all", "hs", "kc", "bj_all"):
        market = "bj"
    from .bj_screener import get_partial_scan
    return get_partial_scan(market) or {"ok": True, "partial": False, "stage": "none", "market_code": market}

@app.get("/api/bj/screener/progress")
async def api_bj_screener_progress(
    request: Request,
    market: str = "bj",
    user_id: int = Depends(get_current_user_id),
) -> dict:
    """掘金扫描进度（前端进度条轮询）；不扣查次，仅做频率限制。"""
    market = str(market or "bj").strip().lower()
    if market == "macd":
        market = "all"
    if market == "pb":
        market = "hs"
    if market not in ("bj", "all", "hs", "kc", "bj_all"):
        market = "bj"
    try:
        _rate_limit(f"bj-screener-progress:{user_id}", 90)
        _auth_ip_rate_limit(request)
    except Exception:
        pass
    from .bj_screener import scan_progress
    return scan_progress(market)


@app.get("/api/bj/history")
async def api_bj_history(
    request: Request,
    date: str = "",
    market: str = "bj",
    user_id: int = Depends(get_current_user_id),
) -> dict:
    """掘金历史归档（VIP 专属）：不传 date 返回归档日期摘要，传 date 返回当日完整结果（按市场隔离）。"""
    market = str(market or "bj").strip().lower()
    if market not in ("bj", "all", "hs", "kc", "bj_all"):
        market = "bj"
    _rate_limit(f"bj-history:{user_id}", 30)
    try:
        _auth_ip_rate_limit(request)
    except Exception:
        pass
    db.downgrade_expired_vip_plan(int(user_id))
    quota = db.get_quota_status(int(user_id))
    plan = str(quota.get("plan") or "anon").strip().lower()
    is_vip = plan not in ("", "free", "anon")
    if not is_vip:
        raise HTTPException(status_code=403, detail="北证掘金历史归档为 VIP 专属功能，开通 VIP 后即可使用")
    from .bj_screener import archive_summary, load_archive

    date = str(date or "").strip()
    if date:
        d = load_archive(market, date)
        if not d:
            raise HTTPException(status_code=404, detail="未找到该日期的归档记录")
        d = dict(d)
        d["ok"] = True
        d["archive"] = True
        d["cached"] = True
        d["vip_required"] = False
        return d
    return {"ok": True, "list": archive_summary(market)}


@app.get("/api/bj/replay")
async def api_bj_replay(
    request: Request,
    date: str = "",
    market: str = "hs",
    user_id: int = Depends(get_current_user_id),
) -> dict:
    """掘金历史日期回放（VIP 专属）：最新算法 × 指定收盘日数据重放各栏目。

    只读不写、零上游；date=YYYY-MM-DD 或 YYYYMMDD；market=hs/kc/bj/bj_all/macd/pb/low10。
    数据局限：仅覆盖本机当日扫描过的成分池（bj_kline_cache/{date}.json）。
    """
    _rate_limit(f"bj-replay:{user_id}", 24)
    try:
        _auth_ip_rate_limit(request)
    except Exception:
        pass
    db.downgrade_expired_vip_plan(int(user_id))
    quota = db.get_quota_status(int(user_id))
    plan = str(quota.get("plan") or "anon").strip().lower()
    is_vip = plan not in ("", "free", "anon")
    if not is_vip:
        raise HTTPException(status_code=403, detail="掘金历史日期回放为 VIP 专属功能，开通 VIP 后即可使用")
    from .bj_screener import replay_scan

    try:
        return await asyncio.to_thread(replay_scan, date, market)
    except HTTPException:
        raise
    except Exception as e:
        return {"ok": False, "error": "replay_failed",
                "message": f"{type(e).__name__}: {str(e)[:160]}"}


@app.get("/api/bj/archive/versions")
async def api_bj_archive_versions(
    request: Request,
    market: str = "",
    user_id: int = Depends(get_current_user_id),
) -> dict:
    """掘金归档版本索引（VIP 专属）：返回全部保留的历史版本文件摘要（含同日多版本），供程序调用。

    页面「往期主推」只展示按最新算法口径的每日最终版；本接口暴露全部存档版本，
    便于历史回溯 / 报告生成 / 统计等程序化调用。
    """
    _rate_limit(f"bj-archive-versions:{user_id}", 30)
    try:
        _auth_ip_rate_limit(request)
    except Exception:
        pass
    db.downgrade_expired_vip_plan(int(user_id))
    quota = db.get_quota_status(int(user_id))
    plan = str(quota.get("plan") or "anon").strip().lower()
    is_vip = plan not in ("", "free", "anon")
    if not is_vip:
        raise HTTPException(status_code=403, detail="掘金归档索引为 VIP 专属功能，开通 VIP 后即可使用")
    from .bj_screener import archive_versions
    return archive_versions(market)


@app.get("/api/bj/winrate")
async def api_bj_winrate(
    request: Request,
    days: int = 14,
    user_id: int = Depends(get_current_user_id),
) -> dict:
    """掘金实测战绩（VIP 专属）：回溯最近 N 天主推的 5日/10日 达标率与止损率，用于胜率自检。"""
    days = int(days or 14)
    _rate_limit(f"bj-winrate:{user_id}", 30)
    try:
        _auth_ip_rate_limit(request)
    except Exception:
        pass
    db.downgrade_expired_vip_plan(int(user_id))
    quota = db.get_quota_status(int(user_id))
    plan = str(quota.get("plan") or "anon").strip().lower()
    is_vip = plan not in ("", "free", "anon")
    if not is_vip:
        raise HTTPException(status_code=403, detail="掘金实测战绩为 VIP 专属功能，开通 VIP 后即可使用")
    from .bj_screener import compute_winrate
    try:
        return await compute_winrate(days)
    except Exception as e:
        return {"ok": False, "error": str(e)[:160]}


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
            # Prefer THS first for pure-letter (pinyin) queries: EM often returns unrelated OTC funds
            # (e.g. gyyc → 复星医药成长基金), while THS correctly hits 高压氧舱.
            kw_letters = "".join(ch for ch in str(q or "").strip().lower() if "a" <= ch <= "z")
            prefer_ths_first = bool(kw_letters) and len(kw_letters) >= 2 and str(q or "").strip().isascii()
            # Deduplicate by QuoteID while merging
            seen: set[str] = set()
            merged: list = []
            primary = d2 + d1 if prefer_ths_first else d1 + d2
            for it in primary:
                if not isinstance(it, dict):
                    continue
                qid = str(it.get("QuoteID") or "").strip().upper()
                if not qid or qid in seen:
                    continue
                seen.add(qid)
                merged.append(it)
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
                priority_override = _anon_priority(base_pri)

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
    request: Request = None,  # type: ignore[assignment]
    user_id: Optional[int] = Depends(get_optional_user_id),
) -> dict:
    """
    Signals/markers computed on server (B-plan MVP).

    Return shape:
    - code: 0 ok
    - data: { markers: [...], version: "a2-v1" }
    """
    _rate_limit(f"signals:{user_id or 'anon'}", settings.kline_per_minute)
    if request is not None:
        _rate_limit(f"signals_ip:{_client_ip(request)}", settings.kline_per_minute)
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
        secid0 = str(secid or "").strip()
        # Keep the same anon policy as /api/kline (whitelist + per-IP daily trial quota).
        if user_id is None:
            is_ths_plate = secid0.lower().startswith("ths:")
            md = market_data_status()
            base_pri = str((md.get("paid") or {}).get("priority") or "").strip().lower()
            if not base_pri:
                base_pri = "tencent,eastmoney,sina,paid"
            if is_ths_plate:
                priority_override = base_pri
                allow_paid = True
            else:
                priority_override = _anon_priority(base_pri)
                allow_paid = False
            count_anon = min(int(count), 800)
            if secid0 in _ANON_KLINE_WHITELIST or is_ths_plate:
                payload = await fetch_tx_kline(
                    secid0,
                    period,
                    count=count_anon,
                    variant="anon",
                    priority_override=priority_override,
                    allow_paid=allow_paid,
                )
            else:
                if request is None or not _anon_daily_can_consume(request):
                    return {"code": -401, "msg": "游客今日体验次数已用完，请登录继续", "data": {}}
                payload = await fetch_tx_kline(
                    secid0,
                    period,
                    count=count_anon,
                    variant="anon",
                    priority_override=priority_override,
                    allow_paid=allow_paid,
                )
            # Consume anon daily trial only for non-whitelist success (same as kline_with_signals).
            try:
                if secid0 not in _ANON_KLINE_WHITELIST and request is not None:
                    if isinstance(payload, dict) and int(payload.get("code") or 0) == 0:
                        _anon_daily_consume(request)
            except Exception:
                pass
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
        # THS concept indices often have short native week/month series; always rebuild from
        # daily history when bars are too few for MA57-based signals (< 80).
        try:
            need_agg = period in ("week", "month") and (
                len(candles) < 80 or str(secid0 or "").lower().startswith("ths:")
            )
            if need_agg:
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
                "meta": sig.get("meta") or {},
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        return {"code": -1, "msg": f"signals failed ({type(e).__name__})", "data": {}}


@app.post("/api/signals/compute")
async def api_signals_compute(
    request: Request,
    user_id: Optional[int] = Depends(get_optional_user_id),
) -> dict:
    """
    Compute full v3 signals from client-provided K-line rows.

    Used when production Windows cannot reach Eastmoney plate endpoints (SSL),
    but the browser already loaded BK candles via JSONP — so the chart has data
    while GET /api/kline_with_signals returns empty markers (frontend then only
    showed minimal local 金/等). Upload rows → same server algorithm → full markers.

    Anti-scrape (2026-07-20):
    - Login required (client controls both secid label and rows; whitelist on secid
      cannot stop uploading arbitrary OHLC under a demo symbol).
    - Stricter per-user + per-IP rate limits than /api/kline.
    - No quota consume here: recovery path after /api/kline already charged.
    """
    ip = _client_ip(request)
    lim_user = int(getattr(settings, "signals_compute_per_minute", 0) or 20)
    lim_ip = int(getattr(settings, "signals_compute_ip_per_minute", 0) or 15)
    _rate_limit(f"sigcomp:{user_id or 'anon'}", lim_user)
    _rate_limit(f"sigcomp_ip:{ip}", lim_ip)
    if user_id is not None:
        _auth_ip_rate_limit(request)

    # Must login: unauthenticated compute = free oracle for reverse-engineering.
    if user_id is None:
        return {"code": -401, "msg": "请先登录后再计算信号", "data": {}}

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid json")
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="invalid body")
    period = str(body.get("period") or "day").strip().lower()
    if period not in ("day", "week", "month"):
        raise HTTPException(status_code=400, detail="Invalid period")
    rows = body.get("rows")
    # Align with build_signals_v3: MACD from 35 bars; full markers need 62.
    if not isinstance(rows, list) or len(rows) < 35:
        return {"code": -1, "msg": "need >=35 kline rows", "data": {}}
    # Cap payload size
    if len(rows) > 3000:
        rows = rows[-3000:]

    # Soft gate: expired/empty quota users still get recovery for an already-open chart,
    # but we refresh plan state so VIP downgrade stays consistent with other routes.
    try:
        db.downgrade_expired_vip_plan(int(user_id))
    except Exception:
        pass

    try:
        from .signals import candles_from_tencent_like_pack, build_signals_v3

        key_plain = {"day": "day", "week": "week", "month": "month"}[period]
        key_qfq = {"day": "qfqday", "week": "qfqweek", "month": "qfqmonth"}[period]
        pack = {key_plain: rows, key_qfq: rows}
        candles = candles_from_tencent_like_pack(pack, period=period)  # type: ignore[arg-type]
        if len(candles) < 35:
            return {"code": -1, "msg": "parsed candles < 35", "data": {}}
        # No disk lock cache: rows come from client and must not mix with server-fetched locks.
        sig = build_signals_v3(candles, cache_key="")
        return {
            "code": 0,
            "msg": "ok",
            "data": {
                "version": "a2-v3-client",
                "markers": sig.get("markers") or [],
                "bar_labels": sig.get("bar_labels") or [],
                "macd": sig.get("macd") or [],
                "meta": sig.get("meta") or {},
            },
        }
    except Exception as e:
        return {"code": -1, "msg": f"compute failed ({type(e).__name__})", "data": {}}


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
    if request is not None:
        _rate_limit(f"kline2_ip:{_client_ip(request)}", settings.kline_per_minute)
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
        priority_override = _anon_priority(base_pri)
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
        # THS concept indices: always rebuild week/month from daily (native series often too short for MA57).
        need_agg = period in ("week", "month") and (
            len(candles) < 80 or str(secid0 or "").lower().startswith("ths:")
        )
        if need_agg:
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
            "meta": sig.get("meta") or {},
        }
        return payload
    except Exception as e:
        payload["signals"] = {"code": -1, "msg": f"signals failed ({type(e).__name__})"}
        return payload


@app.get("/api/plate/map")
def api_plate_map():
    """公开：东财板块(BK) <-> 同花顺板块(88xxxx) 映射，供前端板块查询兜底。"""
    _prov._load_plate_map()
    return {
        "ok": True,
        "bk_to_ths": {k: v for k, v in _prov._PLATE_MAP_BK_TO_THS.items()},
        "ths_to_bk": dict(_prov._PLATE_MAP_THS_TO_BK),
    }


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
            "wechat_h5_enabled": bool(getattr(b, "wechat_h5_enabled", False)),
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
        out: dict = {"ok": True, **(db.invite_cfg_effective() or {})}
    except Exception:
        out = {"ok": True, "invite_reward_inviter_weekly": 0, "invite_reward_invitee_weekly": 0, "invite_weekly_cap": 0}
    try:
        act = db.invite_activity_effective()
        out["activity"] = (
            {
                k: act.get(k)
                for k in (
                    "id",
                    "name",
                    "description",
                    "target_invites",
                    "reward_plan",
                    "reward_days",
                    "stack_enabled",
                    "stack_cap_days",
                    "start_at",
                    "end_at",
                )
            }
            if act
            else None
        )
    except Exception:
        out["activity"] = None
    return out


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
            detail="在线支付暂未开放，请稍后再试。",
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
    if not bool(getattr(b, "wechat_h5_enabled", False)):
        raise HTTPException(status_code=503, detail="微信 H5 支付尚未开通（商户权限预开通中）。请在微信内使用「复制付款链接」方式支付。")
    if not wechat_v3.wechat_pay_configured(wx_cfg):
        raise HTTPException(status_code=503, detail="在线支付暂未开放，请稍后再试。")

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



def _build_alipay_return_url(request: Request, ali_cfg: object, otn: str) -> str:
    """生成带订单号的支付宝同步跳转地址，支付成功回跳后前端可据此续轮询/补发开通。"""
    base = str(getattr(ali_cfg, "alipay_return_url", "") or "").strip()
    if not base:
        try:
            proto = str(
                request.headers.get("x-forwarded-proto") or request.url.scheme or "https"
            ).split(",")[0].strip()
            host = str(
                request.headers.get("x-forwarded-host")
                or request.headers.get("host")
                or request.url.netloc
                or ""
            ).split(",")[0].strip()
            origin = f"{proto}://{host}" if host else str(request.base_url).rstrip("/")
        except Exception:
            origin = str(request.base_url).rstrip("/")
        base = f"{origin}/account.html"
    if "otn=" in base:
        return base
    sep = "&" if "?" in base else "?"
    return f"{base}{sep}otn={quote(otn)}&ch=alipay"


_PUBLIC_FULFILL_LAST_TS: dict[str, float] = {}
_PUBLIC_FULFILL_ATTEMPTS: dict[str, int] = {}


@app.post("/api/billing/pay/query_and_fulfill_public")
async def billing_pay_query_and_fulfill_public(body: dict) -> dict:
    """
    支付回跳兜底（无需登录）：按 out_trade_no 主动查询支付平台并补发开通。
    - 适用于手机支付宝/微信支付完成后回跳到本页但登录态丢失的场景；
    - 幂等：订单已 paid 直接返回成功；
    - 仅 pending 订单、创建 24 小时内允许触发查询（配合内存限流防刷）；
    - 金额/签名由支付平台侧校验，本接口只做「确认已支付 → 开通」。
    """
    otn = str((body or {}).get("out_trade_no") or "").strip()
    if not otn:
        raise HTTPException(status_code=400, detail="missing out_trade_no")
    row = db.pay_order_get_by_out_trade_no(otn)
    if not row:
        raise HTTPException(status_code=404, detail="order_not_found")
    plan = str(row.get("plan") or "")
    amount_yuan = _fen_to_yuan_display(int(row.get("amount_fen") or 0))
    if str(row.get("status") or "") == "paid":
        return {"ok": True, "status": "paid", "duplicate": True, "plan": plan, "amount_yuan_display": amount_yuan}

    now = int(time.time())
    created = int(row.get("created_at") or 0)
    if created <= 0 or now - created > 24 * 3600:
        return {"ok": True, "status": "expired", "plan": plan}

    # 内存限流：每单最多 8 次主动查询、间隔至少 3 秒，防刷上游。
    if now - _PUBLIC_FULFILL_LAST_TS.get(otn, 0.0) < 3:
        return {"ok": True, "status": "pending", "plan": plan}
    if _PUBLIC_FULFILL_ATTEMPTS.get(otn, 0) >= 8:
        return {"ok": True, "status": "pending", "plan": plan}
    _PUBLIC_FULFILL_LAST_TS[otn] = float(now)
    _PUBLIC_FULFILL_ATTEMPTS[otn] = _PUBLIC_FULFILL_ATTEMPTS.get(otn, 0) + 1

    channel = str(row.get("channel") or "")
    try:
        if "wechat" in channel:
            txn = await wechat_v3.query_transaction_by_out_trade_no(resolve_wechat_pay(), out_trade_no=otn)
            if str(txn.get("trade_state") or "") != "SUCCESS":
                return {"ok": True, "status": "pending", "trade_state": str(txn.get("trade_state") or "")}
            transaction_id = str(txn.get("transaction_id") or "").strip()
            amount = txn.get("amount") if isinstance(txn.get("amount"), dict) else {}
            total = int((amount or {}).get("total") or 0)
            r = db.pay_order_try_fulfill_wechat(otn, transaction_id, total)
        elif "alipay" in channel:
            txn = alipay_wap.query_trade(resolve_alipay(), out_trade_no=otn)
            if str(txn.get("trade_status") or "") not in ("TRADE_SUCCESS", "TRADE_FINISHED"):
                return {"ok": True, "status": "pending", "trade_status": str(txn.get("trade_status") or "")}
            trade_no = str(txn.get("trade_no") or "").strip()
            total_amount = str(txn.get("total_amount") or "").strip()
            try:
                total = int(round(float(total_amount) * 100.0))
            except Exception:
                total = 0
            r = db.pay_order_try_fulfill_alipay(otn, trade_no, total)
        else:
            return {"ok": True, "status": "pending", "plan": plan}
    except Exception:
        return {"ok": True, "status": "pending", "plan": plan}
    if not r.get("ok"):
        return {"ok": True, "status": "pending", "plan": plan}
    return {"ok": True, "status": "paid", "duplicate": bool(r.get("duplicate")), "plan": plan, "amount_yuan_display": amount_yuan}


@app.post("/api/billing/alipay/wap", response_model=PayWapOut)
async def billing_alipay_wap(request: Request, body: PayWapIn, user_id: int = Depends(get_current_user_id)) -> PayWapOut:
    ali_cfg = resolve_alipay()
    b = resolve_billing()
    if not bool(getattr(b, "billing_pay_alipay_enabled", True)):
        raise HTTPException(status_code=503, detail="支付宝支付已关闭")
    if not alipay_wap.alipay_configured(ali_cfg):
        raise HTTPException(
            status_code=503,
            detail="在线支付暂未开放，请稍后再试。",
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
            return_url=_build_alipay_return_url(request, ali_cfg, out_trade_no),
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

# ============ 每日板块主攻研判（并入产品后端，路由见 app/daily_report.py） ============
from .daily_report import router as _daily_report_router
app.include_router(_daily_report_router)

# ============ 同花顺金融数据服务（hithink-finance / fuyao，免费期增强通道） ============
from .ths_fuyao import router as _ths_fuyao_router
app.include_router(_ths_fuyao_router)
