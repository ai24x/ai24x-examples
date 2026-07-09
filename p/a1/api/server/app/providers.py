from __future__ import annotations

import asyncio
import json
import re
import time
from datetime import datetime
from urllib.parse import quote as _urlquote
from typing import Any, Dict, Optional, Tuple

import httpx

from .config import settings
from . import db

# Redis cache layer (optional, graceful degradation)
_redis: Any = None
_redis_init_attempted: bool = False
_REDIS_PREFIX: str = "kline:"


def _redis_client() -> Any:
    """Lazy-init Redis client. Returns None if unavailable."""
    global _redis, _redis_init_attempted
    if _redis_init_attempted:
        return _redis
    _redis_init_attempted = True
    redis_url = str(getattr(settings, "redis_url", "") or "").strip()
    if not redis_url:
        return None
    try:
        import redis as _redis_mod  # type: ignore
        _redis = _redis_mod.from_url(redis_url, socket_connect_timeout=2, socket_timeout=2)
        _redis.ping()
        return _redis
    except Exception:
        _redis = None
        return None


def _redis_cache_key(secid: str, period: str, count: int) -> str:
    return _REDIS_PREFIX + "|".join([str(secid), str(period), str(count)])


EM_SUGGEST = "https://searchadapter.eastmoney.com/api/suggest/get"
EM_PLATE_KLINE = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
TX_FQ = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
SINA_KLINE = "https://quotes.sina.cn/cn/api/json_v2.php/CN_MarketDataService.getKLineData"

# Simple in-memory cache to reduce upstream pressure & avoid repeated rate-limit hits.
# key: (variant, secid, period, count) -> (expire_ts, payload)
_KLINE_CACHE: dict[Tuple[str, str, str, int], Tuple[float, Dict[str, Any]]] = {}

_TX_FAILS: list[int] = []
_TX_OPEN_UNTIL: int = 0

# lightweight source health snapshot for ops visibility
_SRC: dict[str, dict[str, Any]] = {}

# route hit counters for ops visibility (best-effort)
_ROUTE: dict[str, dict[str, Any]] = {}

# singleflight: collapse concurrent identical upstream fetches (burst protection)
_KLINE_INFLIGHT: dict[Tuple[str, str, str, int], asyncio.Task[Dict[str, Any]]] = {}
_KLINE_INFLIGHT_LOCK = asyncio.Lock()

# Admin runtime config cache (MVP): allow switching paid provider/priority without redeploy.
_ADMIN_CONF: dict[str, str] | None = None
_ADMIN_CONF_EXP: float = 0.0


def _admin_conf_get_all(ttl_s: float = 5.0) -> dict[str, str]:
    global _ADMIN_CONF, _ADMIN_CONF_EXP
    now = time.time()
    if _ADMIN_CONF is not None and _ADMIN_CONF_EXP > now:
        return _ADMIN_CONF
    try:
        _ADMIN_CONF = db.admin_config_get_all()
    except Exception:
        _ADMIN_CONF = {}
    _ADMIN_CONF_EXP = now + float(ttl_s)
    return _ADMIN_CONF


def _admin_conf_get(key: str, default: str = "") -> str:
    return str(_admin_conf_get_all().get(str(key), default))


def _effective_paid_provider() -> str:
    # admin override wins; fallback to env settings
    v = _admin_conf_get("paid_provider", "").strip().lower()
    if v:
        return v
    return str(getattr(settings, "paid_provider", "off") or "off").strip().lower()


def _effective_priority() -> str:
    v = _admin_conf_get("paid_provider_priority", "").strip().lower()
    if v:
        return v
    return str(getattr(settings, "paid_provider_priority", "") or "").strip().lower()


def _effective_tushare_use_rt_k() -> bool:
    v = _admin_conf_get("tushare_use_rt_k", "").strip().lower()
    if v:
        return v not in ("0", "false", "no", "off", "")
    return bool(getattr(settings, "tushare_use_rt_k", False))


def _effective_tushare_token() -> str:
    v = _admin_conf_get("tushare_token", "").strip()
    if v and v != "***":
        return v
    return str(getattr(settings, "tushare_token", "") or "").strip()


def _effective_paid_vip_only() -> bool:
    v = _admin_conf_get("paid_vip_only", "").strip().lower()
    if v:
        return v not in ("0", "false", "no", "off", "")
    # default: off
    return False


def _src_ok(name: str, ms: float) -> None:
    s = _SRC.setdefault(str(name), {"ok": 0, "fail": 0, "last_ok": None, "last_fail": None, "avg_ms": None})
    s["ok"] = int(s.get("ok") or 0) + 1
    s["last_ok"] = int(time.time())
    prev = s.get("avg_ms")
    try:
        s["avg_ms"] = float(ms) if prev is None else (float(prev) * 0.8 + float(ms) * 0.2)
    except Exception:
        pass


def _src_fail(name: str, ms: float, reason: str | None = None) -> None:
    s = _SRC.setdefault(str(name), {"ok": 0, "fail": 0, "last_ok": None, "last_fail": None, "avg_ms": None})
    s["fail"] = int(s.get("fail") or 0) + 1
    s["last_fail"] = int(time.time())
    if reason:
        s["last_reason"] = str(reason)[:200]
    prev = s.get("avg_ms")
    try:
        s["avg_ms"] = float(ms) if prev is None else (float(prev) * 0.8 + float(ms) * 0.2)
    except Exception:
        pass


def _route_hit(source: str) -> None:
    try:
        s = str(source or "unknown")
        r = _ROUTE.setdefault(s, {"hits": 0, "last_ts": None})
        r["hits"] = int(r.get("hits") or 0) + 1
        r["last_ts"] = int(time.time())
    except Exception:
        pass


def market_data_status() -> dict[str, Any]:
    return {
        "tencent": {"circuit_open_until": int(_TX_OPEN_UNTIL) if _TX_OPEN_UNTIL else 0, "fails_60s": int(len(_TX_FAILS))},
        "sources": _SRC,
        "cache": {"mem_entries": int(len(_KLINE_CACHE)), "ttl_s": float(getattr(settings, "kline_cache_ttl_s", 30.0))},
        "paid": {
            "provider": _effective_paid_provider(),
            "priority": _effective_priority(),
            "tushare_use_rt_k": bool(_effective_tushare_use_rt_k()),
            "tushare_token_set": bool(_effective_tushare_token()),
            "vip_only": bool(_effective_paid_vip_only()),
        },
        "route": _ROUTE,
    }


def _paid_enabled() -> bool:
    v = _effective_paid_provider()
    return v not in ("", "off", "0", "false", "none")


async def fetch_paid_kline(secid: str, period: str, count: int = 500, timeout: float = 10.0) -> Dict[str, Any]:
    """
    Reserved extension point for paid providers (e.g., jqdata / gm).
    Default implementation is disabled unless AI24X_PAID_PROVIDER is set.

    Contract: return Tencent-like payload shape so frontend can reuse existing parsing.
    """
    if not _paid_enabled():
        return {"code": -1, "msg": "paid provider disabled", "data": {}}
    provider = _effective_paid_provider()
    if provider in ("tushare", "ts"):
        return await fetch_tushare_kline(secid, period, count=count, timeout=timeout)
    return {"code": -1, "msg": f"paid provider not implemented: {provider}", "data": {}}


def _secid_to_tushare_ts_code(secid: str) -> str | None:
    """
    Convert internal secid (e.g. 1.600000 / 0.000001 / 0.430047) to TuShare ts_code.
    Returns None for non-stock (e.g. 90.BKxxxx plates).
    """
    s = str(secid).strip()
    # THS plate secid (ths:88397 etc.) — not a stock, handled by ths_daily path
    if s.lower().startswith(("ths:", "ths.")):
        return None
    if is_em_plate_secid(s):
        return None
    parts = s.split(".")
    if len(parts) != 2:
        return None
    market, code = parts[0].strip(), parts[1].strip()
    if not re.fullmatch(r"\d{6}", code or ""):
        return None
    # BSE: TuShare uses .BJ suffix for 8/4/9? but practical is 43/83/87/88/92/89... We'll follow our own bj heuristic.
    if code.startswith("92") or re.fullmatch(r"89\d{4}", code) or code.startswith(("43", "83", "87", "88")):
        return f"{code}.BJ"
    if market == "1":
        return f"{code}.SH"
    return f"{code}.SZ"


def _tencent_rows_from_tushare_daily(df: Any) -> list[list[str]]:
    """
    Map TuShare daily DataFrame -> Tencent row format:
    [date, open, close, high, low, vol]
    """
    try:
        # Expect columns: trade_date(YYYYMMDD), open, high, low, close, vol
        if df is None or getattr(df, "empty", False):
            return []
        out: list[list[str]] = []
        # TuShare usually returns newest first; we want oldest -> newest
        for _, r in df.sort_values("trade_date", ascending=True).iterrows():  # type: ignore[attr-defined]
            d = str(r.get("trade_date", "")).strip()
            if len(d) == 8 and d.isdigit():
                d = f"{d[0:4]}-{d[4:6]}-{d[6:8]}"
            o = str(r.get("open", "")).strip()
            c = str(r.get("close", "")).strip()
            h = str(r.get("high", "")).strip()
            l = str(r.get("low", "")).strip()
            v = str(r.get("vol", "")).strip()
            if not d:
                continue
            out.append([d, o, c, h, l, v])
        return out
    except Exception:
        return []


def _maybe_append_today_placeholder(rows: list[list[str]]) -> tuple[list[list[str]], bool]:
    """
    Best-effort: some paid datasets (e.g. ths_daily/index_daily) may lag intraday and not include today's bar.
    To keep UX consistent, append a synthetic "today" row when:
    - today is a weekday (Mon-Fri)
    - local time is after market close (>=15:10). We intentionally DO NOT synthesize an intraday "today" daily bar,
      because it looks like "0 volume / yesterday close" and is confusing for users expecting real intraday updates.
    - last row date < today
    The synthetic bar uses last close as O/H/L/C and vol=0.
    """
    try:
        if not rows:
            return rows, False
        now = datetime.now()
        # Mon=0 ... Sun=6
        if now.weekday() >= 5:
            return rows, False
        hhmm = now.strftime("%H%M")
        if hhmm < "1510":
            return rows, False
        today = now.strftime("%Y-%m-%d")
        last = rows[-1]
        if not last or len(last) < 6:
            return rows, False
        last_day = str(last[0]).strip()
        if last_day >= today:
            return rows, False
        last_close = str(last[2]).strip()
        if not last_close:
            return rows, False
        syn = [today, last_close, last_close, last_close, last_close, "0"]
        return rows + [syn], True
    except Exception:
        return rows, False


def _rt_k_aggregate_to_today_bar(df: Any) -> list[str] | None:
    """
    Aggregate TuShare pro.rt_k intraday bars into one "today" day bar:
    [YYYY-MM-DD, open, close, high, low, vol]
    Return None if not available.
    """
    try:
        if df is None or getattr(df, "empty", False):
            return None
        # Determine date column
        cols = set([str(c) for c in getattr(df, "columns", [])])
        date_col = None
        for c in ("trade_date", "date", "day"):
            if c in cols:
                date_col = c
                break
        # rt_k often doesn't include trade_date; derive from time-like column if present
        if date_col is None:
            for c in ("trade_time", "time", "datetime"):
                if c in cols:
                    date_col = c
                    break
        if date_col is None:
            return None

        # Normalize today's date
        today = datetime.now().strftime("%Y-%m-%d")

        def _row_date(v: Any) -> str:
            s = str(v or "").strip()
            if not s:
                return ""
            # formats: YYYYMMDD / YYYY-MM-DD / YYYY-MM-DD HH:MM:SS / YYYYMMDDHHMMSS
            if len(s) >= 8 and s[:8].isdigit():
                ymd = s[:8]
                return f"{ymd[0:4]}-{ymd[4:6]}-{ymd[6:8]}"
            if len(s) >= 10 and s[4] == "-" and s[7] == "-":
                return s[:10]
            return ""

        # Filter rows for today
        rows = []
        for _, r in df.iterrows():  # type: ignore[attr-defined]
            d = _row_date(r.get(date_col, ""))
            if d == today:
                rows.append(r)
        if not rows:
            return None

        # Extract numeric fields
        def f(x: Any) -> float:
            try:
                return float(x)
            except Exception:
                return float("nan")

        opens = [f(r.get("open")) for r in rows]
        highs = [f(r.get("high")) for r in rows]
        lows = [f(r.get("low")) for r in rows]
        closes = [f(r.get("close")) for r in rows]
        vols = [f(r.get("vol", r.get("volume", 0))) for r in rows]

        # Use first/last non-NaN semantics
        def first_valid(xs: list[float]) -> float | None:
            for x in xs:
                if x == x and x > 0:
                    return x
            return None

        def last_valid(xs: list[float]) -> float | None:
            for x in reversed(xs):
                if x == x and x > 0:
                    return x
            return None

        o = first_valid(opens)
        c = last_valid(closes)
        h = max([x for x in highs if x == x and x > 0], default=float("nan"))
        l = min([x for x in lows if x == x and x > 0], default=float("nan"))
        v = sum([x for x in vols if x == x and x >= 0], 0.0)
        if o is None or c is None or not (h == h and l == l):
            return None
        if not (h >= max(o, c) and l <= min(o, c)):
            return None
        return [today, f"{o}", f"{c}", f"{h}", f"{l}", f"{v}"]
    except Exception:
        return None

def _today_ymd8() -> str:
    return datetime.now().strftime("%Y%m%d")

def _now_hhmm() -> str:
    return datetime.now().strftime("%H%M")

