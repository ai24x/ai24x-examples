"""US market data providers (markets subproject).

主链: Tencent -> Eastmoney -> Sina daily -> cache -> error.
所有源统一返回 Candle rows: [date, open, close, high, low, vol]（与行情官口径一致）。
"""
from __future__ import annotations

import asyncio
import json
import time
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

_CACHE_DIR = Path(__file__).resolve().parent / ".." / "data" / "cache"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ---------- symbol mapping ----------
_TX_SYMBOL_MAP = {
    "^GSPC": "usINX",
    "^IXIC": "usIXIC",
    "^DJI": "usDJI",
    "^VIX": "usVIX",
}
_EM_INDEX_MAP = {
    "usINX": "100.SPX",
    "usIXIC": "100.NDX",
    "usDJI": "100.DJI",
}
_EM_MARKET_PREFIXES = ("105.", "106.", "107.")

_client: Optional[httpx.AsyncClient] = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            timeout=12.0,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
        )
    return _client


def to_tencent_symbol(symbol: str) -> str:
    s = (symbol or "").strip().upper()
    if not s:
        raise ValueError("empty symbol")
    if s in _TX_SYMBOL_MAP:
        return _TX_SYMBOL_MAP[s]
    if s.startswith("US") and len(s) > 2:
        return s
    return "us" + s


def _em_secids(symbol: str) -> List[str]:
    s = (symbol or "").strip().upper()
    tx = to_tencent_symbol(s)
    if tx in _EM_INDEX_MAP:
        return [_EM_INDEX_MAP[tx]]
    bare = s[2:] if s.startswith("US") else s
    return [p + bare for p in _EM_MARKET_PREFIXES]


