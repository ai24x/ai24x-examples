"""AI24X · Google / Apple 一键登录（OAuth2 / Sign in with Apple）。

仅新增 OAuth 登录链路；不改动 /v1/auth/login 密码登录、支付、配额与模型路由。
凭据全部从环境变量读取，未配置时：
  - GET /v1/auth/providers -> {"google": false, "apple": false}
  - login/callback -> 503 {"code":-1,"msg":"config_missing"}
密钥禁止写入日志 / 响应 / git。
"""
from __future__ import annotations

import base64
import json
import os
import secrets
import time
from typing import Any, Dict, Optional
from urllib.parse import quote, urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from auth_tokens import create_auth_access_token
from auth_user_service import create_user_email, get_by_email, norm_email, raise_if_frozen
from config import settings
from database import get_db

router = APIRouter(prefix="/v1/auth", tags=["auth-social"])

# ---------- 凭据（仅环境变量，绝不进 git/日志/响应） ----------
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "").strip()
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "").strip()
APPLE_TEAM_ID = os.environ.get("APPLE_TEAM_ID", "").strip()
APPLE_SERVICE_ID = os.environ.get("APPLE_SERVICE_ID", "").strip()
APPLE_KEY_ID = os.environ.get("APPLE_KEY_ID", "").strip()
APPLE_PRIVATE_KEY = os.environ.get("APPLE_PRIVATE_KEY", "").strip()
# 可选：redirect_uri 前缀覆盖（默认 https://www.ai24x.com；本机测试设 http://127.0.0.1:8000）
OAUTH_REDIRECT_BASE = os.environ.get("OAUTH_REDIRECT_BASE", "https://www.ai24x.com").strip().rstrip("/")

_ALLOWED_HOSTS = {"ai24x.com", "www.ai24x.com", "markets.ai24x.com", "127.0.0.1", "localhost"}
_COOKIE_MAX_AGE = 2592000  # 30 天，与 api.js 一致


def google_configured() -> bool:
    return bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)


def apple_configured() -> bool:
    return bool(APPLE_TEAM_ID and APPLE_SERVICE_ID and APPLE_KEY_ID and _apple_private_key_pem())


def _apple_private_key_pem() -> str:
    """APPLE_PRIVATE_KEY 支持直接放 .p8 内容或文件路径；兼容 \n 转义。"""
    v = APPLE_PRIVATE_KEY
    if not v:
        return ""
    v = v.replace("\\n", "\n")
    if "BEGIN" in v:
        return v
    p = v if os.path.isabs(v) else os.path.join(os.path.dirname(os.path.abspath(__file__)), v)
    try:
        with open(p, "r", encoding="utf-8") as fh:
            return fh.read().strip()
    except Exception:
        return ""


def _redirect_uri(path: str) -> str:
    return OAUTH_REDIRECT_BASE + path


# ---------- state（内存态，带过期；不落库不落盘） ----------
_STATES: Dict[str, Dict[str, Any]] = {}
_STATE_TTL = 600


def _new_state(next_url: str, provider: str) -> str:
    st = secrets.token_urlsafe(24)
    _STATES[st] = {"next": next_url, "provider": provider, "exp": time.time() + _STATE_TTL}
    return st


def _pop_state(state: str, provider: str) -> Optional[str]:
    if not state:
        return None
    rec = _STATES.pop(state, None)
    if not rec or rec.get("provider") != provider or rec.get("exp", 0) < time.time():
        return None
    return rec.get("next") or ""


