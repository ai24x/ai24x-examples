"""AI24X Markets · 订阅计费 + 自选（SQLite 本地存储）。

身份复用核心层账号（/api/me），本模块只存 markets 自己的订阅订单/自选。
PayPal 客户端复用核心层 pay_paypal.py（共享不复制）。
"""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

_DB_DIR = Path(__file__).resolve().parents[1] / "data"
_DB_PATH = _DB_DIR / "markets.db"

PLANS: Dict[str, Dict[str, Any]] = {
    "weekly": {"usd": 9.9, "days": 7, "label": "Pro Weekly", "description": "AI24X Markets Pro · 1 week"},
    "monthly": {"usd": 24.9, "days": 30, "label": "Pro Monthly", "description": "AI24X Markets Pro · 1 month"},
    "yearly": {"usd": 199.0, "days": 365, "label": "Pro Yearly", "description": "AI24X Markets Pro · 1 year"},
}

_OVERRIDE_PATH = Path(
    os.environ.get("MARKETS_PLANS_OVERRIDE") or str(_DB_DIR / "markets_plans_override.json")
)

# 可被管理台覆盖的字段（与核心 pay_products.MARKET_PLANS 对齐）
_PLAN_EDITABLE = (
    "label", "usd", "days", "description", "enabled",
    "title_zh", "title_en", "price_label", "price_label_zh", "perk", "perk_zh",
)


def _load_plans_overrides() -> Dict[str, Dict[str, Any]]:
    try:
        if not _OVERRIDE_PATH.is_file():
            return {}
        raw = json.loads(_OVERRIDE_PATH.read_text(encoding="utf-8"))
        plans = raw.get("plans") if isinstance(raw, dict) else None
        if not isinstance(plans, dict):
            return {}
        return {str(k): (v if isinstance(v, dict) else {}) for k, v in plans.items()}
    except Exception:
        return {}


def _save_plans_overrides(plans: Dict[str, Dict[str, Any]]) -> None:
    _OVERRIDE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _OVERRIDE_PATH.write_text(
        json.dumps({"plans": plans, "updated_note": "admin_ui"}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def resolve_plans() -> Dict[str, Dict[str, Any]]:
    """代码默认 + 管理台覆盖（markets_plans_override.json），统一供订阅/履约/管理/前台读取。"""
    ov = _load_plans_overrides()
    out: Dict[str, Dict[str, Any]] = {}
    for pid, base in PLANS.items():
        p = dict(base)
        o = ov.get(pid) or {}
        for key in _PLAN_EDITABLE:
            if key in o and o[key] is not None:
                p[key] = o[key]
        p.setdefault("enabled", True)
        out[pid] = p
    return out


def get_plan(plan_id: str) -> Optional[Dict[str, Any]]:
    return resolve_plans().get(str(plan_id or "").strip().lower())


def admin_list_plans() -> Dict[str, Any]:
    """管理台套餐目录（含覆盖来源标记，供编辑回显）。"""
    ov = _load_plans_overrides()
    out = []
    for pid, p in resolve_plans().items():
        out.append(
            {
                "plan": pid,
                "label": p.get("label"),
                "usd": p.get("usd"),
                "days": p.get("days"),
                "description": p.get("description"),
                "enabled": bool(p.get("enabled", True)),
                "title_zh": p.get("title_zh"),
                "title_en": p.get("title_en"),
                "price_label": p.get("price_label"),
                "price_label_zh": p.get("price_label_zh"),
                "perk": p.get("perk"),
                "perk_zh": p.get("perk_zh"),
                "has_override": bool(ov.get(pid)),
            }
        )
    return {"plans": out}


def admin_update_plans(plans: list) -> Dict[str, Any]:
    """写入管理台覆盖（只允许改已知套餐；等于默认值的字段自动清掉，避免文件膨胀）。"""
    ov = _load_plans_overrides()
    changed: list[str] = []
    for item in plans or []:
        if not isinstance(item, dict):
            continue
        pid = str(item.get("plan") or "").strip().lower()
        base = PLANS.get(pid)
        if not base:
            continue
        defaults = dict(base)
        defaults.setdefault("enabled", True)
        cur = dict(ov.get(pid) or {})
        for key in _PLAN_EDITABLE:
            if key in item and item[key] is not None:
                cur[key] = item[key]
        cleaned = {k: v for k, v in cur.items() if v != defaults.get(k)}
        if cleaned:
            ov[pid] = cleaned
        else:
            ov.pop(pid, None)
        changed.append(pid)
    _save_plans_overrides(ov)
    return {"ok": True, "changed": changed, "note": "markets plans saved"}


FREE_WATCH_LIMIT = 10
PRO_WATCH_LIMIT = 50
FREE_AI_BRIEF_DAILY = 10

# 7 天 Pro 体验券（每账号限一次；source='trial'，到期自动过期）
TRIAL_PLAN = "trial7"
TRIAL_DAYS = 7

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
  out_trade_no TEXT UNIQUE,
  channel TEXT DEFAULT 'paypal',
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
        # 兼容旧库：hub 单新增列（SQLite ADD COLUMN 幂等）
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(orders)").fetchall()}
        if "out_trade_no" not in cols:
            # SQLite 不支持 ALTER TABLE ADD COLUMN UNIQUE → 普通列 + 唯一索引
            conn.execute("ALTER TABLE orders ADD COLUMN out_trade_no TEXT")
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_orders_out_trade_no "
                "ON orders(out_trade_no)"
            )
        if "channel" not in cols:
            conn.execute("ALTER TABLE orders ADD COLUMN channel TEXT DEFAULT 'paypal'")
        conn.commit()


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
    meta = get_plan(plan)
    if not meta or not meta.get("enabled", True):
        raise ValueError(f"unknown_plan:{plan}")
    days = int(meta["days"])
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


def has_used_trial(user_id: str) -> bool:
    with _conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM subscriptions WHERE user_id=? AND source='trial' LIMIT 1",
            (user_id,),
        ).fetchone()
    return row is not None


