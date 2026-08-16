"""AI24X Markets · 订阅计费 + 自选（SQLite 本地存储）。

身份复用核心层账号（/api/me），本模块只存 markets 自己的订阅订单/自选。
PayPal 客户端复用核心层 pay_paypal.py（共享不复制）。
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

_DB_DIR = Path(__file__).resolve().parents[1] / "data"
_DB_PATH = _DB_DIR / "markets.db"

PLANS: Dict[str, Dict[str, Any]] = {
    "monthly": {"usd": 24.9, "days": 30, "label": "Pro Monthly", "description": "AI24X Markets Pro · 1 month"},
    "yearly": {"usd": 199.0, "days": 365, "label": "Pro Yearly", "description": "AI24X Markets Pro · 1 year"},
}

FREE_WATCH_LIMIT = 3
PRO_WATCH_LIMIT = 50
FREE_AI_BRIEF_DAILY = 3

_SCHEMA = """
CREATE TABLE IF NOT EXISTS subscriptions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL,
  plan TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  started_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  source TEXT DEFAULT 'paypal',
  created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_sub_user ON subscriptions(user_id);

CREATE TABLE IF NOT EXISTS orders (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  paypal_order_id TEXT UNIQUE,
  custom_id TEXT NOT NULL,
  amount_usd REAL NOT NULL,
  plan TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'created',
  created_at TEXT DEFAULT (datetime('now')),
  paid_at TEXT
);

CREATE TABLE IF NOT EXISTS watchlist (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL,
  symbol TEXT NOT NULL,
  created_at TEXT DEFAULT (datetime('now')),
  UNIQUE(user_id, symbol)
);

CREATE TABLE IF NOT EXISTS ai_brief_usage (
  user_id TEXT NOT NULL,
  day TEXT NOT NULL,
  used INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (user_id, day)
);
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


# ---------------------------------------------------------------- 订阅

def get_subscription(user_id: str) -> Optional[Dict[str, Any]]:
    """返回用户最新一条未过期订阅（active 且 expires_at > now）。"""
    with _conn() as conn:
        row = conn.execute(
            """
            SELECT * FROM subscriptions
            WHERE user_id = ? AND status = 'active' AND expires_at > datetime('now')
            ORDER BY expires_at DESC LIMIT 1
            """,
            (user_id,),
        ).fetchone()
    return dict(row) if row else None


def is_pro(user_id: str) -> bool:
    return get_subscription(user_id) is not None


def activate_subscription(user_id: str, plan: str, source: str = "paypal") -> Dict[str, Any]:
    """激活/续订：已有未过期订阅则在其到期日上加时长，否则从现在起算。"""
    if plan not in PLANS:
        raise ValueError(f"unknown_plan:{plan}")
    days = int(PLANS[plan]["days"])
    with _conn() as conn:
        cur = conn.execute(
            """
            SELECT expires_at FROM subscriptions
            WHERE user_id = ? AND status = 'active' AND expires_at > datetime('now')
            ORDER BY expires_at DESC LIMIT 1
            """,
            (user_id,),
        ).fetchone()
        base = cur["expires_at"] if cur else None
        if base:
            sql = (
                "INSERT INTO subscriptions (user_id, plan, status, started_at, expires_at, source) "
                "VALUES (?, ?, 'active', ?, datetime(?, '+' || ? || ' days'), ?)"
            )
            params: tuple = (user_id, plan, base, base, days, source)
        else:
            sql = (
                "INSERT INTO subscriptions (user_id, plan, status, started_at, expires_at, source) "
                "VALUES (?, ?, 'active', datetime('now'), datetime('now', '+' || ? || ' days'), ?)"
            )
            params = (user_id, plan, days, source)
        conn.execute(sql, params)
        row = conn.execute(
            "SELECT * FROM subscriptions WHERE id = last_insert_rowid()"
        ).fetchone()
    return dict(row)


def expire_overdue() -> int:
    """批量把已过期的订阅标记为 expired（幂等，可每日跑）。"""
    with _conn() as conn:
        cur = conn.execute(
            "UPDATE subscriptions SET status='expired' WHERE status='active' AND expires_at <= datetime('now')"
        )
        return cur.rowcount


# ---------------------------------------------------------------- 订单

