from __future__ import annotations

import csv
import io
import logging
import random
import re
import string
import time
from typing import Optional

import httpx
from fastapi import Cookie, Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, Response

from . import db, wechat_v3
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
from .billing_runtime import identity_configured, resolve_identity, resolve_wechat_pay
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
    InviteBindIn,
    LoginIn,
    LoginOut,
    PasswordChangeIn,
    PasswordResetIn,
    PayNativeIn,
    PayNativeOut,
    QuotaConsumeIn,
    QuotaConsumeOut,
    RegisterIn,
    RequestCodeIn,
    RequestCodeOut,
    SmsSendProxyIn,
)


app = FastAPI(title="AI24X 股票查询助手 API", version="0.1.0")


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


# in-memory rate limit buckets (single-process MVP)
_RL: dict[str, tuple[int, int]] = {}

# Anonymous whitelist: allow a few demo/sample symbols without login to improve onboarding.
# Keep it small to avoid abuse.
_ANON_KLINE_WHITELIST: set[str] = {
    "1.000001",  # 上证指数
    "0.399001",  # 深证成指
    "0.399006",  # 创业板指
    "0.899050",  # 北证50
    "0.000977",  # 浪潮信息（示例）
}


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
        raise HTTPException(status_code=503, detail=f"Identity API unreachable: {e}") from e
    ct = (r.headers.get("content-type") or "").lower()
    if r.status_code >= 400:
        detail = r.text[:4000]
        if "json" in ct:
            try:
                detail = str(r.json())
            except Exception:
                pass
        raise HTTPException(status_code=r.status_code, detail=detail)
    if "json" not in ct:
        raise HTTPException(status_code=502, detail="Identity API returned non-JSON")
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
    if (p.endswith("/sms/diagnostics") or p.startswith("/v1/admin/sms/")) and cfg.sms_internal_key:
        headers["X-SMS-Internal-Key"] = cfg.sms_internal_key
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.get(url, headers=headers or None)
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Identity API unreachable: {e}") from e
    ct = (r.headers.get("content-type") or "").lower()
    if r.status_code >= 400:
        detail = r.text[:4000]
        if "json" in ct:
            try:
                detail = str(r.json())
            except Exception:
                pass
        raise HTTPException(status_code=r.status_code, detail=detail)
    if "json" not in ct:
        raise HTTPException(status_code=502, detail="Identity API returned non-JSON")
    return r.json()


def _cors_list(v: str) -> list[str]:
    vv = (v or "").strip()
    if vv == "*" or not vv:
        return ["*"]
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


_NO_STORE = {"Cache-Control": "no-store, no-cache, must-revalidate", "Pragma": "no-cache"}

# 浏览器管理台挂载路径（默认 /admin20260501，对齐宣发 2026-05-01）；见 AI24X_ADMIN_MOUNT_PATH
_ADMIN_BASE = str(settings.admin_mount_path)


@app.get("/", include_in_schema=False)
def root_landing() -> dict:
    """根路径说明：避免只打开 http://host:port/ 时误以为服务未启动；并给出当前管理台真实路径。"""
    return {
        "ok": True,
        "service": "ai24x-p-a-api",
        "hint": "若管理页 404，请确认本进程为 p/a/api/server 的 uvicorn，并已重启；路径以 AI24X_ADMIN_MOUNT_PATH 为准。",
        "paths": {
            "health": "/health",
            "docs": "/docs",
            "admin_mount": _ADMIN_BASE,
            "admin_login": f"{_ADMIN_BASE}/login",
            "admin_app": _ADMIN_BASE,
            "admin_otp_send": "/api/admin/otp/send",
            "admin_otp_required": admin_browser_otp_required(),
            "admin_browser_otp_feature_enabled": admin_browser_otp_feature_enabled(),
            **(
                {
                    "admin_login_compat": "/admin/login",
                    "admin_app_compat": "/admin",
                }
                if _ADMIN_BASE.rstrip("/") != "/admin"
                else {}
            ),
        },
    }


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
                _identity_post(
                    "/v1/admin/users/contact/set",
                    {"user_id": int(user_id), "email": email, "phone": phone},
                    extra_headers={"X-SMS-Internal-Key": cfg.sms_internal_key},
                )
        return db.admin_update_user_basic(int(user_id), email=body.get("email"), phone=body.get("phone"))
    except ValueError as e:
        # keep user-friendly; do not leak DB error details
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
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
    data = _identity_post(
        "/v1/admin/users/password/set",
        {"user_id": int(user_id), "new_password": npw},
        extra_headers={"X-SMS-Internal-Key": cfg.sms_internal_key},
    )
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


