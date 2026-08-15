"""AI24X Markets API — Phase 1: US quotes, K-line, technical indicators."""

from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import providers_us
from .a1_engine import signals as a1signals

SERVICE_NAME = "AI24X-markets-api"
PORT = 18012
_WEB_DIR = Path(__file__).resolve().parents[3] / "web"

app = FastAPI(
    title="AI24X Markets API",
    description="15-min delayed US market data + technical indicators (educational, not investment advice).",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:18012", "https://markets.ai24x.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _rsi_series(closes: List[float], period: int = 14) -> List[Optional[float]]:
    """Wilder-smoothed RSI series, None for warmup bars."""
    n = len(closes)
    if n <= period:
        return [None] * n
    out: List[Optional[float]] = [None] * n

    def _val(avg_g: float, avg_l: float) -> float:
        if avg_l == 0.0:
            return 100.0 if avg_g > 0 else 50.0
        rs = avg_g / avg_l
        return 100.0 - 100.0 / (1.0 + rs)

    gains = 0.0
    losses = 0.0
    for i in range(1, period + 1):
        chg = closes[i] - closes[i - 1]
        if chg >= 0:
            gains += chg
        else:
            losses -= chg
    avg_g = gains / period
    avg_l = losses / period
    out[period] = _val(avg_g, avg_l)
    for i in range(period + 1, n):
        chg = closes[i] - closes[i - 1]
        avg_g = (avg_g * (period - 1) + max(chg, 0.0)) / period
        avg_l = (avg_l * (period - 1) + max(-chg, 0.0)) / period
        out[i] = _val(avg_g, avg_l)
    return out


def _to_candles(rows: List[List[Any]], period: str) -> List[Any]:
    candles = a1signals.candles_from_tencent_like_pack({"day": rows}, "day")
    if period == "week":
        candles = a1signals.aggregate_daily_to_week(candles)
    elif period == "month":
        candles = a1signals.aggregate_daily_to_month(candles)
    return candles


def _base_payload(symbol: str, period: str, candles: List[Any], source: str) -> Dict[str, Any]:
    asof = candles[-1].time if candles else ""
    return {
        "symbol": symbol.upper(),
        "period": period,
        "source": source,
        "delayed": True,
        "meta": {
            "bars": len(candles),
            "asof": asof,
            "note": "15-minute delayed market data",
        },
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": SERVICE_NAME, "port": PORT}


@app.get("/api/quote")
async def api_quote(symbol: str = Query(..., min_length=1, max_length=20)):
    try:
        quote = await providers_us.get_quote(symbol)
        return {"code": 0, "data": quote}
    except Exception as e:
        return {"code": -1, "msg": str(e), "data": {}}


@app.get("/api/kline")
async def api_kline(
    symbol: str = Query(..., min_length=1, max_length=20),
    period: str = Query("day", pattern="^(day|week|month)$"),
    count: int = Query(500, ge=10, le=1500),
):
    try:
        obj = await providers_us.get_kline_rows(symbol, period, count)
        candles = _to_candles(obj["rows"], period)
        data = _base_payload(symbol, period, candles, obj["source"])
        data["candles"] = a1signals.rows_from_candles(candles)
        return {"code": 0, "data": data}
    except Exception as e:
        return {"code": -1, "msg": str(e), "data": {}}


@app.get("/api/signals")
async def api_signals(
    symbol: str = Query(..., min_length=1, max_length=20),
    period: str = Query("day", pattern="^(day|week|month)$"),
    count: int = Query(500, ge=10, le=1500),
):
    try:
        obj = await providers_us.get_kline_rows(symbol, period, count)
        candles = _to_candles(obj["rows"], period)
        cache_key = f"markets:{symbol.upper()}:{period}:{obj['source']}"
        sig = a1signals.build_signals_v3(candles, cache_key=cache_key)
        closes = [float(c.close) for c in candles]
        ma = {str(n): a1signals._sma(closes, n) for n in (5, 10, 20, 60)}
        data = _base_payload(symbol, period, candles, obj["source"])
        data.update(
            {
                "candles": a1signals.rows_from_candles(candles),
                "markers": sig.get("markers", []),
                "bar_labels": [],
                "macd": sig.get("macd", []),
                "ma": ma,
                "rsi": _rsi_series(closes, 14),
            }
        )
        return {"code": 0, "data": data}
    except Exception as e:
        return {"code": -1, "msg": str(e), "data": {}}


app.mount("/", StaticFiles(directory=str(_WEB_DIR), html=True), name="web")