def create_order(paypal_order_id: str, custom_id: str, amount_usd: float, plan: str) -> Dict[str, Any]:
    with _conn() as conn:
        conn.execute(
            "INSERT INTO orders (paypal_order_id, custom_id, amount_usd, plan) VALUES (?, ?, ?, ?)",
            (paypal_order_id, custom_id, amount_usd, plan),
        )
        row = conn.execute("SELECT * FROM orders WHERE id = last_insert_rowid()").fetchone()
    return dict(row)


def mark_order_paid(paypal_order_id: str) -> Optional[Dict[str, Any]]:
    with _conn() as conn:
        conn.execute(
            "UPDATE orders SET status='paid', paid_at=datetime('now') WHERE paypal_order_id=? AND status!='paid'",
            (paypal_order_id,),
        )
        row = conn.execute(
            "SELECT * FROM orders WHERE paypal_order_id = ?", (paypal_order_id,)
        ).fetchone()
    return dict(row) if row else None


def get_order(paypal_order_id: str) -> Optional[Dict[str, Any]]:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM orders WHERE paypal_order_id = ?", (paypal_order_id,)
        ).fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------------- 自选

def add_watch(user_id: str, symbol: str) -> Dict[str, Any]:
    symbol = (symbol or "").strip().upper()
    if not symbol:
        raise ValueError("empty_symbol")
    limit = PRO_WATCH_LIMIT if is_pro(user_id) else FREE_WATCH_LIMIT
    with _conn() as conn:
        cnt = conn.execute(
            "SELECT COUNT(*) AS n FROM watchlist WHERE user_id = ?", (user_id,)
        ).fetchone()["n"]
        if cnt >= limit:
            raise ValueError(f"watch_limit:{limit}")
        conn.execute(
            "INSERT OR IGNORE INTO watchlist (user_id, symbol) VALUES (?, ?)",
            (user_id, symbol),
        )
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM watchlist WHERE user_id = ?", (user_id,)
        ).fetchone()
    return {"symbol": symbol, "limit": limit, "count": int(row["n"])}


def list_watch(user_id: str) -> List[str]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT symbol FROM watchlist WHERE user_id = ? ORDER BY created_at DESC, id DESC",
            (user_id,),
        ).fetchall()
    return [r["symbol"] for r in rows]


def remove_watch(user_id: str, symbol: str) -> bool:
    with _conn() as conn:
        cur = conn.execute(
            "DELETE FROM watchlist WHERE user_id = ? AND symbol = ?",
            (user_id, (symbol or "").strip().upper()),
        )
        return cur.rowcount > 0


def watch_limit(user_id: str) -> int:
    return PRO_WATCH_LIMIT if is_pro(user_id) else FREE_WATCH_LIMIT


# ---------------------------------------------------------------- AI 点评额度

def _today_utc() -> str:
    import datetime

    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")


def ai_brief_remaining(user_id: str) -> int:
    """免费档每日剩余次数；Pro 返回 -1（不限）。"""
    if is_pro(user_id):
        return -1
    with _conn() as conn:
        row = conn.execute(
            "SELECT used FROM ai_brief_usage WHERE user_id = ? AND day = ?",
            (user_id, _today_utc()),
        ).fetchone()
    used = int(row["used"]) if row else 0
    return max(0, FREE_AI_BRIEF_DAILY - used)


def consume_ai_brief(user_id: str) -> Optional[int]:
    """消费一次 AI 点评额度，返回剩余次数；Pro 返回 -1；超限返回 None。"""
    if is_pro(user_id):
        return -1
    day = _today_utc()
    with _conn() as conn:
        row = conn.execute(
            "SELECT used FROM ai_brief_usage WHERE user_id = ? AND day = ?",
            (user_id, day),
        ).fetchone()
        used = int(row["used"]) if row else 0
        if used >= FREE_AI_BRIEF_DAILY:
            return None
        conn.execute(
            """
            INSERT INTO ai_brief_usage (user_id, day, used) VALUES (?, ?, 1)
            ON CONFLICT(user_id, day) DO UPDATE SET used = used + 1
            """,
            (user_id, day),
        )
    return FREE_AI_BRIEF_DAILY - (used + 1)


init_db()