def _last_row_date(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    try:
        return str(rows[-1][0] or "").strip()
    except Exception:
        return ""

def _apply_qfq(rows: list[list[str]], factors: list[tuple[str, float]]) -> list[list[str]]:
    """
    Apply forward-adjusted prices (前复权) using adj_factor.
    qfq_price = raw_price * (adj_factor / last_adj_factor)
    factors: list of (YYYY-MM-DD, adj_factor) for each trade day.
    """
    if not rows or not factors:
        return rows
    f_map: dict[str, float] = {d: float(f) for d, f in factors if d}
    # anchor to last available factor in rows
    last_factor: float | None = None
    for r in reversed(rows):
        d = r[0]
        if d in f_map:
            last_factor = f_map[d]
            break
    if not last_factor or last_factor <= 0:
        return rows
    out: list[list[str]] = []
    for r in rows:
        d = r[0]
        f = f_map.get(d)
        if not f or f <= 0:
            out.append(r)
            continue
        k = f / last_factor
        try:
            o = str(float(r[1]) * k)
            c = str(float(r[2]) * k)
            h = str(float(r[3]) * k)
            l = str(float(r[4]) * k)
            out.append([d, o, c, h, l, r[5]])
        except Exception:
            out.append(r)
    return out


def _is_flat_placeholder(row: list[str]) -> bool:
    """Return True if row is a synthetic/intraday placeholder (OHLC all equal + zero volume)."""
    try:
        o = float(row[1]); c = float(row[2]); h = float(row[3]); l = float(row[4])
        v = float(row[5] if len(row) > 5 else 0)
        return abs(o - c) < 0.001 and abs(h - c) < 0.001 and abs(l - c) < 0.001 and v < 1
    except (ValueError, IndexError):
        return False


async def fetch_tushare_kline(secid: str, period: str, count: int = 500, timeout: float = 10.0) -> Dict[str, Any]:
    """
    TuShare paid provider:
    - Supports stock day/week/month (week/month via daily aggregation in our stack).
    - For day: use pro.daily + adj_factor (qfqday) by default.
    - Optionally use pro.rt_k for today's realtime day bar when AI24X_TUSHARE_USE_RT_K=1 and period=day.
    """
    t0 = time.time()
    sid = str(secid).strip()
    def _secid_to_tushare_index_ts_code(s: str) -> str | None:
        ss = str(s or "").strip()
        if ss == "0.899050":
            return "899050.BJ"
        # common CN index ids
        if re.fullmatch(r"[01]\.\d{6}", ss):
            mkt, code = ss.split(".", 1)
            code = code.strip()
            # Shenzhen indices usually start with 399xxx
            if mkt == "0" and code.startswith("399"):
                return f"{code}.SZ"
            # Shanghai indices we currently support: 000001.SH (上证指数)
            if mkt == "1" and code == "000001":
                return f"{code}.SH"
        return None

    idx_ts = _secid_to_tushare_index_ts_code(sid)
    if idx_ts:
        ts_code = idx_ts
        is_index = True
    else:
        ts_code = _secid_to_tushare_ts_code(sid)
        is_index = False
    if not ts_code:
        # Allow THS index secid like "ths:881271" even though it's not a stock secid.
        if str(sid).lower().startswith(("ths:", "ths.")):
            ts_code = "THS"
        else:
            return {"code": -1, "msg": "tushare only supports stock secid", "data": {}}
    token = _effective_tushare_token()
    if not token:
        # keep user-facing message friendly; detailed env guidance belongs to admin docs/logs
        return {"code": -1, "msg": "数据源暂未就绪，请稍后再试", "data": {}}

    # Import lazily so server can run without paid deps installed.
    try:
        import tushare as ts  # type: ignore
    except Exception as e:
        return {"code": -1, "msg": f"tushare not installed: {e}", "data": {}}

    try:
        ts.set_token(token)
        pro = ts.pro_api()
        per = str(period).strip().lower()
        if per not in ("day", "week", "month"):
            return {"code": -1, "msg": f"tushare unsupported period: {per}", "data": {}}

        # THS industry/concept index path: "ths:881271" / "ths:886078" etc.
        if str(sid).lower().startswith(("ths:", "ths.")):
            six = str(sid)[4:].strip()
            if not re.fullmatch(r"\d{5,6}", six or ""):
                return {"code": -1, "msg": "invalid ths code", "data": {}}
            lookback = max(int(count) * 3, 900)
            start_dt = datetime.utcfromtimestamp(time.time() - lookback * 86400)
            start_date = start_dt.strftime("%Y%m%d")
            # ths_daily uses "ts_code" like "881271.TI" (from ths_index list).
            ths_ts_code = f"{six}.TI"
            df = await asyncio.to_thread(pro.ths_daily, ts_code=ths_ts_code, start_date=start_date)  # type: ignore[misc]
            rows: list[list[str]] = []
            try:
                df2 = df.sort_values("trade_date", ascending=True)  # type: ignore[attr-defined]
                for _, r in df2.iterrows():  # type: ignore[attr-defined]
                    d = str(r.get("trade_date", "")).strip()
                    if len(d) == 8 and d.isdigit():
                        d = f"{d[0:4]}-{d[4:6]}-{d[6:8]}"
                    try:
                        o = float(r.get("open", 0) or 0)
                        c = float(r.get("close", 0) or 0)
                        h = float(r.get("high", 0) or 0)
                        l = float(r.get("low", 0) or 0)
                        v0 = r.get("vol", r.get("volume", 0))
                        v = float(v0 or 0)
                        # Skip invalid bars to avoid frontend NaN -> 0 artifacts
                        if not d:
                            continue
                        if not (o > 0 and c > 0 and h > 0 and l > 0):
                            continue
                        if not (h >= max(o, c) and l <= min(o, c)):
                            # tolerate slight inconsistencies but skip obviously broken rows
                            continue
                        # Skip intraday placeholder bars: OHLC all equal + zero volume
                        if abs(o - c) < 0.001 and abs(h - c) < 0.001 and abs(l - c) < 0.001 and v < 1:
                            continue
                        rows.append([d, f"{o}", f"{c}", f"{h}", f"{l}", f"{v}"])
                    except Exception:
                        continue
            except Exception:
                rows = []
            if len(rows) > int(count):
                rows = rows[-int(count) :]
            if not rows:
                return {"code": -1, "msg": "该板块暂未收录，暂无K线数据", "data": {}}
            # If today's bar is missing, try to fetch today's bar explicitly after market data is expected to be updated.
            syn_today = False
            try:
                last_d = _last_row_date(rows)
                today = datetime.now().strftime("%Y-%m-%d")
                if last_d and last_d < today and _now_hhmm() >= "1610":
                    df_today = await asyncio.to_thread(
                        pro.ths_daily, ts_code=ths_ts_code, start_date=_today_ymd8(), end_date=_today_ymd8()
                    )  # type: ignore[misc]
                    try:
                        if df_today is not None and not getattr(df_today, "empty", False):
                            r0 = df_today.iloc[0]  # type: ignore[attr-defined]
                            d = str(r0.get("trade_date", "")).strip()
                            if len(d) == 8 and d.isdigit():
                                d = f"{d[0:4]}-{d[4:6]}-{d[6:8]}"
                            try:
                                o = float(r0.get("open", 0) or 0)
                                c = float(r0.get("close", 0) or 0)
                                h = float(r0.get("high", 0) or 0)
                                l = float(r0.get("low", 0) or 0)
                                v0 = r0.get("vol", r0.get("volume", 0))
                                v = float(v0 or 0)
                                if d and (o > 0 and c > 0 and h > 0 and l > 0):
                                    if h >= max(o, c) and l <= min(o, c):
                                        # replace/append today bar
                                        if rows and str(rows[-1][0]) == d:
                                            rows[-1] = [d, f"{o}", f"{c}", f"{h}", f"{l}", f"{v}"]
                                        else:
                                            rows.append([d, f"{o}", f"{c}", f"{h}", f"{l}", f"{v}"])
                            except Exception:
                                pass
                    except Exception:
                        pass
            except Exception:
                pass

            day_rows, syn_today = _maybe_append_today_placeholder(rows)
            # If today's bar is missing, try real-time intraday bars (rt_k) and aggregate to a real "today" day-bar.
            try:
                if syn_today and bool(_effective_tushare_use_rt_k()):
                    rt = await asyncio.to_thread(pro.rt_k, ts_code=ths_ts_code)  # type: ignore[misc]
                    bar = _rt_k_aggregate_to_today_bar(rt)
                    if bar:
                        # overwrite last placeholder if present
                        if day_rows and str(day_rows[-1][0]) == bar[0]:
                            day_rows[-1] = bar
                        else:
                            day_rows.append(bar)
                        syn_today = False
            except Exception:
                pass
            week_rows = _agg_to_week(day_rows)
            month_rows = _agg_to_month(day_rows)
            # Final filter: remove any flat placeholder bars (OHLC all equal + zero vol)
            day_rows = [r for r in day_rows if len(r) >= 6 and not _is_flat_placeholder(r)]
            if not day_rows:
                return {"code": -1, "msg": "该板块暂未收录，暂无K线数据", "data": {}}
            key = f"THS:{six}"
            payload = _wrap_as_tencent_shape(key, day_rows, week_rows, month_rows)
            try:
                payload["_meta"] = {
                    "source": "paid:tushare(ths_daily)",
                    "variant": "paid",
                    "ts": int(time.time()),
                    "synthetic_today": bool(syn_today),
                }
            except Exception:
                pass
            return payload

        # Index path: use index_daily and aggregate for week/month.
        if is_index:
            lookback = max(int(count) * 3, 900)
            start_dt = datetime.utcfromtimestamp(time.time() - lookback * 86400)
            start_date = start_dt.strftime("%Y%m%d")
            df = await asyncio.to_thread(pro.index_daily, ts_code=ts_code, start_date=start_date)  # type: ignore[misc]
            rows: list[list[str]] = []
            try:
                # Ensure ascending by date
                df2 = df.sort_values("trade_date", ascending=True)  # type: ignore[attr-defined]
                for _, r in df2.iterrows():  # type: ignore[attr-defined]
                    d = str(r.get("trade_date", "")).strip()
                    if len(d) == 8 and d.isdigit():
                        d = f"{d[0:4]}-{d[4:6]}-{d[6:8]}"
                    try:
                        o = float(r.get("open", 0) or 0)
                        c = float(r.get("close", 0) or 0)
                        h = float(r.get("high", 0) or 0)
                        l = float(r.get("low", 0) or 0)
                        v = float(r.get("vol", 0) or 0)
                        if not d:
                            continue
                        if not (o > 0 and c > 0 and h > 0 and l > 0):
                            continue
                        if not (h >= max(o, c) and l <= min(o, c)):
                            continue
                        rows.append([d, f"{o}", f"{c}", f"{h}", f"{l}", f"{v}"])
                    except Exception:
                        continue
            except Exception:
                rows = []
            if len(rows) > int(count):
                rows = rows[-int(count) :]
            if not rows:
                return {"code": -1, "msg": "tushare index_daily empty", "data": {}}
            day_rows, syn_today = _maybe_append_today_placeholder(rows)
            week_rows = _agg_to_week(day_rows)
            month_rows = _agg_to_month(day_rows)
            key = sid.upper()
            payload = _wrap_as_tencent_shape(key, day_rows, week_rows, month_rows)
            try:
                payload["_meta"] = {
                    "source": "paid:tushare(index_daily)",
                    "variant": "paid",
                    "ts": int(time.time()),
                    "synthetic_today": bool(syn_today),
                }
            except Exception:
                pass
            return payload

        # Fetch last N days (use trading calendar implicitly by API).
        # TuShare daily needs date range; we approximate by requesting recent 2*count days window.
        # For robustness & simplicity in MVP, request by start_date using a conservative lookback.
        lookback = max(int(count) * 3, 600)
        start = (datetime.utcnow().date()).strftime("%Y%m%d")
        # crude lookback: subtract days in seconds
        start_dt = datetime.utcfromtimestamp(time.time() - lookback * 86400)
        start_date = start_dt.strftime("%Y%m%d")

        # daily bars
        df = await asyncio.to_thread(pro.daily, ts_code=ts_code, start_date=start_date)  # type: ignore[misc]
        rows = _tencent_rows_from_tushare_daily(df)
        if len(rows) > int(count):
            rows = rows[-int(count) :]

        # adj factors for qfq
        af = await asyncio.to_thread(pro.adj_factor, ts_code=ts_code, start_date=start_date)  # type: ignore[misc]
        factors: list[tuple[str, float]] = []
        try:
            for _, r in af.sort_values("trade_date", ascending=True).iterrows():  # type: ignore[attr-defined]
                d = str(r.get("trade_date", "")).strip()
                if len(d) == 8 and d.isdigit():
                    d = f"{d[0:4]}-{d[4:6]}-{d[6:8]}"
                f = float(r.get("adj_factor", 0.0) or 0.0)
                if d and f > 0:
                    factors.append((d, f))
        except Exception:
            factors = []
        qfq_rows = _apply_qfq(rows, factors)

        # Optional rt_k overlay for today's bar (requires separate permission).
        if per == "day" and bool(_effective_tushare_use_rt_k()):
            try:
                rt = await asyncio.to_thread(pro.rt_k, ts_code=ts_code)  # type: ignore[misc]
                # rt_k returns one row for single ts_code with open/high/low/close/vol.
                if rt is not None and not getattr(rt, "empty", False):
                    r0 = rt.iloc[0]  # type: ignore[attr-defined]
                    today = datetime.utcnow().date().strftime("%Y-%m-%d")
                    o = str(r0.get("open", "")).strip()
                    c = str(r0.get("close", "")).strip()
                    h = str(r0.get("high", "")).strip()
                    l = str(r0.get("low", "")).strip()
                    v = str(r0.get("vol", "")).strip()
                    if o and c and h and l:
                        # overwrite last row if same date else append
                        if qfq_rows and qfq_rows[-1][0] == today:
                            qfq_rows[-1] = [today, o, c, h, l, v]
                        else:
                            qfq_rows.append([today, o, c, h, l, v])
            except Exception:
                pass

        # Reuse existing aggregation helpers for week/month.
        pack_rows = qfq_rows
        if per == "week":
            pack_rows = _agg_to_week(qfq_rows)
        if per == "month":
            pack_rows = _agg_to_month(qfq_rows)

        key = secid_to_tencent_symbol(secid)
        payload = {"code": 0, "data": {key: {"qfqday": qfq_rows, "day": rows, "qfqweek": _agg_to_week(qfq_rows), "week": _agg_to_week(rows), "qfqmonth": _agg_to_month(qfq_rows), "month": _agg_to_month(rows)}}}
        # Narrow to requested period by trimming other lists is unnecessary; frontend picks by period.
        _src_ok("tushare", (time.time() - t0) * 1000.0)
        return payload
    except Exception as e:
        _src_fail("tushare", (time.time() - t0) * 1000.0, reason=str(e))
        return {"code": -1, "msg": f"tushare error: {e}", "data": {}}


def _tx_allow(now: int | None = None) -> bool:
    now = int(now or time.time())
    return now >= _TX_OPEN_UNTIL


def _tx_on_fail(now: int | None = None) -> None:
    global _TX_OPEN_UNTIL
    now = int(now or time.time())
    # keep failures within 60s window
    _TX_FAILS.append(now)
    while _TX_FAILS and now - _TX_FAILS[0] > 60:
        _TX_FAILS.pop(0)
    # open circuit: 3 fails in 60s -> cool down 120s
    if len(_TX_FAILS) >= 3:
        _TX_OPEN_UNTIL = now + 120


def _tx_on_ok(now: int | None = None) -> None:
    _TX_FAILS.clear()


def is_em_plate_secid(secid: str) -> bool:
    """东方财富板块：QuoteID 形如 90.BK0963（与 A 股 0/1.六位 区分）。"""
    return bool(re.fullmatch(r"90\.BK\d+", str(secid).strip(), flags=re.I))


def secid_to_tencent_symbol(secid: str) -> str:
    parts = str(secid).split(".")
    market = parts[0] if parts else "0"
    code = parts[1] if len(parts) > 1 else ""
    if not re.fullmatch(r"\d{6}", code or ""):
        return "sz" + (code or "")
    # BSE / 北交所（BJ）常见代码段：43/83/87/88/92/89xxxx
    if code.startswith("92") or re.fullmatch(r"89\d{4}", code) or code.startswith(("43", "83", "87", "88")):
        return "bj" + code
    if market == "1":
        return "sh" + code
    return "sz" + code


def secid_to_sina_symbol(secid: str) -> str | None:
    """
    Sina symbol examples:
    - sh000001 (上证指数)
    - sz399001 (深证成指)
    - sz399006 (创业板指)
    - bj899050 (北证50, 新浪用 bj 前缀表示北交所)
    - bj920509 (北交所股票, 新浪同样用 bj 前缀)

    BSE / 北交所（BJ）常见代码段：43/83/87/88/92/89xxxx
    """
    s = str(secid).strip()
    if s == "1.000001":
        return "sh000001"
    if s == "0.399001":
        return "sz399001"
    if s == "0.399006":
        return "sz399006"
    # BSE / 北交所：统一用 bj 前缀
    parts = s.split(".")
    market = parts[0] if parts else "0"
    code = parts[1] if len(parts) > 1 else ""
    if re.fullmatch(r"89\d{4}", code or "") or code.startswith(("43", "83", "87", "88", "92")):
        return "bj" + code
    # 其他 A 股默认 sz（新浪也会接受 sz/sh 前缀）
    if market == "1":
        return "sh" + code
    if re.fullmatch(r"\d{6}", code or ""):
        return "sz" + code
    return None


def _strip_js_wrapper(s: str) -> str:
    # handles: var xxx = {...}; or xxx({...})
    s = s.strip()
    m = re.search(r"(\{[\s\S]+\})", s)
    if m:
        return m.group(1)
    m2 = re.search(r"\((\{[\s\S]+\})\)", s)
    if m2:
        return m2.group(1)
    return s


def _payload_missing_today(payload: Dict[str, Any]) -> bool:
    """Return True if payload's last bar date is before today (cache stale during trading)."""
    try:
        now = datetime.now()
        if now.weekday() >= 5:
            return False
        today = now.strftime("%Y-%m-%d")
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            return False
        for pack in data.values():
            if not isinstance(pack, dict):
                continue
            rows = pack.get("day") or pack.get("qfqday") or []
            if rows and isinstance(rows, list) and len(rows) > 0:
                last = rows[-1]
                if isinstance(last, list) and len(last) > 0:
                    return str(last[0]) < today
        return False
    except Exception:
        return False


def _cache_get(variant: str, secid: str, period: str, count: int) -> Dict[str, Any] | None:
    ttl = float(getattr(settings, "kline_cache_ttl_s", 30.0))
    if ttl <= 0:
        return None
    k = (str(variant or ""), str(secid), str(period), int(count))
    now = time.time()
    v = _KLINE_CACHE.get(k)
    if not v:
        # In-memory range reuse: if we already cached a bigger `count` for the same
        # (variant, secid, period) within TTL, reuse it by slicing the latest bars.
        try:
            v0, s0, p0, c0 = k
            best_key: Tuple[str, str, str, int] | None = None
            best_payload: Dict[str, Any] | None = None
            best_exp: float | None = None
            for kk, vv in list(_KLINE_CACHE.items()):
                if not isinstance(kk, tuple) or len(kk) != 4:
                    continue
                if kk[0] != v0 or kk[1] != s0 or kk[2] != p0:
                    continue
                exp2, payload2 = vv
                if exp2 <= now:
                    continue
                try:
                    cc = int(kk[3])
                except Exception:
                    continue
                if cc < int(count):
                    continue
                if best_key is None or cc < int(best_key[3]):  # smallest sufficient superset
                    best_key = kk
                    best_payload = payload2
                    best_exp = exp2
            if best_payload is not None and best_exp is not None:
                def _slice_payload(payload: Dict[str, Any], n: int) -> Dict[str, Any]:
                    try:
                        if not isinstance(payload, dict):
                            return payload
                        out = dict(payload)
                        data = payload.get("data")
                        if not isinstance(data, dict):
                            return out
                        data2: Dict[str, Any] = {}
                        for key_pack, pack in data.items():
                            if not isinstance(pack, dict):
                                data2[key_pack] = pack
                                continue
                            pack2: Dict[str, Any] = {}
                            for kk2, vv2 in pack.items():
                                if isinstance(vv2, list) and len(vv2) > n:
                                    pack2[kk2] = vv2[-int(n) :]
                                else:
                                    pack2[kk2] = vv2
                            data2[key_pack] = pack2
                        out["data"] = data2
                        return out
                    except Exception:
                        return payload

                sliced = _slice_payload(best_payload, int(count))
                if _payload_missing_today(sliced):
                    return None  # force refresh during trading hours
                # memoize sliced variant for faster future hits
                _KLINE_CACHE[k] = (min(best_exp, now + ttl), sliced)
                return sliced
        except Exception:
            pass
        # Redis cache layer (shared across workers, ~1ms latency)
        try:
            r = _redis_client()
            if r:
                rk = _redis_cache_key(str(k[1]), str(k[2]), int(k[3]))
                raw = r.get(rk)
                if raw:
                    payload = json.loads(raw)
                    if isinstance(payload, dict):
                        _KLINE_CACHE[k] = (now + ttl, payload)
                        return payload
        except Exception:
            pass
        # DB cache fallback for resilience across restarts.
        try:
            payload = db.kline_cache_get("|".join([k[0], k[1], k[2], str(k[3])]))
            if isinstance(payload, dict):
                if _payload_missing_today(payload):
                    return None  # force refresh during trading hours
                _KLINE_CACHE[k] = (now + ttl, payload)
                return payload
        except Exception:
            pass
        return None
    exp, payload = v
    if exp <= now:
        _KLINE_CACHE.pop(k, None)
        return None
    if _payload_missing_today(payload):
        _KLINE_CACHE.pop(k, None)
        return None  # force refresh for stale intraday cache
    return payload


def _cache_put(variant: str, secid: str, period: str, count: int, payload: Dict[str, Any]) -> None:
    ttl = float(getattr(settings, "kline_cache_ttl_s", 30.0))
    if ttl <= 0:
        return
    k = (str(variant or ""), str(secid), str(period), int(count))
    _KLINE_CACHE[k] = (time.time() + ttl, payload)
    # Redis cache (shared across workers)
    try:
        r = _redis_client()
        if r:
            rk = _redis_cache_key(str(secid), str(period), int(count))
            r.setex(rk, int(ttl), json.dumps(payload))
    except Exception:
        pass
    try:
        db.kline_cache_put("|".join([k[0], k[1], k[2], str(k[3])]), payload, ttl_s=ttl)
    except Exception:
        pass


def _tencent_payload_has_rows(payload: Dict[str, Any]) -> bool:
    try:
        if not isinstance(payload, dict):
            return False
        if int(payload.get("code", -1)) != 0:
            return False
        data = payload.get("data")
        if not isinstance(data, dict) or not data:
            return False
        for _, pack in data.items():
            if not isinstance(pack, dict):
                continue
            for v in pack.values():
                if isinstance(v, list) and len(v) > 10:
                    return True
    except Exception:
        return False
    return False


def _parse_sina_rows(payload: Any) -> list[list[str]]:
    """
    Sina returns JSON array of objects like:
    [{"day":"2026-04-14","open":"...","high":"...","low":"...","close":"...","volume":"..."}]
    Convert to rows: [date, open, close, high, low, vol] (stringified)
    """
    if not isinstance(payload, list):
        return []
    out: list[list[str]] = []
    for it in payload:
        if not isinstance(it, dict):
            continue
        day = str(it.get("day", "")).strip()
        if not day:
            continue
        o = str(it.get("open", "")).strip()
        c = str(it.get("close", "")).strip()
        h = str(it.get("high", "")).strip()
        l = str(it.get("low", "")).strip()
        v = str(it.get("volume", "")).strip()
        out.append([day, o, c, h, l, v])
    return out


def _agg_to_week(rows: list[list[str]]) -> list[list[str]]:
    buckets: dict[tuple[int, int], list[list[str]]] = {}
    for r in rows:
        if not r or len(r) < 6:
            continue
        try:
            dt = datetime.strptime(str(r[0]), "%Y-%m-%d")
        except Exception:
            continue
        y, w, _ = dt.isocalendar()
        buckets.setdefault((int(y), int(w)), []).append(r)
    out: list[list[str]] = []
    for _, br in sorted(buckets.items()):
        br.sort(key=lambda x: str(x[0]))
        first = br[0]
        last = br[-1]
        o = first[1]
        c = last[2]
        h = max((float(x[3]) for x in br if x[3] != ""), default=0.0)
        l = min((float(x[4]) for x in br if x[4] != ""), default=0.0)
        vol = 0.0
        for x in br:
            try:
                v = x[5]
                if v == "" or v is None:
                    continue
                f = float(v)
                if f != f:  # NaN
                    continue
                vol += f
            except Exception:
                continue
        out.append([str(last[0]), str(o), str(c), str(h), str(l), str(int(vol))])
    return out


def _agg_to_month(rows: list[list[str]]) -> list[list[str]]:
    buckets: dict[tuple[int, int], list[list[str]]] = {}
    for r in rows:
        if not r or len(r) < 6:
            continue
        try:
            dt = datetime.strptime(str(r[0]), "%Y-%m-%d")
        except Exception:
            continue
        buckets.setdefault((dt.year, dt.month), []).append(r)
    out: list[list[str]] = []
    for _, br in sorted(buckets.items()):
        br.sort(key=lambda x: str(x[0]))
        first = br[0]
        last = br[-1]
        o = first[1]
        c = last[2]
        h = max((float(x[3]) for x in br if x[3] != ""), default=0.0)
        l = min((float(x[4]) for x in br if x[4] != ""), default=0.0)
        vol = 0.0
        for x in br:
            try:
                v = x[5]
                if v == "" or v is None:
                    continue
                f = float(v)
                if f != f:  # NaN
                    continue
                vol += f
            except Exception:
                continue
        out.append([str(last[0]), str(o), str(c), str(h), str(l), str(int(vol))])
    return out


def _wrap_as_tencent_shape(symbol_key: str, day_rows: list[list[str]], week_rows: list[list[str]], month_rows: list[list[str]]) -> Dict[str, Any]:
    return {
        "code": 0,
        "data": {
            str(symbol_key): {
                "qfqday": day_rows,
                "day": day_rows,
                "qfqweek": week_rows,
                "week": week_rows,
                "qfqmonth": month_rows,
                "month": month_rows,
            }
        },
    }


def _em_suggest_filter(payload: Dict[str, Any], include_plates: bool = False) -> Dict[str, Any]:
    """
    Eastmoney suggest often returns BK plates (e.g. 90.BKxxxx). Our paid kline path does not support plates,
    and Eastmoney plate kline may be rate-limited. Default behavior: hide plates from suggest results.
    """
    if include_plates:
        return payload
    try:
        tbl = payload.get("QuotationCodeTable") if isinstance(payload, dict) else None
        data = (tbl or {}).get("Data") if isinstance(tbl, dict) else None
        if not isinstance(data, list):
            return payload
        filtered = []
        for it in data:
            if not isinstance(it, dict):
                continue
            classify = str(it.get("Classify") or "").strip().upper()
            quote_id = str(it.get("QuoteID") or "").strip().upper()
            code = str(it.get("Code") or "").strip().upper()
            # Drop plates (BK/90.BKxxxx)
            if classify == "BK" or quote_id.startswith("90.BK") or code.startswith("BK"):
                continue
            filtered.append(it)
        if isinstance(tbl, dict):
            tbl2 = dict(tbl)
            tbl2["Data"] = filtered
            tbl2["TotalCount"] = int(len(filtered))
            out = dict(payload)
            out["QuotationCodeTable"] = tbl2
            return out
    except Exception:
        return payload
    return payload


async def fetch_em_suggest(q: str, timeout: float = 8.0, include_plates: bool = False) -> Dict[str, Any]:
    params = {"input": q, "type": "14", "count": "30", "cb": "1"}
    async with httpx.AsyncClient(timeout=timeout, headers={"User-Agent": "ai24x/1.0"}) as client:
        r = await client.get(EM_SUGGEST, params=params)
        r.raise_for_status()
        txt = r.text
        j = json.loads(_strip_js_wrapper(txt))
        return _em_suggest_filter(j, include_plates=include_plates)


# THS index suggest cache (TuShare)
_THS_INDEX_CACHE: list[dict[str, Any]] | None = None
_THS_INDEX_CACHE_EXP: float = 0.0

# THS funds pages allowlist cache (best-effort; admin/test only)
_THS_FUNDS_ALLOW_NAMES: set[str] | None = None
_THS_FUNDS_ALLOW_SIX: set[str] | None = None
_THS_FUNDS_ALLOW_EXP: float = 0.0


async def _ths_hotspot_allow_from_10jqka(ttl_s: float = 300.0) -> tuple[set[str], set[str]]:
    """
    Best-effort: pull THS "行业资金/概念资金" summary pages and build an allowlist of plate names.
    Only used for admin/test to align with THS "热点掘金" vibe.
    """
    global _THS_FUNDS_ALLOW_NAMES, _THS_FUNDS_ALLOW_SIX, _THS_FUNDS_ALLOW_EXP
    now = time.time()
    if _THS_FUNDS_ALLOW_NAMES is not None and _THS_FUNDS_ALLOW_SIX is not None and _THS_FUNDS_ALLOW_EXP > now:
        return _THS_FUNDS_ALLOW_NAMES, _THS_FUNDS_ALLOW_SIX
    # Keep it lightweight & stable: only fetch the main summary pages.
    # (Multi-page scraping can easily drift and degrade "涨榜" alignment.)
    sources = [
        ("industry", "https://data.10jqka.com.cn/funds/hyzjl/", 1),
        ("concept", "https://data.10jqka.com.cn/funds/gnzjl/", 1),
    ]
    names: set[str] = set()
    six_codes: set[str] = set()
    try:
        async with httpx.AsyncClient(
            timeout=8.0,
            headers={"User-Agent": "ai24x/1.0"},
            follow_redirects=True,
        ) as client:
            for kind, base, _pages in sources:
                try:
                    r = await client.get(base)
                    if r.status_code >= 400:
                        continue
                    html = r.text or ""
                    if kind == "industry":
                        for m in re.finditer(
                            r'href="[^"]*/thshy/detail/code/(\d+)/"[^>]*>([^<]{1,64})</a>',
                            html,
                        ):
                            six = str(m.group(1) or "").strip()
                            nm = str(m.group(2) or "").strip()
                            if nm:
                                names.add(nm)
                            if six and six.isdigit():
                                six_codes.add(six)
                    else:
                        for m in re.finditer(r'href="[^"]*/gn/detail/code/\d+/"[^>]*>([^<]{1,64})</a>', html):
                            nm = str(m.group(1) or "").strip()
                            if nm:
                                names.add(nm)
                except Exception:
                    continue
    except Exception:
        names = set()
    _THS_FUNDS_ALLOW_NAMES = names
    _THS_FUNDS_ALLOW_SIX = six_codes
    _THS_FUNDS_ALLOW_EXP = now + float(ttl_s)
    return names, six_codes


async def _ths_hotspot_allow_names_from_10jqka(ttl_s: float = 300.0) -> set[str]:
    names, _six = await _ths_hotspot_allow_from_10jqka(ttl_s=ttl_s)
    return names


#
# NOTE: We intentionally do NOT parse THS funds ranking pages into the hotspot ranking.
# These pages are used only for optional name allowlist gating (see `_ths_hotspot_allow_names_from_10jqka`).
# When we need "funds net ranking" in the future, implement it as a separate mode to avoid mixing ranking rules.


async def _ths_index_list(ttl_s: float = 3600.0) -> list[dict[str, Any]]:
    """
    Cache TuShare ths_index list in memory (contains ts_code like 881271.TI).
    Requires tushare token.
    """
    global _THS_INDEX_CACHE, _THS_INDEX_CACHE_EXP
    now = time.time()
    if _THS_INDEX_CACHE is not None and _THS_INDEX_CACHE_EXP > now:
        return _THS_INDEX_CACHE
    token = _effective_tushare_token()
    if not token:
        _THS_INDEX_CACHE = []
        _THS_INDEX_CACHE_EXP = now + 10.0
        return _THS_INDEX_CACHE
    try:
        import tushare as ts  # type: ignore

        ts.set_token(token)
        pro = ts.pro_api()
        df = await asyncio.to_thread(pro.ths_index)  # type: ignore[misc]
        out: list[dict[str, Any]] = []
        try:
            for _, r in df.iterrows():  # type: ignore[attr-defined]
                ts_code = str(r.get("ts_code", "")).strip()
                name = str(r.get("name", "")).strip()
                typ = str(r.get("type", "")).strip()
                if ts_code and name:
                    out.append({"ts_code": ts_code, "name": name, "type": typ})
        except Exception:
            out = []
        _THS_INDEX_CACHE = out
        _THS_INDEX_CACHE_EXP = now + float(ttl_s)
        return out
    except Exception:
        _THS_INDEX_CACHE = []
        _THS_INDEX_CACHE_EXP = now + 30.0
        return _THS_INDEX_CACHE


async def _ths_index_lookup_by_six(six: str) -> dict[str, Any] | None:
    """
    Best-effort lookup for a specific THS index code (e.g. 886108) to get its Chinese name,
    without fetching the entire ths_index list.
    """
    code = str(six or "").strip()
    if not (code.isdigit() and len(code) == 6):
        return None
    token = _effective_tushare_token()
    if not token:
        return None
    try:
        import tushare as ts  # type: ignore

        ts.set_token(token)
        pro = ts.pro_api()
        ts_code = f"{code}.TI"
        df = await asyncio.to_thread(pro.ths_index, ts_code=ts_code)  # type: ignore[misc]
        if df is None or getattr(df, "empty", False):
            return None
        try:
            r0 = df.iloc[0]  # type: ignore[attr-defined]
            name = str(r0.get("name", "")).strip()
            typ = str(r0.get("type", "")).strip()
            if name:
                return {"ts_code": ts_code, "name": name, "type": typ}
        except Exception:
            return None
    except Exception:
        return None
    return None


async def fetch_ths_suggest(q: str, limit: int = 30) -> dict:
    """
    Return Eastmoney-like suggest payload for THS indices.
    QuoteID uses our backend format: ths:881271 (not 881271.TI).
    """
    kw = str(q or "").strip()
    if not kw:
        return {"QuotationCodeTable": {"Data": [], "TotalCount": 0, "Status": 0, "Message": "OK"}}
    items = await _ths_index_list()
    kw2 = kw.replace(" ", "")
    if not items:
        # Cache list may be empty when TuShare is rate-limited/temporarily unavailable.
        # Try exact lookup by 6-digit code to keep UX functional for direct-code queries (e.g. 886108).
        out = []
        if kw2.isdigit() and len(kw2) == 6:
            one = await _ths_index_lookup_by_six(kw2)
            if one and one.get("name"):
                name = str(one.get("name") or "").strip()
                ts_code = str(one.get("ts_code") or "").strip()
                typ = str(one.get("type") or "").strip()
                six = ts_code.split(".", 1)[0].strip() if ts_code else kw2
                out.append(
                    {
                        "Code": six,
                        "Name": name,
                        "PinYin": "",
                        "ID": six,
                        "JYS": "",
                        "Classify": "THS",
                        "MarketType": "",
                        "SecurityTypeName": "同花顺指数",
                        "SecurityType": "",
                        "MktNum": "",
                        "TypeUS": typ,
                        "QuoteID": f"ths:{six}",
                        "UnifiedCode": six,
                        "InnerCode": "",
                    }
                )
        return {"QuotationCodeTable": {"Data": out, "TotalCount": len(out), "Status": 0, "Message": "OK"}}
    out = []
    for it in items:
        name = str(it.get("name") or "")
        ts_code = str(it.get("ts_code") or "")
        if not name or not ts_code:
            continue
        six = ts_code.split(".", 1)[0].strip()
        if not six.isdigit() or len(six) != 6:
            continue
        hay = name.replace(" ", "")
        if kw2 in hay or kw2 in six:
            out.append(
                {
                    "Code": six,
                    "Name": name,
                    "PinYin": "",
                    "ID": six,
                    "JYS": "",
                    "Classify": "THS",
                    "MarketType": "",
                    "SecurityTypeName": "同花顺指数",
                    "SecurityType": "",
                    "MktNum": "",
                    "TypeUS": "",
                    "QuoteID": f"ths:{six}",
                    "UnifiedCode": six,
                    "InnerCode": "",
                }
            )
        if len(out) >= int(limit):
            break
    # If cache list is empty/unavailable, try exact lookup by code.
    if not out and kw2.isdigit() and len(kw2) == 6:
        one = await _ths_index_lookup_by_six(kw2)
        if one and one.get("name"):
            name = str(one.get("name") or "").strip()
            ts_code = str(one.get("ts_code") or "").strip()
            typ = str(one.get("type") or "").strip()
            six = ts_code.split(".", 1)[0].strip() if ts_code else kw2
            out.append(
                {
                    "Code": six,
                    "Name": name,
                    "PinYin": "",
                    "ID": six,
                    "JYS": "",
                    "Classify": "THS",
                    "MarketType": "",
                    "SecurityTypeName": "同花顺指数",
                    "SecurityType": "",
                    "MktNum": "",
                    "TypeUS": typ,
                    "QuoteID": f"ths:{six}",
                    "UnifiedCode": six,
                    "InnerCode": "",
                }
            )
    return {"QuotationCodeTable": {"Data": out, "TotalCount": len(out), "Status": 0, "Message": "OK"}}


async def hotspots_ths_pct_change_top(
    *,
    sample: int = 80,
    topk: int = 10,
    lookback_days: int = 30,
    concurrency: int = 6,
    timeout_s: float = 10.0,
    gate_by_ths_funds_pages: bool = True,
    include_regions: bool = False,
    allow_code_prefix_88xx: bool = True,
) -> dict[str, Any]:
    """
    Test helper for "hotspot ranking" prototyping (admin only).
    - Uses TuShare `ths_index` for list and `ths_daily` for bars.
    - Computes pct_change using the last available `pct_change` field if present,
      falling back to (close/prev_close - 1)*100 when needed.
    - Hard-limited to small sample to avoid hitting per-minute QPS limits.
    """
    t0 = time.time()
    sample = max(1, min(int(sample or 80), 200))
    topk = max(1, min(int(topk or 10), 50))
    lookback_days = max(7, min(int(lookback_days or 30), 120))
    concurrency = max(1, min(int(concurrency or 6), 10))
    token = _effective_tushare_token()
    if not token:
        return {"ok": False, "error": "tushare_token_missing"}
    try:
        import tushare as ts  # type: ignore
    except Exception as e:
        return {"ok": False, "error": f"tushare_not_installed:{type(e).__name__}"}

    items = await _ths_index_list()
    if not items:
        return {"ok": False, "error": "ths_index_empty_or_rate_limited"}

    allow_names: set[str] | None = None
    allow_six: set[str] | None = None
    if gate_by_ths_funds_pages:
        try:
            allow_names, allow_six = await _ths_hotspot_allow_from_10jqka()
            if not allow_names:
                allow_names = None
            if not allow_six:
                allow_six = None
        except Exception:
            allow_names = None
            allow_six = None

    def _is_region_like_name(n: str) -> bool:
        s = str(n or "").strip()
        if not s:
            return False
        # Common China region tokens; best-effort exclude "地方板块"
        region_tokens = (
            "北京",
            "天津",
            "上海",
            "重庆",
            "河北",
            "山西",
            "辽宁",
            "吉林",
            "黑龙江",
            "江苏",
            "浙江",
            "安徽",
            "福建",
            "江西",
            "山东",
            "河南",
            "湖北",
            "湖南",
            "广东",
            "海南",
            "四川",
            "贵州",
            "云南",
            "陕西",
            "甘肃",
            "青海",
            "台湾",
            "内蒙古",
            "广西",
            "西藏",
            "宁夏",
            "新疆",
            "深圳",
        )
        if any(tok in s for tok in region_tokens):
            # Avoid false positive for some tech names; require additional hints.
            if any(x in s for x in ("板块", "地区", "本地", "区域", "概念")):
                return True
        if any(x in s for x in ("本地股", "地域", "地区", "区域", "地方")):
            return True
        return False

    def _hotspot_keep(it: dict[str, Any]) -> bool:
        ts_code = str(it.get("ts_code") or "").strip()
        name = str(it.get("name") or "").strip()
        typ = str(it.get("type") or "").strip().upper()
        six = ts_code.split(".", 1)[0] if "." in ts_code else ts_code
        # Prefer TuShare type filter: keep only concept/industry (best-effort).
        if typ and typ not in ("N", "I", "IND", "CONCEPT"):
            return False
        # Name-based exclusions: "昨日/近期/业绩/风格/事件" buckets are not desired.
        bad_tokens = (
            "昨日",
            "近期",
            "业绩",
            "预增",
            "预减",
            "高股息",
            "高分红",
            "龙虎榜",
            "涨停",
            "连板",
            "热点",
            "强势",
            "领涨",
        )
        if any(tok in name for tok in bad_tokens):
            return False
        # Strong heuristic: exclude obvious non-hotspot buckets.
        if six.isdigit():
            # Prefer typical THS plate buckets. If allow_code_prefix_88xx=True, keep all 88xxxx
            # except obvious buckets (883xxx / 8820xxx / 7xxxx). Otherwise only keep 881/885/886.
            if allow_code_prefix_88xx:
                if not six.startswith("88"):
                    return False
                if six.startswith(("883", "8820")):
                    return False
            else:
                if not six.startswith(("881", "885", "886")):
                    return False
        if _is_region_like_name(name):
            return bool(include_regions)
        if allow_names is not None and (name not in allow_names) and (allow_six is None or six not in allow_six):
            return False
        return True

    # Stable sampling: keep request volume bounded, but avoid biasing to early list entries.
    filtered_items = [x for x in items if _hotspot_keep(x)]
    if gate_by_ths_funds_pages and len(filtered_items) > 0:
        # When gating by THS funds pages, the candidate set is already bounded (usually a few hundred).
        # Compute the full candidate set to avoid missing true Top10 like 881267/885907/881270.
        hard_cap = 600
        picked = filtered_items[:hard_cap]
        picked_strategy = "all_candidates" if len(filtered_items) <= hard_cap else f"cap({hard_cap})"
    else:
        if len(filtered_items) <= sample:
            picked = filtered_items
            picked_strategy = "all"
        else:
            step = max(1, int(len(filtered_items) / float(sample)))
            picked = [filtered_items[i] for i in range(0, len(filtered_items), step)][:sample]
            if len(picked) < sample:
                # pad from head to reach sample size (still deterministic)
                need = sample - len(picked)
                picked.extend([x for x in filtered_items[: sample * 2] if x not in picked][:need])
            picked_strategy = f"spread(step={step})"

    ts.set_token(token)
    pro = ts.pro_api()
    start_dt = datetime.utcfromtimestamp(time.time() - lookback_days * 86400)
    start_date = start_dt.strftime("%Y%m%d")

    sem = asyncio.Semaphore(concurrency)
    out: list[dict[str, Any]] = []
    fails: list[dict[str, Any]] = []

    async def one(it: dict[str, Any]) -> None:
        ts_code = str(it.get("ts_code") or "").strip()
        name = str(it.get("name") or "").strip()
        typ = str(it.get("type") or "").strip()
        if not ts_code:
            return
        async with sem:
            try:
                df = await asyncio.to_thread(pro.ths_daily, ts_code=ts_code, start_date=start_date)  # type: ignore[misc]
                if df is None or getattr(df, "empty", False):
                    raise ValueError("empty")
                try:
                    df2 = df.sort_values("trade_date", ascending=True)  # type: ignore[attr-defined]
                    r0 = df2.iloc[-1]  # type: ignore[attr-defined]
                    r_first = df2.iloc[0]  # type: ignore[attr-defined]
                except Exception:
                    r0 = df.iloc[0]  # type: ignore[attr-defined]
                    r_first = df.iloc[-1]  # type: ignore[attr-defined]
                trade_date = str(r0.get("trade_date", "")).strip()
                # "今日涨跌幅"（最后一根K线的 pct_change / pct_chg / pct）
                pct = r0.get("pct_change", None)
                if pct is None or pct == "":
                    pct = r0.get("pct_chg", None)
                if pct is None or pct == "":
                    pct = r0.get("pct", None)
                if pct is None or pct == "":
                    try:
                        c0 = float(r0.get("close", 0) or 0)
                        pc0 = float(r0.get("pre_close", 0) or 0)
                        pct = (c0 / pc0 - 1.0) * 100.0 if (c0 > 0 and pc0 > 0) else None
                    except Exception:
                        pct = None
                try:
                    pct_f = float(pct) if pct is not None else None
                except Exception:
                    pct_f = None
                # "近N日涨跌幅"：窗口首尾收盘
                win_pct_f: float | None = None
                try:
                    c_last = float(r0.get("close", 0) or 0)
                    c_first = float(r_first.get("close", 0) or 0)
                    if c_last > 0 and c_first > 0:
                        win_pct_f = (c_last / c_first - 1.0) * 100.0
                except Exception:
                    win_pct_f = None
                out.append(
                    {
                        "ts_code": ts_code,
                        "six": ts_code.split(".", 1)[0] if "." in ts_code else ts_code,
                        "name": name,
                        "type": typ,
                        "trade_date": trade_date,
                        "pct_change": pct_f,
                        "window_pct_change": win_pct_f,
                    }
                )
            except Exception as e:
                fails.append(
                    {
                        "ts_code": ts_code,
                        "name": name[:32],
                        "error": f"{type(e).__name__}:{str(e)[:120]}",
                    }
                )

    await asyncio.gather(*[one(x) for x in picked])
    # Prefer window ranking when available (aligns with lookback_days).
    out2 = [x for x in out if x.get("window_pct_change") is not None or x.get("pct_change") is not None]
    def _rk(r: dict[str, Any]) -> float:
        v = r.get("window_pct_change", None)
        if v is None:
            v = r.get("pct_change", None)
        try:
            return float(v) if v is not None else -999999.0
        except Exception:
            return -999999.0
    out2.sort(key=_rk, reverse=True)
    top = out2[:topk]
    return {
        "ok": True,
        "meta": {
            "sample": sample,
            "topk": topk,
            "lookback_days": lookback_days,
            "concurrency": concurrency,
            "elapsed_ms": int((time.time() - t0) * 1000),
            "items_total": int(len(items)),
            "items_after_filter": int(len(filtered_items)),
            "items_picked": int(len(picked)),
            "picked_strategy": picked_strategy,
            "items_ok": int(len(out)),
            "items_ok_rankable": int(len(out2)),
            "items_fail": int(len(fails)),
        },
        "items": top,
        "fails_head": fails[:10],
    }


async def hotspots_ths_daily_grid(
    *,
    sample: int = 160,
    topk: int = 10,
    long_days: int = 30,
    daily_days: int = 10,
    concurrency: int = 6,
    timeout_s: float = 10.0,
    gate_by_ths_funds_pages: bool = True,
    include_regions: bool = False,
    allow_code_prefix_88xx: bool = True,
    losers_from_10jqka_funds_tails: bool = False,
) -> dict[str, Any]:
    """
    Admin/test helper: build a "daily hotspot grid" like THS heatmap.
    - Left: long_days total ranking (top/bottom).
    - Right: last daily_days trading dates, each date has topk winners + topk losers.
    Filtering rules are shared with `hotspots_ths_pct_change_top`.
    """
    t0 = time.time()
    # sample is a "candidate cap" to control cost; allow up to 600 to reduce sampling bias.
    sample = max(1, min(int(sample or 160), 600))
    topk = max(1, min(int(topk or 10), 20))
    long_days = max(7, min(int(long_days or 30), 120))
    daily_days = max(5, min(int(daily_days or 10), 20))
    concurrency = max(1, min(int(concurrency or 6), 10))
    token = _effective_tushare_token()
    if not token:
        return {"ok": False, "error": "tushare_token_missing"}
    try:
        import tushare as ts  # type: ignore
    except Exception as e:
        return {"ok": False, "error": f"tushare_not_installed:{type(e).__name__}"}

    # Reuse list and filtering from existing function by calling it twice would re-fetch daily bars.
    items = await _ths_index_list()
    if not items:
        return {"ok": False, "error": "ths_index_empty_or_rate_limited"}

    allow_names: set[str] | None = None
    allow_six: set[str] | None = None
    if gate_by_ths_funds_pages:
        try:
            allow_names, allow_six = await _ths_hotspot_allow_from_10jqka()
            if not allow_names:
                allow_names = None
            if not allow_six:
                allow_six = None
        except Exception:
            allow_names = None
            allow_six = None

    def _is_region_like_name(n: str) -> bool:
        s = str(n or "").strip()
        if not s:
            return False
        region_tokens = (
            "北京","天津","上海","重庆","河北","山西","辽宁","吉林","黑龙江","江苏","浙江","安徽","福建","江西","山东","河南","湖北","湖南","广东","海南",
            "四川","贵州","云南","陕西","甘肃","青海","台湾","内蒙古","广西","西藏","宁夏","新疆","深圳",
        )
        if any(tok in s for tok in region_tokens):
            if any(x in s for x in ("板块", "地区", "本地", "区域", "概念")):
                return True
        if any(x in s for x in ("本地股", "地域", "地区", "区域", "地方")):
            return True
        return False

    def _hotspot_keep(it: dict[str, Any]) -> bool:
        ts_code = str(it.get("ts_code") or "").strip()
        name = str(it.get("name") or "").strip()
        typ = str(it.get("type") or "").strip().upper()
        six = ts_code.split(".", 1)[0] if "." in ts_code else ts_code
        if typ and typ not in ("N", "I", "IND", "CONCEPT"):
            return False
        bad_tokens = ("昨日","近期","业绩","预增","预减","高股息","高分红","龙虎榜","涨停","连板","热点","强势","领涨")
        if any(tok in name for tok in bad_tokens):
            return False
        if six.isdigit():
            if allow_code_prefix_88xx:
                if not six.startswith("88"):
                    return False
                if six.startswith(("883", "8820")):
                    return False
            else:
                if not six.startswith(("881", "885", "886")):
                    return False
        if _is_region_like_name(name) and not include_regions:
            return False
        if allow_names is not None:
            if (name not in allow_names) and (allow_six is None or six not in allow_six):
                return False
        return True

    filtered_items = [x for x in items if _hotspot_keep(x)]
    if gate_by_ths_funds_pages and len(filtered_items) > 0:
        hard_cap = 600
        picked = filtered_items[:hard_cap]
        picked_strategy = "all_candidates" if len(filtered_items) <= hard_cap else f"cap({hard_cap})"
    else:
        if len(filtered_items) <= sample:
            picked = filtered_items
            picked_strategy = "all"
        else:
            step = max(1, int(len(filtered_items) / float(sample)))
            picked = [filtered_items[i] for i in range(0, len(filtered_items), step)][:sample]
            if len(picked) < sample:
                need = sample - len(picked)
                picked.extend([x for x in filtered_items[: sample * 2] if x not in picked][:need])
            picked_strategy = f"spread(step={step})"

    ts.set_token(token)
    pro = ts.pro_api()

    # Fetch enough range to cover both long window and last daily_days columns.
    fetch_days = max(long_days, daily_days) + 5
    start_dt = datetime.utcfromtimestamp(time.time() - fetch_days * 86400)
    start_date = start_dt.strftime("%Y%m%d")

    sem = asyncio.Semaphore(concurrency)
    fails: list[dict[str, Any]] = []

    # Collect per-symbol daily pct_change by trade_date, and closes for long window ranking.
    by_date: dict[str, list[dict[str, Any]]] = {}
    long_rank_rows: list[dict[str, Any]] = []

    async def one(it: dict[str, Any]) -> None:
        ts_code = str(it.get("ts_code") or "").strip()
        name = str(it.get("name") or "").strip()
        typ = str(it.get("type") or "").strip()
        if not ts_code:
            return
        async with sem:
            try:
                df = await asyncio.to_thread(pro.ths_daily, ts_code=ts_code, start_date=start_date)  # type: ignore[misc]
                if df is None or getattr(df, "empty", False):
                    raise ValueError("empty")
                try:
                    df2 = df.sort_values("trade_date", ascending=True)  # type: ignore[attr-defined]
                except Exception:
                    df2 = df
                # build daily pct map
                rows: list[tuple[str, float | None, float | None, float | None]] = []
                try:
                    for _, r in df2.iterrows():  # type: ignore[attr-defined]
                        td = str(r.get("trade_date", "")).strip()
                        if not td:
                            continue
                        pct = r.get("pct_change", None)
                        if pct is None or pct == "":
                            pct = r.get("pct_chg", None)
                        if pct is None or pct == "":
                            pct = r.get("pct", None)
                        # Row-level fallback: compute from close/pre_close when pct isn't present.
                        if pct is None or pct == "":
                            try:
                                c0 = float(r.get("close", 0) or 0)
                                pc0 = float(r.get("pre_close", 0) or 0)
                                pct = (c0 / pc0 - 1.0) * 100.0 if (c0 > 0 and pc0 > 0) else None
                            except Exception:
                                pct = None
                        try:
                            pct_f = float(pct) if pct is not None and pct != "" else None
                        except Exception:
                            pct_f = None
                        close = r.get("close", None)
                        try:
                            close_f = float(close) if close is not None and close != "" else None
                        except Exception:
                            close_f = None
                        rows.append((td, pct_f, close_f, None))
                except Exception:
                    rows = []
                # add daily rows to global by_date
                for td, pct_f, _, _ in rows:
                    if pct_f is None:
                        continue
                    by_date.setdefault(td, []).append(
                        {
                            "ts_code": ts_code,
                            "six": ts_code.split(".", 1)[0] if "." in ts_code else ts_code,
                            "name": name,
                            "type": typ,
                            "pct_change": pct_f,
                        }
                    )
                # long window rank by closes: take last `long_days` trading bars within df2
                try:
                    closes = []
                    for _, r in df2.iterrows():  # type: ignore[attr-defined]
                        td = str(r.get("trade_date", "")).strip()
                        if not td:
                            continue
                        close = r.get("close", None)
                        try:
                            close_f = float(close) if close is not None and close != "" else None
                        except Exception:
                            close_f = None
                        if close_f and close_f > 0:
                            closes.append((td, close_f))
                    if len(closes) >= 2:
                        closes2 = closes[-long_days:] if len(closes) > long_days else closes
                        td_first, c_first = closes2[0]
                        td_last, c_last = closes2[-1]
                        win = (c_last / c_first - 1.0) * 100.0 if (c_first > 0 and c_last > 0) else None
                        long_rank_rows.append(
                            {
                                "ts_code": ts_code,
                                "six": ts_code.split(".", 1)[0] if "." in ts_code else ts_code,
                                "name": name,
                                "type": typ,
                                "trade_date": td_last,
                                "window_pct_change": win,
                            }
                        )
                except Exception:
                    pass
            except Exception as e:
                fails.append({"ts_code": ts_code, "name": name[:32], "error": f"{type(e).__name__}:{str(e)[:120]}"})

    await asyncio.gather(*[one(x) for x in picked])

    # Determine last daily_days trading dates based on dates present in by_date.
    dates_sorted = sorted(by_date.keys())
    dates_last = dates_sorted[-daily_days:] if len(dates_sorted) > daily_days else dates_sorted

    def _top_bottom_for_date(td: str) -> dict[str, Any]:
        arr = list(by_date.get(td) or [])
        arr = [x for x in arr if x.get("pct_change") is not None]
        def _pf(r: dict[str, Any]) -> float:
            try:
                return float(r.get("pct_change"))  # type: ignore[arg-type]
            except Exception:
                return 0.0
        # Winners: high to low
        arr.sort(key=_pf, reverse=True)
        top = arr[:topk]
        # Losers: low to high (most negative first)
        losers = sorted(arr, key=_pf)[:topk]
        # bottom: worst -> least-worst; bottom_display: least-worst -> worst (UI shows 10→1)
        bottom = losers
        bottom_display = list(reversed(losers))
        return {"trade_date": td, "top": top, "bottom": bottom, "bottom_display": bottom_display}

    daily_cols = [_top_bottom_for_date(td) for td in dates_last]

    # Long ranking: top and bottom by window_pct_change.
    long_ok = [x for x in long_rank_rows if x.get("window_pct_change") is not None]
    def _wf(r: dict[str, Any]) -> float:
        try:
            return float(r.get("window_pct_change"))  # type: ignore[arg-type]
        except Exception:
            return 0.0
    long_ok.sort(key=_wf, reverse=True)
    long_top = long_ok[:topk]
    long_losers = sorted(long_ok, key=_wf)[:topk]
    long_bottom = long_losers
    long_bottom_display = list(reversed(long_losers))

    def _parse_net_num(t: str) -> float | None:
        # 10jqka pages usually show values in "亿" and may include commas, minus sign "−",
        # or be wrapped in nested tags (<span>...</span>).
        s = str(t or "").strip().replace("−", "-")
        if not s or s in ("--", "—"):
            return None
        s = s.replace(",", "").replace("亿", "").replace("%", "").strip()
        try:
            return float(s)
        except Exception:
            return None

    def _extract_funds_rows(html: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        if not html:
            return out
        for tr in re.findall(r"<tr[^>]*>.*?</tr>", html, flags=re.S | re.I):
            m = re.search(r'href="([^"]*/(?:thshy|gn)/detail/code/(\d+)/)"[^>]*>([^<]{1,64})</a>', tr)
            if not m:
                continue
            href = str(m.group(1) or "").strip()
            code = str(m.group(2) or "").strip()
            name = str(m.group(3) or "").strip()
            # Capture full inner HTML of each <td>, then strip tags to keep sign and numbers.
            tds_html = re.findall(r"<td[^>]*>(.*?)</td>", tr, flags=re.S | re.I)
            tds = []
            for x in tds_html:
                y = re.sub(r"<[^>]+>", "", x or "")
                y = re.sub(r"\s+", " ", y).strip()
                tds.append(y)
            net = None
            if len(tds) >= 7:
                net = _parse_net_num(tds[6])
            if name and net is not None:
                out.append({"name": name, "net_yi": float(net), "href": href, "code": code})
        return out

    async def _fetch_funds_tail_pages() -> dict[str, list[dict[str, Any]]]:
        urls = [
            ("industry", "https://data.10jqka.com.cn/funds/hyzjl/index/index/page/2/"),
            ("concept", "https://data.10jqka.com.cn/funds/gnzjl/index/index/page/8/"),
        ]
        out: dict[str, list[dict[str, Any]]] = {"industry": [], "concept": []}
        async with httpx.AsyncClient(timeout=10.0, headers={"User-Agent": "ai24x/1.0"}, follow_redirects=True) as client:
            for kind, url in urls:
                try:
                    r = await client.get(url)
                    if r.status_code >= 400:
                        continue
                    one = _extract_funds_rows(r.text or "")
                    for x in one:
                        x["kind"] = kind
                    out[kind] = one
                except Exception:
                    continue
        return out

    losers_source = "ths_daily_pct"
    if losers_from_10jqka_funds_tails and daily_cols:
        try:
            pages = await _fetch_funds_tail_pages()
            # Use tail-page rank (bottom of the page), not re-sorting by net.
            ind = [x for x in (pages.get("industry") or []) if x.get("net_yi") is not None]
            con = [x for x in (pages.get("concept") or []) if x.get("net_yi") is not None]
            ind_tail = list(reversed(ind))[:topk]
            con_tail = list(reversed(con))[:topk]
            merged: list[dict[str, Any]] = []
            seen: set[str] = set()
            for i in range(max(len(ind_tail), len(con_tail))):
                for arr in (ind_tail, con_tail):
                    if i >= len(arr):
                        continue
                    x = arr[i]
                    k = str(x.get("code") or x.get("name") or "")
                    if not k or k in seen:
                        continue
                    seen.add(k)
                    merged.append(x)
                    if len(merged) >= topk:
                        break
                if len(merged) >= topk:
                    break
            worst = merged
            td_today = dates_last[-1] if dates_last else ""
            # Only override today's bottom list; keep top list from ths_daily.
            bottom_rank_worst_first = list(worst)
            daily_cols[-1]["bottom"] = [
                {
                    "ts_code": "",
                    "six": str(x.get("code") or ""),
                    "name": str(x.get("name") or ""),
                    "type": str(x.get("kind") or ""),
                    "trade_date": td_today,
                    "pct_change": None,
                    "window_pct_change": None,
                    "net_yi": float(x.get("net_yi") or 0.0),
                    "href": str(x.get("href") or ""),
                    "rank_source": "funds_tail_pages",
                }
                for x in bottom_rank_worst_first
            ]
            # UI expects 10→1 (least-worst -> worst)
            daily_cols[-1]["bottom_display"] = list(reversed(daily_cols[-1]["bottom"]))
            losers_source = "funds_tail_pages_rank"
        except Exception:
            pass

    # Fallback: if today's pct set contains no negatives, TuShare ths_daily may not match THS plate move ranking.
    # In that case, override ONLY today's column top/bottom using public 10jqka plate ranking pages (industry+concept).
    try:
        if daily_cols and (losers_source == "ths_daily_pct"):
            td_today = dates_last[-1] if dates_last else ""
            today_arr = list(by_date.get(td_today) or [])
            today_pcts = [float(x.get("pct_change")) for x in today_arr if x.get("pct_change") is not None]
            if today_pcts and all(v >= 0 for v in today_pcts):
                ths_rows = await _ths_plate_rank_from_10jqka(timeout_s=10.0)
                # top: high to low; bottom: low to high
                ths_rows = [x for x in ths_rows if x.get("pct_change") is not None]
                ths_rows.sort(key=lambda r: float(r.get("pct_change") or 0.0), reverse=True)
                top2 = ths_rows[:topk]
                bot2 = list(reversed(ths_rows[-topk:])) if len(ths_rows) >= topk else list(reversed(ths_rows))
                daily_cols[-1]["top"] = top2
                daily_cols[-1]["bottom"] = bot2
                daily_cols[-1]["bottom_display"] = list(reversed(bot2))
                losers_source = "10jqka_plate_rank_fallback"
    except Exception:
        pass

    return {
        "ok": True,
        "meta": {
            "sample": sample,
            "topk": topk,
            "long_days": long_days,
            "daily_days": daily_days,
            "concurrency": concurrency,
            "elapsed_ms": int((time.time() - t0) * 1000),
            "items_total": int(len(items)),
            "items_after_filter": int(len(filtered_items)),
            "items_picked": int(len(picked)),
            "items_fail": int(len(fails)),
            "daily_dates": dates_last,
            "picked_strategy": picked_strategy,
            "losers_source": losers_source,
        },
        "long": {"top": long_top, "bottom": long_bottom, "bottom_display": long_bottom_display},
        "daily": daily_cols,
        "fails_head": fails[:10],
        "gate_funds_names_count": int(len(allow_names)) if allow_names is not None else 0,
    }


async def debug_10jqka_funds_tail_losers(*, topk: int = 10) -> dict[str, Any]:
    """
    Debug helper: fetch and parse specific 10jqka funds tail pages, then merge and compute worst (net) losers.
    Intended to validate rules like:
    - Industry funds page 2 tail
    - Concept funds page 8 tail
    """
    topk = max(1, min(int(topk or 10), 50))

    def _parse_net_num(t: str) -> float | None:
        s = str(t or "").strip().replace("−", "-")
        if not s or s in ("--", "—"):
            return None
        s = s.replace(",", "").replace("亿", "").replace("%", "").strip()
        try:
            return float(s)
        except Exception:
            return None

    def _extract_funds_rows(html: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        if not html:
            return out
        for tr in re.findall(r"<tr[^>]*>.*?</tr>", html, flags=re.S | re.I):
            m = re.search(r'href="([^"]*/(?:thshy|gn)/detail/code/(\d+)/)"[^>]*>([^<]{1,64})</a>', tr)
            if not m:
                continue
            href = str(m.group(1) or "").strip()
            code = str(m.group(2) or "").strip()
            name = str(m.group(3) or "").strip()
            tds_html = re.findall(r"<td[^>]*>(.*?)</td>", tr, flags=re.S | re.I)
            tds = []
            for x in tds_html:
                y = re.sub(r"<[^>]+>", "", x or "")
                y = re.sub(r"\s+", " ", y).strip()
                tds.append(y)
            net = None
            if len(tds) >= 7:
                net = _parse_net_num(tds[6])
            if name and net is not None:
                out.append({"name": name, "code": code, "net_yi": float(net), "href": href})
        return out

    pages = [
        ("industry_p2", "industry", "https://data.10jqka.com.cn/funds/hyzjl/index/index/page/2/"),
        ("concept_p8", "concept", "https://data.10jqka.com.cn/funds/gnzjl/index/index/page/8/"),
    ]
    raw: dict[str, Any] = {}
    fetch_errors: dict[str, Any] = {}

    async with httpx.AsyncClient(timeout=12.0, headers={"User-Agent": "ai24x/1.0"}, follow_redirects=True) as client:
        for key, kind, url in pages:
            try:
                r = await client.get(url)
                raw[key] = {
                    "url": url,
                    "status_code": int(r.status_code),
                    "len": int(len(r.text or "")),
                }
                if r.status_code >= 400:
                    fetch_errors[key] = f"http_{r.status_code}"
                    raw[key]["rows"] = []
                    continue
                rows = _extract_funds_rows(r.text or "")
                for x in rows:
                    x["kind"] = kind
                    x["page"] = key
                raw[key]["rows"] = rows
            except Exception as e:
                fetch_errors[key] = f"{type(e).__name__}:{str(e)[:120]}"
                raw[key] = {"url": url, "rows": []}

    # Build bottom-of-page tails, then merge by tail rank (not re-sorting by net).
    ind = [x for x in (raw.get("industry_p2", {}).get("rows") or []) if x.get("net_yi") is not None]
    con = [x for x in (raw.get("concept_p8", {}).get("rows") or []) if x.get("net_yi") is not None]
    ind_tail = list(reversed(ind))[:topk]
    con_tail = list(reversed(con))[:topk]
    worst: list[dict[str, Any]] = []
    seen: set[str] = set()
    for i in range(max(len(ind_tail), len(con_tail))):
        for arr in (ind_tail, con_tail):
            if i >= len(arr):
                continue
            x = arr[i]
            k = str(x.get("code") or x.get("name") or "")
            if not k or k in seen:
                continue
            seen.add(k)
            worst.append(x)
            if len(worst) >= topk:
                break
        if len(worst) >= topk:
            break
    # Helpful probes for expected names
    expected = ["能源金属", "芬太尼", "青蒿素"]
    presence = {nm: any(nm in str(x.get("name") or "") for x in (ind + con)) for nm in expected}
    return {
        "ok": True,
        "topk": topk,
        "fetch_errors": fetch_errors,
        "pages": {k: {"url": raw.get(k, {}).get("url"), "status_code": raw.get(k, {}).get("status_code"), "rows_count": len(raw.get(k, {}).get("rows") or [])} for k, _, _u in pages},
        "presence": presence,
        "worst": worst,
        "merged_count": int(len(ind) + len(con)),
        # include small samples for human inspection
        "industry_p2_head": (raw.get("industry_p2", {}).get("rows") or [])[:8],
        "industry_p2_tail": (raw.get("industry_p2", {}).get("rows") or [])[-8:],
        "concept_p8_head": (raw.get("concept_p8", {}).get("rows") or [])[:8],
        "concept_p8_tail": (raw.get("concept_p8", {}).get("rows") or [])[-8:],
    }


async def debug_ths_daily_day(
    *,
    trade_date: str,
    sample: int = 600,
    topk: int = 10,
    gate_by_ths_funds_pages: bool = True,
    include_regions: bool = False,
    allow_code_prefix_88xx: bool = True,
    concurrency: int = 6,
) -> dict[str, Any]:
    """
    Debug helper: show what we actually have for a specific trade_date from TuShare ths_daily.
    Returns min/max pct_change, negative counts, and top/bottom lists for that date.
    """
    trade_date = str(trade_date or "").strip()
    if not (len(trade_date) == 8 and trade_date.isdigit()):
        return {"ok": False, "error": "bad_trade_date"}
    topk = max(1, min(int(topk or 10), 50))
    sample = max(1, min(int(sample or 600), 600))
    concurrency = max(1, min(int(concurrency or 6), 10))

    token = _effective_tushare_token()
    if not token:
        return {"ok": False, "error": "tushare_token_missing"}
    try:
        import tushare as ts  # type: ignore
    except Exception as e:
        return {"ok": False, "error": f"tushare_not_installed:{type(e).__name__}"}

    items = await _ths_index_list()
    if not items:
        return {"ok": False, "error": "ths_index_empty_or_rate_limited"}

    allow_names: set[str] | None = None
    allow_six: set[str] | None = None
    if gate_by_ths_funds_pages:
        try:
            allow_names, allow_six = await _ths_hotspot_allow_from_10jqka()
            if not allow_names:
                allow_names = None
            if not allow_six:
                allow_six = None
        except Exception:
            allow_names = None
            allow_six = None

    def _is_region_like_name(n: str) -> bool:
        s = str(n or "").strip()
        if not s:
            return False
        region_tokens = (
            "北京","天津","上海","重庆","河北","山西","辽宁","吉林","黑龙江","江苏","浙江","安徽","福建","江西","山东","河南","湖北","湖南","广东","海南",
            "四川","贵州","云南","陕西","甘肃","青海","台湾","内蒙古","广西","西藏","宁夏","新疆","深圳",
        )
        if any(tok in s for tok in region_tokens):
            if any(x in s for x in ("板块", "地区", "本地", "区域", "概念")):
                return True
        if any(x in s for x in ("本地股", "地域", "地区", "区域", "地方")):
            return True
        return False

    def _hotspot_keep(it: dict[str, Any]) -> bool:
        ts_code = str(it.get("ts_code") or "").strip()
        name = str(it.get("name") or "").strip()
        typ = str(it.get("type") or "").strip().upper()
        six = ts_code.split(".", 1)[0] if "." in ts_code else ts_code
        if typ and typ not in ("N", "I", "IND", "CONCEPT"):
            return False
        bad_tokens = ("昨日","近期","业绩","预增","预减","高股息","高分红","龙虎榜","涨停","连板","热点","强势","领涨")
        if any(tok in name for tok in bad_tokens):
            return False
        if six.isdigit():
            if allow_code_prefix_88xx:
                if not six.startswith("88"):
                    return False
                if six.startswith(("883", "8820")):
                    return False
            else:
                if not six.startswith(("881", "885", "886")):
                    return False
        if _is_region_like_name(name) and not include_regions:
            return False
        if allow_names is not None:
            if (name not in allow_names) and (allow_six is None or six not in allow_six):
                return False
        return True

    filtered_items = [x for x in items if _hotspot_keep(x)]
    picked = filtered_items[: min(len(filtered_items), sample)]

    ts.set_token(token)
    pro = ts.pro_api()
    sem = asyncio.Semaphore(concurrency)
    out: list[dict[str, Any]] = []
    fails: list[dict[str, Any]] = []

    async def one(it: dict[str, Any]) -> None:
        ts_code = str(it.get("ts_code") or "").strip()
        name = str(it.get("name") or "").strip()
        typ = str(it.get("type") or "").strip()
        if not ts_code:
            return
        async with sem:
            try:
                df = await asyncio.to_thread(pro.ths_daily, ts_code=ts_code, start_date=trade_date, end_date=trade_date)  # type: ignore[misc]
                if df is None or getattr(df, "empty", False):
                    return
                # take first row
                try:
                    r = df.iloc[0]  # type: ignore[attr-defined]
                except Exception:
                    return
                pct = r.get("pct_change", None)
                if pct is None or pct == "":
                    pct = r.get("pct_chg", None)
                if pct is None or pct == "":
                    pct = r.get("pct", None)
                if pct is None or pct == "":
                    try:
                        c0 = float(r.get("close", 0) or 0)
                        pc0 = float(r.get("pre_close", 0) or 0)
                        pct = (c0 / pc0 - 1.0) * 100.0 if (c0 > 0 and pc0 > 0) else None
                    except Exception:
                        pct = None
                try:
                    pct_f = float(pct) if pct is not None else None
                except Exception:
                    pct_f = None
                if pct_f is None:
                    return
                out.append({"ts_code": ts_code, "six": ts_code.split(".", 1)[0], "name": name, "type": typ, "pct_change": pct_f})
            except Exception as e:
                fails.append({"ts_code": ts_code, "name": name[:32], "error": f"{type(e).__name__}:{str(e)[:80]}"})

    await asyncio.gather(*[one(x) for x in picked])
    pcts = [float(x["pct_change"]) for x in out if x.get("pct_change") is not None]
    pmin = min(pcts) if pcts else None
    pmax = max(pcts) if pcts else None
    neg = sum(1 for v in pcts if v < 0) if pcts else 0
    z0 = sum(1 for v in pcts if v == 0) if pcts else 0
    out_sorted_desc = sorted(out, key=lambda r: float(r.get("pct_change") or 0.0), reverse=True)
    out_sorted_asc = sorted(out, key=lambda r: float(r.get("pct_change") or 0.0))
    return {
        "ok": True,
        "trade_date": trade_date,
        "picked": len(picked),
        "items_ok": len(out),
        "items_fail": len(fails),
        "pct_min": pmin,
        "pct_max": pmax,
        "neg_count": neg,
        "zero_count": z0,
        "top": out_sorted_desc[:topk],
        "bottom": out_sorted_asc[:topk],
        "fails_head": fails[:10],
    }


_THS_PLATE_RANK_CACHE: dict[str, Any] = {"ts": 0.0, "rows": []}


async def _ths_plate_rank_from_10jqka(*, timeout_s: float = 10.0) -> list[dict[str, Any]]:
    """
    Fetch public 10jqka plate move ranking (industry + concept) for TODAY (no historical guarantee).
    Uses GBK pages:
    - https://q.10jqka.com.cn/thshy/  (industry)
    - https://q.10jqka.com.cn/gn/     (concept)
    Returns rows: {six,name,type,trade_date,pct_change,href,rank_source}
    """
    now = time.time()
    if (now - float(_THS_PLATE_RANK_CACHE.get("ts") or 0.0)) < 90.0:
        return list(_THS_PLATE_RANK_CACHE.get("rows") or [])

    def _parse_pct(s: str) -> float | None:
        t = str(s or "").strip().replace("−", "-").replace("%", "").replace(",", "")
        if not t:
            return None
        try:
            return float(t)
        except Exception:
            return None

    def _extract_rows(html: str, kind: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        if not html:
            return out
        # locate table tbody
        m = re.search(r"<tbody[^>]*>([\s\S]*?)</tbody>", html, flags=re.I)
        body = m.group(1) if m else html
        for tr in re.findall(r"<tr[^>]*>[\s\S]*?</tr>", body, flags=re.I):
            # code+name anchor
            ma = re.search(r'href="([^"]*/(?:thshy|gn)/detail/code/(\d+)/)"[^>]*>([^<]{1,64})</a>', tr)
            if not ma:
                continue
            href = str(ma.group(1) or "").strip()
            code = str(ma.group(2) or "").strip()
            name = str(ma.group(3) or "").strip()
            # tds
            tds_html = re.findall(r"<td[^>]*>(.*?)</td>", tr, flags=re.S | re.I)
            tds: list[str] = []
            for x in tds_html:
                y = re.sub(r"<[^>]+>", "", x or "")
                y = re.sub(r"\s+", " ", y).strip()
                tds.append(y)
            # pick first cell that looks like pct (contains % or endswith digits with sign)
            pct: float | None = None
            for cell in tds:
                if "%" in cell:
                    pct = _parse_pct(cell)
                    if pct is not None:
                        break
            if pct is None:
                # fallback: find a small numeric column commonly used for zdf
                for cell in tds:
                    if any(ch.isdigit() for ch in cell) and ("." in cell or cell.lstrip("-").isdigit()):
                        v = _parse_pct(cell)
                        if v is not None:
                            pct = v
                            break
            if pct is None:
                continue
            out.append(
                {
                    "ts_code": "",
                    "six": code,
                    "name": name,
                    "type": kind,
                    "trade_date": _today_ymd8(),
                    "pct_change": float(pct),
                    "window_pct_change": None,
                    "href": href if href.startswith("http") else ("https://q.10jqka.com.cn" + href),
                    "rank_source": "10jqka_plate_rank",
                }
            )
        return out

    urls = [
        ("industry", "https://q.10jqka.com.cn/thshy/"),
        ("concept", "https://q.10jqka.com.cn/gn/"),
    ]
    rows_all: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=timeout_s, headers={"User-Agent": "Mozilla/5.0"}, follow_redirects=True) as client:
        for kind, url in urls:
            try:
                r = await client.get(url)
                # pages are gbk
                try:
                    html = r.content.decode("gbk", errors="ignore")
                except Exception:
                    html = (r.text or "")
                rows_all.extend(_extract_rows(html, kind))
            except Exception:
                continue

    _THS_PLATE_RANK_CACHE["ts"] = now
    _THS_PLATE_RANK_CACHE["rows"] = rows_all
    return rows_all


def _em_kline_rows_from_payload(payload: Dict[str, Any]) -> list[list[str]]:
    data = payload.get("data") if isinstance(payload, dict) else None
    lines = (data or {}).get("klines") if isinstance(data, dict) else None
    if not lines or not isinstance(lines, list):
        return []
    out: list[list[str]] = []
    for ln in lines:
        parts = str(ln).split(",")
        if len(parts) < 6:
            continue
        # 与腾讯 fq 行一致：[date, open, close, high, low, vol]
        out.append([str(parts[0]), str(parts[1]), str(parts[2]), str(parts[3]), str(parts[4]), str(parts[5])])
    return out


async def _fetch_em_plate_klt(client: httpx.AsyncClient, secid: str, klt: int) -> list[list[str]]:
    t0 = time.perf_counter()
    params = {
        "fields1": "f1",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "beg": "0",
        "end": "20500101",
        "ut": "fa5fd1943c7b386f172d6893dbfba10b",
        "rtntype": "6",
        "secid": secid,
        "klt": str(klt),
        "fqt": "1",
    }
    urls = []
    try:
        http_url = EM_PLATE_KLINE.replace("https://", "http://", 1)
        if http_url != EM_PLATE_KLINE:
            urls.append(http_url)
    except Exception:
        pass
    urls.append(EM_PLATE_KLINE)  # HTTPS as fallback

    for attempt in range(2):
        url = urls[min(attempt, len(urls) - 1)]
        try:
            r = await client.get(url, params=params)
            r.raise_for_status()
            payload = r.json()
            _src_ok("eastmoney.push2his", (time.perf_counter() - t0) * 1000.0)
            return _em_kline_rows_from_payload(payload)
        except httpx.RemoteProtocolError as e:
            _src_fail("eastmoney.push2his", (time.perf_counter() - t0) * 1000.0, f"RemoteProtocolError:{e}")
            await asyncio.sleep(0.25)
            continue
        except Exception as e:
            _src_fail("eastmoney.push2his", (time.perf_counter() - t0) * 1000.0, type(e).__name__)
            raise
    raise httpx.RemoteProtocolError("eastmoney push2his disconnected")


async def fetch_em_plate_kline(
    secid: str, period: str, count: int = 500, timeout: float = 5.0
) -> Dict[str, Any]:
    """
    东财板块指数 K 线；返回结构与腾讯 fqkline JSON 接近，便于前端 pickTencentKlineRows 复用。
    同时返回日/周/月三套序列（周月为东财聚合，与前端自聚合可能略有差异）。

    注意：东财 push2his 在 Windows schannel 下有 SSL 重协商问题（RemoteProtocolError）。
    此函数快速重试 2 轮后即返回，让浏览器端 JSONP 兜底。
    """
    sid = str(secid).strip()
    if not is_em_plate_secid(sid):
        raise ValueError("invalid eastmoney plate secid")
    key = sid.upper()

    def _client_opts() -> dict:
        return {
            "timeout": timeout,
            "headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://quote.eastmoney.com/",
                "Connection": "close",
            },
            "limits": httpx.Limits(max_connections=10, max_keepalive_connections=0),
            "follow_redirects": True,
            "verify": False,
        }

    last_err: Optional[Exception] = None

    # Fast retry: at most 2 attempts, short sleep between, so frontend timeout isn't triggered.
    for attempt in range(2):
        try:
            async with httpx.AsyncClient(**_client_opts()) as client:
                day_rows, week_rows, month_rows = await asyncio.gather(
                    _fetch_em_plate_klt(client, sid, 101),
                    _fetch_em_plate_klt(client, sid, 102),
                    _fetch_em_plate_klt(client, sid, 103),
                )
        except httpx.RemoteProtocolError as e:
            last_err = e
            if attempt < 1:
                await asyncio.sleep(0.5)
            continue
        except Exception as e:
            last_err = e
            break

        def tail(rows: list[list[str]]) -> list[list[str]]:
            if count > 0 and len(rows) > count:
                return rows[-count:]
            return rows

        d = tail(day_rows)
        w = tail(week_rows)
        m = tail(month_rows)
        if not d:
            return {"code": -1, "msg": "no eastmoney plate kline", "data": {}}
        # Plate intraday may lag; append a synthetic today bar so UI shows "today" consistently.
        d2, syn_today = _maybe_append_today_placeholder(d)
        if syn_today:
            d = d2

        pack: Dict[str, Any] = {
            "qfqday": d,
            "day": d,
            "qfqweek": w,
            "week": w,
            "qfqmonth": m,
            "month": m,
        }
        return {"code": 0, "data": {key: pack}}

    # All 3 attempts exhausted — return descriptive error so frontend can react.
    err_name = type(last_err).__name__ if last_err else "unknown"
    err_msg = str(last_err) if last_err else ""
    return {"code": -1, "msg": f"eastmoney plate kline temporarily unavailable ({err_name}: {err_msg})", "data": {}}


def is_em_stock_secid(secid: str) -> bool:
    """
    Eastmoney stock kline supports standard secid like 0.000001 / 1.600000 / 0.920564.
    We use this as a server-side fallback when Tencent is empty/unstable (common for BJ / NEEQ names).
    """
    return bool(re.fullmatch(r"[01]\.\d{6}", str(secid or "").strip()))


async def fetch_em_stock_kline(
    secid: str, period: str, count: int = 500, timeout: float = 15.0
) -> Dict[str, Any]:
    """
    Eastmoney stock kline (same endpoint as plate), returns Tencent-like shape for frontend reuse.
    """
    sid = str(secid).strip()
    if not is_em_stock_secid(sid):
        return {"code": -1, "msg": "invalid eastmoney stock secid", "data": {}}

    key = sid.upper()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://quote.eastmoney.com/",
        "Connection": "close",
    }
    limits = httpx.Limits(max_connections=20, max_keepalive_connections=0)
    async with httpx.AsyncClient(timeout=timeout, headers=headers, limits=limits, follow_redirects=True, verify=False) as client:
        day_rows, week_rows, month_rows = await asyncio.gather(
            _fetch_em_plate_klt(client, sid, 101),
            _fetch_em_plate_klt(client, sid, 102),
            _fetch_em_plate_klt(client, sid, 103),
        )

    def tail(rows: list[list[str]]) -> list[list[str]]:
        if count > 0 and len(rows) > count:
            return rows[-count:]
        return rows

    d = tail(day_rows)
    w = tail(week_rows)
    m = tail(month_rows)
    if not d:
        return {"code": -1, "msg": "no eastmoney stock kline", "data": {}}

    pack: Dict[str, Any] = {
        "qfqday": d,
        "day": d,
        "qfqweek": w,
        "week": w,
        "qfqmonth": m,
        "month": m,
    }
    return {"code": 0, "data": {key: pack}}


async def fetch_em_index_kline(
    secid: str, period: str, count: int = 500, timeout: float = 15.0
) -> Dict[str, Any]:
    """
    Eastmoney kline for standard secid like 0.899050 (北证50).
    Used as fallback for indices when Tencent fails or is blocked.
    Returns Tencent-like shape.
    """
    sid = str(secid).strip()
    if not re.fullmatch(r"[01]\.\d{6}", sid):
        return {"code": -1, "msg": "invalid eastmoney index secid", "data": {}}

    key = sid.upper()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://quote.eastmoney.com/",
        "Connection": "close",
    }
    limits = httpx.Limits(max_connections=20, max_keepalive_connections=0)
    async with httpx.AsyncClient(timeout=timeout, headers=headers, limits=limits, follow_redirects=True, verify=False) as client:
        day_rows, week_rows, month_rows = await asyncio.gather(
            _fetch_em_plate_klt(client, sid, 101),
            _fetch_em_plate_klt(client, sid, 102),
            _fetch_em_plate_klt(client, sid, 103),
        )

    def tail(rows: list[list[str]]) -> list[list[str]]:
        if count > 0 and len(rows) > count:
            return rows[-count:]
        return rows

    d = tail(day_rows)
    w = tail(week_rows)
    m = tail(month_rows)
    if not d:
        return {"code": -1, "msg": "no eastmoney index kline", "data": {}}

    pack: Dict[str, Any] = {
        "qfqday": d,
        "day": d,
        "qfqweek": w,
        "week": w,
        "qfqmonth": m,
        "month": m,
    }
    return {"code": 0, "data": {key: pack}}


