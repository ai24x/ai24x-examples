"""AI24X Markets API — Phase 1+2: US quotes, K-line, indicators, watchlist, subscriptions."""

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from fastapi import FastAPI, Body, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

from . import providers_us
from .a1_engine import signals as a1signals
from . import billing
from . import paypal
from . import ai_brief
from . import screener

SERVICE_NAME = "AI24X-markets-api"
PORT = 18012
_WEB_DIR = Path(__file__).resolve().parents[3] / "web"
CORE_BASE = os.environ.get("AI24X_CORE_BASE", "http://127.0.0.1:8000").rstrip("/")

app = FastAPI(
    title="AI24X Markets API",
    description="15-min delayed US market data + technical indicators (educational, not investment advice).",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:18012",
        "https://markets.ai24x.com",
        "https://www.ai24x.com",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
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


@app.get("/api/me")
async def api_me(request: Request):
    """代验核心层登录态：AI24X Markets 与 www 共用同一账号体系。"""
    auth = (request.headers.get("Authorization") or "").strip()
    if not auth.lower().startswith("bearer "):
        return JSONResponse(status_code=401, content={"code": -1, "msg": "missing bearer token"})
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(CORE_BASE + "/v1/user/info", headers={"Authorization": auth})
        if r.status_code != 200:
            return JSONResponse(
                status_code=401, content={"code": -1, "msg": "invalid session", "status": r.status_code}
            )
        return {"code": 0, "data": r.json()}
    except Exception as e:
        print(f"[markets] /api/me auth upstream error: {e!r}", file=sys.stderr)
        return JSONResponse(
            status_code=502, content={"code": -1, "msg": "auth service unavailable"}
        )


async def _auth_user_id(request: Request) -> str:
    """校验 Bearer 会话并返回核心层 user_id（str）。401 抛异常由上层转 JSON。"""
    auth = (request.headers.get("Authorization") or "").strip()
    if not auth.lower().startswith("bearer "):
        raise ValueError("missing_bearer_token")
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(CORE_BASE + "/v1/user/info", headers={"Authorization": auth})
    except Exception as e:
        print(f"[markets] _auth_user_id core upstream error: {e!r}", file=sys.stderr)
        raise RuntimeError("auth_service_unavailable")
    if r.status_code != 200:
        raise ValueError("invalid_session")
    data = r.json() or {}
    uid = data.get("user_id")
    if uid is None:
        raise ValueError("missing_user_id")
    return str(uid)


@app.get("/api/watchlist")
async def api_watchlist_list(request: Request):
    try:
        uid = await _auth_user_id(request)
        return {"code": 0, "data": {"symbols": billing.list_watch(uid), "limit": billing.watch_limit(uid)}}
    except ValueError as e:
        return JSONResponse(status_code=401, content={"code": -1, "msg": str(e)})
    except Exception as e:
        return {"code": -1, "msg": str(e), "data": {}}


@app.post("/api/watchlist")
async def api_watchlist_add(request: Request, payload: dict = Body(...)):
    try:
        uid = await _auth_user_id(request)
        symbol = str((payload or {}).get("symbol") or "").strip()
        if not symbol:
            raise ValueError("empty_symbol")
        info = billing.add_watch(uid, symbol)
        return {"code": 0, "data": info}
    except ValueError as e:
        msg = str(e)
        if msg.startswith("watch_limit"):
            return JSONResponse(status_code=403, content={"code": -1, "msg": msg})
        if msg in ("missing_bearer_token", "invalid_session", "missing_user_id"):
            return JSONResponse(status_code=401, content={"code": -1, "msg": msg})
        return JSONResponse(status_code=400, content={"code": -1, "msg": msg})
    except Exception as e:
        return JSONResponse(status_code=500, content={"code": -1, "msg": str(e)})


@app.delete("/api/watchlist")
async def api_watchlist_remove(request: Request, symbol: str = Query(..., min_length=1, max_length=20)):
    try:
        uid = await _auth_user_id(request)
        removed = billing.remove_watch(uid, symbol)
        return {"code": 0, "data": {"removed": removed}}
    except ValueError as e:
        return JSONResponse(status_code=401, content={"code": -1, "msg": str(e)})
    except RuntimeError as e:
        return JSONResponse(status_code=503, content={"code": -1, "msg": str(e)})
    except Exception as e:
        print(f"[markets] /api/subscribe/status error: {e!r}", file=sys.stderr)
        return JSONResponse(status_code=500, content={"code": -1, "msg": "internal_error"})


@app.get("/api/subscribe/status")
async def api_subscribe_status(request: Request):
    try:
        uid = await _auth_user_id(request)
        sub = billing.get_subscription(uid)
        return {
            "code": 0,
            "data": {
                "pro": sub is not None,
                "plan": (sub or {}).get("plan"),
                "expires_at": (sub or {}).get("expires_at"),
                "brief_remaining": billing.ai_brief_remaining(uid),
            },
        }
    except ValueError as e:
        return JSONResponse(status_code=401, content={"code": -1, "msg": str(e)})
    except Exception as e:
        return JSONResponse(status_code=500, content={"code": -1, "msg": str(e)})


@app.post("/api/subscribe/checkout")
async def api_subscribe_checkout(request: Request, payload: dict = Body(...)):
    try:
        uid = await _auth_user_id(request)
        plan = str((payload or {}).get("plan") or "monthly").strip().lower()
        if plan not in billing.PLANS:
            raise ValueError(f"unknown_plan:{plan}")
        result = await paypal.create_checkout(uid, plan)
        return {"code": 0, "data": result}
    except ValueError as e:
        msg = str(e)
        if msg in ("missing_bearer_token", "invalid_session", "missing_user_id"):
            return JSONResponse(status_code=401, content={"code": -1, "msg": msg})
        return JSONResponse(status_code=400, content={"code": -1, "msg": msg})
    except RuntimeError as e:
        return JSONResponse(status_code=503, content={"code": -1, "msg": str(e)})
    except Exception as e:
        print(f"[markets] /api/subscribe/checkout error: {e!r}", file=sys.stderr)
        return JSONResponse(status_code=500, content={"code": -1, "msg": "internal_error"})


@app.post("/api/subscribe/capture")
async def api_subscribe_capture(request: Request, payload: dict = Body(...)):
    """PayPal 支付返回后 Capture + 履约（也可当「确认到账」，幂等）。"""
    try:
        uid = await _auth_user_id(request)
        order_id = str((payload or {}).get("order_id") or "").strip()
        if not order_id:
            raise ValueError("missing_order_id")
        result = await paypal.capture_and_fulfill(order_id)
        return {"code": 0, "data": result}
    except ValueError as e:
        msg = str(e)
        if msg in ("missing_bearer_token", "invalid_session", "missing_user_id"):
            return JSONResponse(status_code=401, content={"code": -1, "msg": msg})
        return JSONResponse(status_code=400, content={"code": -1, "msg": msg})
    except RuntimeError as e:
        return JSONResponse(status_code=503, content={"code": -1, "msg": str(e)})
    except Exception as e:
        print(f"[markets] /api/subscribe/capture error: {e!r}", file=sys.stderr)
        return JSONResponse(status_code=500, content={"code": -1, "msg": "internal_error"})


@app.post("/api/ai/brief")
async def api_ai_brief(request: Request, payload: dict = Body(...)):
    """AI 技术体检点评（Pro 主力；免费档日 3 次）。描述性输出，不构成投资建议。"""
    try:
        uid = await _auth_user_id(request)
        symbol = str((payload or {}).get("symbol") or "").strip()
        period = str((payload or {}).get("period") or "day").strip().lower()
        if not symbol:
            raise ValueError("empty_symbol")
        data = await ai_brief.generate_brief(uid, symbol, period)
        return {"code": 0, "data": data}
    except ValueError as e:
        msg = str(e)
        if msg in ("missing_bearer_token", "invalid_session", "missing_user_id"):
            return JSONResponse(status_code=401, content={"code": -1, "msg": msg})
        if msg == "quota_exceeded":
            return JSONResponse(status_code=403, content={"code": -1, "msg": msg})
        return JSONResponse(status_code=400, content={"code": -1, "msg": msg})
    except RuntimeError as e:
        return JSONResponse(status_code=503, content={"code": -1, "msg": str(e)})
    except Exception as e:
        return JSONResponse(status_code=500, content={"code": -1, "msg": str(e)})


@app.post("/api/paypal/webhook")
async def api_paypal_webhook(request: Request):
    body = (await request.body()).decode("utf-8", errors="replace")
    headers = {
        "PAYPAL-TRANSMISSION-ID": request.headers.get("paypal-transmission-id", ""),
        "PAYPAL-TRANSMISSION-TIME": request.headers.get("paypal-transmission-time", ""),
        "PAYPAL-CERT-URL": request.headers.get("paypal-cert-url", ""),
        "PAYPAL-AUTH-ALGO": request.headers.get("paypal-auth-algo", ""),
        "PAYPAL-TRANSMISSION-SIG": request.headers.get("paypal-transmission-sig", ""),
    }
    try:
        result = await paypal.handle_webhook(headers, body)
        return {"code": 0, "data": result}
    except PermissionError as e:
        return JSONResponse(status_code=400, content={"code": -1, "msg": str(e)})
    except Exception as e:
        return JSONResponse(status_code=500, content={"code": -1, "msg": str(e)})


@app.get("/api/kline")
async def api_kline(
    symbol: str = Query(..., min_length=1, max_length=20),
    period: str = Query("day", pattern="^(day|week|month)$"),
    count: int = Query(500, ge=10, le=1500),
):
    try:
        obj = await providers_us.get_kline_rows(symbol, period, count)
        candles = _to_candles(obj["rows"][-count:], period)
        data = _base_payload(symbol, period, candles, obj["source"])
        data["candles"] = a1signals.rows_from_candles(candles)
        return {"code": 0, "data": data}
    except Exception as e:
        payload = {"code": -1, "msg": str(e), "data": {}}
        if isinstance(e, providers_us.SymbolNotFoundError):
            payload["suggested"] = e.suggested
        return payload


@app.get("/api/signals")
async def api_signals(
    symbol: str = Query(..., min_length=1, max_length=20),
    period: str = Query("day", pattern="^(day|week|month)$"),
    count: int = Query(500, ge=10, le=1500),
):
    try:
        obj = await providers_us.get_kline_rows(symbol, period, count)
        candles = _to_candles(obj["rows"][-count:], period)
        cache_key = f"markets:{symbol.upper()}:{period}:{obj['source']}"
        sig = a1signals.build_signals_v3(candles, cache_key=cache_key)
        closes = [float(c.close) for c in candles]
        ma = {str(n): a1signals._sma(closes, n) for n in (5, 10, 20, 60)}
        data = _base_payload(symbol, period, candles, obj["source"])
        score = screener.compute_score(symbol, period, candles)
        data.update(
            {
                "candles": a1signals.rows_from_candles(candles),
                "markers": sig.get("markers", []),
                "bar_labels": [],
                "macd": sig.get("macd", []),
                "ma": ma,
                "rsi": _rsi_series(closes, 14),
                "score": score,
            }
        )
        return {"code": 0, "data": data}
    except Exception as e:
        payload = {"code": -1, "msg": str(e), "data": {}}
        if isinstance(e, providers_us.SymbolNotFoundError):
            payload["suggested"] = e.suggested
        return payload


@app.get("/api/score")
async def api_score(
    symbol: str = Query(..., min_length=1, max_length=20),
    period: str = Query("day", pattern="^(day|week|month)$"),
    count: int = Query(300, ge=60, le=800),
):
    """0-100 technical health score（免费，仅本地指标，不消耗 AI 额度）。"""
    try:
        obj = await providers_us.get_kline_rows(symbol, period, count)
        candles = _to_candles(obj["rows"][-count:], period)
        score = screener.compute_score(symbol, period, candles)
        return {"code": 0, "data": score}
    except Exception as e:
        payload = {"code": -1, "msg": str(e), "data": {}}
        if isinstance(e, providers_us.SymbolNotFoundError):
            payload["suggested"] = e.suggested
        return payload


@app.get("/api/screener")
async def api_screener(
    mode: str = Query("all", pattern="^(all|Bottom volume surge|Breakout on volume|Uptrend building|MACD momentum building|Pullback holding near MAs)$"),
    limit: int = Query(24, ge=1, le=40),
):
    """美股技术扫描：底部放量异动 / 放量突破 / 趋势启动 / 回踩企稳（教育用途）。"""
    try:
        data = await screener.run_screener(mode, limit)
        return {"code": 0, "data": data}
    except Exception as e:
        return {"code": -1, "msg": str(e), "data": {}}


app.mount("/", StaticFiles(directory=str(_WEB_DIR), html=True), name="web")
