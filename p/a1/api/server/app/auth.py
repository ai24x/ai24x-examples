from __future__ import annotations

import time
from typing import Optional

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt

from .config import settings

security = HTTPBearer(auto_error=False)


def create_token(user_id: int, email: str | None, phone: str | None = None) -> str:
    now = int(time.time())
    exp = now + settings.jwt_expire_days * 86400
    payload = {"sub": str(user_id), "email": email or "", "phone": phone or "", "iat": now, "exp": exp}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def parse_token(token: str) -> dict:
    secrets: list[str] = []
    try:
        cur = str(getattr(settings, "jwt_secret", "") or "").strip()
        if cur:
            secrets.append(cur)
    except Exception:
        pass
    try:
        prev = str(getattr(settings, "jwt_secret_prev", "") or "").strip()
        if prev and prev not in secrets:
            secrets.append(prev)
    except Exception:
        pass

    for sec in secrets:
        try:
            return jwt.decode(token, sec, algorithms=["HS256"])
        except Exception:
            continue
    raise HTTPException(status_code=401, detail="Invalid token")


def get_current_user_id(
    cred: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> int:
    if not cred or not cred.credentials:
        raise HTTPException(status_code=401, detail="Missing token")
    data = parse_token(cred.credentials)
    sub = data.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Invalid token")
    try:
        uid = int(sub)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    from . import db

    db.ensure_platform_user(uid, data.get("email") or None, data.get("phone") or None)
    return uid


def get_optional_user_id(
    cred: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[int]:
    if not cred or not cred.credentials:
        return None
    data = parse_token(cred.credentials)
    sub = data.get("sub")
    if not sub:
        return None
    try:
        uid = int(sub)
    except Exception:
        return None
    from . import db

    db.ensure_platform_user(uid, data.get("email") or None, data.get("phone") or None)
    return uid

