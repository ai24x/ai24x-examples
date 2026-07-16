from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import glob
import json
import math
import os
from typing import Any, Literal

# v1.08: auto-clean old signal caches on import to prevent stale B/S naming
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_CACHE_DIR = os.path.join(_BASE_DIR, "..", "data", "signal_cache")


def _safe_signal_cache_filename(cache_key: str) -> str:
    """
    Windows forbids ':' in filenames. Keys like 'ths:886018_day' used to create an NTFS
    Alternate Data Stream on a zero-byte file named 'ths', corrupting signal locking.
    """
    s = str(cache_key or "").strip()
    for ch in '<>:"/\\|?*':
        s = s.replace(ch, "_")
    s = s.strip(" .")
    return s or "unknown"


try:
    for _f in glob.glob(os.path.join(_CACHE_DIR, "*.json")):
        try:
            _mtime = os.path.getmtime(_f)
            _age_h = (__import__("time").time() - _mtime) / 3600
            if _age_h > 24:  # only clean >24h old to avoid race with active requests
                os.remove(_f)
        except Exception:
            pass
    # Remove legacy NTFS ADS host file created by cache_key containing ':'
    try:
        _ads_host = os.path.join(_CACHE_DIR, "ths")
        if os.path.isfile(_ads_host):
            os.remove(_ads_host)
    except Exception:
        pass
except Exception:
    pass

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
    # Providers in this repo may return either:
    # - qfqday/qfqweek/qfqmonth (legacy)
    # - day/week/month (current tx-like payload)
    key_qfq = {"day": "qfqday", "week": "qfqweek", "month": "qfqmonth"}[period]
    key_plain = {"day": "day", "week": "week", "month": "month"}[period]
    rows = pack.get(key_qfq)
    if rows is None:
        rows = pack.get(key_plain)
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


def rows_from_candles(candles: list[Candle]) -> list[list[str]]:
    """Convert Candle list back to Tencent-like rows: [date, open, close, high, low, vol]."""
    out: list[list[str]] = []
    for c in candles or []:
        try:
            out.append(
                [
                    str(c.time),
                    str(float(c.open)),
                    str(float(c.close)),
                    str(float(c.high)),
                    str(float(c.low)),
                    str(float(c.vol)) if c.vol is not None else "0",
                ]
            )
        except Exception:
            continue
    return out


def _parse_ymd(s: str) -> date | None:
    try:
        s = str(s or "").strip()
        if not s:
            return None
        # Expect YYYY-MM-DD (provider payload).
        y = int(s[0:4])
        m = int(s[5:7])
        d = int(s[8:10])
        return date(y, m, d)
    except Exception:
        return None


def aggregate_daily_to_week(candles: list[Candle]) -> list[Candle]:
    """
    Aggregate daily candles into ISO-week candles.
    - time uses the last trading day in that week (for stable marker alignment).
    """
    if not candles:
        return []
    out: list[Candle] = []
    cur_key: tuple[int, int] | None = None  # (iso_year, iso_week)
    buf: list[Candle] = []

    def flush() -> None:
        nonlocal buf
        if not buf:
            return
        o = buf[0].open
        c = buf[-1].close
        h = max(x.high for x in buf)
        l = min(x.low for x in buf)
        v: float | None = None
        try:
            vs = [x.vol for x in buf if x.vol is not None]
            v = float(sum(vs)) if vs else None
        except Exception:
            v = None
        out.append(Candle(time=buf[-1].time, open=o, close=c, high=h, low=l, vol=v))
        buf = []

    for x in candles:
        dt = _parse_ymd(x.time)
        if dt is None:
            continue
        k = (dt.isocalendar().year, dt.isocalendar().week)
        if cur_key is None:
            cur_key = k
        if k != cur_key:
            flush()
            cur_key = k
        buf.append(x)
    flush()
    return out


def aggregate_daily_to_month(candles: list[Candle]) -> list[Candle]:
    """Aggregate daily candles into month candles; time uses last day in month bucket."""
    if not candles:
        return []
    out: list[Candle] = []
    cur_key: tuple[int, int] | None = None  # (year, month)
    buf: list[Candle] = []

    def flush() -> None:
        nonlocal buf
        if not buf:
            return
        o = buf[0].open
        c = buf[-1].close
        h = max(x.high for x in buf)
        l = min(x.low for x in buf)
        v: float | None = None
        try:
            vs = [x.vol for x in buf if x.vol is not None]
            v = float(sum(vs)) if vs else None
        except Exception:
            v = None
        out.append(Candle(time=buf[-1].time, open=o, close=c, high=h, low=l, vol=v))
        buf = []

    for x in candles:
        dt = _parse_ymd(x.time)
        if dt is None:
            continue
        k = (dt.year, dt.month)
        if cur_key is None:
            cur_key = k
        if k != cur_key:
            flush()
            cur_key = k
        buf.append(x)
    flush()
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


def _nan() -> float:
    return float("nan")


def _isnan(x: float) -> bool:
    return math.isnan(x)


def _atr(closes: list[float], highs: list[float | None], lows: list[float | None], n: int) -> list[float]:
    """Average True Range (Wilder's smoothed). Returns NaN for warmup bars."""
    tr: list[float] = []
    for i in range(len(closes)):
        h = highs[i] if highs[i] is not None and not _isnan(float(highs[i])) else _nan()
        l = lows[i] if lows[i] is not None and not _isnan(float(lows[i])) else _nan()
        prev_c = float(closes[i - 1]) if i > 0 and not _isnan(float(closes[i - 1])) else _nan()
        if _isnan(h) or _isnan(l):
            tr.append(_nan())
        else:
            r1 = h - l
            r2 = abs(h - prev_c) if not _isnan(prev_c) else 0.0
            r3 = abs(l - prev_c) if not _isnan(prev_c) else 0.0
            tr.append(max(r1, r2, r3))
    atr: list[float] = []
    s = 0.0
    for i in range(len(tr)):
        if _isnan(tr[i]):
            atr.append(_nan())
            continue
        if i < n:
            atr.append(_nan())
            s += tr[i]
            if i == n - 1:
                atr[i] = s / n
        else:
            atr.append((atr[i - 1] * (n - 1) + tr[i]) / n)
    return atr


def _sma_nan(closes: list[float], n: int) -> list[float]:
    """JS parity: returns NaN for warmup bars."""
    out = [_nan() for _ in closes]
    if n <= 0:
        return out
    for i in range(n - 1, len(closes)):
        s = 0.0
        for j in range(n):
            s += float(closes[i - j])
        out[i] = s / float(n)
    return out


def _ema_nan(closes: list[float], n: int) -> list[float]:
    """v1.02 EMA: faster response than SMA (~2-3 bars). Warmup uses SMA as seed."""
    alpha = 2.0 / (n + 1)
    out = [_nan() for _ in closes]
    if n <= 0:
        return out
    # Seed first valid bar with SMA
    s = 0.0
    for j in range(n):
        s += float(closes[j])
    out[n - 1] = s / float(n)
    # EMA from then on
    for i in range(n, len(closes)):
        out[i] = float(closes[i]) * alpha + out[i - 1] * (1.0 - alpha)
    return out


def _cross_up_nan(a: list[float], b: list[float], i: int) -> bool:
    if i < 1:
        return False
    if _isnan(a[i]) or _isnan(b[i]) or _isnan(a[i - 1]) or _isnan(b[i - 1]):
        return False
    return a[i] > b[i] and a[i - 1] <= b[i - 1]


