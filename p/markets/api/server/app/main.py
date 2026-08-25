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
from . import admin_api
from . import alerts

SERVICE_NAME = "AI24X-markets-api"
PORT = 18012
_WEB_DIR = Path(__file__).resolve().parents[3] / "web"
_BRIEF_DIR = Path(__file__).resolve().parents[3] / "data" / "brief"
CORE_BASE = os.environ.get("AI24X_CORE_BASE", "http://127.0.0.1:8000").rstrip("/")

app = FastAPI(
    title="AI24X Markets API",
    description="15-min delayed US market data + technical indicators (educational, not investment advice).",
    version="0.1.0",
)
app.include_router(admin_api.router)

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
                "trial": billing.trial_info(uid),
            },
        }
    except ValueError as e:
        return JSONResponse(status_code=401, content={"code": -1, "msg": str(e)})
    except Exception as e:
        return JSONResponse(status_code=500, content={"code": -1, "msg": str(e)})


@app.post("/api/subscribe/trial")
async def api_subscribe_trial(request: Request):
    """领取 7 天 Pro 体验券（每账号限一次；已 Pro 不可领）。"""
    try:
        uid = await _auth_user_id(request)
        sub = billing.grant_trial(uid)
        return {
            "code": 0,
            "data": {
                "pro": True,
                "plan": sub["plan"],
                "expires_at": sub["expires_at"],
                "source": "trial",
                "trial": billing.trial_info(uid),
            },
        }
    except ValueError as e:
        msg = str(e)
        if msg in ("trial_used", "already_pro"):
            return JSONResponse(status_code=403, content={"code": -1, "msg": msg})
        return JSONResponse(status_code=401, content={"code": -1, "msg": msg})
    except Exception as e:
        print(f"[markets] /api/subscribe/trial error: {e!r}", file=sys.stderr)
        return JSONResponse(status_code=500, content={"code": -1, "msg": "internal_error"})


@app.get("/api/subscribe/plans")
async def api_subscribe_plans():
    """公开套餐目录（管理台可改；禁用套餐不展示）。供 app.html 订阅面板动态渲染。"""
    try:
        plans = []
        for pid, p in billing.resolve_plans().items():
            if not p.get("enabled", True):
                continue
            plans.append(
                {
                    "plan": pid,
                    "label": p.get("label"),
                    "usd": p.get("usd"),
                    "days": p.get("days"),
                    "description": p.get("description"),
                    "price_label": p.get("price_label") or f"${p.get('usd')}",
                    "price_label_zh": p.get("price_label_zh") or f"${p.get('usd')}",
                }
            )
        return {"code": 0, "data": {"plans": plans}}
    except Exception as e:
        print(f"[markets] /api/subscribe/plans error: {e!r}", file=sys.stderr)
        return JSONResponse(status_code=500, content={"code": -1, "msg": "internal_error"})


@app.post("/api/subscribe/checkout")
async def api_subscribe_checkout(request: Request, payload: dict = Body(...)):
    try:
        uid = await _auth_user_id(request)
        plan = str((payload or {}).get("plan") or "monthly").strip().lower()
        meta = billing.get_plan(plan)
        if not meta or not meta.get("enabled", True):
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


@app.post("/api/subscribe/fulfill")
async def api_subscribe_fulfill(request: Request, payload: dict = Body(...)):
    """统一支付中台回调：验签名 → 幂等激活订阅（webhook/查单重试安全）。

    只接受带 X-Markets-Secret 的服务端调用（核心 pay_products 配置同一密钥），
    不走用户 Bearer。订单级幂等：已 paid 且 Pro 有效直接返回 already_activated。
    """
    secret = os.environ.get("MARKETS_FULFILL_SECRET", "")
    got = (request.headers.get("x-markets-secret") or "").strip()
    if not secret or got != secret:
        return JSONResponse(status_code=403, content={"code": -1, "msg": "bad_secret"})
    otn = str((payload or {}).get("out_trade_no") or "").strip()
    uid = str((payload or {}).get("user_id") or "").strip()
    # 核心 /v1/user/info 返回 user_id=auth_<id>，与 _auth_user_id 口径一致
    if uid and not uid.startswith("auth_"):
        uid = "auth_" + uid
    plan = str((payload or {}).get("plan") or "").strip().lower()
    source = str((payload or {}).get("source") or "paypal").strip()[:16]
    meta = billing.get_plan(plan)
    if not otn or not uid or not meta or not meta.get("enabled", True):
        return JSONResponse(status_code=400, content={"code": -1, "msg": "bad_payload"})
    try:
        existing = billing.get_hub_order(otn)
        if existing and str(existing.get("status")) == "paid" and billing.is_pro(uid):
            return {"code": 0, "data": {"status": "already_activated", "out_trade_no": otn}}
        amount = float(meta["usd"])
        billing.create_hub_order(otn, f"markets:{uid}:{plan}", amount, plan, source)
        billing.mark_hub_order_paid(otn)
        sub = billing.activate_subscription(uid, plan, source=source)
        return {"code": 0, "data": {"status": "activated", "out_trade_no": otn, "subscription": sub}}
    except Exception as e:
        print(f"[markets] /api/subscribe/fulfill error: {e!r}", file=sys.stderr)
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


