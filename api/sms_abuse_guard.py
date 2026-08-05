"""
短信发送防刷（进程内，多 worker 不共享 — 生产请换 Redis + 全局限流网关）。

策略摘要：
- 同一 IP：最短间隔内不允许连续请求；滑动窗口内每小时最多 N 次「进入发送逻辑」。
- 同一手机号：滑动 1 小时内最多 M 次成功进入发送逻辑（与 60s 冷却叠加）。
"""

from __future__ import annotations

import time
from collections import defaultdict

from security_util import client_ip as client_ip  # noqa: F401 — 统一 X-Real-IP / XFF 右段

_phone_window: dict[str, list[float]] = defaultdict(list)
_ip_window: dict[str, list[float]] = defaultdict(list)
_ip_last_ts: dict[str, float] = {}


def _prune(ts_list: list[float], window_s: float) -> None:
    now = time.time()
    cut = now - window_s
    while ts_list and ts_list[0] < cut:
        ts_list.pop(0)


def check_before_send(
    ip: str,
    phone: str,
    *,
    ip_min_interval_s: float,
    ip_max_per_hour: int,
    phone_max_per_hour: int,
) -> tuple[bool, str]:
    now = time.time()
    if ip and ip != "unknown":
        last = _ip_last_ts.get(ip, 0.0)
        if now - last < float(ip_min_interval_s):
            return False, "请求过于频繁，请稍后再试"
        _prune(_ip_window[ip], 3600.0)
        if len(_ip_window[ip]) >= int(ip_max_per_hour):
            return False, "当前网络发送次数过多，请稍后再试"

    _prune(_phone_window[phone], 3600.0)
    if len(_phone_window[phone]) >= int(phone_max_per_hour):
        return False, "该号码验证短信发送次数过多，请稍后再试或联系客服"

    return True, ""


def record_attempt(ip: str, phone: str) -> None:
    """在即将调用短信网关前调用（无论网关是否返回成功）。"""
    now = time.time()
    if ip and ip != "unknown":
        _ip_last_ts[ip] = now
        _ip_window[ip].append(now)
    _phone_window[phone].append(now)