def trial_info(user_id: str) -> Dict[str, Any]:
    """体验券状态：granted/used/active/到期时间（幂等只读）。"""
    with _conn() as conn:
        row = conn.execute(
            """
            SELECT plan, status, started_at, expires_at,
                   CASE WHEN status='active' AND expires_at > datetime('now') THEN 1 ELSE 0 END AS active
            FROM subscriptions WHERE user_id=? AND source='trial' ORDER BY id DESC LIMIT 1
            """,
            (user_id,),
        ).fetchone()
    if not row:
        return {"granted": False, "used": False, "active": False}
    d = dict(row)
    return {
        "granted": True,
        "used": True,
        "active": bool(d["active"]),
        "plan": d["plan"],
        "status": d["status"],
        "started_at": d["started_at"],
        "expires_at": d["expires_at"],
    }


def grant_trial(user_id: str) -> Dict[str, Any]:
    """发放 7 天 Pro 体验券：已 Pro 或已领过则拒绝；到期自动过期由 expire_overdue 处理。"""
    if is_pro(user_id):
        raise ValueError("already_pro")
    if has_used_trial(user_id):
        raise ValueError("trial_used")
    with _conn() as conn:
        conn.execute(
            "INSERT INTO subscriptions (user_id, plan, status, started_at, expires_at, source) "
            "VALUES (?, ?, 'active', datetime('now'), datetime('now', '+' || ? || ' days'), 'trial')",
            (user_id, TRIAL_PLAN, TRIAL_DAYS),
        )
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

def create_hub_order(
    out_trade_no: str, custom_id: str, amount_usd: float, plan: str, channel: str = "paypal"
) -> Dict[str, Any]:
    """统一支付中台回调前的本地订单落库（out_trade_no 为外部单号）。"""
    with _conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO orders (out_trade_no, custom_id, amount_usd, plan, channel) "
            "VALUES (?, ?, ?, ?, ?)",
            (out_trade_no, custom_id, amount_usd, plan, channel),
        )
        row = conn.execute(
            "SELECT * FROM orders WHERE out_trade_no = ?", (out_trade_no,)
        ).fetchone()
    return dict(row) if row else {}


def mark_hub_order_paid(out_trade_no: str) -> Optional[Dict[str, Any]]:
    with _conn() as conn:
        conn.execute(
            "UPDATE orders SET status='paid', paid_at=datetime('now') "
            "WHERE out_trade_no=? AND status!='paid'",
            (out_trade_no,),
        )
        row = conn.execute(
            "SELECT * FROM orders WHERE out_trade_no = ?", (out_trade_no,)
        ).fetchone()
    return dict(row) if row else None


def get_hub_order(out_trade_no: str) -> Optional[Dict[str, Any]]:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM orders WHERE out_trade_no = ?", (out_trade_no,)
        ).fetchone()
    return dict(row) if row else None

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


# ---------------------------------------------------------------- 管理只读（P1，供 core 运营后台）

