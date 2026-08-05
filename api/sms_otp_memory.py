"""
开发/联调用：短信验证码内存存储（进程内）。
生产应换 Redis + 限次校验，并与用户表事务一致。
"""

from __future__ import annotations

import time

from sms_106_client import normalize_mobile

_store: dict[str, tuple[str, float]] = {}
# key → (fail_count, lock_until_ts)
_fails: dict[str, tuple[int, float]] = {}

_MAX_FAILS = 5
_LOCK_S = 900.0


def _key(phone: str, purpose: str) -> str:
    return f"{normalize_mobile(phone)}:{purpose.strip().lower()}"


def store_otp(phone: str, purpose: str, code: str, ttl_s: float = 300.0) -> None:
    k = _key(phone, purpose)
    _store[k] = (str(code).strip(), time.time() + float(ttl_s))
    _fails.pop(k, None)


def verify_and_consume_otp(phone: str, purpose: str, code: str) -> bool:
    k = _key(phone, purpose)
    now = time.time()
    fail = _fails.get(k)
    if fail and fail[1] > now:
        return False

    tup = _store.get(k)
    if not tup:
        _bump_fail(k, now)
        return False
    stored, exp = tup
    if now > exp:
        try:
            del _store[k]
        except KeyError:
            pass
        _bump_fail(k, now)
        return False
    if stored != str(code or "").strip():
        _bump_fail(k, now)
        return False
    del _store[k]
    _fails.pop(k, None)
    return True


def _bump_fail(k: str, now: float) -> None:
    n, lock_until = _fails.get(k, (0, 0.0))
    if lock_until > now:
        return
    n += 1
    if n >= _MAX_FAILS:
        _fails[k] = (n, now + _LOCK_S)
        try:
            del _store[k]
        except KeyError:
            pass
    else:
        _fails[k] = (n, 0.0)
