"""进程内邮箱验证码（与 sms_otp_memory 同模式；生产建议换 Redis）。"""

from __future__ import annotations

import time

_store: dict[str, tuple[str, float]] = {}


def _norm_email(email: str) -> str:
    return (email or "").strip().lower()


def _key(email: str, purpose: str) -> str:
    return f"{_norm_email(email)}:{purpose.strip().lower()}"


def store_otp(email: str, purpose: str, code: str, ttl_s: float = 300.0) -> None:
    _store[_key(email, purpose)] = (str(code).strip(), time.time() + float(ttl_s))


def verify_and_consume_otp(email: str, purpose: str, code: str) -> bool:
    k = _key(email, purpose)
    tup = _store.get(k)
    if not tup:
        return False
    stored, exp = tup
    now = time.time()
    if now > exp:
        try:
            del _store[k]
        except KeyError:
            pass
        return False
    if stored != str(code or "").strip():
        return False
    del _store[k]
    return True
