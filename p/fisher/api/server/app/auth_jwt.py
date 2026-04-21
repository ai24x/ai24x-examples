from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .models import Player

ALGO = "HS256"
_bearer = HTTPBearer(auto_error=False)


def create_access_token(*, sub: str, extra: dict[str, Any] | None = None) -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(days=int(settings.jwt_expire_days))
    payload: dict[str, Any] = {"sub": sub, "iat": int(now.timestamp()), "exp": exp}
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGO)


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.jwt_secret, algorithms=[ALGO])


def get_current_player(
    cred: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Player:
    if cred is None or (cred.scheme or "").lower() != "bearer":
        raise HTTPException(status_code=401, detail="Missing bearer token")
    try:
        payload = decode_token(cred.credentials)
        sub = str(payload.get("sub") or "")
        pid = int(sub)
    except (JWTError, ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Invalid token")
    p = db.get(Player, pid)
    if not p:
        raise HTTPException(status_code=401, detail="Player not found")
    return p