async def _em_stock_kline_fallback(
    secid: str, period: str, count: int, timeout: float
) -> Optional[Dict[str, Any]]:
    if not is_em_stock_secid(secid):
        return None
    try:
        em_payload = await fetch_em_stock_kline(secid, period, count=count, timeout=timeout)
        if _tencent_payload_has_rows(em_payload):
            return em_payload
    except Exception:
        return None
    return None


async def _fetch_tx_kline_core(
    variant: str,
    secid: str,
    period: str,
    count: int = 500,
    timeout: float = 10.0,
    priority_override: str | None = None,
    allow_paid: bool = True,
) -> Dict[str, Any]:
    if is_em_plate_secid(secid):
        payload = await fetch_em_plate_kline(secid, period, count=count, timeout=timeout)
        if _tencent_payload_has_rows(payload):
            _cache_put("plate", secid, period, count, payload)
        return payload

    def _priority() -> list[str]:
        raw = str(priority_override or _effective_priority() or "").strip().lower()
        items = [x.strip() for x in raw.split(",") if x.strip()]
        # default: public first, paid last
        if not items:
            return ["tencent", "eastmoney", "sina", "paid"]
        # ensure uniqueness while preserving order
        out: list[str] = []
        for it in items:
            if it not in out:
                out.append(it)
        return out

    async def _try_paid() -> Dict[str, Any] | None:
        if not allow_paid or not _paid_enabled():
            return None
        try:
            paid = await fetch_paid_kline(secid, period, count=count, timeout=timeout)
            if _tencent_payload_has_rows(paid):
                try:
                    paid["_meta"] = {
                        "source": f"paid:{_effective_paid_provider()}",
                        "variant": str(variant),
                        "priority": str(priority_override or _effective_priority() or ""),
                        "ts": int(time.time()),
                    }
                except Exception:
                    pass
                _route_hit(str((paid.get("_meta") or {}).get("source") or f"paid:{_effective_paid_provider()}"))
                _cache_put(variant, secid, period, count, paid)
                return paid
            # propagate error payload for better diagnostics / fallback decisions
            if isinstance(paid, dict) and int(paid.get("code") or 0) != 0:
                try:
                    paid["_meta"] = {
                        "source": f"paid:{_effective_paid_provider()}",
                        "variant": str(variant),
                        "priority": str(priority_override or _effective_priority() or ""),
                        "ts": int(time.time()),
                    }
                except Exception:
                    pass
                return paid
        except Exception:
            return None
        return None

    async def _try_eastmoney() -> Dict[str, Any] | None:
        # Index fallback: for BSE indices (北证50 etc.), skip eastmoney entirely.
        # Eastmoney push2his has SSL renegotiation issues on Windows (schannel),
        # and tencent doesn't support BSE indices either. Go straight to sina.
        sid_str = str(secid).strip()
        is_bse_index = sid_str == "0.899050" or bool(re.fullmatch(r"0\.89\d{4}", sid_str))
        if is_bse_index:
            return None
            try:
                t0 = time.perf_counter()
                em_payload = await fetch_em_index_kline(secid, period, count=count, timeout=timeout)
                if _tencent_payload_has_rows(em_payload):
                    try:
                        em_payload["_meta"] = {
                            "source": "eastmoney:index",
                            "variant": str(variant),
                            "priority": str(priority_override or _effective_priority() or ""),
                            "ts": int(time.time()),
                        }
                    except Exception:
                        pass
                    _route_hit("eastmoney:index")
                    _cache_put(variant, secid, period, count, em_payload)
                    _src_ok("eastmoney.index", (time.perf_counter() - t0) * 1000.0)
                    return em_payload
                if isinstance(em_payload, dict) and int(em_payload.get("code") or 0) != 0:
                    return em_payload
            except Exception:
                _src_fail("eastmoney.index", 0.0, "exception")
                return None
        # Stock fallback
        em_stock = await _em_stock_kline_fallback(secid, period, count, timeout)
        if em_stock is not None:
            try:
                em_stock["_meta"] = {
                    "source": "eastmoney:stock",
                    "variant": str(variant),
                    "priority": str(priority_override or _effective_priority() or ""),
                    "ts": int(time.time()),
                }
            except Exception:
                pass
            _route_hit("eastmoney:stock")
            _cache_put(variant, secid, period, count, em_stock)
            _src_ok("eastmoney.stock", 0.0)
            return em_stock
        return None

    async def _try_sina() -> Dict[str, Any] | None:
        if not getattr(settings, "kline_fallback_sina", True):
            return None
        if not secid_to_sina_symbol(secid):
            return None
        try:
            t1 = time.perf_counter()
            fb = await fetch_sina_kline(secid=secid, period=period, count=count, timeout=timeout)
            if _tencent_payload_has_rows(fb):
                try:
                    fb["_meta"] = {
                        "source": "sina:index",
                        "variant": str(variant),
                        "priority": str(priority_override or _effective_priority() or ""),
                        "ts": int(time.time()),
                    }
                except Exception:
                    pass
                _route_hit("sina:index")
                _cache_put(variant, secid, period, count, fb)
                _src_ok("sina.index", (time.perf_counter() - t1) * 1000.0)
                return fb
            if isinstance(fb, dict) and int(fb.get("code") or 0) != 0:
                return fb
        except Exception:
            _src_fail("sina.index", 0.0, "exception")
            return None
        return None

    async def _try_tencent() -> Dict[str, Any] | None:
        # Skip tencent for BSE indices — it returns empty day[] for 899050 etc.
        sid_str = str(secid).strip()
        if sid_str == "0.899050" or bool(re.fullmatch(r"0\.89\d{4}", sid_str)):
            return None
        if not _tx_allow():
            return {"code": -1, "msg": "tencent kline temporarily unavailable (circuit open)", "data": {}}
        scale = "day" if period == "day" else "week" if period == "week" else "month"
        sym = secid_to_tencent_symbol(secid)
        start = "2000-01-01"
        end = "2099-12-31"
        param = f"{sym},{scale},{start},{end},{count},qfq"
        params = {"param": param, "_var": "1"}
        try:
            t2 = time.perf_counter()
            async with httpx.AsyncClient(timeout=timeout, headers={"User-Agent": "ai24x/1.0"}) as client:
                r = await client.get(TX_FQ, params=params)
                r.raise_for_status()
                txt = r.text
                j = json.loads(_strip_js_wrapper(txt))
                _tx_on_ok()
                if _tencent_payload_has_rows(j):
                    try:
                        j["_meta"] = {
                            "source": "tencent:fqkline",
                            "variant": str(variant),
                            "priority": str(priority_override or _effective_priority() or ""),
                            "ts": int(time.time()),
                        }
                    except Exception:
                        pass
                    _route_hit("tencent:fqkline")
                    _cache_put(variant, secid, period, count, j)
                    _src_ok("tencent.fqkline", (time.perf_counter() - t2) * 1000.0)
                    return j
                _src_fail("tencent.fqkline", (time.perf_counter() - t2) * 1000.0, "empty_payload")
                raise ValueError("empty tencent payload")
        except Exception:
            _src_fail("tencent.fqkline", 0.0, "exception")
            _tx_on_fail()
            return None

    last_err: Dict[str, Any] | None = None
    is_ths = str(secid).lower().startswith(("ths:", "ths."))
    best_stale: Dict[str, Any] | None = None  # fallback when all sources are stale
    for src in _priority():
        if src == "paid":
            r = await _try_paid()
            if r is not None and _tencent_payload_has_rows(r):
                return r
            if r is not None and not _tencent_payload_has_rows(r):
                # Treat "not ready / misconfigured" paid provider as a soft-fail:
                # continue falling back to public sources and avoid returning a misleading error.
                try:
                    msg = str(r.get("msg") or "").strip()
                    if (
                        "暂未就绪" in msg
                        or "token" in msg.lower()
                        or "tushare not installed" in msg.lower()
                        or "no module named" in msg.lower()
                    ):
                        continue
                except Exception:
                    pass
                last_err = r
                # v1.06: THS plates — public sources don't support ths: codes, stop here
                if is_ths:
                    return r
        elif src == "tencent":
            if is_ths:
                continue  # tencent doesn't support THS plate codes
            r = await _try_tencent()
            # circuit open returns an error payload (not None) so we can still continue
            if r is not None and _tencent_payload_has_rows(r):
                if _payload_missing_today(r) and not is_ths:
                    if best_stale is None: best_stale = r
                    continue  # stale — try next source for fresher data
                return r
            if r is not None and not _tencent_payload_has_rows(r):
                last_err = r
        elif src == "eastmoney":
            if is_ths:
                continue  # eastmoney doesn't support THS plate codes
            try:
                r = await _try_eastmoney()
            except Exception as e:
                r = {"code": -1, "msg": f"eastmoney failed: {type(e).__name__}", "data": {}}
            if r is not None and _tencent_payload_has_rows(r):
                if _payload_missing_today(r) and not is_ths:
                    if best_stale is None: best_stale = r
                    continue  # stale — try next source for fresher data
                return r
            if r is not None and not _tencent_payload_has_rows(r):
                last_err = r
        elif src == "sina":
            if is_ths:
                continue  # sina doesn't support THS plate codes
            try:
                r = await _try_sina()
            except Exception as e:
                r = {"code": -1, "msg": f"sina failed: {type(e).__name__}", "data": {}}
            if r is not None and _tencent_payload_has_rows(r):
                if _payload_missing_today(r) and not is_ths:
                    if best_stale is None: best_stale = r
                    continue  # stale — try next source for fresher data
                return r
            if r is not None and not _tencent_payload_has_rows(r):
                last_err = r

    # All sources stale or failed — try paid as last resort (data quality fallback)
    if best_stale is not None and (not allow_paid or not _paid_enabled()):
        try:
            r = await _try_paid()
            if r is not None and _tencent_payload_has_rows(r) and not _payload_missing_today(r):
                return r
        except Exception:
            pass
    if best_stale is not None:
        return best_stale

    # If Tencent failed later in the chain, retry once with its existing fallbacks.
    # This keeps legacy behavior when priority does not include eastmoney/sina.
    if last_err is None:
        last_err = {"code": -1, "msg": "kline temporarily unavailable", "data": {}}
    return last_err


