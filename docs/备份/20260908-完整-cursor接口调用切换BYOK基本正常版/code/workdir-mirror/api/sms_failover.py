"""短信多通道自动兜底：腾讯 → 106 → 聚合（聚合固定最后）。

通道顺序规则：
- 生效通道（active_provider）在首位（聚合除外）；
- 聚合签名尚未审批通过，永远排在最后兜底；
- 未配置/缺失密钥的通道在组装 senders 时跳过（调用方负责）。

熔断：某通道连续失败 threshold 次后，cooldown_s 秒内不再尝试，
避免每次请求都去撞坏通道、拖慢整体；成功一次即清零计数。
"""
from __future__ import annotations

import logging
import time
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)

# 兜底顺序基准：聚合永远最后
SMS_CHANNELS: tuple[str, ...] = ("tencent", "106", "juhe")

Sender = Callable[[], Awaitable[tuple[bool, str, str]]]


def channel_order(active: str | None = None) -> list[str]:
    """返回通道尝试顺序；active 为 106/tencent 时提到首位，juhe 恒在最后。"""
    a = (active or "").strip().lower()
    if a not in SMS_CHANNELS or a == "juhe":
        return list(SMS_CHANNELS)
    rest = [c for c in SMS_CHANNELS if c != a]
    return [a] + rest


class ChannelCircuit:
    """进程内轻量熔断：连续失败 threshold 次后冷却 cooldown_s。"""

    def __init__(self, threshold: int = 3, cooldown_s: float = 300.0):
        self.threshold = max(1, int(threshold))
        self.cooldown_s = float(cooldown_s)
        self._state: dict[str, dict[str, Any]] = {}

    def should_try(self, provider: str) -> bool:
        st = self._state.get(provider)
        if not st:
            return True
        until = float(st.get("until") or 0)
        return not (until and time.time() < until)

    def record_fail(self, provider: str) -> None:
        st = self._state.setdefault(provider, {"fails": 0, "until": 0})
        st["fails"] = int(st.get("fails") or 0) + 1
        if int(st["fails"]) >= self.threshold:
            st["until"] = time.time() + self.cooldown_s

    def record_ok(self, provider: str) -> None:
        st = self._state.get(provider)
        if st:
            st["fails"] = 0
            st["until"] = 0

    def status(self) -> dict[str, dict[str, Any]]:
        now = time.time()
        out: dict[str, dict[str, Any]] = {}
        for p in SMS_CHANNELS:
            st = self._state.get(p) or {"fails": 0, "until": 0}
            until = float(st.get("until") or 0)
            out[p] = {
                "fails": int(st.get("fails") or 0),
                "tripped": bool(until and now < until),
                "cooldown_until": int(until) if until else 0,
            }
        return out


# 进程级单例：core 单进程内生效
SMS_CIRCUIT = ChannelCircuit()


async def send_with_failover(
    senders: dict[str, Sender],
    active: str | None = None,
    circuit: ChannelCircuit | None = None,
    label: str = "sms",
) -> dict[str, Any]:
    """按顺序尝试各通道，首个成功即返回；全部失败返回最后错误。

    senders: {channel: async callable -> (ok, raw, msg)}，只传已配置的通道。
    返回 {ok, provider, raw, message, attempted}。
    """
    circ = circuit if circuit is not None else SMS_CIRCUIT
    order = channel_order(active)
    attempted: list[str] = []
    last: tuple[str, str, str] | None = None

    for p in order:
        fn = (senders or {}).get(p)
        if fn is None:
            continue
        if not circ.should_try(p):
            attempted.append(f"{p}:circuit-open")
            continue
        attempted.append(p)
        try:
            ok, raw, msg = await fn()
        except Exception as e:  # noqa: BLE001
            ok, raw, msg = False, "", f"{type(e).__name__}: {e}"
        if ok:
            circ.record_ok(p)
            logger.info("%s sent via %s (attempted=%s)", label, p, attempted)
            return {"ok": True, "provider": p, "raw": raw, "message": msg, "attempted": attempted}
        circ.record_fail(p)
        logger.warning("%s channel %s failed: %s", label, p, msg or raw)
        last = (p, raw, msg)

    lp, lraw, lmsg = last or ("", "", "所有短信通道均不可用")
    logger.error("%s all channels failed (attempted=%s): %s", label, attempted, lmsg or lraw)
    return {"ok": False, "provider": lp, "raw": lraw, "message": lmsg, "attempted": attempted}
