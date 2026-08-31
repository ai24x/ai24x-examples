# -*- coding: utf-8 -*-
"""大周期均线公共判定：5/10/20/30/60/144（与 AI 雷达对齐）。

档位：
- S / full   ：短均(5/10/20/30)全部站上 MA60，且 MA60>MA144，MA144 走平向上
- A / medium ：MA20/30>MA60>MA144，MA144 走平向上
- B / lite   ：MA60>MA144，MA144 不走弱（可放宽）

图表信号体系（MA14/28/57）不在此模块，保持独立。
"""
from __future__ import annotations

from typing import Any, Callable, Optional

# 模式别名：雷达用 full/medium/lite，复盘用 S/A/B
_MODE_ALIAS = {
    "full": "full", "s": "full", "strict": "full",
    "medium": "medium", "a": "medium", "balanced": "medium", "standard": "medium",
    "lite": "lite", "loose": "lite", "b": "lite", "weak": "lite",
}

TIER_RANK = {"": 0, "B": 1, "A": 2, "S": 3}
TIER_LABEL = {"S": "趋势最强", "A": "趋势良好", "B": "启动初期", "": ""}


def normalize_mode(mode: str | None) -> str:
    m = str(mode or "medium").strip().lower()
    return _MODE_ALIAS.get(m, "medium")


def _cfg_get(cfg: dict | None, *keys: str, default: Any = None) -> Any:
    if not cfg:
        return default
    for k in keys:
        if k in cfg and cfg[k] is not None:
            return cfg[k]
    return default


def check_big_cycle(
    cfg: dict | None,
    MA: Callable[[int, int], Optional[float]],
    ma5: Optional[float],
    ma10: Optional[float],
    ma20: Optional[float],
    ma30: Optional[float],
    ma60: Optional[float],
    ma144: Optional[float],
    last: int,
    *,
    mode: str | None = None,
) -> tuple[bool, str]:
    """与 radar_screener._check_big_cycle 同口径。

    cfg 兼容键：
      bigCycleMode / big_cycle_mode
      ma144Lookback / ma144_lookback
      ma144FlatPct / ma144_flat_pct
    """
    lookback = int(_cfg_get(cfg, "ma144Lookback", "ma144_lookback", default=5) or 5)
    ma144_prev = MA(144, last - lookback)
    use_mode = normalize_mode(mode or _cfg_get(cfg, "bigCycleMode", "big_cycle_mode", default="medium"))
    if not ma60 or not ma144 or not ma144_prev:
        return False, "均线数据不足"
    if use_mode == "full":
        if not (ma5 and ma10 and ma20 and ma30
                and ma5 > ma60 and ma10 > ma60 and ma20 > ma60 and ma30 > ma60):
            return False, "短均线未全部站上MA60"
        if ma60 <= ma144 or ma144 <= ma144_prev:
            return False, "大周期多头不足"
        return True, ""
    if use_mode == "medium":
        if not (ma20 and ma30 and ma20 > ma60 and ma30 > ma60 and ma60 > ma144):
            return False, "MA20/30未站上MA60"
        ma144_10 = MA(144, last - 10)
        flat = float(_cfg_get(cfg, "ma144FlatPct", "ma144_flat_pct", default=0.998) or 0.998)
        if not (ma144 >= ma144_prev * flat or (ma144_10 and ma144 >= ma144_10 * 0.995)):
            return False, "MA144未走平向上"
        return True, ""
    # lite：允许略松
    flat_lite = float(_cfg_get(cfg, "ma144FlatPct", "ma144_flat_pct", default=0.995) or 0.995)
    if ma60 <= ma144 or ma144 < ma144_prev * flat_lite:
        return False, "MA60/MA144不足"
    return True, ""


def check_big_cycle_values(
    *,
    ma5: float = 0.0,
    ma10: float = 0.0,
    ma20: float = 0.0,
    ma30: float = 0.0,
    ma60: float = 0.0,
    ma144: float = 0.0,
    ma144_prev: float = 0.0,
    ma144_prev10: float = 0.0,
    mode: str = "medium",
    flat_pct: float | None = None,
) -> tuple[bool, str]:
    """无 MA 回调版（复盘 analyze / 日报成分已算好均线时用）。"""
    use_mode = normalize_mode(mode)
    if not ma60 or not ma144 or not ma144_prev:
        # 数据不足时 lite 降级：有 60 且短多即可过 B 档宽松
        if use_mode == "lite" and ma60 and ma20 and ma20 >= ma60 * 0.98:
            return True, ""
        return False, "均线数据不足"
    if use_mode == "full":
        if not (ma5 and ma10 and ma20 and ma30
                and ma5 > ma60 and ma10 > ma60 and ma20 > ma60 and ma30 > ma60):
            return False, "短均线未全部站上MA60"
        if ma60 <= ma144 or ma144 <= ma144_prev:
            return False, "大周期多头不足"
        return True, ""
    if use_mode == "medium":
        if not (ma20 and ma30 and ma20 > ma60 and ma30 > ma60 and ma60 > ma144):
            return False, "MA20/30未站上MA60"
        flat = 0.998 if flat_pct is None else float(flat_pct)
        if not (ma144 >= ma144_prev * flat or (ma144_prev10 and ma144 >= ma144_prev10 * 0.995)):
            return False, "MA144未走平向上"
        return True, ""
    flat = 0.995 if flat_pct is None else float(flat_pct)
    if ma60 <= ma144 or ma144 < ma144_prev * flat:
        # 无 144 历史时：短多贴近 60 视为 B
        if (not ma144_prev) and ma5 > ma10 > ma20 and ma20 >= ma60 * 0.98:
            return True, ""
        return False, "MA60/MA144不足"
    return True, ""


