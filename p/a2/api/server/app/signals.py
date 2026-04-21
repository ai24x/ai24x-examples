from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


Period = Literal["day", "week", "month"]


@dataclass(frozen=True)
class Candle:
    time: str  # YYYY-MM-DD
    open: float
    close: float
    high: float
    low: float
    vol: float | None = None


def _safe_f(x: Any) -> float | None:
    try:
        if x is None:
            return None
        s = str(x).strip()
        if not s:
            return None
        v = float(s)
        if v != v:  # NaN
            return None
        return v
    except Exception:
        return None


def candles_from_tencent_like_pack(pack: dict[str, Any], period: Period) -> list[Candle]:
    """
    Convert providers.fetch_tx_kline() payload pack rows into Candle list.

    Row format is expected: [day, open, close, high, low, volume]
    """
    key = {"day": "qfqday", "week": "qfqweek", "month": "qfqmonth"}[period]
    rows = pack.get(key)
    if not isinstance(rows, list):
        return []
    out: list[Candle] = []
    for r in rows:
        if not isinstance(r, list) or len(r) < 5:
            continue
        d = str(r[0] or "").strip()
        o = _safe_f(r[1])
        c = _safe_f(r[2])
        h = _safe_f(r[3])
        l = _safe_f(r[4])
        v = _safe_f(r[5]) if len(r) > 5 else None
        if not d or o is None or c is None or h is None or l is None:
            continue
        out.append(Candle(time=d, open=o, close=c, high=h, low=l, vol=v))
    return out


def _sma(closes: list[float], n: int) -> list[float | None]:
    if n <= 0:
        return [None for _ in closes]
    out: list[float | None] = [None for _ in closes]
    s = 0.0
    for i, v in enumerate(closes):
        s += float(v)
        if i >= n:
            s -= float(closes[i - n])
        if i >= n - 1:
            out[i] = s / float(n)
    return out


def _cross_up(a: list[float | None], b: list[float | None], i: int) -> bool:
    if i <= 0:
        return False
    if a[i] is None or b[i] is None or a[i - 1] is None or b[i - 1] is None:
        return False
    return float(a[i]) > float(b[i]) and float(a[i - 1]) <= float(b[i - 1])


def _cross_down(a: list[float | None], b: list[float | None], i: int) -> bool:
    if i <= 0:
        return False
    if a[i] is None or b[i] is None or a[i - 1] is None or b[i - 1] is None:
        return False
    return float(a[i]) < float(b[i]) and float(a[i - 1]) >= float(b[i - 1])


def build_markers_v1(candles: list[Candle]) -> list[dict[str, Any]]:
    """
    MVP markers:
    - buy: MA14 crosses above MA28
    - sell: MA14 crosses below MA28

    Output is compatible with lightweight-charts series.setMarkers([...]).
    """
    if not candles or len(candles) < 60:
        return []
    closes = [c.close for c in candles]
    ma14 = _sma(closes, 14)
    ma28 = _sma(closes, 28)
    markers: list[dict[str, Any]] = []
    for i in range(len(candles)):
        t = candles[i].time
        if _cross_up(ma14, ma28, i):
            markers.append(
                {
                    "time": t,
                    "position": "belowBar",
                    "color": "#ff3d5c",
                    "shape": "arrowUp",
                    "text": "买",
                    "id": f"a2-b-{i}",
                }
            )
        elif _cross_down(ma14, ma28, i):
            markers.append(
                {
                    "time": t,
                    "position": "aboveBar",
                    "color": "#00e68a",
                    "shape": "arrowDown",
                    "text": "卖",
                    "id": f"a2-s-{i}",
                }
            )
    return markers