def _bars_last_9999(cond: list[bool] | None, i: int) -> int:
    """JS parity: 0 if current True, else distance, else 9999."""
    if i < 0 or not cond:
        return 9999
    if cond[i]:
        return 0
    for k in range(1, i + 1):
        if cond[i - k]:
            return k
    return 9999


def _bar_slast_count(x: list[bool], i: int) -> int:
    """JS parity: consecutive True streak ending at i, else 0."""
    if i < 0 or i >= len(x) or not x[i]:
        return 0
    c = 0
    k = 0
    while i - k >= 0 and x[i - k]:
        c += 1
        k += 1
    return c


def _hhv(arr: list[float], period: int, i: int) -> float:
    start = max(0, i - int(period) + 1)
    mx = float("-inf")
    for k in range(start, i + 1):
        if not _isnan(arr[k]):
            mx = max(mx, float(arr[k]))
    return mx


def _approx_eq(x: float, y: float) -> bool:
    t = (abs(float(x)) + abs(float(y)) + 1.0) * 1e-9
    return abs(float(x) - float(y)) <= t


def _count_true_in_range_js(arr: list[bool], i: int, lookback: int) -> int:
    c = 0
    for k in range(0, int(lookback) + 1):
        j = i - k
        if j < 0:
            break
        if arr[j]:
            c += 1
    return c


def _bars_last(cond: list[bool], i: int) -> int:
    """How many bars since last True (0 means current is True). -1 if never."""
    if i < 0:
        return -1
    for k in range(i, -1, -1):
        if cond[k]:
            return i - k
    return -1


def _count_true_in_range(cond: list[bool], i: int, lookback: int) -> int:
    c = 0
    for k in range(0, lookback + 1):
        j = i - k
        if j < 0:
            break
        if cond[j]:
            c += 1
    return c


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


def _close_pos(closes: list[float], i: int, window: int) -> float:
    """Relative position in recent window: 0 low, 1 high."""
    if i < 0:
        return 0.5
    start = max(0, i - max(1, int(window)) + 1)
    lo = float("inf")
    hi = float("-inf")
    for j in range(start, i + 1):
        v = float(closes[j])
        if v < lo:
            lo = v
        if v > hi:
            hi = v
    if not (lo < float("inf")) or not (hi > float("-inf")) or hi == lo:
        return 0.5
    return (float(closes[i]) - lo) / (hi - lo)


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