def ma_tier_from_values(
    *,
    ma5: float = 0.0,
    ma10: float = 0.0,
    ma20: float = 0.0,
    ma30: float = 0.0,
    ma60: float = 0.0,
    ma144: float = 0.0,
    ma144_prev: float = 0.0,
    ma144_prev10: float = 0.0,
    n_bars: int = 0,
) -> str:
    """返回 S / A / B / ""。K 线不足 144 时允许降级判定。"""
    kw = dict(
        ma5=ma5, ma10=ma10, ma20=ma20, ma30=ma30, ma60=ma60,
        ma144=ma144, ma144_prev=ma144_prev, ma144_prev10=ma144_prev10,
    )
    # 不足 144：用 60 作长周期锚，最高给到 A（不给 S）
    if n_bars and n_bars < 149:
        if ma5 and ma10 and ma20 and ma30 and ma60 and ma5 > ma60 and ma10 > ma60 and ma20 > ma60 and ma30 > ma60:
            if ma20 > ma30 > 0:
                return "A"
        if ma20 and ma30 and ma60 and ma20 > ma60 and ma30 > ma60:
            return "B"
        if ma5 > ma10 > ma20 and ma20 >= ma60 * 0.98:
            return "B"
        return ""
    ok_s, _ = check_big_cycle_values(mode="full", **kw)
    if ok_s:
        return "S"
    ok_a, _ = check_big_cycle_values(mode="medium", **kw)
    if ok_a:
        return "A"
    ok_b, _ = check_big_cycle_values(mode="lite", **kw)
    if ok_b:
        return "B"
    return ""


def ma_tier_from_closes(closes: list[float]) -> str:
    """从收盘价序列算档位。"""
    n = len(closes)
    if n < 60:
        return ""

    def _ma(p: int, i: int) -> float:
        if i < p - 1 or i < 0 or i >= n:
            return 0.0
        seg = closes[i - p + 1: i + 1]
        return sum(seg) / p if len(seg) == p else 0.0

    last = n - 1
    return ma_tier_from_values(
        ma5=_ma(5, last), ma10=_ma(10, last), ma20=_ma(20, last),
        ma30=_ma(30, last), ma60=_ma(60, last),
        ma144=_ma(144, last) if n >= 144 else 0.0,
        ma144_prev=_ma(144, last - 5) if n >= 149 else 0.0,
        ma144_prev10=_ma(144, last - 10) if n >= 154 else 0.0,
        n_bars=n,
    )


def sector_ma_gate(tiers: list[str], *, for_main: bool = True) -> dict[str, Any]:
    """板块成分档位聚合 → 主线门控。

    主攻主线(for_main=True)：Top 成分中 A+ 达标（≥3 只 A/S，或 ≥2 只 S）
    观察(for_main=False)：≥2 只 B+
    """
    clean = [str(t or "").upper() for t in (tiers or []) if str(t or "").upper() in ("S", "A", "B")]
    n = len(clean)
    n_s = sum(1 for t in clean if t == "S")
    n_a = sum(1 for t in clean if t in ("S", "A"))
    n_b = sum(1 for t in clean if t in ("S", "A", "B"))
    best = ""
    for t in ("S", "A", "B"):
        if t in clean:
            best = t
            break
    if for_main:
        ok = (n_s >= 2) or (n_a >= 3) or (n >= 3 and n_a >= 2 and n_s >= 1)
        # 样本少时放宽：2 只里有 2 只 A+
        if n < 3:
            ok = n_a >= 2 or n_s >= 1
    else:
        ok = n_b >= 2 or n_a >= 1
    return {
        "ok": bool(ok),
        "best": best,
        "n": n,
        "n_s": n_s,
        "n_a": n_a,
        "n_b": n_b,
        "label": TIER_LABEL.get(best, ""),
    }


def strong_event_patterns(patterns: dict | None) -> bool:
    """强事件形态：允许 B 档进入主推（否则主推至少 A）。"""
    p = patterns or {}
    keys = (
        "pullback", "pullback2", "ztPullback", "surgePullback", "eventPullback",
        "firstBoardRight", "surgeStart", "tightZt", "macdFirstRed",
        "washOut", "firstWeek", "ztWeek", "breakout", "tightBurst", "pb45",
    )
    return any(bool(p.get(k)) for k in keys)


