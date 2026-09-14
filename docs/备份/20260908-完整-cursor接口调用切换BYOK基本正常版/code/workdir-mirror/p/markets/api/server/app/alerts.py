"""Alert 提醒（纯规则，零 LLM）：价格/突破/指标触发。

- 免费档 1 个，Pro 无限；
- 触发条件全部本地计算（K线缓存 15 分钟）；
- 触发后写入 alert_events（站内提醒），并尽力发邮件（配 MARKETS_SMTP_* 才发）；
- 一次性触发：status=triggered，用户可在前端重新启用（re-arm）。

合规：只做事实描述（"price crossed above X"），无建议措辞。
"""
from __future__ import annotations

import json
import logging
import os
import smtplib
import sqlite3
import ssl
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import providers_us
from .a1_engine import signals as a1signals

logger = logging.getLogger(__name__)

_DB_DIR = Path(__file__).resolve().parents[1] / "data"
_DB_PATH = _DB_DIR / "markets.db"

FREE_ALERT_LIMIT = 1
ALERT_KINDS = ("price_above", "price_below", "breakout", "rsi_overbought", "rsi_oversold", "ma_cross")
ALERT_KIND_LABELS = {
    "price_above": "Price above",
    "price_below": "Price below",
    "breakout": "Breakout above 20-bar high",
    "rsi_overbought": "RSI-14 >= 70",
    "rsi_oversold": "RSI-14 <= 30",
    "ma_cross": "MA5 crosses above MA10",
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS alerts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL,
  symbol TEXT NOT NULL,
  kind TEXT NOT NULL,
  params TEXT DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'active',
  triggered_at TEXT,
  last_checked_at TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  UNIQUE(user_id, symbol, kind)
);
CREATE TABLE IF NOT EXISTS alert_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  alert_id INTEGER NOT NULL,
  user_id TEXT NOT NULL,
  symbol TEXT NOT NULL,
  kind TEXT NOT NULL,
  detail TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_alerts_user ON alerts(user_id);