def build_markers_v3_js_port(candles: list[Candle], *, cache_key: str = "") -> list[dict[str, Any]]:
    """Server-side port of original `p/a/web/demo.html` leishen markers."""
    if not candles:
        return []
    n = len(candles)
    MA_N1 = 14
    MA_N2 = 28
    MA_N3 = 57
    LS_N4 = 5
    LS_N5 = 10
    LS_N7 = 20  # v1.02: restored from 28 — MA20 spacing critical for dCand2/ts1/顶2 signals
    # v1.04: 双生命线体系 — MA57(主) + MA28(次)
    PRIMARY_LIFE = MA_N3   # 57 — 季度级别，管大趋势方向
    SECONDARY_LIFE = MA_N2  # 28 — 月度级别，管信号时机
    LS_PERIOD_HIGH = 20

    LS_COL_BUY = "#ff3d5c"
    LS_COL_SELL = "#00e68a"
    LS_COL_RISK = "#ffb300"
    LS_COL_HIGH = "#ff0090"
    LS_COL_BOTTOM = "#38bdf8"
    LS_COL_BOTTOM_HINT = "#22c55e"
    LS_COL_TURN = "#00e5ff"        # v1.04: 斜率拐点亮青色

    if n < MA_N3 + 5:
        return []

    closes = [float(c.close) for c in candles]
    highs = [float(c.high) for c in candles]
    lows = [float(c.low) for c in candles]
    vols: list[float] = []
    for c in candles:
        v = c.vol
        if v is None:
            vols.append(_nan())
        else:
            try:
                vv = float(v)
            except Exception:
                vv = _nan()
            vols.append(vv if (vv == vv) else _nan())

    ma1 = _sma_nan(closes, MA_N1)
    ma2 = _sma_nan(closes, MA_N2)
    ma3 = _sma_nan(closes, MA_N3)
    ma4 = _sma_nan(closes, LS_N4)
    ma5 = _sma_nan(closes, LS_N5)
    ma7 = _sma_nan(closes, LS_N7)

    # v1.05: MACD (EMA12-EMA26, DEA=EMA9) — 二重确认，不改变触发条件
    def _ema_nan(src: list[float], period: int) -> list[float]:
        out = [_nan()] * len(src)
        k = 2.0 / (period + 1)
        first = -1
        for i in range(len(src)):
            if _isnan(src[i]):
                continue
            if first < 0:
                first = i
                out[i] = src[i]
            else:
                out[i] = src[i] * k + out[i - 1] * (1 - k)
        return out

    ema12 = _ema_nan(closes, 12)
    ema26 = _ema_nan(closes, 26)
    dif: list[float] = []
    dea: list[float] = []
    macdBar: list[float] = []
    for i in range(n):
        if (not _isnan(ema12[i])) and (not _isnan(ema26[i])):
            dif.append(ema12[i] - ema26[i])
        else:
            dif.append(_nan())
    dea = _ema_nan(dif, 9)
    for i in range(n):
        if (not _isnan(dif[i])) and (not _isnan(dea[i])):
            macdBar.append((dif[i] - dea[i]) * 2)
        else:
            macdBar.append(_nan())

    # MACD 金叉/死叉检测
    macdGoldenCross: list[bool] = [False] * n
    macdDeadCross: list[bool] = [False] * n
    macdBullish: list[int] = [0] * n   # 1=金叉后持续, -1=死叉后持续, 0=无效
    for i in range(1, n):
        if (not _isnan(dif[i])) and (not _isnan(dea[i])) and (not _isnan(dif[i-1])) and (not _isnan(dea[i-1])):
            if dif[i-1] <= dea[i-1] and dif[i] > dea[i]:
                macdGoldenCross[i] = True
            elif dif[i-1] >= dea[i-1] and dif[i] < dea[i]:
                macdDeadCross[i] = True
    # MACD 方向状态（滞后1日，确保非未来数据）
    lastMacdDir = 0
    for i in range(n):
        if macdGoldenCross[i]:
            lastMacdDir = 1
        elif macdDeadCross[i]:
            lastMacdDir = -1
        macdBullish[i] = lastMacdDir if i > 0 else 0

    # regime filter (same as JS)
    REG_SLOPE_LOOKBACK = 6
    REG_FLAT_TH = 0.0015
    regime: list[int] = []
    regSlope28: list[float] = []
    regSlope57: list[float] = []
    for i in range(n):
        cur28 = ma2[i]
        cur57 = ma3[i]
        prev28 = ma2[i - REG_SLOPE_LOOKBACK] if i - REG_SLOPE_LOOKBACK >= 0 else _nan()
        prev57 = ma3[i - REG_SLOPE_LOOKBACK] if i - REG_SLOPE_LOOKBACK >= 0 else _nan()
        if _isnan(cur28) or _isnan(prev28) or prev28 == 0 or _isnan(cur57) or _isnan(prev57) or prev57 == 0:
            regime.append(0)
            regSlope28.append(_nan())
            regSlope57.append(_nan())
            continue
        r28 = (cur28 - prev28) / abs(prev28)
        r57 = (cur57 - prev57) / abs(prev57)
        regSlope28.append(r28)
        regSlope57.append(r57)
        f28 = abs(r28) <= REG_FLAT_TH
        f57 = abs(r57) <= REG_FLAT_TH
        if f28 and f57:
            regime.append(0)
        elif r28 > REG_FLAT_TH and r57 > REG_FLAT_TH:
            regime.append(1)
        elif r28 < -REG_FLAT_TH and r57 < -REG_FLAT_TH:
            regime.append(-1)
        else:
            regime.append(0)

    # v1.04: 双生命线坡度 — 用于判断走平/上拐/下拐状态
    SLOPE_LOOKBACK_5 = 5
    SLOPE_LOOKBACK_10 = 10
    slopeMA28_5: list[float] = []
    slopeMA57_10: list[float] = []
    for i in range(n):
        # MA28 5-bar slope
        if i >= SLOPE_LOOKBACK_5 and (not _isnan(ma2[i])) and (not _isnan(ma2[i - SLOPE_LOOKBACK_5])) and ma2[i - SLOPE_LOOKBACK_5] != 0:
            slopeMA28_5.append((ma2[i] - ma2[i - SLOPE_LOOKBACK_5]) / abs(ma2[i - SLOPE_LOOKBACK_5]))
        else:
            slopeMA28_5.append(_nan())
        # MA57 10-bar slope
        if i >= SLOPE_LOOKBACK_10 and (not _isnan(ma3[i])) and (not _isnan(ma3[i - SLOPE_LOOKBACK_10])) and ma3[i - SLOPE_LOOKBACK_10] != 0:
            slopeMA57_10.append((ma3[i] - ma3[i - SLOPE_LOOKBACK_10]) / abs(ma3[i - SLOPE_LOOKBACK_10]))
        else:
            slopeMA57_10.append(_nan())
    # 斜率阈值：±0.2% ≈ 走平，>0.3% 明确上拐，<-0.3% 明确下拐
    SLOPE_FLAT = 0.002
    SLOPE_BULL = 0.003
    SLOPE_BEAR = -0.003

    # v1.04: MA14 斜率拐点检测 — 灵敏度高于MA28/MA57，适合抄底逃顶
    TURN_UP_TH_14 = 0.002    # MA14 5日斜率突破0.2% = 走平上拐 (灵敏)
    TURN_DN_TH_14 = -0.002   # MA14 5日斜率跌破-0.2% = 走平下拐
    TURN_FLAT_14 = 0.0008    # MA14 "走平"区间 ±0.08%

    slopeMA14_5: list[float] = []
    for i in range(n):
        if i >= SLOPE_LOOKBACK_5 and (not _isnan(ma1[i])) and (not _isnan(ma1[i - SLOPE_LOOKBACK_5])) and ma1[i - SLOPE_LOOKBACK_5] != 0:
            slopeMA14_5.append((ma1[i] - ma1[i - SLOPE_LOOKBACK_5]) / abs(ma1[i - SLOPE_LOOKBACK_5]))
        else:
            slopeMA14_5.append(_nan())

    turnUp14: list[bool] = [False] * n
    turnDn14: list[bool] = [False] * n
    for i in range(1, n):
        s14 = slopeMA14_5[i] if i < len(slopeMA14_5) else _nan()
        s14p = slopeMA14_5[i-1] if i-1 < len(slopeMA14_5) else _nan()
        if (not _isnan(s14p)) and (not _isnan(s14)) and s14p <= TURN_FLAT_14 and s14 > TURN_UP_TH_14:
            turnUp14[i] = True
        if (not _isnan(s14p)) and (not _isnan(s14)) and s14p >= -TURN_FLAT_14 and s14 < TURN_DN_TH_14:
            turnDn14[i] = True

    # close position filter
    BOTTOM_RANGE_N = 60
    BOTTOM_MAX_POS = 0.65
    BUY_MAX_POS = 0.55
    closePos: list[float] = [0.5 for _ in range(n)]
    for i in range(n):
        start = max(0, i - BOTTOM_RANGE_N + 1)
        lo = float("inf")
        hi = float("-inf")
        for t in range(start, i + 1):
            cc = closes[t]
            if math.isnan(cc):
                continue
            lo = min(lo, cc)
            hi = max(hi, cc)
        if not math.isfinite(lo) or not math.isfinite(hi) or hi == lo:
            closePos[i] = 0.5
        else:
            closePos[i] = (closes[i] - lo) / (hi - lo)

    crossM5M10 = [_cross_up_nan(ma4, ma5, i) for i in range(n)]
    crossM10M20 = [_cross_up_nan(ma5, ma7, i) for i in range(n)]
    dCand1 = [crossM5M10[i] and not (i > 0 and crossM5M10[i - 1]) for i in range(n)]
    dCand2 = [crossM10M20[i] and not (i > 0 and crossM10M20[i - 1]) for i in range(n)]

    d1Once = [False] * n
    d2Once = [False] * n
    d1HintOnce = [False] * n
    d1SmallOnce = [False] * n
    d1MainOnce = [False] * n
    d1StrongOnce = [False] * n
    lastCand1 = -9999
    lastCand2 = -9999
    lastConf1 = -9999
    lastConf2 = -9999
    lastHint1 = -9999
    CONF_WINDOW = 10
    # v1.03: ATR-based adaptive cooldown (replaces fixed CONF_COOLDOWN)
    _atr14 = _atr(closes, highs, lows, 14)
    _atr_pct = [(float(_atr14[i]) / float(closes[i]) * 100) if (i < n and not _isnan(_atr14[i]) and closes[i] > 0) else 1.5 for i in range(n)]

    def _cooldown_at(i: int) -> int:
        pct = _atr_pct[i] if i < len(_atr_pct) else 1.5
        # clamp between 6 and 16 days based on volatility
        return max(6, min(16, int(pct * 3.5 + 2)))
    RECLAIM_BAND_PCT = 0.03  # v1.02: widened from 1.2% to 3% for V-bounce capture
    # v1.04: 底信号简化 — 站上MA14 + 有点放量即可
    REQUIRE_ABOVE_MA14 = True
    BASE_LOOKBACK = 6
    BASE_MIN_BELOW = 3

    def count_closes_below(maArr: list[float], end: int, lookback: int) -> int:
        cnt = 0
        for t in range(0, lookback):
            j = end - t
            if j < 0:
                break
            cc = closes[j]
            mm = maArr[j]
            if (not _isnan(cc)) and (not _isnan(mm)) and cc <= mm:
                cnt += 1
        return cnt

    def vol_sma_at(end: int, ln: int) -> float:
        if end < ln - 1:
            return _nan()
        s = 0.0
        ok = 0
        for t2 in range(0, ln):
            vv = vols[end - t2]
            if (not _isnan(vv)) and vv > 0:
                s += vv
                ok += 1
        return (s / ok) if ok >= max(3, int(math.floor(ln * 0.6))) else _nan()

    for i in range(n):
        if dCand1[i]:
            lastCand1 = i
        if dCand2[i]:
            lastCand2 = i
        low = float(candles[i].low)
        close = closes[i]
        reclaim10 = (not _isnan(close)) and (not _isnan(ma5[i])) and close >= ma5[i] and close <= ma5[i] * (1 + RECLAIM_BAND_PCT)
        touch10 = (not _isnan(low)) and (not _isnan(ma5[i])) and low <= ma5[i]
        # v1.04: 双生命线判断
        aboveMA14 = (not _isnan(close)) and (not _isnan(ma1[i])) and close >= ma1[i]
        aboveMA28 = (not _isnan(close)) and (not _isnan(ma2[i])) and close >= ma2[i]
        aboveMA57 = (not _isnan(close)) and (not _isnan(ma3[i])) and close >= ma3[i]
        belowMA28 = (not _isnan(close)) and (not _isnan(ma2[i])) and close < ma2[i]
        belowMA57 = (not _isnan(close)) and (not _isnan(ma3[i])) and close < ma3[i]
        # 四象限：①=双下(深熊) ②=主下次上(熊反弹) ③=主上次下(牛回调) ④=双上(强牛)
        bothBelow = belowMA57 and belowMA28
        primaryBelow = belowMA57 and (not belowMA28)
        bothAbove = aboveMA57 and aboveMA28
        primaryAbove = aboveMA57 and (not aboveMA28)
        # v1.02: golden cross recovery — catch V-bounces within 3 bars of cross
        crossRecovery10 = (
            (i - lastCand1) <= 3 and lastCand1 >= 0
            and aboveMA14 and close >= ma5[i]
            and ma4[i] >= ma5[i]
        )
        stUp510_d1 = (
            i > 0
            and (not _isnan(ma4[i]))
            and (not _isnan(ma5[i]))
            and (not _isnan(ma4[i - 1]))
            and (not _isnan(ma5[i - 1]))
            and ma4[i] >= ma5[i]
            and ma4[i] > ma4[i - 1]
            and ma5[i] > ma5[i - 1]
        )
        crossDayOk10 = dCand1[i] and stUp510_d1 and aboveMA14 and (not _isnan(close)) and (not _isnan(ma5[i])) and close >= ma5[i]
        baseCnt10 = count_closes_below(ma5, i, BASE_LOOKBACK)
        cooldownOk1 = (i - lastConf1) > (_cooldown_at(i) if not crossRecovery10 else 4)
        windowOk1 = lastCand1 >= 0 and 0 <= (i - lastCand1) <= CONF_WINDOW
        # v1.02: d1 buy signals now require volume confirmation (≥20MA * 0.85)
        vNowD1 = vols[i]
        vMa20D1 = vol_sma_at(i, 20)
        volumeOkD1 = (not _isnan(vNowD1)) and vNowD1 > 0 and ((vNowD1 >= vMa20D1 * 0.75) if (not _isnan(vMa20D1)) else True)
        if (
            windowOk1
            and cooldownOk1
            and volumeOkD1
            and (not _isnan(low))
            and (not _isnan(close))
            and (not _isnan(ma5[i]))
            and (not _isnan(ma4[i]))
            and ((not REQUIRE_ABOVE_MA14) or aboveMA14)
            and (((reclaim10 and (touch10 or dCand1[i])) or crossDayOk10 or crossRecovery10 or dCand1[i]))
            and ma4[i] >= ma5[i]
            and baseCnt10 >= BASE_MIN_BELOW
        ):
            d1Once[i] = True
            d1MainOnce[i] = True
            d1StrongOnce[i] = bool(crossDayOk10)
            lastConf1 = i

        # hint small bottom
        HINT_COOLDOWN = 6
        HINT_LOOKAHEAD = 2
        HINT_WINDOW = 25  # v1.02: wider window for hint (EMA shifts golden cross later)
        hintWindowOk = lastCand1 >= 0 and 0 <= (i - lastCand1) <= HINT_WINDOW
        futureCrossSoon = False
        for fh in range(1, HINT_LOOKAHEAD + 1):
            if i + fh < n and dCand1[i + fh]:
                futureCrossSoon = True
                break
        hintOk = (
            hintWindowOk
            and (i - lastHint1) > HINT_COOLDOWN
            and (not _isnan(low))
            and (not _isnan(close))
            and (not _isnan(ma5[i]))
            and (not _isnan(ma4[i]))
            and (not aboveMA14)  # v1.04: hint仅在MA14下方
            and belowMA57  # v1.04: 必须在主生命线下方
            and (i > 0 and (not _isnan(closes[i-1])) and (not _isnan(ma3[i-1])) and closes[i-1] < ma3[i-1])  # 非刚跌破，前日也在MA57下方
            and closePos[i] <= BOTTOM_MAX_POS
            and (close >= ma5[i] * 0.98)  # v1.02: relaxed reclaim (EMA lag-tolerant)
            and (touch10 or dCand1[i] or futureCrossSoon)
            and ma4[i] >= ma5[i]  # v1.04: 必须MA5≥MA10，非死叉区
            and (not turnDn14[i])  # v1.04: 下拐日不出小底（矛盾信号）
            and baseCnt10 >= BASE_MIN_BELOW
        )
        if hintOk and (not d1Once[i]):
            d1HintOnce[i] = True
            lastHint1 = i

        # small bottom enhancement
        if (not d1Once[i]) and (i - lastConf1) > _cooldown_at(i):
            vNow1 = vols[i]
            vMa20_1 = vol_sma_at(i, 20)
            if (_isnan(vNow1)) or vNow1 <= 0:
                volumeOk1 = True
            else:
                volumeOk1 = True if (_isnan(vMa20_1)) else (vNow1 >= vMa20_1 * 1.0)  # v1.02: unified to 1.0x
            downCnt = 0
            for dd in range(1, 6):
                if i - dd < 0:
                    break
                c0 = closes[i - dd]
                c1 = closes[i - dd + 1]
                if (not _isnan(c0)) and (not _isnan(c1)) and c1 < c0:
                    downCnt += 1
            stUp510_1 = (
                i > 0
                and (not _isnan(ma4[i]))
                and (not _isnan(ma5[i]))
                and (not _isnan(ma4[i - 1]))
                and (not _isnan(ma5[i - 1]))
                and ma4[i] >= ma5[i]
                and ma4[i] > ma4[i - 1]
                and ma5[i] > ma5[i - 1]
            )
            stUp510Loose = (
                i > 0
                and (not _isnan(ma4[i]))
                and (not _isnan(ma5[i]))
                and (not _isnan(ma4[i - 1]))
                and (not _isnan(ma5[i - 1]))
                and ma4[i] > ma4[i - 1]
                and ma5[i] >= ma5[i - 1]
            )
            cross514 = _cross_up_nan(ma4, ma1, i) and not (i > 0 and _cross_up_nan(ma4, ma1, i - 1))
            cross510Once = dCand1[i]
            cross510Cnt = 0
            for bk in range(0, 15):
                if i - bk < 0:
                    break
                if dCand1[i - bk]:
                    cross510Cnt += 1
            secondCross510 = cross510Once and cross510Cnt == 2
            lowPosOk = (closePos[i] <= 0.7) if (closePos[i] == closePos[i]) else True
            SMALL_RECLAIM_BAND_PCT = 0.03
            smallReclaim10 = (not _isnan(close)) and (not _isnan(ma5[i])) and close >= ma5[i] and close <= ma5[i] * (1 + SMALL_RECLAIM_BAND_PCT)
            smallOk = (
                lowPosOk
                and volumeOk1
                and downCnt >= 1
                and (((secondCross510 and stUp510_1) or (cross514 and stUp510Loose)))
                and smallReclaim10
                and ((not REQUIRE_ABOVE_MA14) or aboveMA14)
            )
            if smallOk:
                d1Once[i] = True
                d1SmallOnce[i] = True
                lastConf1 = i

        reclaim20 = (not _isnan(close)) and (not _isnan(ma7[i])) and close >= ma7[i] and close <= ma7[i] * (1 + RECLAIM_BAND_PCT)
        touch20 = (not _isnan(low)) and (not _isnan(ma7[i])) and low <= ma7[i]
        stUp510 = (
            i > 0
            and (not _isnan(ma4[i]))
            and (not _isnan(ma5[i]))
            and (not _isnan(ma4[i - 1]))
            and (not _isnan(ma5[i - 1]))
            and ma4[i] >= ma5[i]
            and ma4[i] > ma4[i - 1]
            and ma5[i] > ma5[i - 1]
        )
        crossDayOk20 = dCand2[i] and stUp510 and (not _isnan(close)) and (not _isnan(ma7[i])) and close >= ma7[i]
        vNow = vols[i]
        vMa20 = vol_sma_at(i, 20)
        volumeOk2 = (not _isnan(vNow)) and vNow > 0 and ((vNow >= vMa20 * 1.15) if (not _isnan(vMa20)) else True)
        if (
            lastCand2 >= 0
            and 0 <= (i - lastCand2) <= CONF_WINDOW
            and (i - lastConf2) > _cooldown_at(i)
            and (not _isnan(low))
            and (not _isnan(close))
            and (not _isnan(ma7[i]))
            and (not _isnan(ma5[i]))
            and ((not REQUIRE_ABOVE_MA14) or aboveMA14)
            and (((reclaim20 and touch20) or crossDayOk20))
            and volumeOk2
            and ma5[i] >= ma7[i]
            and count_closes_below(ma7, i, BASE_LOOKBACK + 2) >= (BASE_MIN_BELOW + 1)
        ):
            d2Once[i] = True
            lastConf2 = i

    jc1 = [_cross_up_nan(ma1, ma2, i) for i in range(n)]
    jc3 = [_cross_up_nan(ma2, ma3, i) for i in range(n)]

    # hold confirm (d2 only — d1 already requires close ≥ MA14)
    HOLD_WIN = 3
    d2Keep = d2Once[:]
    for i in range(n):
        if d2Once[i]:
            ok2 = False
            for f2 in range(0, HOLD_WIN):
                if i + f2 >= n:
                    break
                cc2 = closes[i + f2]
                m14_2 = ma1[i + f2]
                if (not _isnan(cc2)) and (not _isnan(m14_2)) and cc2 >= m14_2:
                    ok2 = True
                    break
            if not ok2:
                d2Keep[i] = False
    d2Once = d2Keep

    jc1Once = [jc1[i] and not (i > 0 and jc1[i - 1]) for i in range(n)]
    # v1.03: B1/B2 短周期金叉数组（MA5金叉MA14 / MA5金叉MA20）
    cross514 = [_cross_up_nan(ma4, ma1, i) for i in range(n)]
    cross520 = [_cross_up_nan(ma4, ma7, i) for i in range(n)]
    cross514Once = [cross514[i] and not (i > 0 and cross514[i - 1]) for i in range(n)]
    cross520Once = [cross520[i] and not (i > 0 and cross520[i - 1]) for i in range(n)]
    tj3Post = [jc3[i + 5] if (i + 5) < n else False for i in range(n)]
    tj3PostOnce = [tj3Post[i] and not (i > 0 and tj3Post[i - 1]) for i in range(n)]

    hasBuyPoint2: list[bool] = []
    seen = False
    for i in range(n):
        seen = seen or tj3PostOnce[i]
        hasBuyPoint2.append(seen)

    ma1High = [_hhv(ma1, LS_PERIOD_HIGH, i) for i in range(n)]
    ma2High = [_hhv(ma2, LS_PERIOD_HIGH, i) for i in range(n)]
    condPeak: list[bool] = []
    ma1Peak: list[float] = []
    ma1Decline: list[bool] = []
    isRelativeHigh: list[bool] = []
    for i in range(n):
        h10 = _hhv(ma1, 10, i)
        condPeak.append((not _isnan(ma1[i])) and _approx_eq(ma1[i], h10))
        blP = _bars_last_9999(condPeak, i)
        idx = i - blP
        ma1Peak.append(ma1[idx] if (idx >= 0 and not _isnan(ma1[idx])) else ma1[i])
        m2 = ma2[i]
        decline = (
            (not _isnan(ma1[i]))
            and (not _isnan(m2))
            and m2 != 0
            and ma1[i] < ma1Peak[i]
            and (abs(ma1[i] - m2) / abs(m2) < 0.01)
        )
        ma1Decline.append(bool(decline))
        isRelativeHigh.append(
            (not _isnan(ma1[i]))
            and (not _isnan(m2))
            and (ma1[i] > m2)
            and (ma1[i] > ma1High[i] * 0.9)
            and (m2 > ma2High[i] * 0.9)
        )

    ts2First = [False] * n
    ts2OnceFirst = [False] * n
    for i in range(n):
        t2 = (hasBuyPoint2[i] or closePos[i] >= 0.6) and isRelativeHigh[i] and ma1Decline[i]
        ts2First[i] = t2
        ts2OnceFirst[i] = t2 and not (i > 0 and ts2First[i - 1])

    shiftTs2Once = [False] * n
    for i in range(n):
        shiftTs2Once[i] = (i > 0 and ts2OnceFirst[i - 1])

    lastSell2: list[int] = []
    ts2 = [False] * n
    ts2Once = [False] * n
    for i in range(n):
        bl = _bars_last_9999(shiftTs2Once, i)
        lastSell2.append(bl)
        t2b = ts2First[i] and (bl == 9999 or bl > 5)
        ts2[i] = t2b
        ts2Once[i] = t2b and not (i > 0 and ts2[i - 1])

    cross520 = [_cross_up_nan(ma7, ma4, i) for i in range(n)]
    cross510 = [_cross_up_nan(ma5, ma4, i) for i in range(n)]

    cntCross520 = [_bar_slast_count(cross520, i) for i in range(n)]
    ts1 = [cross520[i] and cntCross520[i] == 1 for i in range(n)]
    ts1Once = [ts1[i] and not (i > 0 and ts1[i - 1]) for i in range(n)]

    zCrossPrev = [(i > 0 and cross510[i - 1]) for i in range(n)]
    lastRisk1 = [_bars_last_9999(zCrossPrev, i) for i in range(n)]
    risk1 = [
        cross510[i] and (not (i > 0 and cross510[i - 1])) and (lastRisk1[i] == 9999 or lastRisk1[i] > 15)
        for i in range(n)
    ]
    lastRisk1Time = [_bars_last_9999(risk1, i) for i in range(n)]
    risk2 = [cross510[i] and (lastRisk1Time[i] > 0 and lastRisk1Time[i] <= 30) for i in range(n)]
    risk2Once = [risk2[i] and not (i > 0 and risk2[i - 1]) for i in range(n)]

    countCross2: list[bool] = []
    for i in range(n):
        ge2 = _count_true_in_range_js(cross520, i, 10) >= 2
        blc = _bars_last_9999(cross520, i)
        countCross2.append(bool(ge2 and blc <= 10))

    HIGH2_COOLDOWN = 12
    high2Once = [False] * n
    lastHigh2 = -9999
    for i in range(n):
        once = countCross2[i] and not (i > 0 and countCross2[i - 1]) and (i - lastHigh2) > HIGH2_COOLDOWN
        high2Once[i] = bool(once)
        if once:
            lastHigh2 = i

    markers: list[dict[str, Any]] = []

    def push_dot(idx: int, position: str, color: str, idStr: str, sizeMul: float | None = None, weight: int = 0) -> None:
        if idx < 0 or idx >= n:
            return
        m: dict[str, Any] = {
            "time": candles[idx].time,
            "position": position,
            "color": color,
            "shape": "circle",
            "text": "\u200b",
            "id": idStr,
            "size": float(sizeMul) if sizeMul is not None else 0.72,
            "weight": weight,
        }
        markers.append(m)

    def push_arrow(idx: int, position: str, color: str, arrowShape: str, text: str, idStr: str, sizeMul: float | None = None, weight: int = 0) -> None:
        if idx < 0 or idx >= n or not text:
            return
        m: dict[str, Any] = {
            "time": candles[idx].time,
            "position": position,
            "color": color,
            "shape": arrowShape,
            "text": text,
            "id": idStr,
            "weight": weight,
        }
        if sizeMul is not None and float(sizeMul) != 1.0:
            m["size"] = float(sizeMul)
        markers.append(m)

    def push_pair(idx: int, position: str, color: str, arrowShape: str, label: str, idBase: str, arrSize: float | None = None, weight: int = 0) -> None:
        push_dot(idx, position, color, idBase + "-0", 0.72, weight)
        push_arrow(idx, position, color, arrowShape, label, idBase + "-1", arrSize if arrSize is not None else 1.06, weight)

    lastBreakdownIdx = -9999
    # v1.03: B1/B2/B3 独立冷却计数
    lastB1Idx = -9999
    lastB2Idx = -9999
    lastB3Idx = -9999
    # v1.04: MA14斜率拐点独立冷却（8天冷却，适合短周期抄底逃顶）
    lastTurn14UpIdx = -9999
    lastTurn14DnIdx = -9999
    # v1.04: 破线信号冷却
    lastBreak28UpIdx = -9999
    for i in range(n):
        reg = int(regime[i] or 0)
        # v1.04: 双生命线位置提前计算（供允许买卖判断用）
        closeV = closes[i]
        aboveMA57_2 = (not _isnan(closeV)) and (not _isnan(ma3[i])) and closeV >= ma3[i]
        aboveMA28_2 = (not _isnan(closeV)) and (not _isnan(ma2[i])) and closeV >= ma2[i]
        belowMA57_2 = (not _isnan(closeV)) and (not _isnan(ma3[i])) and closeV < ma3[i]
        belowMA28_2 = (not _isnan(closeV)) and (not _isnan(ma2[i])) and closeV < ma2[i]
        bothBelowQ = belowMA57_2 and belowMA28_2    # 象限① 深熊
        bothAboveQ = aboveMA57_2 and aboveMA28_2    # 象限④ 强牛
        abovePrimary = aboveMA57_2 and (not aboveMA28_2)  # 主生命线上(顶信号门禁)
        # v1.04: 象限①深熊区突破regime封锁 — 双生命线下方正是抄底时机
        allowBottomBuy = (reg != -1) or aboveMA28_2 or bothBelowQ
        allowSellHigh = reg != 1

        strongBottomException = (reg == -1 and d2Once[i] and (closePos[i] <= 0.25))
        strongSmallBottomException = (
            reg == -1
            and d1SmallOnce[i]
            and (closePos[i] <= 0.7)
            and ((_isnan(regSlope28[i]) or regSlope28[i] > -0.003) or ((not _isnan(regSlope57[i])) and regSlope57[i] > -0.0035))
        )
        strongMainBottomException = reg == -1 and d1MainOnce[i] and (closePos[i] <= 0.7) and ((not _isnan(regSlope57[i])) and regSlope57[i] > -0.0035)
        strongBottomStrongD1Exception = reg == -1 and d1StrongOnce[i] and (closePos[i] <= BOTTOM_MAX_POS)
        SMALL_BOTTOM_MAX_POS = 0.7
        allowBottomSignal = (
            (allowBottomBuy and (closePos[i] <= BOTTOM_MAX_POS or (d1SmallOnce[i] and closePos[i] <= SMALL_BOTTOM_MAX_POS)))
            or strongBottomException
            or strongSmallBottomException
            or strongMainBottomException
            or strongBottomStrongD1Exception
            or (d1MainOnce[i] and closePos[i] <= BOTTOM_MAX_POS and (not _isnan(ma1[i])) and closes[i] >= ma1[i])
        )

        highBits: list[str] = []
        # v1.06: 顶须在主生命线上方，绿线下方不出顶
        if allowSellHigh and (bothAboveQ or abovePrimary):
            if high2Once[i]:
                highBits.append("顶2")

        # v1.04: 双生命线四象限（位置定义已提前，此处只补充过渡区）
        primaryBelowQ = belowMA57_2 and (not belowMA28_2)  # 象限② 熊反弹
        primaryAboveQ = aboveMA57_2 and (not aboveMA28_2)  # 象限③ 牛回调

        # 斜率方向（v1.04）
        slope28 = slopeMA28_5[i] if i < len(slopeMA28_5) else _nan()
        slope57 = slopeMA57_10[i] if i < len(slopeMA57_10) else _nan()
        slopeBullish = (not _isnan(slope28)) and (not _isnan(slope57)) and slope28 > -SLOPE_FLAT and slope57 > -SLOPE_BEAR
        slopeBearish = (not _isnan(slope28)) and (not _isnan(slope57)) and slope28 < SLOPE_FLAT and slope57 < SLOPE_BULL

        buyBits: list[str] = []
        # v1.04: B信号四象限+斜率增强
        if allowBottomBuy and (bothBelowQ or primaryBelowQ):
            signalWeight = 3 if bothBelowQ else 2  # 双下=强, 主下=中
            # 斜率同向增强: 价格在下方 + 斜率走平/上拐 → 反转概率↑
            if bothBelowQ and slopeBullish:
                signalWeight = 4
            # 斜率背离降权: 价格在下方但斜率在下拐 → 可能只是反弹
            if bothBelowQ and (not _isnan(slope57)) and slope57 < SLOPE_BEAR:
                signalWeight = max(1, signalWeight - 1)

            b1Cooldown = (i - lastB1Idx) > _cooldown_at(i) if lastB1Idx >= 0 else True
            b2Cooldown = (i - lastB2Idx) > _cooldown_at(i) if lastB2Idx >= 0 else True
            b3Cooldown = (i - lastB3Idx) > _cooldown_at(i) if lastB3Idx >= 0 else True
            if cross514Once[i] and b1Cooldown:
                buyBits.append("金1")
                lastB1Idx = i
            if cross520Once[i] and b2Cooldown:
                buyBits.append("金2")
                lastB2Idx = i
            if jc1Once[i] and b3Cooldown:
                buyBits.append("金3")
                lastB3Idx = i
        # 买2: different algorithm (price bottom zone + future MA28/MA57 cross prediction)
        if allowBottomBuy and (closePos[i] <= BUY_MAX_POS) and tj3PostOnce[i]:
            buyBits.append("买2")

        # v1.04: MA14斜率拐点 — ↗走平上拐 / ↘走平下拐 特殊箭头
        turnBits: list[str] = []
        TURN_COOLDOWN_14 = 5
        if i - lastTurn14UpIdx > TURN_COOLDOWN_14 if lastTurn14UpIdx >= 0 else True:
            if turnUp14[i]:
                turnBits.append("↗")
                lastTurn14UpIdx = i
        if i - lastTurn14DnIdx > TURN_COOLDOWN_14 if lastTurn14DnIdx >= 0 else True:
            if turnDn14[i]:
                turnBits.append("↘")
                lastTurn14DnIdx = i

        # v1.04: 破线信号 — 放量突破MA28(次生命线)从下方
        breakBits: list[str] = []
        BREAK_COOLDOWN = 10
        if i - lastBreak28UpIdx > BREAK_COOLDOWN if lastBreak28UpIdx >= 0 else True:
            if allowBottomBuy:
                # cross_close_up_ma28: close was < MA28 last bar, now >= MA28
                if (i > 0 and (not _isnan(closes[i-1])) and (not _isnan(ma2[i-1])) and closes[i-1] < ma2[i-1]
                        and aboveMA28_2):
                    vNowBr = vols[i]
                    vMa20Br = vol_sma_at(i, 20)
                    volumeOkBr = (not _isnan(vNowBr)) and vNowBr > 0 and ((vNowBr >= vMa20Br * 1.1) if (not _isnan(vMa20Br)) else True)
                    if volumeOkBr:
                        breakBits.append("底1")
                        lastBreak28UpIdx = i

        sellBits: list[str] = []
        # v1.04: 卖/险信号 — 价格必须在主生命线上方（bothAbove优先）
        hasBuyToday = bool(buyBits or (allowBottomSignal and (d1Once[i] or d2Once[i])))
        isSellValid = allowSellHigh and (bothAboveQ or primaryAboveQ)
        if isSellValid and hasBuyToday:
            isSellValid = False  # buy signals suppress same-day sell
        if isSellValid:
            if ts1Once[i]:
                sellBits.append("卖1")
            if ts2Once[i]:
                sellBits.append("卖2")

        riskBits: list[str] = []
        if risk1[i]:
            riskBits.append("险1")
        if risk2Once[i]:
            riskBits.append("险2")
        # v1.04: 破位 — 价格必须在主生命线上方（双上方）
        breakdownCooldown = (i - lastBreakdownIdx) > 15 if lastBreakdownIdx >= 0 else True
        highBreakdown = (
            cross510[i] and (not (i > 0 and cross510[i - 1]))
            and closePos[i] >= 0.5
            and bothAboveQ
            and breakdownCooldown
        )
        if highBreakdown:
            riskBits.append("破")
            lastBreakdownIdx = i

        # v1.02: 同bar去重 — 卖/险/顶 三者只保留最高severity
        # severity: 顶2 > 卖1+卖2 > 卖1 > 卖2 > 险1+破 > 险1 > 险2 > 破
        def _danger_score(bits: list[str]) -> int:
            s = set(bits)
            score = 0
            if '顶2' in s: score = max(score, 100)
            if '卖1' in s and '卖2' in s: score = max(score, 90)
            if '卖1' in s: score = max(score, 80)
            if '卖2' in s: score = max(score, 70)
            if '险1' in s and '破' in s: score = max(score, 60)
            if '险1' in s: score = max(score, 50)
            if '险2' in s: score = max(score, 40)
            if '破' in s: score = max(score, 30)
            return score
        danger = [(sellBits, _danger_score(sellBits)), (riskBits, _danger_score(riskBits)), (highBits, _danger_score(highBits))]
        danger = [(b, s) for b, s in danger if b]
        if len(danger) > 1:
            danger.sort(key=lambda x: -x[1])
            winner = danger[0][0]
            for b, _ in danger[1:]:
                b.clear()
        # Re-check highBits special case (already in danger list)
        if not highBits:
            pass  # cleared by dedup

        if d1HintOnce[i]:
            push_pair(i, "belowBar", LS_COL_BOTTOM_HINT, "arrowUp", "小底", f"ls-x-{i}", 0.98, 3)
        realBottomBits: list[str] = []
        if allowBottomSignal and (d1Once[i] or d2Once[i]):
            if d1Once[i]:
                realBottomBits.append("底1")
            if d2Once[i]:
                realBottomBits.append("底2")
            dn = len(realBottomBits)
            push_pair(i, "belowBar", LS_COL_BOTTOM, "arrowUp", "·".join(realBottomBits), f"ls-d-{i}", 1.1 if dn > 1 else 1.02, 5 if dn == 1 else 7)
        if allowBottomBuy and buyBits:
            bn = len(buyBits)
            push_pair(i, "belowBar", LS_COL_BUY, "arrowUp", "·".join(buyBits), f"ls-b-{i}", 1.14 if bn > 1 else 1.08, 4 if bn == 1 else 7)
        # v1.04: MA14拐点 — 亮青箭头醒目: ↗belowBar ↘aboveBar
        if turnBits:
            for tb in turnBits:
                if tb == "↗":
                    push_arrow(i, "belowBar", LS_COL_TURN, "arrowUp", tb, f"ls-turn-{i}-up", 1.35, 3)
                else:
                    push_arrow(i, "aboveBar", LS_COL_TURN, "arrowDown", tb, f"ls-turn-{i}-dn", 1.35, 3)
        # v1.04: 破线信号 — 用底1标签+底颜色
        # 去重：如果 realBottomBits 已有"底1"，则 breakBits 中的"底1"跳过（避免同一根K线两个底1）
        if breakBits:
            dedupBreakBits = [b for b in breakBits if b not in realBottomBits]
            if dedupBreakBits:
                push_pair(i, "belowBar", LS_COL_BOTTOM, "arrowUp", "·".join(dedupBreakBits), f"ls-break-{i}", 1.02, 5)
        if sellBits:
            sn = len(sellBits)
            push_pair(i, "aboveBar", LS_COL_SELL, "arrowDown", "·".join(sellBits), f"ls-as-{i}", 1.12 if sn > 1 else 1.06, 3)
        if riskBits:
            rn = len(riskBits)
            push_pair(i, "aboveBar", LS_COL_RISK, "arrowDown", "·".join(riskBits), f"ls-ar-{i}", 1.12 if rn > 1 else 1.06, 2)
        if highBits:
            push_pair(i, "aboveBar", LS_COL_HIGH, "arrowDown", "·".join(highBits), f"ls-ah-{i}", 1.06, 2)

        # v1.05: MACD 金叉/死叉 — 仅通过 macd_json 传给前端渲染在 MACD 副图上
        # K线上不重复显示，避免信号过载

    # v1.05: MACD 增强 — 同向信号加权重（仅对B信号改颜色，不覆盖底信号的蓝色）
    for m in markers:
        t = m.get("time", "")
        mid = str(m.get("id", ""))
        for j in range(n):
            if candles[j].time == t and m.get("position") == "belowBar" and macdGoldenCross[j]:
                m["weight"] = (m.get("weight") or 0) + 1
                # 只对B信号(金叉)加亮红色，底/小底保持原有颜色
                if mid.startswith("ls-b-"):
                    m["color"] = "#ff1744"
            elif candles[j].time == t and m.get("position") == "aboveBar" and macdDeadCross[j]:
                m["weight"] = (m.get("weight") or 0) + 1
                # 只对卖信号(死叉)加亮绿色，险/顶保持原有颜色
                if mid.startswith("ls-as-"):
                    m["color"] = "#00e676"

    def lane(mid: Any) -> int:
        s = str(mid)
        if s.startswith("ls-d-"):
            return 0
        if s.startswith("ls-x-"):
            return 1
        if s.startswith("ls-b-"):
            return 2
        if s.startswith("ls-as-"):
            return 3
        if s.startswith("ls-ah-"):
            return 5
        if s.startswith("ls-ar-"):
            return 6
        if s.startswith("ls-turn-"):
            return 7
        if s.startswith("ls-break-"):
            return 8
        if s.startswith("ls-macd-"):
            return 0  # 最底层，不影响其他信号
        return 9

    def time_key(t: Any) -> str:
        return str(t or "")

    markers.sort(
        key=lambda m: (
            time_key(m.get("time")),
            0 if m.get("position") == "belowBar" else 1,
            lane(m.get("id")),
            str(m.get("id")),
        )
    )
    # v1.02: signal locking — freeze markers >5 bars old
    # CACHE_VERSION: bump when algorithm OR cache filename scheme changes
    CACHE_VERSION = 5
    if cache_key and len(candles) > 10:
        LOCK_BARS = 5
        freeze_cutoff = candles[-LOCK_BARS - 1].time if len(candles) > LOCK_BARS else ""
        range_t0 = str(candles[0].time)
        range_t1 = str(candles[-1].time)
        try:
            cache_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "signal_cache")
            os.makedirs(cache_dir, exist_ok=True)
            safe_name = _safe_signal_cache_filename(cache_key)
            cache_path = os.path.join(cache_dir, f"{safe_name}.json")
            cache_exists = os.path.exists(cache_path)
            if cache_exists:
                try:
                    with open(cache_path, "r", encoding="utf-8") as fh:
                        cached = json.load(fh)
                except Exception:
                    cached = {}
                # Auto-invalidate if cache version mismatches
                if int(cached.get("v", 0)) != CACHE_VERSION:
                    cached = {}
                # Rolling window: drop locked markers outside current candle range
                if cached.get("markers"):
                    locked = []
                    seen_times = set()
                    for mk in cached.get("markers", []):
                        t = str(mk.get("time") or "")
                        if not t or t < range_t0 or t > range_t1:
                            continue
                        if t < freeze_cutoff:
                            locked.append(mk)
                            seen_times.add(t + str(mk.get("id") or ""))
                    for mk in markers:
                        t = str(mk.get("time") or "")
                        key2 = t + str(mk.get("id") or "")
                        if t >= freeze_cutoff and key2 not in seen_times:
                            locked.append(mk)
                    markers = locked
            # Save current markers for next time
            try:
                with open(cache_path, "w", encoding="utf-8") as fh:
                    json.dump(
                        {
                            "v": CACHE_VERSION,
                            "markers": markers,
                            "ts": range_t1,
                            "t0": range_t0,
                        },
                        fh,
                        ensure_ascii=False,
                    )
            except Exception:
                pass
        except Exception:
            pass
    return markers, dif, dea, macdBar, macdGoldenCross, macdDeadCross