@app.get("/api/alerts")
async def api_alerts_list(request: Request):
    """我的提醒列表 + 最近触发事件（免费 1 个，Pro 无限）。"""
    try:
        uid = await _auth_user_id(request)
        return {"code": 0, "data": alerts.list_alerts(uid)}
    except ValueError as e:
        return JSONResponse(status_code=401, content={"code": -1, "msg": str(e)})
    except RuntimeError as e:
        return JSONResponse(status_code=503, content={"code": -1, "msg": str(e)})
    except Exception as e:
        print(f"[markets] /api/alerts list error: {e!r}", file=sys.stderr)
        return JSONResponse(status_code=500, content={"code": -1, "msg": "internal_error"})


def _brief_list() -> List[str]:
    if not _BRIEF_DIR.is_dir():
        return []
    out = []
    for p in _BRIEF_DIR.iterdir():
        if p.is_dir() and (p / "brief.md").is_file() and len(p.name) == 8 and p.name.isdigit():
            out.append(p.name)
    return sorted(out, reverse=True)


@app.get("/api/brief/latest")
async def api_brief_latest(date: Optional[str] = Query(None, min_length=8, max_length=8)):
    """最近一份每日简报（公开，全英文，纯规则无模型）。"""
    try:
        dates = _brief_list()
        if not dates:
            return {"code": 0, "data": {"available": False, "dates": []}}
        if date and date not in dates:
            date = dates[0]
        if not date:
            date = dates[0]
        d = _BRIEF_DIR / date
        html = (d / "brief.html").read_text(encoding="utf-8") if (d / "brief.html").is_file() else ""
        md = (d / "brief.md").read_text(encoding="utf-8") if (d / "brief.md").is_file() else ""
        asof = ""
        import re as _re

        m = _re.search(r"Data as of ([0-9]{4}-[0-9]{2}-[0-9]{2})", html or md)
        if m:
            asof = m.group(1)
        return {
            "code": 0,
            "data": {
                "available": True,
                "date": date,
                "asof": asof,
                "dates": dates,
                "html": html,
                "md": md,
            },
        }
    except Exception as e:
        print(f"[markets] /api/brief/latest error: {e!r}", file=sys.stderr)
        return JSONResponse(status_code=500, content={"code": -1, "msg": "internal_error"})


@app.post("/api/alerts")
async def api_alerts_create(request: Request, payload: dict = Body(...)):
    try:
        uid = await _auth_user_id(request)
        symbol = str((payload or {}).get("symbol") or "").strip()
        kind = str((payload or {}).get("kind") or "").strip().lower()
        params = payload.get("params") if isinstance(payload, dict) else None
        info = alerts.add_alert(uid, symbol, kind, params)
        return {"code": 0, "data": info}
    except ValueError as e:
        msg = str(e)
        if msg.startswith("alert_limit"):
            return JSONResponse(status_code=403, content={"code": -1, "msg": msg})
        if msg in ("missing_bearer_token", "invalid_session", "missing_user_id"):
            return JSONResponse(status_code=401, content={"code": -1, "msg": msg})
        return JSONResponse(status_code=400, content={"code": -1, "msg": msg})
    except Exception as e:
        return JSONResponse(status_code=500, content={"code": -1, "msg": str(e)})


@app.delete("/api/alerts")
async def api_alerts_delete(request: Request, alert_id: int = Query(..., ge=1)):
    try:
        uid = await _auth_user_id(request)
        removed = alerts.delete_alert(uid, alert_id)
        return {"code": 0, "data": {"removed": removed}}
    except ValueError as e:
        return JSONResponse(status_code=401, content={"code": -1, "msg": str(e)})
    except Exception as e:
        return JSONResponse(status_code=500, content={"code": -1, "msg": str(e)})