async def fetch_tx_kline(
    secid: str,
    period: str,
    count: int = 500,
    timeout: float = 10.0,
    *,
    variant: str = "default",
    priority_override: str | None = None,
    allow_paid: bool = True,
) -> Dict[str, Any]:
    cached = _cache_get(variant, secid, period, count)
    if cached is not None:
        return cached

    k = (str(variant or ""), str(secid).strip(), str(period).strip(), int(count))

    async def _release_inflight(done: asyncio.Task[Dict[str, Any]]) -> None:
        async with _KLINE_INFLIGHT_LOCK:
            cur = _KLINE_INFLIGHT.get(k)
            if cur is done:
                _KLINE_INFLIGHT.pop(k, None)

    async with _KLINE_INFLIGHT_LOCK:
        t = _KLINE_INFLIGHT.get(k)
        if t is None or t.done():
            t = asyncio.create_task(
                _fetch_tx_kline_core(
                    variant=variant,
                    secid=secid,
                    period=period,
                    count=count,
                    timeout=timeout,
                    priority_override=priority_override,
                    allow_paid=allow_paid,
                )
            )
            _KLINE_INFLIGHT[k] = t
            try:
                loop = asyncio.get_running_loop()

                def _on_done(done: asyncio.Task[Dict[str, Any]]) -> None:
                    try:
                        loop.create_task(_release_inflight(done))
                    except Exception:
                        pass

                t.add_done_callback(_on_done)
            except Exception:
                pass

    return await t


