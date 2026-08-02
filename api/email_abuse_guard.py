"""
邮箱注册防刷（进程内；多 worker 不共享 — 生产建议换 Redis）。

- 一次性/临时邮箱域名拒绝（可 env 追加）
- 同 IP：最短间隔 + 每小时发送次数帽（与短信防刷同思路）
"""
from __future__ import annotations

import os
import time
from collections import defaultdict

from fastapi import Request

# 常见临时邮箱域名（小写）。正式邮箱误杀极少；可用 TOKEN_EMAIL_DISPOSABLE_EXTRA 追加。
_DISPOSABLE_DOMAINS: frozenset[str] = frozenset(
    {
        "mailinator.com",
        "guerrillamail.com",
        "guerrillamail.net",
        "sharklasers.com",
        "grr.la",
        "guerrillamailblock.com",
        "pokemail.net",
        "spam4.me",
        "yopmail.com",
        "yopmail.fr",
        "trashmail.com",
        "trashmail.me",
        "trashmail.net",
        "tempmail.com",
        "temp-mail.org",
        "tempmailo.com",
        "10minutemail.com",
        "10minutemail.net",
        "minuteinbox.com",
        "moakt.com",
        "dispostable.com",
        "mailnesia.com",
        "maildrop.cc",
        "getnada.com",
        "nada.ltd",
        "emailondeck.com",
        "throwaway.email",
        "fakeinbox.com",
        "mailcatch.com",
        "mytemp.email",
        "tmpmail.org",
        "tmpmail.net",
        "burnermail.io",
        "inboxkitten.com",
        "mailnull.com",
        "spamgourmet.com",
        "discard.email",
        "discardmail.com",
        "mailnesia.com",
        "tempail.com",
        "tempr.email",
        "trash-mail.com",
        "wegwerfmail.de",
        "wegwerfmail.net",
        "jetable.org",
        "spam.la",
        "binkmail.com",
        "bobmail.info",
        "chammy.info",
        "devnullmail.com",
        "mailin8r.com",
        "mailinator2.com",
        "notmailinator.com",
        "reallymymail.com",
        "reconmail.com",
        "safetymail.info",
        "sogetthis.com",
        "spamherelots.com",
        "superrito.com",
        "thisisnotmyrealemail.com",
        "tradermail.info",
        "veryrealemail.com",
        "zippymail.info",
    }
)

_ip_window: dict[str, list[float]] = defaultdict(list)
_ip_last_ts: dict[str, float] = {}
_email_window: dict[str, list[float]] = defaultdict(list)


def client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for") or request.headers.get("X-Forwarded-For")
    if xff:
        part = xff.split(",")[0].strip()
        if part:
            return part
    if request.client and request.client.host:
        return str(request.client.host)
    return "unknown"


def _env_bool(name: str, default: bool = True) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    return raw not in ("0", "false", "no", "off")


def _extra_domains() -> set[str]:
    raw = (os.getenv("TOKEN_EMAIL_DISPOSABLE_EXTRA") or "").strip().lower()
    if not raw:
        return set()
    return {x.strip() for x in raw.replace(";", ",").split(",") if x.strip()}


def email_domain(email: str) -> str:
    em = (email or "").strip().lower()
    if "@" not in em:
        return ""
    return em.rsplit("@", 1)[-1].strip()


def is_test_mailbox(email: str) -> bool:
    em = (email or "").strip().lower()
    return (
        em.endswith(".local")
        or em.endswith("@example.com")
        or em.endswith(".example.com")
    )


def is_disposable_email(email: str) -> bool:
    if not _env_bool("TOKEN_EMAIL_BLOCK_DISPOSABLE", True):
        return False
    if is_test_mailbox(email):
        return False
    dom = email_domain(email)
    if not dom:
        return False
    blocked = _DISPOSABLE_DOMAINS | _extra_domains()
    if dom in blocked:
        return True
    # 二级子域：如 mx.mailinator.com
    parts = dom.split(".")
    if len(parts) >= 3:
        parent = ".".join(parts[-2:])
        if parent in blocked:
            return True
    return False


def _prune(ts_list: list[float], window_s: float) -> None:
    now = time.time()
    cut = now - window_s
    while ts_list and ts_list[0] < cut:
        ts_list.pop(0)


def check_email_send_allowed(
    ip: str,
    email: str,
    *,
    ip_min_interval_s: float = 2.0,
    ip_max_per_hour: int = 30,
    email_max_per_hour: int = 8,
) -> tuple[bool, str]:
    """发验证码前检查。返回 (ok, user_message)。"""
    if is_disposable_email(email):
        return False, "该邮箱暂不支持注册，请使用常用邮箱。"

    now = time.time()
    if ip and ip != "unknown":
        last = _ip_last_ts.get(ip, 0.0)
        if now - last < float(ip_min_interval_s):
            return False, "请求过于频繁，请稍后再试"
        _prune(_ip_window[ip], 3600.0)
        if len(_ip_window[ip]) >= int(ip_max_per_hour):
            return False, "当前网络发送次数过多，请稍后再试"

    em = (email or "").strip().lower()
    _prune(_email_window[em], 3600.0)
    if len(_email_window[em]) >= int(email_max_per_hour):
        return False, "该邮箱验证码发送次数过多，请稍后再试"

    return True, ""


def record_email_send_attempt(ip: str, email: str) -> None:
    now = time.time()
    if ip and ip != "unknown":
        _ip_last_ts[ip] = now
        _ip_window[ip].append(now)
    em = (email or "").strip().lower()
    if em:
        _email_window[em].append(now)


def assert_email_ok_for_register(email: str) -> tuple[bool, str]:
    if is_disposable_email(email):
        return False, "该邮箱暂不支持注册，请使用常用邮箱。"
    return True, ""