def build_signals_v3(candles: list[Candle], *, cache_key: str = "") -> dict[str, Any]:
    """
    Return both markers and per-bar signal labels (barLabels in original JS).
    Shape:
    - markers: lightweight-charts markers
    - bar_labels: list[str|None] aligned to candles index
    """
    if not candles:
        return {"markers": [], "bar_labels": [], "macd": []}

    # Reuse the JS-port implementation flow, but also collect per-bar labels.
    n = len(candles)
    if n < 62:
        return {"markers": [], "bar_labels": [None for _ in range(n)], "macd": []}

    # We compute markers using the port, but we also need the same intermediate arrays to build labels.
    # To avoid duplicating 600+ lines, we rebuild labels from the returned markers by day index.
    # This keeps frontend behavior (labels are just hints) consistent and stable.

    markers, dif_arr, dea_arr, macd_bar_arr, macd_golden, macd_dead = build_markers_v3_js_port(candles, cache_key=cache_key)

    # Build MACD timeseries for frontend sub-chart
    n_macd = len(candles)
    macd_json: list[dict[str, Any]] = []
    for i in range(n_macd):
        t = str(candles[i].time)
        d = dif_arr[i] if i < len(dif_arr) else None
        e = dea_arr[i] if i < len(dea_arr) else None
        b = macd_bar_arr[i] if i < len(macd_bar_arr) else None
        if d is not None and d == d and e is not None and e == e:
            entry = {"time": t, "dif": round(float(d), 4), "dea": round(float(e), 4), "bar": round(float(b if b == b else 0), 4)}
            if i < len(macd_golden) and macd_golden[i]:
                entry["golden_cross"] = True
            if i < len(macd_dead) and macd_dead[i]:
                entry["dead_cross"] = True
            macd_json.append(entry)

    # Map timeKey -> idx for label alignment
    idx_by_time: dict[str, int] = {}
    for i, c in enumerate(candles):
        idx_by_time[str(c.time)] = i

    bar_labels: list[str | None] = [None for _ in range(n)]

    # collect bits per bar
    bottom_bits: list[list[str]] = [[] for _ in range(n)]
    buy_bits: list[list[str]] = [[] for _ in range(n)]
    sell_bits: list[list[str]] = [[] for _ in range(n)]
    risk_bits: list[list[str]] = [[] for _ in range(n)]
    high_bits: list[list[str]] = [[] for _ in range(n)]

    def add_bit(arr: list[list[str]], i: int, txt: str) -> None:
        if 0 <= i < n and txt and txt not in arr[i]:
            arr[i].append(txt)

    for m in markers:
        t = str(m.get("time") or "")
        i = idx_by_time.get(t, -1)
        if i < 0:
            continue
        mid = str(m.get("id") or "")
        txt = str(m.get("text") or "")
        # ignore dot markers (text is zero-width space)
        if txt == "\u200b" or txt == "":
            continue
        # Normalize: sometimes multiple bits in one label separated by ·
        parts = [p for p in txt.split("·") if p]
        if mid.startswith("ls-x-"):
            for p in parts:
                add_bit(bottom_bits, i, p)
        elif mid.startswith("ls-d-"):
            for p in parts:
                add_bit(bottom_bits, i, p)
        elif mid.startswith("ls-b-"):
            for p in parts:
                add_bit(buy_bits, i, p)
        elif mid.startswith("ls-as-"):
            for p in parts:
                add_bit(sell_bits, i, p)
        elif mid.startswith("ls-ar-"):
            for p in parts:
                add_bit(risk_bits, i, p)
        elif mid.startswith("ls-ah-"):
            for p in parts:
                add_bit(high_bits, i, p)

    for i in range(n):
        rem_parts: list[str] = []
        if bottom_bits[i]:
            rem_parts.append("·".join(bottom_bits[i]))
        if buy_bits[i]:
            rem_parts.append("·".join(buy_bits[i]))
        if sell_bits[i]:
            rem_parts.append("·".join(sell_bits[i]))
        if risk_bits[i]:
            rem_parts.append("·".join(risk_bits[i]))
        if high_bits[i]:
            rem_parts.append("·".join(high_bits[i]))
        bar_labels[i] = ("　".join(rem_parts)) if rem_parts else None

    return {"markers": markers, "bar_labels": bar_labels, "macd": macd_json}

