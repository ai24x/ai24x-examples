"""Technical reference levels (ATR-aware) — pure local computation, no LLM.

Supports the "rule-based technical brief" (zero token cost):
- ATR-14 (Wilder) + ATR % of price
- Near support: closest level below price among (recent 5-bar low, MA20, MA60)
- Near resistance: closest level above price among (recent 10-bar high, 60-bar high)
- 52-week position: where the last close sits in the trailing 252-bar range

All output is descriptive ("technical reference levels"), never advice.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def _sma(values: List[float], n: int) -> List[Optional[float]]:
    out: List[Optional[float]] = []
    s = 0.0
    for i, v in enumerate(values):
        s += v
        if i >= n:
            s -= values[i - n]
        out.append(s / n if i >= n - 1 else None)
    return out


def _atr14(highs: List[float], lows: List[float], closes: List[float]) -> Optional[float]:
    """Wilder-smoothed ATR-14 over available history; None if too short."""
    n = len(closes)
    if n < 16:
        return None
    trs: List[float] = []
    for i in range(1, n):
        h, l, pc = highs[i], lows[i], closes[i - 1]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    if len(trs) < 14:
        return None
    atr = sum(trs[:14]) / 14.0
    for i in range(14, len(trs)):
        atr = (atr * 13.0 + trs[i]) / 14.0
    return atr


def _position_pct(closes: List[float], window: int = 252) -> Optional[float]:
    if len(closes) < 2:
        return None
    seg = closes[-window:]
    lo, hi = min(seg), max(seg)
    if hi == lo:
        return 50.0
    return (closes[-1] - lo) / (hi - lo) * 100.0


def compute_key_levels(candles: List[Any]) -> Dict[str, Any]:
    """Return ATR + near support/resistance + 52-week position for a candle list."""
    if not candles or len(candles) < 16:
        return {
            "ok": False,
            "atr": None,
            "atr_pct": None,
            "support": None,
            "resistance": None,
            "dist_support_pct": None,
            "dist_resistance_pct": None,
            "pos_52w_pct": None,
        }
    closes = [float(c.close) for c in candles]
    highs = [float(c.high) for c in candles]
    lows = [float(c.low) for c in candles]
    last = closes[-1]
    atr = _atr14(highs, lows, closes)
    atr_pct = (atr / last * 100.0) if atr and last else None

    ma20 = _sma(closes, 20)[-1]
    ma60 = _sma(closes, 60)[-1]
    hi60 = max(highs[-60:]) if len(highs) >= 60 else max(highs)

    # Near support: closest level below price among candidates
    support_cands = [min(lows[-5:]), ma20, ma60]
    below = [v for v in support_cands if v is not None and v <= last]
    support = max(below) if below else min(lows[-5:])

    # Near resistance: closest level above price among candidates
    res_cands = [max(highs[-10:]), hi60]
    above = [v for v in res_cands if v is not None and v >= last]
    resistance = min(above) if above else max(highs[-10:])

    dist_s = (support / last - 1.0) * 100.0 if support else None
    dist_r = (resistance / last - 1.0) * 100.0 if resistance else None
    pos_52w = _position_pct(closes, 252)

    return {
        "ok": True,
        "atr": round(atr, 4) if atr else None,
        "atr_pct": round(atr_pct, 2) if atr_pct is not None else None,
        "support": round(support, 2) if support else None,
        "resistance": round(resistance, 2) if resistance else None,
        "dist_support_pct": round(dist_s, 2) if dist_s is not None else None,
        "dist_resistance_pct": round(dist_r, 2) if dist_r is not None else None,
        "pos_52w_pct": round(pos_52w, 1) if pos_52w is not None else None,
    }