# ---------- 工具 ----------
def _safe_next(raw: str, fallback: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return fallback
    if raw.startswith("//"):
        return fallback
    if raw.startswith("/"):
        return raw  # 同站相对路径
    low = raw.lower()
    if low.startswith("http://") or low.startswith("https://"):
        try:
            host = raw.split("/")[2].split(":")[0].lower()
        except Exception:
            return fallback
        if host in _ALLOWED_HOSTS:
            return raw
    return fallback


def _default_next(request: Request) -> str:
    h = (request.url.hostname or "").lower()
    if h in ("127.0.0.1", "localhost"):
        return f"{request.url.scheme}://{request.url.netloc}/console.html"
    return "https://www.ai24x.com"


def _with_oauth_fragment(url: str) -> str:
    frag = "oauth=1"
    if "#" in url:
        base, _, f = url.partition("#")
        return base + "#" + ((f + "&") if f else "") + frag
    return url + "#" + frag


def _oauth_error_redirect(next_raw: str, fallback: str, code: str) -> RedirectResponse:
    target = _safe_next(next_raw, fallback)
    sep = "&" if "?" in target else "?"
    return RedirectResponse(target + sep + "oauth_error=" + quote(code), status_code=302)


def _cookie_domain(hostname: str) -> str:
    h = (hostname or "").lower()
    return ".ai24x.com" if (h == "ai24x.com" or h.endswith(".ai24x.com")) else ""


def _finish_oauth(db: Session, *, email: str, next_raw: str, request: Request, fallback: str):
    """按邮箱 upsert 用户 -> 签发与 /v1/auth/login 一致的令牌 -> 302 回 next 并种 cookie。"""
    try:
        u = get_by_email(db, email)
        if not u:
            u = create_user_email(db, email, secrets.token_urlsafe(24))
        raise_if_frozen(u)
    except HTTPException:
        return _oauth_error_redirect(next_raw, fallback, "account_frozen")
    except Exception:
        return _oauth_error_redirect(next_raw, fallback, "user_create_failed")
    token = create_auth_access_token(
        user_id=int(u.id),
        email=u.email,
        phone=u.phone,
        secret=settings.secret_key,
        expire_days=int(settings.auth_jwt_expire_days),
    )
    target = _safe_next(next_raw, fallback)
    user_dict = {"id": int(u.id), "email": u.email or "", "phone": u.phone or ""}
    domain = _cookie_domain(request.url.hostname or "")
    secure = (request.url.scheme or "").lower() == "https"
    resp = RedirectResponse(_with_oauth_fragment(target), status_code=302)
    resp.set_cookie(
        "ai24x_auth_token", token, max_age=_COOKIE_MAX_AGE, path="/",
        domain=domain or None, secure=secure, httponly=False, samesite="lax",
    )
    resp.set_cookie(
        "ai24x_auth_user", json.dumps(user_dict, ensure_ascii=False), max_age=_COOKIE_MAX_AGE, path="/",
        domain=domain or None, secure=secure, httponly=False, samesite="lax",
    )
    return resp


def _config_missing() -> JSONResponse:
    return JSONResponse(status_code=503, content={"code": -1, "msg": "config_missing"})


# ---------- Providers ----------
@router.get("/providers")
async def oauth_providers():
    return {"google": google_configured(), "apple": apple_configured()}


# ---------- Google ----------
@router.get("/google/login")
async def google_login(request: Request, next: str = ""):
    if not google_configured():
        return _config_missing()
    fallback = _default_next(request)
    state = _new_state(_safe_next(next, fallback), "google")
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": _redirect_uri("/v1/auth/google/callback"),
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "prompt": "select_account",
    }
    return RedirectResponse(
        "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params), status_code=302
    )


@router.get("/google/callback")
async def google_callback(request: Request, code: str = "", state: str = "", db: Session = Depends(get_db)):
    if not google_configured():
        return _config_missing()
    fallback = _default_next(request)
    nxt = _pop_state(state, "google")
    if nxt is None:
        return _oauth_error_redirect("", fallback, "state_invalid")
    if not code:
        return _oauth_error_redirect(nxt, fallback, "code_missing")
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "redirect_uri": _redirect_uri("/v1/auth/google/callback"),
                    "grant_type": "authorization_code",
                },
            )
            if r.status_code != 200:
                return _oauth_error_redirect(nxt, fallback, "token_exchange_failed")
            tok = r.json()
            ui = await client.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {(tok.get('access_token') or '')}"},
            )
            if ui.status_code != 200:
                return _oauth_error_redirect(nxt, fallback, "userinfo_failed")
            info = ui.json()
    except Exception:
        return _oauth_error_redirect(nxt, fallback, "provider_unreachable")
    email = (info.get("email") or "").strip().lower()
    if not email:
        return _oauth_error_redirect(nxt, fallback, "email_missing")
    if not info.get("email_verified", False):
        return _oauth_error_redirect(nxt, fallback, "email_unverified")
    return _finish_oauth(db, email=email, next_raw=nxt, request=request, fallback=fallback)