def pick_ma_ok(tier: str, patterns: dict | None = None, *, min_tier: str = "A") -> bool:
    """个股主推门槛：无强事件则至少 min_tier；有强事件则 B 也可。"""
    t = str(tier or "").upper()
    need = str(min_tier or "A").upper()
    if strong_event_patterns(patterns):
        return TIER_RANK.get(t, 0) >= TIER_RANK.get("B", 1)
    return TIER_RANK.get(t, 0) >= TIER_RANK.get(need, 2)


def above_ma60_structure(
    *,
    ma5: float = 0.0,
    ma10: float = 0.0,
    ma20: float = 0.0,
    ma30: float = 0.0,
    ma60: float = 0.0,
    ma144: float = 0.0,
    n_bars: int = 0,
) -> bool:
    """用户口径：短均线站上中长均线 MA60（至少）；有 144 时再要求 60≥144*0.998。"""
    if not (ma20 and ma60):
        return False
    short_ok = bool(ma20 > ma60 and (not ma30 or ma30 >= ma60 * 0.995))
    if ma5 and ma10:
        short_ok = short_ok and (ma5 >= ma60 * 0.98) and (ma10 >= ma60 * 0.98)
    if not short_ok:
        return False
    if n_bars >= 144 and ma144:
        return bool(ma60 >= ma144 * 0.998)
    return True


def above_ma144_structure(
    *,
    ma5: float = 0.0,
    ma10: float = 0.0,
    ma20: float = 0.0,
    ma30: float = 0.0,
    ma60: float = 0.0,
    ma144: float = 0.0,
    n_bars: int = 0,
) -> bool:
    """短均（5/10/20/30）站上 MA144；K 线不足 144 时无法判定为 True。"""
    if n_bars and n_bars < 144:
        return False
    if not ma144 or not ma20:
        return False
    short_ok = bool(ma20 > ma144 and (not ma30 or ma30 > ma144 * 0.998))
    if ma5 and ma10:
        short_ok = short_ok and (ma5 >= ma144 * 0.98) and (ma10 >= ma144 * 0.98)
    if not short_ok:
        return False
    # 中长均也尽量在 144 上/贴近，避免短均孤立上冲
    if ma60 and ma60 < ma144 * 0.98:
        return False
    return True


def count_ma60_strong_days(
    closes: list[float],
    *,
    ratio: float = 1.03,
    lookback: int = 25,
) -> int:
    """连续多少日 MA20 明显高于 MA60（默认 ≥3%）。用于 144 过严时的次优强势门。"""
    n = len(closes)
    if n < 60:
        return 0
    last = n - 1
    max_i = min(int(lookback), last - 59)
    if max_i < 1:
        return 0
    days = 0
    for back in range(0, max_i + 1):
        i = last - back
        seg20 = closes[i - 19: i + 1]
        seg60 = closes[i - 59: i + 1]
        if len(seg20) < 20 or len(seg60) < 60:
            break
        m20 = sum(seg20) / 20.0
        m60 = sum(seg60) / 60.0
        if m60 <= 0 or m20 < m60 * float(ratio):
            break
        days += 1
    return days


def ma60_strong_ok(
    *,
    ma5: float = 0.0,
    ma10: float = 0.0,
    ma20: float = 0.0,
    ma30: float = 0.0,
    ma60: float = 0.0,
    strong_days: int = 0,
    min_days: int = 5,
    ratio: float = 1.03,
) -> bool:
    """次优：短均远高于 MA60，且已持续 min_days 日。"""
    if not (ma20 and ma60) or ma60 <= 0:
        return False
    if ma20 < ma60 * float(ratio):
        return False
    if ma30 and ma30 < ma60 * (float(ratio) * 0.99):
        return False
    if ma5 and ma5 < ma60 * 1.01:
        return False
    if ma10 and ma10 < ma60 * 1.01:
        return False
    return int(strong_days or 0) >= int(min_days)


def pick_strong_ok(
    tier: str,
    patterns: dict | None = None,
    *,
    days_since_zt: int | None = None,
    zt_max_days: int = 20,
    require_zt: bool = True,
    above_ma144: bool = False,
    ma60_strong: bool = False,
    prefer_144: bool = True,
) -> bool:
    """主推强势门：优先短均站上144；过严无票时允许「远高于60且持续」。默认还要近期涨停基因。"""
    t = str(tier or "").upper()
    if prefer_144:
        structure_ok = bool(above_ma144) or TIER_RANK.get(t, 0) >= TIER_RANK["S"]
    else:
        structure_ok = bool(ma60_strong) or bool(above_ma144) or TIER_RANK.get(t, 0) >= TIER_RANK["A"]
    if not structure_ok:
        return False
    if not require_zt:
        return True
    if days_since_zt is not None and 0 <= int(days_since_zt) <= int(zt_max_days):
        return True
    p = patterns or {}
    if p.get("ztWeek") or p.get("firstWeek") or p.get("ztPullback") or p.get("tightZt"):
        return True
    if p.get("firstBoardRight") or p.get("pullback2") or p.get("surgeStart"):
        return True
    return False
