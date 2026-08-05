"""进程内邮箱验证码（与 sms_otp_memory 同模式；生产建议换 Redis）。"""

from __future__ import annotations

import time

_store: dict[str, tuple[str, float]] = {}
# key → (fail_count, lock_until_ts)
_fails: dict[str, tuple[int, float]] = {}

_MAX_FAILS = 5
_LOCK_S = 900.0  # 15 分钟


def _norm_email(email: str) -> str:
    return (email or "").strip().lower()


def _key(email: str, purpose: str) -> str:
    return f"{_norm_email(email)}:{purpose.strip().lower()}"


def store_otp(email: str, purpose: str, code: str, ttl_s: float = 300.0) -> None:
    k = _key(email, purpose)
    _store[k] = (str(code).strip(), time.time() + float(ttl_s))
    # 重新发码时清失败计数（不延长已有锁，防刷仍靠发码频控）
    _fails.pop(k, None)


def verify_and_consume_otp(email: str, purpose: str, code: str) -> bool:
    k = _key(email, purpose)
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