# ---------- Apple ----------
def _apple_client_secret() -> str:
    """用 APPLE_PRIVATE_KEY 生成 ES256 client_secret（iss=TEAM_ID, sub=SERVICE_ID）。"""
    pem = _apple_private_key_pem()
    if not pem:
        return ""
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec

        key = serialization.load_pem_private_key(pem.encode("utf-8"), password=None)
        now = int(time.time())

        def b64url(data: bytes) -> str:
            return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

        header = {"alg": "ES256", "kid": APPLE_KEY_ID}
        payload = {
            "iss": APPLE_TEAM_ID,
            "iat": now,
            "exp": now + 300,
            "aud": "https://appleid.apple.com",
            "sub": APPLE_SERVICE_ID,
        }
        signing_input = (
            b64url(json.dumps(header, separators=(",", ":")).encode("utf-8"))
            + "."
            + b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
        )
        sig = key.sign(signing_input.encode("ascii"), ec.ECDSA(hashes.SHA256()))
        return signing_input + "." + b64url(sig)
    except Exception:
        return ""


def _decode_id_token(id_token: str) -> Optional[Dict[str, Any]]:
    try:
        parts = id_token.split(".")
        if len(parts) != 3:
            return None
        raw = base64.urlsafe_b64decode(parts[1] + "=" * (-len(parts[1]) % 4))
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None


@router.get("/apple/login")
async def apple_login(request: Request, next: str = ""):
    if not apple_configured():
        return _config_missing()
    fallback = _default_next(request)
    state = _new_state(_safe_next(next, fallback), "apple")
    params = {
        "client_id": APPLE_SERVICE_ID,
        "redirect_uri": _redirect_uri("/v1/auth/apple/callback"),
        "response_type": "code",
        "scope": "name email",
        "state": state,
        "response_mode": "query",
    }
    return RedirectResponse(
        "https://appleid.apple.com/auth/authorize?" + urlencode(params), status_code=302
    )


@router.get("/apple/callback")
async def apple_callback(request: Request, code: str = "", state: str = "", db: Session = Depends(get_db)):
    if not apple_configured():
        return _config_missing()
    fallback = _default_next(request)
    nxt = _pop_state(state, "apple")
    if nxt is None:
        return _oauth_error_redirect("", fallback, "state_invalid")
    if not code:
        return _oauth_error_redirect(nxt, fallback, "code_missing")
    client_secret = _apple_client_secret()
    if not client_secret:
        return _oauth_error_redirect(nxt, fallback, "apple_key_error")
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(
                "https://appleid.apple.com/auth/token",
                data={
                    "client_id": APPLE_SERVICE_ID,
                    "client_secret": client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            if r.status_code != 200:
                return _oauth_error_redirect(nxt, fallback, "token_exchange_failed")
            tok = r.json()
    except Exception:
        return _oauth_error_redirect(nxt, fallback, "provider_unreachable")
    claims = _decode_id_token(tok.get("id_token") or "")
    if not claims:
        return _oauth_error_redirect(nxt, fallback, "id_token_invalid")
    if claims.get("iss") != "https://appleid.apple.com" or claims.get("aud") != APPLE_SERVICE_ID:
        return _oauth_error_redirect(nxt, fallback, "id_token_invalid")
    exp = int(claims.get("exp") or 0)
    if exp and exp < time.time():
        return _oauth_error_redirect(nxt, fallback, "id_token_expired")
    email = (claims.get("email") or "").strip().lower()
    if not email:
        return _oauth_error_redirect(nxt, fallback, "email_missing")
    return _finish_oauth(db, email=email, next_raw=nxt, request=request, fallback=fallback)