CREATE INDEX IF NOT EXISTS idx_alert_events_user ON alert_events(user_id);
"""


def _conn() -> sqlite3.Connection:
    _DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    with _conn() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()


def alert_limit(user_id: str) -> Optional[int]:
    from . import billing

    return None if billing.is_pro(user_id) else FREE_ALERT_LIMIT


def add_alert(user_id: str, symbol: str, kind: str, params: Optional[dict] = None) -> Dict[str, Any]:
    from . import billing

    symbol = (symbol or "").strip().upper()
    kind = (kind or "").strip().lower()
    if not symbol:
        raise ValueError("empty_symbol")
    if kind not in ALERT_KINDS:
        raise ValueError(f"unknown_kind:{kind}")
    limit = alert_limit(user_id)
    with _conn() as conn:
        cnt = conn.execute(
            "SELECT COUNT(*) AS n FROM alerts WHERE user_id=? AND status='active'", (user_id,)
        ).fetchone()["n"]
        if limit is not None and int(cnt) >= int(limit):
            raise ValueError(f"alert_limit:{limit}")
        p = json.dumps(params or {}, ensure_ascii=False)
        conn.execute(
            """
            INSERT INTO alerts (user_id, symbol, kind, params, status)
            VALUES (?, ?, ?, ?, 'active')
            ON CONFLICT(user_id, symbol, kind) DO UPDATE SET params=excluded.params, status='active', triggered_at=NULL
            """,
            (user_id, symbol, kind, p),
        )
        row = conn.execute(
            "SELECT * FROM alerts WHERE user_id=? AND symbol=? AND kind=?",
            (user_id, symbol, kind),
        ).fetchone()
    return dict(row)


def list_alerts(user_id: str) -> Dict[str, Any]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM alerts WHERE user_id=? ORDER BY id DESC", (user_id,)
        ).fetchall()
        events = conn.execute(
            "SELECT * FROM alert_events WHERE user_id=? ORDER BY id DESC LIMIT 20", (user_id,)
        ).fetchall()
    alerts = []
    for r in rows:
        d = dict(r)
        try:
            d["params"] = json.loads(d.get("params") or "{}")
        except Exception:
            d["params"] = {}
        alerts.append(d)
    return {
        "alerts": alerts,
        "events": [dict(e) for e in events],
        "limit": alert_limit(user_id),
        "kind_labels": ALERT_KIND_LABELS,
    }


def delete_alert(user_id: str, alert_id: int) -> bool:
    with _conn() as conn:
        cur = conn.execute(
            "DELETE FROM alerts WHERE id=? AND user_id=?", (alert_id, user_id)
        )
        return cur.rowcount > 0


def rearm_alert(user_id: str, alert_id: int) -> Optional[Dict[str, Any]]:
    """重新启用已触发提醒（一次性触发 → active，清触发记录）。"""
    with _conn() as conn:
        cur = conn.execute(
            "UPDATE alerts SET status='active', triggered_at=NULL WHERE id=? AND user_id=?",
            (alert_id, user_id),
        )
        if cur.rowcount <= 0:
            return None
        row = conn.execute(
            "SELECT * FROM alerts WHERE id=? AND user_id=?", (alert_id, user_id)
        ).fetchone()
    d = dict(row)
    try:
        d["params"] = json.loads(d.get("params") or "{}")
    except Exception:
        d["params"] = {}
    return d


def _to_candles(rows: List[List[Any]], period: str = "day"):
    candles = a1signals.candles_from_tencent_like_pack({"day": rows}, "day")
    return candles


def _rsi(closes: List[float], period: int = 14) -> Optional[float]:
    if len(closes) <= period:
        return None
    gains, losses = 0.0, 0.0
    for i in range(1, period + 1):
        chg = closes[i] - closes[i - 1]
        if chg >= 0:
            gains += chg
        else:
            losses -= chg
    avg_g, avg_l = gains / period, losses / period
    for i in range(period + 1, len(closes)):
        chg = closes[i] - closes[i - 1]
        avg_g = (avg_g * (period - 1) + max(chg, 0.0)) / period
        avg_l = (avg_l * (period - 1) + max(-chg, 0.0)) / period
    if avg_l == 0.0:
        return 100.0 if avg_g > 0 else 50.0
    return 100.0 - 100.0 / (1.0 + avg_g / avg_l)


def evaluate_alert(alert: Dict[str, Any], candles: List[Any]) -> Optional[str]:
    """评估单个提醒，命中返回英文事实描述，否则 None。"""
    if not candles or len(candles) < 25:
        return None
    closes = [float(c.close) for c in candles]
    highs = [float(c.high) for c in candles]
    lows = [float(c.low) for c in candles]
    last = closes[-1]
    kind = alert["kind"]
    params = alert.get("params") or {}
    if kind == "price_above":
        thr = float(params.get("threshold") or 0)
        if thr and last >= thr:
            return f"Price {last:.2f} is at or above {thr:.2f}"
    if kind == "price_below":
        thr = float(params.get("threshold") or 0)
        if thr and last <= thr:
            return f"Price {last:.2f} is at or below {thr:.2f}"
    if kind == "breakout":
        prev_hi = max(highs[-21:-1])
        if prev_hi > 0 and last > prev_hi:
            return f"Price {last:.2f} broke above the prior 20-bar high {prev_hi:.2f}"
    if kind in ("rsi_overbought", "rsi_oversold"):
        r = _rsi(closes)
        if r is not None and kind == "rsi_overbought" and r >= 70:
            return f"RSI-14 at {r:.0f} (>= 70)"
        if r is not None and kind == "rsi_oversold" and r <= 30:
            return f"RSI-14 at {r:.0f} (<= 30)"
    if kind == "ma_cross":
        if len(closes) >= 11:
            p5, p10 = sum(closes[-6:-1]) / 5, sum(closes[-11:-1]) / 10
            c5, c10 = sum(closes[-5:]) / 5, sum(closes[-10:]) / 10
            if p5 <= p10 and c5 > c10:
                return "MA5 crossed above MA10"
    return None


async def evaluate_user_alerts(user_id: str) -> List[Dict[str, Any]]:
    """评估用户全部 active 提醒，命中即置 triggered + 写事件。返回新触发事件。"""
    with _conn() as conn:
        rows = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM alerts WHERE user_id=? AND status='active'", (user_id,)
            ).fetchall()
        ]
    for alert in rows:
        try:
            alert["params"] = json.loads(alert.get("params") or "{}")
        except Exception:
            alert["params"] = {}
    out: List[Dict[str, Any]] = []
    by_symbol: Dict[str, Any] = {}
    for alert in rows:
        sym = alert["symbol"]
        if sym not in by_symbol:
            try:
                obj = await providers_us.get_kline_rows(sym, "day", 60)
                by_symbol[sym] = _to_candles(obj.get("rows") or [])
            except Exception as e:  # noqa: BLE001
                logger.warning("alert kline failed symbol=%s err=%s", sym, e)
                by_symbol[sym] = []
        detail = evaluate_alert(alert, by_symbol.get(sym) or [])
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        if detail:
            with _conn() as conn:
                conn.execute(
                    "UPDATE alerts SET status='triggered', triggered_at=?, last_checked_at=? WHERE id=?",
                    (now, now, alert["id"]),
                )
                conn.execute(
                    """
                    INSERT INTO alert_events (alert_id, user_id, symbol, kind, detail)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (alert["id"], user_id, alert["symbol"], alert["kind"], detail),
                )
                conn.commit()
            out.append({"id": alert["id"], "symbol": alert["symbol"], "kind": alert["kind"], "detail": detail})
        else:
            with _conn() as conn:
                conn.execute("UPDATE alerts SET last_checked_at=? WHERE id=?", (now, alert["id"]))
                conn.commit()
    return out