@app.post("/api/alerts/rearm")
async def api_alerts_rearm(request: Request, payload: dict = Body(...)):
    """重新启用已触发提醒（一次性触发 → active）。"""
    try:
        uid = await _auth_user_id(request)
        alert_id = int((payload or {}).get("alert_id") or 0)
        if alert_id <= 0:
            raise ValueError("bad_alert_id")
        info = alerts.rearm_alert(uid, alert_id)
        if info is None:
            return JSONResponse(status_code=404, content={"code": -1, "msg": "alert_not_found"})
        return {"code": 0, "data": info}
    except ValueError as e:
        msg = str(e)
        if msg in ("missing_bearer_token", "invalid_session", "missing_user_id"):
            return JSONResponse(status_code=401, content={"code": -1, "msg": msg})
        return JSONResponse(status_code=400, content={"code": -1, "msg": msg})
    except Exception as e:
        return JSONResponse(status_code=500, content={"code": -1, "msg": str(e)})


@app.post("/api/alerts/evaluate")
async def api_alerts_evaluate(request: Request):
    """评估我的全部 active 提醒；命中置 triggered + 写站内事件 + 尽力发邮件。"""
    try:
        uid = await _auth_user_id(request)
        triggered = await alerts.evaluate_user_alerts(uid)
        email = ""
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                r = await client.get(
                    CORE_BASE + "/v1/billing/balance",
                    headers={"Authorization": request.headers.get("Authorization", "")},
                )
            if r.status_code == 200:
                email = str((r.json() or {}).get("email") or "")
        except Exception as e:
            print(f"[markets] alerts evaluate email lookup error: {e!r}", file=sys.stderr)
        sent = 0
        for ev in triggered:
            if alerts.send_alert_email(email, ev.get("symbol", ""), ev.get("detail", "")):
                sent += 1
        return {
            "code": 0,
            "data": {
                "triggered": triggered,
                "email_configured": alerts._email_configured(),
                "email_sent": sent,
            },
        }
    except ValueError as e:
        return JSONResponse(status_code=401, content={"code": -1, "msg": str(e)})
    except RuntimeError as e:
        return JSONResponse(status_code=503, content={"code": -1, "msg": str(e)})
    except Exception as e:
        print(f"[markets] /api/alerts/evaluate error: {e!r}", file=sys.stderr)
        return JSONResponse(status_code=500, content={"code": -1, "msg": "internal_error"})


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
    request: Request,
    mode: str = Query("all", pattern="^(all|Bottom volume surge|Breakout on volume|Uptrend building|MACD momentum building|Pullback holding near MAs)$"),
    limit: int = Query(24, ge=1, le=40),
    min_mcap: Optional[float] = Query(None, ge=0),
    max_mcap: Optional[float] = Query(None, ge=0),
    min_pe: Optional[float] = Query(None, ge=0),
    max_pe: Optional[float] = Query(None, ge=0),
    min_rsi: Optional[float] = Query(None, ge=0, le=100),
    max_rsi: Optional[float] = Query(None, ge=0, le=100),
    min_pos52: Optional[float] = Query(None, ge=0, le=1),
    max_pos52: Optional[float] = Query(None, ge=0, le=1),
    min_vol_ratio: Optional[float] = Query(None, ge=0),
):
    """美股技术扫描（Pro 专属）：多因子（市值/PE/RSI/52周位置/量比）+ 形态模式（教育用途）。"""
    try:
        uid = await _auth_user_id(request)
        if not billing.is_pro(uid):
            return JSONResponse(status_code=403, content={"code": -1, "msg": "vip_required"})
        filters = {
            "min_mcap": min_mcap,
            "max_mcap": max_mcap,
            "min_pe": min_pe,
            "max_pe": max_pe,
            "min_rsi": min_rsi,
            "max_rsi": max_rsi,
            "min_pos52": min_pos52,
            "max_pos52": max_pos52,
            "min_vol_ratio": min_vol_ratio,
        }
        data = await screener.run_screener(mode, limit, filters)
        return {"code": 0, "data": data}
    except ValueError as e:
        return JSONResponse(status_code=401, content={"code": -1, "msg": str(e)})
    except Exception as e:
        return {"code": -1, "msg": str(e), "data": {}}


app.mount("/", StaticFiles(directory=str(_WEB_DIR), html=True), name="web")
