"""与 p/a 行情官 JWT 载荷一致：sub=id, email, phone, iat, exp（算法 HS256）。"""

from __future__ import annotations

import time
from typing import Any

from jose import jwt


def create_auth_access_token(
    *,
    user_id: int,
    email: str | None,
    phone: str | None,
    secret: str,
    expire_days: int,
) -> str:
    now = int(time.time())
    exp = now + int(expire_days) * 86400
    payload: dict[str, Any] = {
        "sub": str(int(user_id)),
        "email": (email or "").strip(),
        "phone": (phone or "").strip(),
        "iat": now,
        "exp": exp,
    }
    return jwt.encode(payload, secret, algorithm="HS256")