def _email_configured() -> bool:
    return bool(os.environ.get("MARKETS_SMTP_HOST") and os.environ.get("MARKETS_SMTP_USER")
                and os.environ.get("MARKETS_SMTP_PASSWORD"))


def send_alert_email(user_email: str, symbol: str, detail: str) -> bool:
    """尽力发提醒邮件；未配 MARKETS_SMTP_* 时静默跳过。"""
    if not _email_configured() or not user_email:
        return False
    host = os.environ.get("MARKETS_SMTP_HOST", "")
    port = int(os.environ.get("MARKETS_SMTP_PORT", "587"))
    user = os.environ.get("MARKETS_SMTP_USER", "")
    password = os.environ.get("MARKETS_SMTP_PASSWORD", "")
    frm = os.environ.get("MARKETS_SMTP_FROM") or user
    try:
        msg = EmailMessage()
        msg["Subject"] = f"AI24X Markets Alert · {symbol}"
        msg["From"] = frm
        msg["To"] = user_email
        msg.set_content(
            f"{symbol}: {detail}\n\n"
            "This notification is for educational purposes only and is not investment advice. "
            "Market data is delayed at least 15 minutes."
        )
        use_ssl = bool(os.environ.get("MARKETS_SMTP_SSL"))
        if use_ssl or port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=20, context=ssl.create_default_context()) as smtp:
                smtp.login(user, password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=20) as smtp:
                smtp.ehlo()
                if os.environ.get("MARKETS_SMTP_TLS", "1") != "0":
                    smtp.starttls(context=ssl.create_default_context())
                    smtp.ehlo()
                smtp.login(user, password)
                smtp.send_message(msg)
        return True
    except Exception as e:  # noqa: BLE001
        logger.warning("alert email failed email=%s err=%s", user_email, e)
        return False


init_db()