@app.get("/api/admin/quota_ledger")
def admin_quota_ledger(user_id: int, limit: int = 50, _: bool = Depends(require_admin)) -> dict:
    return db.admin_list_quota_ledger(user_id=user_id, limit=limit)


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
        return db.admin_config_set(key, value)
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
    if prov == "tencent":
        raise HTTPException(
            status_code=503,
            detail="当前已选「腾讯短信」为预留通道，发送逻辑尚未接入；请在管理后台改为主通道 identity_proxy（经主站 API 走 106接口网）或后续再接腾讯 SDK。",
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
            detail="请使用手机号/邮箱+密码登录（需配置 AI24X_IDENTITY_API_BASE），或邮箱+验证码（仅开发回退）",
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
    user_id: Optional[int] = Depends(get_optional_user_id),
) -> dict:
    _rate_limit(f"kline:{user_id or 'anon'}", settings.kline_per_minute)
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
            if secid0 in _ANON_KLINE_WHITELIST:
                # Force public sources only; do not allow paid provider for anonymous traffic.
                md = market_data_status()
                base_pri = str((md.get("paid") or {}).get("priority") or "").strip().lower()
                if not base_pri:
                    base_pri = "tencent,eastmoney,sina,paid"
                priority_override = ",".join([x for x in base_pri.split(",") if x.strip() and x.strip() != "paid"])
                # Keep it lighter for anonymous: smaller count.
                # Anonymous whitelist is for onboarding; still needs enough history for MA57 + signals.
                # 2y daily bars ~= 520. Keep a little buffer.
                count_anon = min(int(count), 800)
                return await fetch_tx_kline(
                    secid0,
                    period,
                    count=count_anon,
                    variant="anon",
                    priority_override=priority_override,
                    allow_paid=False,
                )
            # Prevent unlimited anonymous queries from public/demo pages.
            return {"code": -401, "msg": "请先登录后再查询", "data": {}}

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
            if secid0 in _ANON_KLINE_WHITELIST:
                md = market_data_status()
                base_pri = str((md.get("paid") or {}).get("priority") or "").strip().lower()
                if not base_pri:
                    base_pri = "tencent,eastmoney,sina,paid"
                priority_override = ",".join([x for x in base_pri.split(",") if x.strip() and x.strip() != "paid"])
                count_anon = min(int(count), 800)
                payload = await fetch_tx_kline(
                    secid0,
                    period,
                    count=count_anon,
                    variant="anon",
                    priority_override=priority_override,
                    allow_paid=False,
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
        sig = build_signals_v3(candles)
        return {
            "code": 0,
            "msg": "ok",
            "data": {
                "version": "a2-v3",
                "markers": sig.get("markers") or [],
                "bar_labels": sig.get("bar_labels") or [],
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        return {"code": -1, "msg": f"signals failed ({type(e).__name__})", "data": {}}


@app.get("/api/status/market-data")
def api_market_data_status(_: bool = Depends(require_admin)) -> dict:
    return market_data_status()


def _billing_normalize_plan(plan: str) -> tuple[str, int]:
    p = (plan or "").strip().lower()
    if p in ("vip_month", "month", "monthly", "vip"):
        return "vip_month", int(settings.price_vip_month_fen)
    if p in ("vip_year_999", "vip_year", "year", "yearly"):
        return "vip_year_999", int(settings.price_vip_year_fen)
    if p in ("vip_trial_99", "vip_trial", "trial", "trial_99"):
        return "vip_trial_99", int(settings.price_vip_trial_fen)
    raise HTTPException(
        status_code=400,
        detail="不支持的套餐：vip_trial_99 / vip_month / vip_year_999",
    )


def _billing_charge_amount_fen(catalog_fen: int) -> int:
    """非 prod 可开启真实小额扣款用于联调。"""
    if settings.billing_dev_real_pay:
        return max(1, int(settings.billing_dev_amount_fen))
    return int(catalog_fen)


@app.post("/api/billing/wechat/native", response_model=PayNativeOut)
async def billing_wechat_native(body: PayNativeIn, user_id: int = Depends(get_current_user_id)) -> PayNativeOut:
    wx_cfg = resolve_wechat_pay()
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
        desc = "AI24X VIP月会员"
    elif plan_norm == "vip_year_999":
        desc = "AI24X VIP年会员"
    else:
        desc = "AI24X VIP体验卡"
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

