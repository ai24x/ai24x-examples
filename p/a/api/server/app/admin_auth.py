from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Optional

from .config import settings


def admin_key_matches(provided: str | None, expected: str | None) -> bool:
    """常量时间比较管理密钥，降低时序侧信道风险。"""
    a = (provided or "").strip().encode("utf-8")
    b = (expected or "").strip().encode("utf-8")
    if not b:
        return False
    try:
        return hmac.compare_digest(a, b)
    except Exception:
        return False

# HttpOnly cookie for browser admin UI (automation may still use X-Admin-Key).
COOKIE_NAME = "ai24x_admin_session"
SESSION_TTL_S = 8 * 3600


def issue_admin_session(
    *,
    phone: str = "",
    role: str = "super",
    perm_flags: int = 0,
) -> str:
    exp = int(time.time()) + SESSION_TTL_S
    payload = json.dumps(
        {"exp": exp, "phone": phone or "", "role": role or "super", "pf": int(perm_flags)},
        separators=(",", ":"),
        sort_keys=True,
    )
    b64 = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
    sig = hmac.new(settings.jwt_secret.encode(), b64.encode(), hashlib.sha256).hexdigest()
    return f"{b64}.{sig}"


def decode_admin_session(cookie_val: Optional[str]) -> Optional[dict]:
    if not cookie_val or "." not in cookie_val:
        return None
    b64, sig = cookie_val.rsplit(".", 1)
    expect = hmac.new(settings.jwt_secret.encode(), b64.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expect, sig):
        return None
    pad = "=" * ((4 - len(b64) % 4) % 4)
    try:
        raw = base64.urlsafe_b64decode(b64 + pad).decode()
        data = json.loads(raw)
        if int(data.get("exp", 0)) <= int(time.time()):
            return None
        return data
    except Exception:
        return None


def verify_admin_session(cookie_val: Optional[str]) -> bool:
    return decode_admin_session(cookie_val) is not None
