from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import math
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


def build_markers_v3_js_port(candles: list[Candle]) -> list[dict[str, Any]]:
    """Server-side port of original `p/a/web/demo.html` leishen markers."""
    if not candles:
        return []
    n = len(candles)
    MA_N1 = 14
    MA_N2 = 28
    MA_N3 = 57
    LS_N4 = 5
    LS_N5 = 10
    LS_N7 = 20
    LS_PERIOD_HIGH = 20

    LS_COL_BUY = "#ff3d5c"
    LS_COL_SELL = "#00e68a"
    LS_COL_RISK = "#ffb300"
    LS_COL_HIGH = "#ff0090"
    LS_COL_BOTTOM = "#38bdf8"
    LS_COL_BOTTOM_HINT = "#22c55e"

    if n < MA_N3 + 5:
        return []

    closes = [float(c.close) for c in candles]
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

    # close position filter
    BOTTOM_RANGE_N = 60
    BOTTOM_MAX_POS = 0.55
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
    CONF_COOLDOWN = 10
    RECLAIM_BAND_PCT = 0.012
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
        above14 = (not _isnan(close)) and (not _isnan(ma1[i])) and close >= ma1[i]
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
        crossDayOk10 = dCand1[i] and stUp510_d1 and above14 and (not _isnan(close)) and (not _isnan(ma5[i])) and close >= ma5[i]
        baseCnt10 = count_closes_below(ma5, i, BASE_LOOKBACK)
        cooldownOk1 = (i - lastConf1) > CONF_COOLDOWN
        windowOk1 = lastCand1 >= 0 and 0 <= (i - lastCand1) <= CONF_WINDOW
        if (
            windowOk1
            and cooldownOk1
            and (not _isnan(low))
            and (not _isnan(close))
            and (not _isnan(ma5[i]))
            and (not _isnan(ma4[i]))
            and ((not REQUIRE_ABOVE_MA14) or above14)
            and (((reclaim10 and (touch10 or dCand1[i])) or crossDayOk10))
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
        futureCrossSoon = False
        for fh in range(1, HINT_LOOKAHEAD + 1):
            if i + fh < n and dCand1[i + fh]:
                futureCrossSoon = True
                break
        hintOk = (
            windowOk1
            and (i - lastHint1) > HINT_COOLDOWN
            and (not _isnan(low))
            and (not _isnan(close))
            and (not _isnan(ma5[i]))
            and (not _isnan(ma4[i]))
            and (not above14)
            and reclaim10
            and (touch10 or dCand1[i] or futureCrossSoon)
            and ma4[i] >= ma5[i]
            and baseCnt10 >= BASE_MIN_BELOW
        )
        if hintOk and (not d1Once[i]):
            d1HintOnce[i] = True
            lastHint1 = i

        # small bottom enhancement
        if (not d1Once[i]) and (i - lastConf1) > CONF_COOLDOWN:
            vNow1 = vols[i]
            vMa20_1 = vol_sma_at(i, 20)
            if (_isnan(vNow1)) or vNow1 <= 0:
                volumeOk1 = True
            else:
                volumeOk1 = (not _isnan(vMa20_1)) and (vNow1 >= vMa20_1 * 1.1) if (not _isnan(vMa20_1)) else True
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
                and ((not REQUIRE_ABOVE_MA14) or above14)
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
            and (i - lastConf2) > CONF_COOLDOWN
            and (not _isnan(low))
            and (not _isnan(close))
            and (not _isnan(ma7[i]))
            and (not _isnan(ma5[i]))
            and ((not REQUIRE_ABOVE_MA14) or above14)
            and (((reclaim20 and touch20) or crossDayOk20))
            and volumeOk2
            and ma5[i] >= ma7[i]
            and count_closes_below(ma7, i, BASE_LOOKBACK + 2) >= (BASE_MIN_BELOW + 1)
        ):
            d2Once[i] = True
            lastConf2 = i

    jc1 = [_cross_up_nan(ma1, ma2, i) for i in range(n)]
    jc3 = [_cross_up_nan(ma2, ma3, i) for i in range(n)]

    # hold confirm
    HOLD_WIN = 3
    d1Keep = d1Once[:]
    d2Keep = d2Once[:]
    for i in range(n):
        if d1Once[i]:
            ok1 = False
            for f1 in range(0, HOLD_WIN):
                if i + f1 >= n:
                    break
                cc1 = closes[i + f1]
                m14 = ma1[i + f1]
                if (not _isnan(cc1)) and (not _isnan(m14)) and cc1 >= m14:
                    ok1 = True
                    break
            if not ok1:
                d1Keep[i] = False
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
    d1Once = d1Keep
    d2Once = d2Keep

    jc1Once = [jc1[i] and not (i > 0 and jc1[i - 1]) for i in range(n)]
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
        t2 = hasBuyPoint2[i] and isRelativeHigh[i] and ma1Decline[i]
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
        cross510[i] and (not (i > 0 and cross510[i - 1])) and (lastRisk1[i] == 9999 or lastRisk1[i] > 20)
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

    def push_dot(idx: int, position: str, color: str, idStr: str, sizeMul: float | None = None) -> None:
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
        }
        markers.append(m)

    def push_arrow(idx: int, position: str, color: str, arrowShape: str, text: str, idStr: str, sizeMul: float | None = None) -> None:
        if idx < 0 or idx >= n or not text:
            return
        m: dict[str, Any] = {
            "time": candles[idx].time,
            "position": position,
            "color": color,
            "shape": arrowShape,
            "text": text,
            "id": idStr,
        }
        if sizeMul is not None and float(sizeMul) != 1.0:
            m["size"] = float(sizeMul)
        markers.append(m)

    def push_pair(idx: int, position: str, color: str, arrowShape: str, label: str, idBase: str, arrSize: float | None = None) -> None:
        push_dot(idx, position, color, idBase + "-0", 0.72)
        push_arrow(idx, position, color, arrowShape, label, idBase + "-1", arrSize if arrSize is not None else 1.06)

    for i in range(n):
        reg = int(regime[i] or 0)
        allowBottomBuy = reg != -1
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
        )

        highBits: list[str] = []
        if allowSellHigh:
            if high2Once[i]:
                highBits.append("顶2")

        allowBuySignal = allowBottomBuy and (jc1Once[i] or closePos[i] <= BUY_MAX_POS)
        buyBits: list[str] = []
        if allowBuySignal:
            if jc1Once[i]:
                buyBits.append("买1")
            if (closePos[i] <= BUY_MAX_POS) and tj3PostOnce[i]:
                buyBits.append("买2")

        sellBits: list[str] = []
        if allowSellHigh:
            if ts1Once[i]:
                sellBits.append("卖1")
            if ts2Once[i]:
                sellBits.append("卖2")

        riskBits: list[str] = []
        if risk1[i]:
            riskBits.append("险1")
        if risk2Once[i]:
            riskBits.append("险2")

        if d1HintOnce[i]:
            push_pair(i, "belowBar", LS_COL_BOTTOM_HINT, "arrowUp", "小底", f"ls-x-{i}", 0.98)
        if allowBottomSignal and (d1Once[i] or d2Once[i]):
            realBottomBits: list[str] = []
            if d1Once[i]:
                realBottomBits.append("底1")
            if d2Once[i]:
                realBottomBits.append("底2")
            dn = len(realBottomBits)
            push_pair(i, "belowBar", LS_COL_BOTTOM, "arrowUp", "·".join(realBottomBits), f"ls-d-{i}", 1.1 if dn > 1 else 1.02)
        if allowBottomBuy and buyBits:
            bn = len(buyBits)
            push_pair(i, "belowBar", LS_COL_BUY, "arrowUp", "·".join(buyBits), f"ls-b-{i}", 1.14 if bn > 1 else 1.08)
        if sellBits:
            sn = len(sellBits)
            push_pair(i, "aboveBar", LS_COL_SELL, "arrowDown", "·".join(sellBits), f"ls-as-{i}", 1.12 if sn > 1 else 1.06)
        if riskBits:
            rn = len(riskBits)
            push_pair(i, "aboveBar", LS_COL_RISK, "arrowDown", "·".join(riskBits), f"ls-ar-{i}", 1.12 if rn > 1 else 1.06)
        if highBits:
            push_pair(i, "aboveBar", LS_COL_HIGH, "arrowDown", "·".join(highBits), f"ls-ah-{i}", 1.06)

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
    return markers


def build_signals_v3(candles: list[Candle]) -> dict[str, Any]:
    """
    Return both markers and per-bar signal labels (barLabels in original JS).
    Shape:
    - markers: lightweight-charts markers
    - bar_labels: list[str|None] aligned to candles index
    """
    if not candles:
        return {"markers": [], "bar_labels": []}

    # Reuse the JS-port implementation flow, but also collect per-bar labels.
    n = len(candles)
    if n < 62:
        return {"markers": [], "bar_labels": [None for _ in range(n)]}

    # We compute markers using the port, but we also need the same intermediate arrays to build labels.
    # To avoid duplicating 600+ lines, we rebuild labels from the returned markers by day index.
    # This keeps frontend behavior (labels are just hints) consistent and stable.

    markers = build_markers_v3_js_port(candles)

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

    return {"markers": markers, "bar_labels": bar_labels}