def admin_summary() -> Dict[str, Any]:
    """运营总览：订阅/订单/收入核心计数 + 最近 10 笔订单 + 套餐分布。"""
    with _conn() as conn:
        active = conn.execute(
            "SELECT COUNT(*) FROM subscriptions WHERE status='active' AND expires_at > datetime('now')"
        ).fetchone()[0]
        total_subs = conn.execute("SELECT COUNT(*) FROM subscriptions").fetchone()[0]
        expiring_7d = conn.execute(
            "SELECT COUNT(*) FROM subscriptions WHERE status='active' "
            "AND expires_at > datetime('now') AND expires_at <= datetime('now','+7 days')"
        ).fetchone()[0]
        paid = conn.execute("SELECT COUNT(*) FROM orders WHERE status='paid'").fetchone()[0]
        pending = conn.execute("SELECT COUNT(*) FROM orders WHERE status!='paid'").fetchone()[0]
        revenue = float(
            conn.execute(
                "SELECT COALESCE(SUM(amount_usd),0) FROM orders WHERE status='paid'"
            ).fetchone()[0]
            or 0
        )
        trial_count = int(
            conn.execute("SELECT COUNT(*) FROM subscriptions WHERE source='trial'").fetchone()[0] or 0
        )
        recent = [
            dict(r)
            for r in conn.execute(
                "SELECT id, out_trade_no, channel, custom_id, amount_usd, plan, status, "
                "created_at, paid_at FROM orders ORDER BY id DESC LIMIT 10"
            ).fetchall()
        ]
        plans = []
        for pid, p in resolve_plans().items():
            n = conn.execute(
                "SELECT COUNT(*) FROM subscriptions WHERE plan=?", (pid,)
            ).fetchone()[0]
            plans.append(
                {
                    "plan": pid,
                    "label": p.get("label"),
                    "usd": p.get("usd"),
                    "days": p.get("days"),
                    "subs": int(n),
                }
            )
    return {
        "active_subs": int(active),
        "total_subs": int(total_subs),
        "expiring_7d": int(expiring_7d),
        "paid_orders": int(paid),
        "pending_orders": int(pending),
        "revenue_usd": round(revenue, 2),
        "trial_subs": trial_count,
        "plans": plans,
        "recent_orders": recent,
    }


def admin_list_subscriptions(
    user_id: Optional[str] = None,
    status: Optional[str] = None,
    plan: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    where: list[str] = []
    args: list[Any] = []
    if user_id:
        where.append("user_id=?")
        args.append(str(user_id))
    if status:
        where.append("status=?")
        args.append(str(status))
    if plan:
        where.append("plan=?")
        args.append(str(plan))
    cond = (" WHERE " + " AND ".join(where)) if where else ""
    with _conn() as conn:
        total = int(
            conn.execute(f"SELECT COUNT(*) FROM subscriptions{cond}", args).fetchone()[0]
        )
        rows = [
            dict(r)
            for r in conn.execute(
                f"SELECT id, user_id, plan, status, started_at, expires_at, source, created_at "
                f"FROM subscriptions{cond} ORDER BY id DESC LIMIT ? OFFSET ?",
                args + [max(1, min(200, int(limit))), max(0, int(offset))],
            ).fetchall()
        ]
    return {"total": total, "offset": max(0, int(offset)), "rows": rows}


def admin_list_orders(
    status: Optional[str] = None,
    channel: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    where: list[str] = []
    args: list[Any] = []
    if status:
        where.append("status=?")
        args.append(str(status))
    if channel:
        where.append("channel=?")
        args.append(str(channel))
    qq = (q or "").strip()
    if qq:
        where.append("(out_trade_no LIKE ? OR custom_id LIKE ? OR paypal_order_id LIKE ?)")
        like = f"%{qq}%"
        args += [like, like, like]
    cond = (" WHERE " + " AND ".join(where)) if where else ""
    with _conn() as conn:
        total = int(
            conn.execute(f"SELECT COUNT(*) FROM orders{cond}", args).fetchone()[0]
        )
        rows = [
            dict(r)
            for r in conn.execute(
                f"SELECT id, paypal_order_id, out_trade_no, channel, custom_id, amount_usd, plan, "
                f"status, created_at, paid_at FROM orders{cond} ORDER BY id DESC LIMIT ? OFFSET ?",
                args + [max(1, min(200, int(limit))), max(0, int(offset))],
            ).fetchall()
        ]
    return {"total": total, "offset": max(0, int(offset)), "rows": rows}
