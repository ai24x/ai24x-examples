"""
开发/联调用：短信验证码内存存储（进程内）。
生产应换 Redis + 限次校验，并与用户表事务一致。
"""

from __future__ import annotations

import time

from sms_106_client import normalize_mobile

_store: dict[str, tuple[str, float]] = {}


def _key(phone: str, purpose: str) -> str:
    return f"{normalize_mobile(phone)}:{purpose.strip().lower()}"


def store_otp(phone: str, purpose: str, code: str, ttl_s: float = 300.0) -> None:
    _store[_key(phone, purpose)] = (str(code).strip(), time.time() + float(ttl_s))


def verify_and_consume_otp(phone: str, purpose: str, code: str) -> bool:
    k = _key(phone, purpose)
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