async def fetch_sina_kline(secid: str, period: str, count: int = 500, timeout: float = 10.0) -> Dict[str, Any]:
    """
    Sina fallback source for a few key indices.
    Returns payload in the same "Tencent-like" shape used by frontend.
    """
    sym = secid_to_sina_symbol(secid)
    if not sym:
        return {"code": -1, "msg": "sina fallback not supported for this secid", "data": {}}

    # Sina scale: 240=day, 15=week(estimate), 0=60min
    sina_scale_map = {"day": "240", "week": "1680", "month": "7200"}
    scale = sina_scale_map.get(period, "240")
    params = {"symbol": sym, "scale": scale, "ma": "no", "datalen": str(count)}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://finance.sina.com.cn/",
    }
    async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
        r = await client.get(SINA_KLINE, params=params)
        r.raise_for_status()
        try:
            payload = r.json()
        except Exception:
            payload = json.loads(r.text)

    day_rows = _parse_sina_rows(payload)
    if not day_rows:
        return {"code": -1, "msg": "no sina kline rows", "data": {}}

    # Keep recent N
    if count > 0 and len(day_rows) > count:
        day_rows = day_rows[-count:]
    week_rows = _agg_to_week(day_rows)
    month_rows = _agg_to_month(day_rows)

    # Use a stable key (uppercase secid)
    key = str(secid).strip().upper()
    return _wrap_as_tencent_shape(key, day_rows, week_rows, month_rows)