def _f(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        s = str(x).strip()
        if not s:
            return None
        v = float(s)
        return v if v == v else None
    except Exception:
        return None


# ---------- rate gates & circuit breaker ----------
class _RateGate:
    def __init__(self, min_interval: float, per_minute: int):
        self.min_interval = min_interval
        self.per_minute = per_minute
        self._last = 0.0
        self._times: List[float] = []
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            wait = self._last + self.min_interval - now
            cutoff = now - 60.0
            self._times = [t for t in self._times if t > cutoff]
            if len(self._times) >= self.per_minute and self._times:
                wait = max(wait, self._times[0] + 60.0 - now)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last = time.monotonic()
            self._times.append(self._last)


_TX_GATE = _RateGate(0.5, 120)
_EM_GATE = _RateGate(0.5, 90)
_SINA_GATE = _RateGate(1.0, 60)

_CIRCUIT: Dict[str, Dict[str, Any]] = {}


def _circuit_open(source: str) -> bool:
    info = _CIRCUIT.get(source)
    return bool(info and info["open_until"] > time.time())


def _circuit_note(source: str, ok: bool) -> None:
    info = _CIRCUIT.setdefault(source, {"fail_count": 0, "open_until": 0.0})
    if ok:
        info["fail_count"] = 0
        info["open_until"] = 0.0
        return
    info["fail_count"] += 1
    if info["fail_count"] >= 3:
        info["open_until"] = time.time() + 150.0
        info["fail_count"] = 0


class _SourceError(RuntimeError):
    pass


# ---------- Tencent (primary) ----------
async def fetch_tencent_kline(symbol: str, count: int = 500) -> Tuple[List[List[Any]], List[str]]:
    """Return (rows, qt_fields). rows: [date, open, close, high, low, vol]."""
    tx = to_tencent_symbol(symbol)
    if _circuit_open("tencent"):
        raise _SourceError("tencent circuit open")

    # 指数直接带 us 前缀即可（usINX/usIXIC/usDJI/usVIX）
    if tx in _TX_SYMBOL_MAP.values():
        codes = [tx]
    else:
        # 个股/ETF 必须带市场后缀：AAPL.OQ / SPY.AM / BRK.A.N
        # 优先从行情快照取市场限定代码（field[2]），失败则按候选后缀逐个试
        codes: List[str] = []
        try:
            quote = await fetch_tencent_quote(symbol)
            mkt = quote.get("market_code") or ""
            if mkt:
                codes.append("us" + mkt)
        except Exception:
            pass
        bare = symbol.upper()
        if bare.startswith("US"):
            bare = bare[2:]
        codes += [f"us{bare}{s}" for s in (".OQ", ".AM", ".N")]

    last_err: Optional[Exception] = None
    await _TX_GATE.acquire()
    try:
        client = _get_client()
        for code in dict.fromkeys(codes):
            try:
                url = f"https://web.ifzq.gtimg.cn/appstock/app/usfqkline/get?param={code},day,,,{count},qfq"
                r = await client.get(url)
                r.raise_for_status()
                payload = r.json()
                node = (payload.get("data") or {}).get(code) or {}
                rows = node.get("day") or node.get("qfqday") or []
                qt = (node.get("qt") or {}).get(code) or []
                if len(rows) >= min(30, count):
                    _circuit_note("tencent", True)
                    return rows, qt
                last_err = _SourceError(f"tencent kline short ({len(rows)} rows) for {code}")
            except Exception as e:
                last_err = e
                continue
        raise last_err or _SourceError("no tencent kline code matched")
    except Exception as e:
        _circuit_note("tencent", False)
        raise _SourceError(f"tencent kline failed: {e}") from e


async def fetch_tencent_quote(symbol: str) -> Dict[str, Any]:
    tx = to_tencent_symbol(symbol)
    await _TX_GATE.acquire()
    try:
        client = _get_client()
        url = f"https://qt.gtimg.cn/q={tx}"
        r = await client.get(url)
        r.raise_for_status()
        text = r.text
        key = f'v_{tx}="'
        start = text.find(key)
        if start < 0:
            raise _SourceError("tencent quote missing")
        end = text.find('"', start + len(key))
        fields = text[start + len(key):end].split("~")
        if len(fields) < 40:
            raise _SourceError("tencent quote short")
        _circuit_note("tencent", True)
        name_en = fields[46] if len(fields) > 46 else ""
        return {
            "symbol": symbol.upper(),
            "name": name_en or fields[2],
            "market_code": fields[2] if len(fields) > 2 else "",
            "price": _f(fields[3]),
            "prev_close": _f(fields[4]),
            "open": _f(fields[5]),
            "high": _f(fields[33]) if len(fields) > 33 else None,
            "low": _f(fields[34]) if len(fields) > 34 else None,
            "change": _f(fields[31]) if len(fields) > 31 else None,
            "pct": _f(fields[32]) if len(fields) > 32 else None,
            "volume": _f(fields[6]),
            "amount": _f(fields[37]) if len(fields) > 37 else None,
            "time": fields[30] if len(fields) > 30 else "",
            "currency": fields[35] if len(fields) > 35 else "USD",
            "pe": _f(fields[39]) if len(fields) > 39 else None,
            "source": "tencent",
        }
    except Exception as e:
        _circuit_note("tencent", False)
        raise _SourceError(f"tencent quote failed: {e}") from e


# ---------- Eastmoney (fallback 1) ----------
async def fetch_em_kline(symbol: str, count: int = 500) -> List[List[Any]]:
    if _circuit_open("eastmoney"):
        raise _SourceError("eastmoney circuit open")
    secids = _em_secids(symbol)
    last_err: Optional[Exception] = None
    await _EM_GATE.acquire()
    try:
        client = _get_client()
        for sid in secids:
            url = (
                f"https://push2his.eastmoney.com/api/qt/stock/kline/get?secid={sid}&klt=101&fqt=1"
                f"&lmt={count}&end=20500101&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57"
            )
            try:
                r = await client.get(url)
                r.raise_for_status()
                data = (r.json() or {}).get("data") or {}
                klines = data.get("klines") or []
                rows: List[List[Any]] = []
                for line in klines:
                    parts = str(line).split(",")
                    if len(parts) >= 6:
                        rows.append([parts[0], parts[1], parts[2], parts[3], parts[4], parts[5]])
                if rows:
                    _circuit_note("eastmoney", True)
                    return rows
            except Exception as e:
                last_err = e
                continue
    finally:
        pass
    _circuit_note("eastmoney", False)
    raise _SourceError(f"eastmoney kline failed: {last_err}")


# ---------- Sina daily (fallback 2, individual stocks only) ----------
async def fetch_sina_kline(symbol: str, count: int = 500) -> List[List[Any]]:
    if _circuit_open("sina"):
        raise _SourceError("sina circuit open")
    bare = symbol.upper().replace("^", "")
    if bare.startswith("US"):
        bare = bare[2:]
    if bare in ("INX", "IXIC", "DJI", "VIX"):
        raise _SourceError("sina index not supported")
    await _SINA_GATE.acquire()
    try:
        client = _get_client()
        url = (
            "https://stock.finance.sina.com.cn/usstock/api/jsonp.php/var%20_=/US_MinKService.getDailyK"
            f"?symbol={bare}"
        )
        r = await client.get(url)
        r.raise_for_status()
        text = r.text
        marker = "var _="
        body = text[text.find(marker) + len(marker):].strip()
        if body.startswith("("):
            body = body[1:]
        if body.endswith(");"):
            body = body[:-2]
        items = json.loads(body)
        if not isinstance(items, list):
            raise _SourceError("sina bad payload")
        rows: List[List[Any]] = []
        for it in items:
            d = str(it.get("d") or "")
            if len(d) == 10:
                rows.append([d, it.get("o"), it.get("c"), it.get("h"), it.get("l"), it.get("v")])
        if not rows:
            raise _SourceError("sina empty")
        _circuit_note("sina", True)
        return rows[-count:]
    except Exception as e:
        _circuit_note("sina", False)
        raise _SourceError(f"sina kline failed: {e}") from e


# ---------- cache & orchestration ----------
def _today_str() -> str:
    return date.today().isoformat()


def _cache_file(kind: str, symbol: str, period: str) -> Path:
    tx = to_tencent_symbol(symbol).replace("^", "")
    return _CACHE_DIR / f"{kind}_{tx}_{period}.json"


async def get_kline_rows(symbol: str, period: str = "day", count: int = 500) -> Dict[str, Any]:
    period = period or "day"
    cache = _cache_file("kline", symbol, period)
    if cache.exists():
        try:
            obj = json.loads(cache.read_text(encoding="utf-8"))
            if obj.get("day") == _today_str() and len(obj.get("rows", [])) >= min(count, 30):
                return obj
        except Exception:
            pass

    rows: List[List[Any]] = []
    source = ""
    try:
        rows, _qt = await fetch_tencent_kline(symbol, count)
        source = "tencent"
    except Exception:
        try:
            rows = await fetch_em_kline(symbol, count)
            source = "eastmoney"
        except Exception:
            try:
                rows = await fetch_sina_kline(symbol, count)
                source = "sina"
            except Exception as e:
                if cache.exists():
                    try:
                        obj = json.loads(cache.read_text(encoding="utf-8"))
                        if obj.get("rows"):
                            obj["source"] = "cache"
                            return obj
                    except Exception:
                        pass
                raise _SourceError(f"all sources failed for {symbol}: {e}") from e

    if not rows:
        raise _SourceError(f"no data for {symbol}")
    obj = {"symbol": symbol, "period": period, "day": _today_str(), "rows": rows, "source": source}
    try:
        cache.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
    return obj


async def get_quote(symbol: str) -> Dict[str, Any]:
    cache = _cache_file("quote", symbol, "rt")
    if cache.exists():
        try:
            obj = json.loads(cache.read_text(encoding="utf-8"))
            price = obj.get("price")
            if time.time() - obj.get("ts", 0) < 30 and price and price > 0:
                return obj
        except Exception:
            pass
    quote = await fetch_tencent_quote(symbol)
    price = quote.get("price")
    if price is None or price <= 0:
        raise _SourceError(f"symbol not found: {symbol}")
    quote["ts"] = time.time()
    try:
        cache.write_text(json.dumps(quote, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
    return quote
