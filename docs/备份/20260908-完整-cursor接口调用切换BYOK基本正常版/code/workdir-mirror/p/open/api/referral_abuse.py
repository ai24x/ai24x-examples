"""
邀请注册即时奖励反作弊（进程内；多 worker 不共享，生产可再上 Redis）。

原则：
- 不阻断注册与邀请关系绑定
- 仅限制「双方各 +5000」即时奖励的发放频次
- 绝不涉及 a1 / 行情官
"""
from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock
from typing import Optional

from config import settings

_lock = Lock()
# key -> list of timestamps
_referrer_hits: dict[str, list[float]] = defaultdict(list)
_ip_hits: dict[str, list[float]] = defaultdict(list)

WINDOW_S = 24 * 3600.0


def _limit_referrer() -> int:
    try:
        return max(1, int(getattr(settings, "referral_register_bonus_per_referrer_day", 30) or 30))
    except Exception:
        return 30


def _limit_ip() -> int:
    try:
        return max(1, int(getattr(settings, "referral_register_bonus_per_ip_day", 8) or 8))
    except Exception:
        return 8


def _prune(bucket: list[float], now: float) -> None:
    while bucket and now - bucket[0] > WINDOW_S:
        bucket.pop(0)


def allow_register_invite_bonus(
    *,
    referrer_id: int,
    client_ip: Optional[str] = None,
) -> tuple[bool, str]:
    """
    返回 (允许发即时奖励?, 原因码)。
    """
    now = time.time()
    ip = (client_ip or "unknown").strip()[:64] or "unknown"
    rk = f"r:{int(referrer_id)}"
    with _lock:
        rb = _referrer_hits[rk]
        ib = _ip_hits[ip]
        _prune(rb, now)
        _prune(ib, now)
        if len(rb) >= _limit_referrer():
            return False, "referrer_day_cap"
        if len(ib) >= _limit_ip():
            return False, "ip_day_cap"
        rb.append(now)
        ib.append(now)
        return True, "ok"
