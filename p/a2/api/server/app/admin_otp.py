from __future__ import annotations

import random
import re
import threading
import time
from typing import Optional

from .config import settings

_lock = threading.Lock()
# 规范化手机号 -> (code, expire_unix)
_store: dict[str, tuple[str, float]] = {}


def normalize_admin_phone(raw: str) -> str:
    """中国大陆手机：保留数字，去 86 前缀，得到 11 位 1…。"""
    s = (raw or "").strip()
    d = re.sub(r"\D", "", s)
    if d.startswith("86") and len(d) >= 13:
        d = d[2:]
    return d


def parse_admin_otp_env_phones() -> set[str]:
    raw = str(settings.admin_otp_phones or "")
    out: set[str] = set()
    for part in raw.replace(";", ",").split(","):
        p = normalize_admin_phone(part)
        if len(p) >= 10:
            out.add(p)
    return out


def admin_browser_otp_feature_enabled() -> bool:
    """数据库 admin_config.admin_browser_otp_enabled：1=开启浏览器管理短信 OTP；未配置或其它值=关闭（预演默认）。"""
    try:
        from . import db

        v = (db.admin_config_get("admin_browser_otp_enabled") or "").strip().lower()
        return v in ("1", "true", "yes", "on")
    except Exception:
        return False


def admin_browser_otp_required() -> bool:
    """开关开启且白名单（环境变量 + 库表启用行）非空时，浏览器登录须短信 OTP + 管理密钥。"""
    if not admin_browser_otp_feature_enabled():
        return False
    if parse_admin_otp_env_phones():
        return True
    try:
        from . import db

        return len(db.admin_operator_list_enabled_phones_from_db()) > 0
    except Exception:
        return False


def all_otp_allowed_phones() -> set[str]:
    phones = set(parse_admin_otp_env_phones())
    try:
        from . import db

        phones |= set(db.admin_operator_list_enabled_phones_from_db())
    except Exception:
        pass
    return phones


def is_phone_allowed_for_admin_otp(phone: str) -> bool:
    p = normalize_admin_phone(phone)
    if not p:
        return False
    return p in all_otp_allowed_phones()


def admin_otp_put(phone: str, code: str, ttl_s: int) -> None:
    p = normalize_admin_phone(phone)
    exp = time.time() + max(30, int(ttl_s))
    with _lock:
        _store[p] = (code, exp)


def admin_otp_verify_and_consume(phone: str, code: str) -> bool:
    p = normalize_admin_phone(phone)
    c = (code or "").strip()
    if not p or not c:
        return False
    now = time.time()
    with _lock:
        _prune_locked(now)
        hit = _store.get(p)
        if not hit:
            return False
        oc, exp = hit
        if now > exp:
            del _store[p]
            return False
        if not _code_eq(oc, c):
            return False
        del _store[p]
        return True


def _prune_locked(now: float) -> None:
    dead = [k for k, (_, e) in _store.items() if now > e]
    for k in dead:
        _store.pop(k, None)


def _code_eq(expected: str, got: str) -> bool:
    import hmac

    try:
        return hmac.compare_digest(str(expected).encode(), str(got).encode())
    except Exception:
        return False


def admin_otp_generate() -> str:
    return f"{random.randint(0, 999999):06d}"


def dev_admin_otp_bypass_code() -> Optional[str]:
    """非 prod 可选固定码，便于未接主站短信时联调；生产忽略。"""
    if str(settings.env or "").lower() in ("prod", "production"):
        return None
    v = str(settings.admin_otp_dev_code or "").strip()
    return v or None
