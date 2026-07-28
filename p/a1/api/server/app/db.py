from __future__ import annotations

import os
import time
from datetime import date
from datetime import datetime, timezone, timedelta
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator, Optional

import json
import secrets

from .config import settings


def _ensure_parent_dir(path: str) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)


def _is_pg() -> bool:
    return str(getattr(settings, "db_kind", "sqlite") or "sqlite").strip().lower() in ("pg", "pgsql", "postgres", "postgresql")


def _adapt_sql(sql: str) -> str:
    """
    sqlite3 uses `?` parameters while psycopg uses `%s`.
    This adapter keeps the existing MVP SQL readable and swaps placeholders only for Postgres.
    """
    if not _is_pg():
        return sql
    return sql.replace("?", "%s")


def _row_get(row: Any, key: str) -> Any:
    """
    sqlite3.Row supports `row["k"]` but not `.get()`;
    psycopg dict_row returns dict-like rows with `.get()`.
    """
    try:
        if hasattr(row, "get"):
            return row.get(key)  # type: ignore[attr-defined]
    except Exception:
        pass
    try:
        return row[key]
    except Exception:
        return None


def _cfg_int(key: str, default: int) -> int:
    """
    Read integer config from admin_config (DB) with fallback to default.
    Empty / invalid values are treated as missing.
    """
    try:
        v = admin_config_get(key)
        if v is None:
            return int(default)
        s = str(v).strip()
        if s == "":
            return int(default)
        return int(float(s))
    except Exception:
        return int(default)


def invite_cfg_effective() -> dict[str, int]:
    """Effective invite reward config (admin_config overrides env defaults)."""
    return {
        "invite_reward_inviter_weekly": _cfg_int(
            "invite_reward_inviter_weekly", int(getattr(settings, "invite_reward_inviter_weekly", 100) or 100)
        ),
        "invite_reward_invitee_weekly": _cfg_int(
            "invite_reward_invitee_weekly", int(getattr(settings, "invite_reward_invitee_weekly", 50) or 50)
        ),
        "invite_weekly_cap": _cfg_int(
            "invite_weekly_cap", int(getattr(settings, "invite_weekly_cap", 500) or 500)
        ),
        "invite_reward_inviter_daily": _cfg_int(
            "invite_reward_inviter_daily", int(getattr(settings, "invite_reward_inviter_daily", 0) or 0)
        ),
        "invite_reward_invitee_daily": _cfg_int(
            "invite_reward_invitee_daily", int(getattr(settings, "invite_reward_invitee_daily", 0) or 0)
        ),
    }


def vip_quota_cfg_effective() -> dict[str, int]:
    """
    Effective VIP quota caps (admin_config overrides env defaults).
    Keys:
    - vip_daily_cap / vip_weekly: for vip_month & vip_year_999 (current product behavior)
    - vip_trial_daily_cap / vip_trial_weekly: for vip_trial_99
    """
    return {
        "vip_daily_cap": _cfg_int("vip_daily_cap", int(getattr(settings, "vip_daily_cap", 150) or 150)),
        "vip_weekly": _cfg_int("vip_weekly", int(getattr(settings, "vip_weekly", 500) or 500)),
        "vip_trial_daily_cap": _cfg_int("vip_trial_daily_cap", int(getattr(settings, "vip_trial_daily_cap", 20) or 20)),
        "vip_trial_weekly": _cfg_int("vip_trial_weekly", int(getattr(settings, "vip_trial_weekly", 100) or 100)),
    }


class _ConnProxy:
    """
    Uniform DB API for sqlite3/psycopg connections.
    - Auto-adapts placeholder style (`?` -> `%s`) for Postgres.
    - Keeps the existing MVP code mostly unchanged.
    """

    def __init__(self, conn: Any):
        self._conn = conn

    def execute(self, sql: str, params: Any = ()) -> Any:
        return self._conn.execute(_adapt_sql(sql), params)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._conn, name)


@contextmanager
def connect() -> Iterator[Any]:
    if _is_pg():
        try:
            import psycopg  # type: ignore
            from psycopg.rows import dict_row  # type: ignore
        except Exception as e:
            raise RuntimeError("PostgreSQL mode requires psycopg. Install dependencies first.") from e

        dsn = str(getattr(settings, "database_url", "") or "").strip()
        if not dsn:
            raise RuntimeError("AI24X_DATABASE_URL is required when AI24X_DB_KIND=pgsql")

        conn = psycopg.connect(dsn, autocommit=False, row_factory=dict_row)
        try:
            yield _ConnProxy(conn)
            conn.commit()
        finally:
            try:
                conn.close()
            except Exception:
                pass
        return

    # sqlite (default)
    import sqlite3  # local import to avoid forcing sqlite in pg envs

    _ensure_parent_dir(settings.db_path)
    conn = sqlite3.connect(settings.db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield _ConnProxy(conn)
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        if _is_pg():
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                  id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                  email TEXT UNIQUE,
                  phone TEXT UNIQUE,
                  created_at BIGINT NOT NULL
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS quota (
                  user_id BIGINT PRIMARY KEY,
                  plan TEXT NOT NULL DEFAULT 'free',
                  monthly_limit BIGINT NOT NULL,
                  daily_limit BIGINT NOT NULL,
                  monthly_used BIGINT NOT NULL DEFAULT 0,
                  daily_used BIGINT NOT NULL DEFAULT 0,
                  month_key TEXT NOT NULL,
                  day_key TEXT NOT NULL,
                  expires_at BIGINT,
                  updated_at BIGINT NOT NULL
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS invite_codes (
                  user_id BIGINT PRIMARY KEY,
                  code TEXT UNIQUE NOT NULL,
                  created_at BIGINT NOT NULL
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS invite_relations (
                  invitee_id BIGINT PRIMARY KEY,
                  inviter_id BIGINT NOT NULL,
                  inviter_l1_id BIGINT,
                  inviter_l2_id BIGINT,
                  inviter_l3_id BIGINT,
                  depth INTEGER NOT NULL DEFAULT 1,
                  updated_at BIGINT NOT NULL DEFAULT 0,
                  created_at BIGINT NOT NULL
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS quota_ledger (
                  id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                  user_id BIGINT NOT NULL,
                  secid TEXT NOT NULL,
                  period TEXT NOT NULL,
                  idempotency_key TEXT NOT NULL,
                  consumed_at BIGINT NOT NULL,
                  result TEXT NOT NULL,
                  UNIQUE(user_id, idempotency_key)
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS reward_ledger (
                  id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                  inviter_id BIGINT NOT NULL,
                  invitee_id BIGINT NOT NULL,
                  reward_type TEXT NOT NULL,
                  amount BIGINT NOT NULL,
                  created_at BIGINT NOT NULL,
                  UNIQUE(inviter_id, invitee_id, reward_type)
                );
                """
            )

            # Minimal indexes (PG): keep query paths fast under real traffic.
            # - invite list/summary: filter by inviter_id
            # - ledgers: frequent per-user queries by time
            # - cache: enable future cleanup by expire_ts
            conn.execute("CREATE INDEX IF NOT EXISTS idx_invite_relations_inviter_id ON invite_relations(inviter_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_quota_ledger_user_time ON quota_ledger(user_id, consumed_at DESC);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_reward_ledger_inviter_time ON reward_ledger(inviter_id, created_at DESC);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_reward_ledger_inviter_type_time ON reward_ledger(inviter_id, reward_type, created_at DESC);")
        else:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  email TEXT UNIQUE,
                  phone TEXT UNIQUE,
                  created_at INTEGER NOT NULL
                );
                """
            )
            # Soft-migration: older DBs may lack email column (sqlite only)
            try:
                cols = [r["name"] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
                if "email" not in cols:
                    conn.execute("ALTER TABLE users ADD COLUMN email TEXT")
                    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email)")
            except Exception:
                pass

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS quota (
                  user_id INTEGER PRIMARY KEY,
                  plan TEXT NOT NULL DEFAULT 'free',
                  monthly_limit INTEGER NOT NULL,
                  daily_limit INTEGER NOT NULL,
                  monthly_used INTEGER NOT NULL DEFAULT 0,
                  daily_used INTEGER NOT NULL DEFAULT 0,
                  month_key TEXT NOT NULL,
                  day_key TEXT NOT NULL,
                  expires_at INTEGER,
                  updated_at INTEGER NOT NULL,
                  FOREIGN KEY(user_id) REFERENCES users(id)
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS invite_codes (
                  user_id INTEGER PRIMARY KEY,
                  code TEXT UNIQUE NOT NULL,
                  created_at INTEGER NOT NULL,
                  FOREIGN KEY(user_id) REFERENCES users(id)
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS invite_relations (
                  invitee_id INTEGER PRIMARY KEY,
                  inviter_id INTEGER NOT NULL,
                  inviter_l1_id INTEGER,
                  inviter_l2_id INTEGER,
                  inviter_l3_id INTEGER,
                  depth INTEGER NOT NULL DEFAULT 1,
                  updated_at INTEGER NOT NULL DEFAULT 0,
                  created_at INTEGER NOT NULL,
                  FOREIGN KEY(invitee_id) REFERENCES users(id),
                  FOREIGN KEY(inviter_id) REFERENCES users(id)
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS quota_ledger (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER NOT NULL,
                  secid TEXT NOT NULL,
                  period TEXT NOT NULL,
                  idempotency_key TEXT NOT NULL,
                  consumed_at INTEGER NOT NULL,
                  result TEXT NOT NULL,
                  UNIQUE(user_id, idempotency_key),
                  FOREIGN KEY(user_id) REFERENCES users(id)
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS reward_ledger (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  inviter_id INTEGER NOT NULL,
                  invitee_id INTEGER NOT NULL,
                  reward_type TEXT NOT NULL,
                  amount INTEGER NOT NULL,
                  created_at INTEGER NOT NULL,
                  UNIQUE(inviter_id, invitee_id, reward_type),
                  FOREIGN KEY(inviter_id) REFERENCES users(id),
                  FOREIGN KEY(invitee_id) REFERENCES users(id)
                );
                """
            )

        # Market data cache (MVP): persist successful K-line payloads for resilience across restarts.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS kline_cache (
              cache_key TEXT PRIMARY KEY,
              expire_ts BIGINT NOT NULL,
              payload_json TEXT NOT NULL,
              updated_at BIGINT NOT NULL
            );
            """
        )
        if _is_pg():
            conn.execute("CREATE INDEX IF NOT EXISTS idx_kline_cache_expire_ts ON kline_cache(expire_ts);")

        # Admin runtime config (MVP): key-value overrides for ops (e.g. paid provider switch/priority)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS admin_config (
              key TEXT PRIMARY KEY,
              value TEXT NOT NULL,
              updated_at BIGINT NOT NULL
            );
            """
        )

        # 后台分管预留：启用行手机号可与 AI24X_ADMIN_OTP_PHONES 并集参与 OTP 登录；perm_flags/perm_json 预留细粒度权限
        if _is_pg():
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS admin_operators (
                  id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                  phone TEXT NOT NULL UNIQUE,
                  display_name TEXT,
                  role TEXT NOT NULL DEFAULT 'deputy',
                  enabled BIGINT NOT NULL DEFAULT 1,
                  perm_flags BIGINT NOT NULL DEFAULT 0,
                  perm_json TEXT,
                  invited_by TEXT,
                  created_at BIGINT NOT NULL,
                  updated_at BIGINT NOT NULL
                );
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_admin_operators_enabled ON admin_operators(enabled);")
        else:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS admin_operators (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  phone TEXT NOT NULL UNIQUE,
                  display_name TEXT,
                  role TEXT NOT NULL DEFAULT 'deputy',
                  enabled INTEGER NOT NULL DEFAULT 1,
                  perm_flags INTEGER NOT NULL DEFAULT 0,
                  perm_json TEXT,
                  invited_by TEXT,
                  created_at INTEGER NOT NULL,
                  updated_at INTEGER NOT NULL
                );
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_admin_operators_enabled ON admin_operators(enabled);")

        # Admin ops audit log (MVP): quota/plan changes should be traceable.
        if _is_pg():
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS admin_ops_ledger (
                  id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                  user_id BIGINT NOT NULL,
                  actor TEXT NOT NULL,
                  action TEXT NOT NULL,
                  before_json TEXT NOT NULL,
                  after_json TEXT NOT NULL,
                  note TEXT NOT NULL DEFAULT '',
                  created_at BIGINT NOT NULL
                );
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_admin_ops_ledger_user_time ON admin_ops_ledger(user_id, created_at DESC);")
        else:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS admin_ops_ledger (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER NOT NULL,
                  actor TEXT NOT NULL,
                  action TEXT NOT NULL,
                  before_json TEXT NOT NULL,
                  after_json TEXT NOT NULL,
                  note TEXT NOT NULL DEFAULT '',
                  created_at INTEGER NOT NULL,
                  FOREIGN KEY(user_id) REFERENCES users(id)
                );
                """
            )

        # 支付订单（微信 Native 先打通；channel 预留 alipay / paypal）
        if _is_pg():
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS pay_orders (
                  id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                  out_trade_no TEXT NOT NULL UNIQUE,
                  user_id BIGINT NOT NULL,
                  plan TEXT NOT NULL,
                  amount_fen BIGINT NOT NULL,
                  channel TEXT NOT NULL DEFAULT 'wechat',
                  status TEXT NOT NULL DEFAULT 'pending',
                  code_url TEXT,
                  transaction_id TEXT,
                  paid_at BIGINT,
                  referrer_user_id BIGINT,
                  created_at BIGINT NOT NULL,
                  updated_at BIGINT NOT NULL
                );
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_pay_orders_user_id ON pay_orders(user_id);")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_pay_orders_transaction_id ON pay_orders(transaction_id);"
            )
        else:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS pay_orders (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  out_trade_no TEXT NOT NULL UNIQUE,
                  user_id INTEGER NOT NULL,
                  plan TEXT NOT NULL,
                  amount_fen INTEGER NOT NULL,
                  channel TEXT NOT NULL DEFAULT 'wechat',
                  status TEXT NOT NULL DEFAULT 'pending',
                  code_url TEXT,
                  transaction_id TEXT,
                  paid_at INTEGER,
                  referrer_user_id INTEGER,
                  created_at INTEGER NOT NULL,
                  updated_at INTEGER NOT NULL,
                  FOREIGN KEY(user_id) REFERENCES users(id)
                );
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_pay_orders_user_id ON pay_orders(user_id);")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_pay_orders_transaction_id ON pay_orders(transaction_id);"
            )
            try:
                conn.execute("CREATE INDEX IF NOT EXISTS idx_pay_orders_referrer_user_id ON pay_orders(referrer_user_id);")
            except Exception:
                pass

        # Soft-migration: add new columns to existing pay_orders tables.
        if _is_pg():
            try:
                conn.execute("ALTER TABLE pay_orders ADD COLUMN IF NOT EXISTS paid_at BIGINT;")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE pay_orders ADD COLUMN IF NOT EXISTS referrer_user_id BIGINT;")
            except Exception:
                pass
            try:
                conn.execute("CREATE INDEX IF NOT EXISTS idx_pay_orders_referrer_user_id ON pay_orders(referrer_user_id);")
            except Exception:
                pass
        else:
            try:
                cols = [r["name"] for r in conn.execute("PRAGMA table_info(pay_orders)").fetchall()]
                if "paid_at" not in cols:
                    conn.execute("ALTER TABLE pay_orders ADD COLUMN paid_at INTEGER")
                if "referrer_user_id" not in cols:
                    conn.execute("ALTER TABLE pay_orders ADD COLUMN referrer_user_id INTEGER")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_pay_orders_referrer_user_id ON pay_orders(referrer_user_id);")
            except Exception:
                pass

        # Agent status (reserved): normal/senior/gold; currently MVP uses normal only.
        if _is_pg():
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_status (
                  user_id BIGINT PRIMARY KEY,
                  level TEXT NOT NULL,
                  expires_at BIGINT,
                  tier_points BIGINT NOT NULL DEFAULT 0,
                  tier_updated_at BIGINT NOT NULL DEFAULT 0,
                  tier_locked INTEGER NOT NULL DEFAULT 0,
                  updated_at BIGINT NOT NULL
                );
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_status_level ON agent_status(level);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_status_expires_at ON agent_status(expires_at);")
        else:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_status (
                  user_id INTEGER PRIMARY KEY,
                  level TEXT NOT NULL,
                  expires_at INTEGER,
                  tier_points INTEGER NOT NULL DEFAULT 0,
                  tier_updated_at INTEGER NOT NULL DEFAULT 0,
                  tier_locked INTEGER NOT NULL DEFAULT 0,
                  updated_at INTEGER NOT NULL,
                  FOREIGN KEY(user_id) REFERENCES users(id)
                );
                """
            )
            try:
                conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_status_level ON agent_status(level);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_status_expires_at ON agent_status(expires_at);")
            except Exception:
                pass

        # Commission ledger (multi-level): manual settlement; refunds/auto-payout are reserved but disabled by default.
        if _is_pg():
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS commission_ledger (
                  id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                  out_trade_no TEXT NOT NULL,
                  agent_user_id BIGINT NOT NULL,
                  level_depth INTEGER NOT NULL DEFAULT 1,
                  buyer_user_id BIGINT NOT NULL,
                  plan TEXT NOT NULL,
                  amount_fen BIGINT NOT NULL,
                  rate NUMERIC NOT NULL,
                  commission_fen BIGINT NOT NULL,
                  rule_version TEXT NOT NULL DEFAULT 'v1',
                  rate_source TEXT NOT NULL DEFAULT 'base',
                  calc_meta TEXT NOT NULL DEFAULT '{}',
                  eligible_at BIGINT NOT NULL,
                  status TEXT NOT NULL DEFAULT 'pending',
                  request_id BIGINT,
                  paid_at BIGINT,
                  paid_note TEXT NOT NULL DEFAULT '',
                  created_at BIGINT NOT NULL,
                  updated_at BIGINT NOT NULL,
                  UNIQUE(out_trade_no, agent_user_id, level_depth)
                );
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_commission_ledger_agent_status_eligible ON commission_ledger(agent_user_id, status, eligible_at);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_commission_ledger_status_eligible ON commission_ledger(status, eligible_at);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_commission_ledger_out_trade_no ON commission_ledger(out_trade_no);")
        else:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS commission_ledger (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  out_trade_no TEXT NOT NULL,
                  agent_user_id INTEGER NOT NULL,
                  level_depth INTEGER NOT NULL DEFAULT 1,
                  buyer_user_id INTEGER NOT NULL,
                  plan TEXT NOT NULL,
                  amount_fen INTEGER NOT NULL,
                  rate REAL NOT NULL,
                  commission_fen INTEGER NOT NULL,
                  rule_version TEXT NOT NULL DEFAULT 'v1',
                  rate_source TEXT NOT NULL DEFAULT 'base',
                  calc_meta TEXT NOT NULL DEFAULT '{}',
                  eligible_at INTEGER NOT NULL,
                  status TEXT NOT NULL DEFAULT 'pending',
                  request_id INTEGER,
                  paid_at INTEGER,
                  paid_note TEXT NOT NULL DEFAULT '',
                  created_at INTEGER NOT NULL,
                  updated_at INTEGER NOT NULL,
                  FOREIGN KEY(agent_user_id) REFERENCES users(id),
                  FOREIGN KEY(buyer_user_id) REFERENCES users(id)
                  ,
                  UNIQUE(out_trade_no, agent_user_id, level_depth)
                );
                """
            )
            try:
                conn.execute("CREATE INDEX IF NOT EXISTS idx_commission_ledger_agent_status_eligible ON commission_ledger(agent_user_id, status, eligible_at);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_commission_ledger_status_eligible ON commission_ledger(status, eligible_at);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_commission_ledger_out_trade_no ON commission_ledger(out_trade_no);")
            except Exception:
                pass

        # Soft-migration: add request_id to existing commission_ledger tables.
        if _is_pg():
            try:
                conn.execute("ALTER TABLE commission_ledger ADD COLUMN IF NOT EXISTS request_id BIGINT;")
            except Exception:
                pass
        else:
            try:
                cols = [r["name"] for r in conn.execute("PRAGMA table_info(commission_ledger)").fetchall()]
                if "request_id" not in cols:
                    conn.execute("ALTER TABLE commission_ledger ADD COLUMN request_id INTEGER")
            except Exception:
                pass

        # Soft-migration: ensure multi-level commission columns exist (older DBs had UNIQUE(out_trade_no)).
        try:
            if _is_pg():
                conn.execute("ALTER TABLE invite_relations ADD COLUMN IF NOT EXISTS inviter_l1_id BIGINT;")
                conn.execute("ALTER TABLE invite_relations ADD COLUMN IF NOT EXISTS inviter_l2_id BIGINT;")
                conn.execute("ALTER TABLE invite_relations ADD COLUMN IF NOT EXISTS inviter_l3_id BIGINT;")
                conn.execute("ALTER TABLE invite_relations ADD COLUMN IF NOT EXISTS depth INTEGER NOT NULL DEFAULT 1;")
                conn.execute("ALTER TABLE invite_relations ADD COLUMN IF NOT EXISTS updated_at BIGINT NOT NULL DEFAULT 0;")
                # Create indexes after columns are ensured (existing DBs may miss the new columns).
                try:
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_invite_relations_l1 ON invite_relations(inviter_l1_id);")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_invite_relations_l2 ON invite_relations(inviter_l2_id);")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_invite_relations_l3 ON invite_relations(inviter_l3_id);")
                except Exception:
                    pass
                conn.execute("ALTER TABLE agent_status ADD COLUMN IF NOT EXISTS tier_points BIGINT NOT NULL DEFAULT 0;")
                conn.execute("ALTER TABLE agent_status ADD COLUMN IF NOT EXISTS tier_updated_at BIGINT NOT NULL DEFAULT 0;")
                conn.execute("ALTER TABLE agent_status ADD COLUMN IF NOT EXISTS tier_locked INTEGER NOT NULL DEFAULT 0;")
            else:
                cols = [r["name"] for r in conn.execute("PRAGMA table_info(invite_relations)").fetchall()]
                if "inviter_l1_id" not in cols:
                    conn.execute("ALTER TABLE invite_relations ADD COLUMN inviter_l1_id INTEGER")
                if "inviter_l2_id" not in cols:
                    conn.execute("ALTER TABLE invite_relations ADD COLUMN inviter_l2_id INTEGER")
                if "inviter_l3_id" not in cols:
                    conn.execute("ALTER TABLE invite_relations ADD COLUMN inviter_l3_id INTEGER")
                if "depth" not in cols:
                    conn.execute("ALTER TABLE invite_relations ADD COLUMN depth INTEGER NOT NULL DEFAULT 1")
                if "updated_at" not in cols:
                    conn.execute("ALTER TABLE invite_relations ADD COLUMN updated_at INTEGER NOT NULL DEFAULT 0")
                cols2 = [r["name"] for r in conn.execute("PRAGMA table_info(agent_status)").fetchall()]
                if "tier_points" not in cols2:
                    conn.execute("ALTER TABLE agent_status ADD COLUMN tier_points INTEGER NOT NULL DEFAULT 0")
                if "tier_updated_at" not in cols2:
                    conn.execute("ALTER TABLE agent_status ADD COLUMN tier_updated_at INTEGER NOT NULL DEFAULT 0")
                if "tier_locked" not in cols2:
                    conn.execute("ALTER TABLE agent_status ADD COLUMN tier_locked INTEGER NOT NULL DEFAULT 0")
        except Exception:
            pass

        # Hard migration for legacy commission_ledger UNIQUE(out_trade_no): rebuild table once (sqlite) or drop constraint (pg).
        try:
            if _is_pg():
                # Older PG schema had UNIQUE(out_trade_no). Drop it if present.
                try:
                    conn.execute("ALTER TABLE commission_ledger DROP CONSTRAINT IF EXISTS commission_ledger_out_trade_no_key;")
                except Exception:
                    pass
                # Ensure new columns exist (idempotent).
                conn.execute("ALTER TABLE commission_ledger ADD COLUMN IF NOT EXISTS level_depth INTEGER NOT NULL DEFAULT 1;")
                conn.execute("ALTER TABLE commission_ledger ADD COLUMN IF NOT EXISTS rule_version TEXT NOT NULL DEFAULT 'v1';")
                conn.execute("ALTER TABLE commission_ledger ADD COLUMN IF NOT EXISTS rate_source TEXT NOT NULL DEFAULT 'base';")
                conn.execute("ALTER TABLE commission_ledger ADD COLUMN IF NOT EXISTS calc_meta TEXT NOT NULL DEFAULT '{}';")
                # Ensure composite uniqueness (idempotent via unique index).
                conn.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_commission_ledger_otn_agent_depth ON commission_ledger(out_trade_no, agent_user_id, level_depth);"
                )
            else:
                cols = [r["name"] for r in conn.execute("PRAGMA table_info(commission_ledger)").fetchall()]
                has_depth = "level_depth" in cols
                # Detect legacy UNIQUE(out_trade_no) by index list (best-effort).
                legacy_unique = False
                try:
                    idxs = conn.execute("PRAGMA index_list(commission_ledger)").fetchall()
                    for it in idxs or []:
                        name = str(it["name"] or "")
                        unique = int(it["unique"] or 0)
                        if unique == 1 and "out_trade_no" in name:
                            legacy_unique = True
                            break
                except Exception:
                    legacy_unique = False
                if (not has_depth) or legacy_unique:
                    # Rebuild to support one-order-multi-rows.
                    conn.execute(
                        """
                        CREATE TABLE IF NOT EXISTS commission_ledger__v2 (
                          id INTEGER PRIMARY KEY AUTOINCREMENT,
                          out_trade_no TEXT NOT NULL,
                          agent_user_id INTEGER NOT NULL,
                          level_depth INTEGER NOT NULL DEFAULT 1,
                          buyer_user_id INTEGER NOT NULL,
                          plan TEXT NOT NULL,
                          amount_fen INTEGER NOT NULL,
                          rate REAL NOT NULL,
                          commission_fen INTEGER NOT NULL,
                          rule_version TEXT NOT NULL DEFAULT 'v1',
                          rate_source TEXT NOT NULL DEFAULT 'base',
                          calc_meta TEXT NOT NULL DEFAULT '{}',
                          eligible_at INTEGER NOT NULL,
                          status TEXT NOT NULL DEFAULT 'pending',
                          request_id INTEGER,
                          paid_at INTEGER,
                          paid_note TEXT NOT NULL DEFAULT '',
                          created_at INTEGER NOT NULL,
                          updated_at INTEGER NOT NULL,
                          FOREIGN KEY(agent_user_id) REFERENCES users(id),
                          FOREIGN KEY(buyer_user_id) REFERENCES users(id),
                          UNIQUE(out_trade_no, agent_user_id, level_depth)
                        );
                        """
                    )
                    # Copy old rows (assume old schema exists).
                    try:
                        conn.execute(
                            """
                            INSERT OR IGNORE INTO commission_ledger__v2(
                              id, out_trade_no, agent_user_id, level_depth, buyer_user_id, plan, amount_fen, rate, commission_fen,
                              eligible_at, status, request_id, paid_at, paid_note, created_at, updated_at
                            )
                            SELECT
                              id, out_trade_no, agent_user_id, 1 AS level_depth, buyer_user_id, plan, amount_fen, rate, commission_fen,
                              eligible_at, status, request_id, paid_at, paid_note, created_at, updated_at
                            FROM commission_ledger;
                            """
                        )
                    except Exception:
                        pass
                    conn.execute("DROP TABLE IF EXISTS commission_ledger;")
                    conn.execute("ALTER TABLE commission_ledger__v2 RENAME TO commission_ledger;")
                    try:
                        conn.execute("CREATE INDEX IF NOT EXISTS idx_commission_ledger_agent_status_eligible ON commission_ledger(agent_user_id, status, eligible_at);")
                        conn.execute("CREATE INDEX IF NOT EXISTS idx_commission_ledger_status_eligible ON commission_ledger(status, eligible_at);")
                        conn.execute("CREATE INDEX IF NOT EXISTS idx_commission_ledger_out_trade_no ON commission_ledger(out_trade_no);")
                    except Exception:
                        pass
        except Exception:
            pass

        # Backfill invite ancestor cache (best-effort; idempotent).
        try:
            _invite_backfill_ancestors_in_conn(conn)
        except Exception:
            pass

        # Agent payout account (MVP): store user's withdrawal account info (masked display on user side).
        if _is_pg():
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_payout_account (
                  user_id BIGINT PRIMARY KEY,
                  channel TEXT NOT NULL,
                  account_name TEXT NOT NULL DEFAULT '',
                  account_no TEXT NOT NULL DEFAULT '',
                  phone TEXT NOT NULL DEFAULT '',
                  qr_image TEXT NOT NULL DEFAULT '',
                  updated_at BIGINT NOT NULL
                );
                """
            )
        else:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_payout_account (
                  user_id INTEGER PRIMARY KEY,
                  channel TEXT NOT NULL,
                  account_name TEXT NOT NULL DEFAULT '',
                  account_no TEXT NOT NULL DEFAULT '',
                  phone TEXT NOT NULL DEFAULT '',
                  qr_image TEXT NOT NULL DEFAULT '',
                  updated_at INTEGER NOT NULL,
                  FOREIGN KEY(user_id) REFERENCES users(id)
                );
                """
            )

        # Soft-migration: add phone to existing agent_payout_account tables.
        if _is_pg():
            try:
                conn.execute("ALTER TABLE agent_payout_account ADD COLUMN IF NOT EXISTS phone TEXT NOT NULL DEFAULT '';")
            except Exception:
                pass
        else:
            try:
                cols = [r["name"] for r in conn.execute("PRAGMA table_info(agent_payout_account)").fetchall()]
                if "phone" not in cols:
                    conn.execute("ALTER TABLE agent_payout_account ADD COLUMN phone TEXT NOT NULL DEFAULT ''")
            except Exception:
                pass

        # Payout requests (MVP): lock eligible commissions into a request, admin approves & marks paid.
        if _is_pg():
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_payout_requests (
                  id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                  user_id BIGINT NOT NULL,
                  amount_fen BIGINT NOT NULL,
                  channel TEXT NOT NULL,
                  account_snapshot TEXT NOT NULL DEFAULT '',
                  status TEXT NOT NULL DEFAULT 'pending',
                  note TEXT NOT NULL DEFAULT '',
                  transfer_ref TEXT NOT NULL DEFAULT '',
                  exported_at BIGINT,
                  exported_note TEXT NOT NULL DEFAULT '',
                  created_at BIGINT NOT NULL,
                  approved_at BIGINT,
                  paid_at BIGINT,
                  updated_at BIGINT NOT NULL
                );
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_payout_requests_user_status ON agent_payout_requests(user_id, status, created_at);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_payout_requests_status_created ON agent_payout_requests(status, created_at);")
        else:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_payout_requests (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER NOT NULL,
                  amount_fen INTEGER NOT NULL,
                  channel TEXT NOT NULL,
                  account_snapshot TEXT NOT NULL DEFAULT '',
                  status TEXT NOT NULL DEFAULT 'pending',
                  note TEXT NOT NULL DEFAULT '',
                  transfer_ref TEXT NOT NULL DEFAULT '',
                  exported_at INTEGER,
                  exported_note TEXT NOT NULL DEFAULT '',
                  created_at INTEGER NOT NULL,
                  approved_at INTEGER,
                  paid_at INTEGER,
                  updated_at INTEGER NOT NULL,
                  FOREIGN KEY(user_id) REFERENCES users(id)
                );
                """
            )
            try:
                conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_payout_requests_user_status ON agent_payout_requests(user_id, status, created_at);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_payout_requests_status_created ON agent_payout_requests(status, created_at);")
            except Exception:
                pass

        # Soft-migration: exported_at/exported_note for agent_payout_requests.
        if _is_pg():
            try:
                conn.execute("ALTER TABLE agent_payout_requests ADD COLUMN IF NOT EXISTS exported_at BIGINT;")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE agent_payout_requests ADD COLUMN IF NOT EXISTS exported_note TEXT NOT NULL DEFAULT '';")
            except Exception:
                pass
        else:
            try:
                cols = [r["name"] for r in conn.execute("PRAGMA table_info(agent_payout_requests)").fetchall()]
                if "exported_at" not in cols:
                    conn.execute("ALTER TABLE agent_payout_requests ADD COLUMN exported_at INTEGER")
                if "exported_note" not in cols:
                    conn.execute("ALTER TABLE agent_payout_requests ADD COLUMN exported_note TEXT NOT NULL DEFAULT ''")
            except Exception:
                pass

        # User feedback tickets (admin reply workflow).
        if _is_pg():
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_feedback (
                  id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                  user_id BIGINT NOT NULL,
                  category TEXT NOT NULL,
                  title TEXT NOT NULL DEFAULT '',
                  body TEXT NOT NULL,
                  contact TEXT NOT NULL DEFAULT '',
                  status TEXT NOT NULL DEFAULT 'open',
                  admin_reply TEXT NOT NULL DEFAULT '',
                  replied_at BIGINT,
                  replied_by TEXT NOT NULL DEFAULT '',
                  created_at BIGINT NOT NULL,
                  updated_at BIGINT NOT NULL
                );
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_user_feedback_user_time ON user_feedback(user_id, created_at DESC);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_user_feedback_status_time ON user_feedback(status, created_at DESC);")
        else:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_feedback (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER NOT NULL,
                  category TEXT NOT NULL,
                  title TEXT NOT NULL DEFAULT '',
                  body TEXT NOT NULL,
                  contact TEXT NOT NULL DEFAULT '',
                  status TEXT NOT NULL DEFAULT 'open',
                  admin_reply TEXT NOT NULL DEFAULT '',
                  replied_at INTEGER,
                  replied_by TEXT NOT NULL DEFAULT '',
                  created_at INTEGER NOT NULL,
                  updated_at INTEGER NOT NULL,
                  FOREIGN KEY(user_id) REFERENCES users(id)
                );
                """
            )
            try:
                conn.execute("CREATE INDEX IF NOT EXISTS idx_user_feedback_user_time ON user_feedback(user_id, created_at DESC);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_user_feedback_status_time ON user_feedback(status, created_at DESC);")
            except Exception:
                pass

        # User notices / announcements (admin broadcast + targeting + read state).
        if _is_pg():
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_notices (
                  id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                  title TEXT NOT NULL,
                  body TEXT NOT NULL,
                  scope TEXT NOT NULL DEFAULT 'all',      -- all / user / agent_level
                  target_user_id BIGINT,                 -- when scope=user
                  target_agent_level TEXT NOT NULL DEFAULT '', -- when scope=agent_level (starter/growth/pro)
                  pinned INTEGER NOT NULL DEFAULT 0,
                  status TEXT NOT NULL DEFAULT 'active', -- active / archived
                  starts_at BIGINT,
                  ends_at BIGINT,
                  created_by TEXT NOT NULL DEFAULT 'admin',
                  created_at BIGINT NOT NULL,
                  updated_at BIGINT NOT NULL
                );
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_user_notices_status_time ON user_notices(status, created_at DESC);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_user_notices_pinned_time ON user_notices(pinned, created_at DESC);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_user_notices_scope_target ON user_notices(scope, target_user_id, target_agent_level);")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_notice_reads (
                  user_id BIGINT NOT NULL,
                  notice_id BIGINT NOT NULL,
                  read_at BIGINT NOT NULL,
                  PRIMARY KEY (user_id, notice_id)
                );
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_user_notice_reads_user_time ON user_notice_reads(user_id, read_at DESC);")
        else:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_notices (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  title TEXT NOT NULL,
                  body TEXT NOT NULL,
                  scope TEXT NOT NULL DEFAULT 'all',
                  target_user_id INTEGER,
                  target_agent_level TEXT NOT NULL DEFAULT '',
                  pinned INTEGER NOT NULL DEFAULT 0,
                  status TEXT NOT NULL DEFAULT 'active',
                  starts_at INTEGER,
                  ends_at INTEGER,
                  created_by TEXT NOT NULL DEFAULT 'admin',
                  created_at INTEGER NOT NULL,
                  updated_at INTEGER NOT NULL
                );
                """
            )
            try:
                conn.execute("CREATE INDEX IF NOT EXISTS idx_user_notices_status_time ON user_notices(status, created_at DESC);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_user_notices_pinned_time ON user_notices(pinned, created_at DESC);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_user_notices_scope_target ON user_notices(scope, target_user_id, target_agent_level);")
            except Exception:
                pass
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_notice_reads (
                  user_id INTEGER NOT NULL,
                  notice_id INTEGER NOT NULL,
                  read_at INTEGER NOT NULL,
                  PRIMARY KEY (user_id, notice_id),
                  FOREIGN KEY(user_id) REFERENCES users(id),
                  FOREIGN KEY(notice_id) REFERENCES user_notices(id)
                );
                """
            )
            try:
                conn.execute("CREATE INDEX IF NOT EXISTS idx_user_notice_reads_user_time ON user_notice_reads(user_id, read_at DESC);")
            except Exception:
                pass


FEEDBACK_CATEGORIES: tuple[tuple[str, str], ...] = (
    ("suggestion", "建议"),
    ("bug", "Bug / 错误"),
    ("billing", "会员与支付"),
    ("account", "账号与安全"),
    ("data", "行情与数据"),
    ("agent", "代理合作"),
    ("other", "其它"),
)

# 旧版分类 slug 仍可能出现在历史工单；新提交统一写入 canonical
_FEEDBACK_CATEGORY_LEGACY: dict[str, str] = {
    "data_signal": "data",
}

# 提交反馈频控（DB 计数，多进程一致；抑制批量注册刷工单）
FEEDBACK_SUBMIT_MAX_PER_HOUR = 6
FEEDBACK_SUBMIT_MAX_PER_DAY = 20
FEEDBACK_SUBMIT_NEW_ACCOUNT_HOURS = 48
FEEDBACK_SUBMIT_NEW_MAX_PER_HOUR = 2
FEEDBACK_SUBMIT_NEW_MAX_PER_DAY = 5


def feedback_category_labels() -> list[dict[str, str]]:
    return [{"id": k, "label": v} for k, v in FEEDBACK_CATEGORIES]


def _normalize_feedback_category(raw: str) -> str:
    c = str(raw or "").strip().lower()
    c = _FEEDBACK_CATEGORY_LEGACY.get(c, c)
    allowed = {k for k, _ in FEEDBACK_CATEGORIES}
    if c in allowed:
        return c
    raise ValueError("invalid_category")


def _feedback_row_dict(row: Any) -> dict[str, Any]:
    return {
        "id": int(_row_get(row, "id") or 0),
        "user_id": int(_row_get(row, "user_id") or 0),
        "category": str(_row_get(row, "category") or ""),
        "title": str(_row_get(row, "title") or ""),
        "body": str(_row_get(row, "body") or ""),
        "contact": str(_row_get(row, "contact") or ""),
        "status": str(_row_get(row, "status") or ""),
        "admin_reply": str(_row_get(row, "admin_reply") or ""),
        "replied_at": int(_row_get(row, "replied_at") or 0) if _row_get(row, "replied_at") is not None else None,
        "replied_by": str(_row_get(row, "replied_by") or ""),
        "created_at": int(_row_get(row, "created_at") or 0),
        "updated_at": int(_row_get(row, "updated_at") or 0),
    }


def feedback_create(
    user_id: int,
    *,
    category: str,
    title: str,
    body: str,
    contact: str = "",
) -> dict[str, Any]:
    uid = int(user_id)
    if uid <= 0:
        raise ValueError("invalid_user")
    cat = _normalize_feedback_category(category)
    t = str(title or "").strip()[:200]
    b = str(body or "").strip()
    if len(b) < 5:
        raise ValueError("body_too_short")
    if len(b) > 8000:
        raise ValueError("body_too_long")
    ct = str(contact or "").strip()[:200]
    now = int(time.time())
    with connect() as conn:
        ur = conn.execute(_adapt_sql("SELECT created_at FROM users WHERE id = ?"), (uid,)).fetchone()
        u_created = int(_row_get(ur, "created_at") or now) if ur else now
        is_new_account = (now - u_created) < int(FEEDBACK_SUBMIT_NEW_ACCOUNT_HOURS) * 3600
        cap_h = int(FEEDBACK_SUBMIT_NEW_MAX_PER_HOUR if is_new_account else FEEDBACK_SUBMIT_MAX_PER_HOUR)
        cap_d = int(FEEDBACK_SUBMIT_NEW_MAX_PER_DAY if is_new_account else FEEDBACK_SUBMIT_MAX_PER_DAY)
        row_h = conn.execute(
            "SELECT COUNT(1) AS c FROM user_feedback WHERE user_id=? AND created_at>=?",
            (uid, now - 3600),
        ).fetchone()
        n_h = int(row_h["c"] or 0) if row_h else 0
        if n_h >= cap_h:
            raise ValueError("feedback_new_hourly_cap" if is_new_account else "feedback_hourly_cap")
        row_d = conn.execute(
            "SELECT COUNT(1) AS c FROM user_feedback WHERE user_id=? AND created_at>=?",
            (uid, now - 86400),
        ).fetchone()
        n_d = int(row_d["c"] or 0) if row_d else 0
        if n_d >= cap_d:
            raise ValueError("feedback_new_daily_cap" if is_new_account else "feedback_daily_cap")
        if _is_pg():
            row = conn.execute(
                """
                INSERT INTO user_feedback(
                  user_id, category, title, body, contact, status, admin_reply, replied_at, replied_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'open', '', NULL, '', ?, ?)
                RETURNING id
                """,
                (uid, cat, t, b, ct, now, now),
            ).fetchone()
            fid = int(row["id"])
        else:
            cur = conn.execute(
                """
                INSERT INTO user_feedback(
                  user_id, category, title, body, contact, status, admin_reply, replied_at, replied_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'open', '', NULL, '', ?, ?)
                """,
                (uid, cat, t, b, ct, now, now),
            )
            fid = int(cur.lastrowid)
    return {"ok": True, "id": fid}


def feedback_list_for_user(user_id: int, *, limit: int = 30, offset: int = 0) -> dict[str, Any]:
    uid = int(user_id)
    lim = max(1, min(int(limit or 30), 100))
    off = max(0, int(offset or 0))
    with connect() as conn:
        total_row = conn.execute("SELECT COUNT(1) AS c FROM user_feedback WHERE user_id=?", (uid,)).fetchone()
        total = int(total_row["c"] or 0) if total_row else 0
        rows = conn.execute(
            """
            SELECT id, user_id, category, title, body, contact, status, admin_reply, replied_at, replied_by, created_at, updated_at
            FROM user_feedback WHERE user_id=? ORDER BY created_at DESC LIMIT ? OFFSET ?
            """,
            (uid, lim, off),
        ).fetchall()
    items = [_feedback_row_dict(r) for r in (rows or [])]
    return {"total": total, "items": items}


def admin_list_feedback(
    *,
    status: str = "",
    category: str = "",
    q: str = "",
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    st = str(status or "").strip().lower()
    cat_f = str(category or "").strip().lower()
    qq = str(q or "").strip()
    lim = max(1, min(int(limit or 50), 200))
    off = max(0, int(offset or 0))
    clauses: list[str] = ["1=1"]
    params: list[Any] = []
    if st in ("open", "replied", "closed"):
        clauses.append("f.status=?")
        params.append(st)
    if cat_f:
        try:
            _normalize_feedback_category(cat_f)
            clauses.append("f.category=?")
            params.append(cat_f)
        except ValueError:
            cat_f = ""
    if qq:
        like = f"%{qq[:200]}%"
        clauses.append("(f.title LIKE ? OR f.body LIKE ? OR CAST(f.user_id AS TEXT) LIKE ? OR IFNULL(u.phone,'') LIKE ? OR IFNULL(u.email,'') LIKE ?)")
        # sqlite IFNULL; PG: use COALESCE in adapt - actually IFNULL works in PG? PostgreSQL uses COALESCE. Fix for PG.
        if _is_pg():
            clauses[-1] = "(f.title LIKE ? OR f.body LIKE ? OR CAST(f.user_id AS TEXT) LIKE ? OR COALESCE(u.phone,'') LIKE ? OR COALESCE(u.email,'') LIKE ?)"
        params.extend([like, like, like, like, like])
    where_sql = " AND ".join(clauses)
    with connect() as conn:
        total_row = conn.execute(
            f"""
            SELECT COUNT(1) AS c FROM user_feedback f
            LEFT JOIN users u ON u.id = f.user_id
            WHERE {where_sql}
            """,
            tuple(params),
        ).fetchone()
        total = int(total_row["c"] or 0) if total_row else 0
        rows = conn.execute(
            f"""
            SELECT f.id, f.user_id, f.category, f.title, f.body, f.contact, f.status, f.admin_reply,
                   f.replied_at, f.replied_by, f.created_at, f.updated_at,
                   u.phone AS user_phone, u.email AS user_email
            FROM user_feedback f
            LEFT JOIN users u ON u.id = f.user_id
            WHERE {where_sql}
            ORDER BY f.created_at DESC
            LIMIT ? OFFSET ?
            """,
            tuple(params + [lim, off]),
        ).fetchall()
    items: list[dict[str, Any]] = []
    for r in rows or []:
        d = _feedback_row_dict(r)
        d["user_phone"] = str(_row_get(r, "user_phone") or "")
        d["user_email"] = str(_row_get(r, "user_email") or "")
        items.append(d)
    return {"total": total, "items": items}


def admin_feedback_reply(
    feedback_id: int,
    *,
    reply: str,
    status: str = "replied",
    replied_by: str = "",
) -> dict[str, Any]:
    fid = int(feedback_id)
    if fid <= 0:
        raise ValueError("invalid_id")
    rep = str(reply or "").strip()
    st = str(status or "").strip().lower()
    if st not in ("replied", "closed"):
        raise ValueError("invalid_status")
    if len(rep) > 8000:
        raise ValueError("reply_too_long")
    rb = str(replied_by or "").strip()[:64] or "管理员"
    now = int(time.time())
    with connect() as conn:
        row = conn.execute("SELECT id, admin_reply FROM user_feedback WHERE id=?", (fid,)).fetchone()
        if not row:
            raise ValueError("not_found")
        prev = str(_row_get(row, "admin_reply") or "")
        if st == "replied":
            if len(rep) < 1:
                raise ValueError("reply_required")
            final_reply = rep
        else:
            final_reply = rep if rep else prev
        conn.execute(
            """
            UPDATE user_feedback
            SET admin_reply=?, status=?, replied_at=?, replied_by=?, updated_at=?
            WHERE id=?
            """,
            (final_reply, st, now, rb, now, fid),
        )
    return {"ok": True, "id": fid}


def _day_key(ts: Optional[int] = None) -> str:
    t = time.localtime(ts or int(time.time()))
    return f"{t.tm_year:04d}{t.tm_mon:02d}{t.tm_mday:02d}"


def _week_key(ts: Optional[int] = None) -> str:
    """
    ISO year-week key, e.g. 2026W15.

    Note: We intentionally reuse existing DB column names:
    - quota.month_key stores week_key
    - quota.monthly_limit/used represent weekly_limit/used
    This avoids a migration for early MVP.
    """
    d = date.fromtimestamp(ts or int(time.time()))
    iso_year, iso_week, _ = d.isocalendar()
    return f"{iso_year:04d}W{iso_week:02d}"


def _week_start_ts(ts: int) -> int:
    """UTC-like start of ISO week (Mon 00:00) using local timestamp as input.

    For MVP, we only need a stable per-week bucket for rewards. Exact timezone is not critical as
    long as it is consistent for all users in the same deployment.
    """
    d = datetime.fromtimestamp(int(ts))
    # Monday is 0
    monday = d - timedelta(days=d.weekday())
    start = datetime(monday.year, monday.month, monday.day, 0, 0, 0)
    return int(start.timestamp())


def _day_start_ts(ts: int) -> int:
    d = datetime.fromtimestamp(int(ts))
    start = datetime(d.year, d.month, d.day, 0, 0, 0)
    return int(start.timestamp())


@dataclass
class User:
    id: int
    email: str
    phone: str | None = None


def get_or_create_user_by_email(email: str, phone: str | None = None) -> User:
    now = int(time.time())
    email = (email or "").strip().lower()
    with connect() as conn:
        row = conn.execute(_adapt_sql("SELECT id, email, phone FROM users WHERE email = ?"), (email,)).fetchone()
        if row:
            email_v = _row_get(row, "email")
            phone_v = _row_get(row, "phone")
            return User(
                id=int(_row_get(row, "id") or 0),
                email=str(email_v) if email_v is not None else "",
                phone=str(phone_v) if phone_v is not None else None,
            )

        user_id: int
        if _is_pg():
            cur = conn.execute(
                "INSERT INTO users(email, phone, created_at) VALUES (%s, %s, %s) RETURNING id",
                (email, phone, now),
            )
            rr = cur.fetchone()
            user_id = int(rr["id"]) if rr and (rr.get("id") is not None) else 0
        else:
            cur = conn.execute(
                "INSERT INTO users(email, phone, created_at) VALUES (?, ?, ?)",
                (email, phone, now),
            )
            user_id = int(cur.lastrowid)
        free_weekly_eff, free_daily_eff = _effective_free_limits()
        # init quota
        if _is_pg():
            conn.execute(
                """
                INSERT INTO quota(
                  user_id, plan, monthly_limit, daily_limit,
                  monthly_used, daily_used, month_key, day_key, expires_at, updated_at
                ) VALUES (%s, 'free', %s, %s, 0, 0, %s, %s, NULL, %s)
                ON CONFLICT (user_id) DO UPDATE SET
                  plan=EXCLUDED.plan,
                  monthly_limit=EXCLUDED.monthly_limit,
                  daily_limit=EXCLUDED.daily_limit,
                  monthly_used=EXCLUDED.monthly_used,
                  daily_used=EXCLUDED.daily_used,
                  month_key=EXCLUDED.month_key,
                  day_key=EXCLUDED.day_key,
                  expires_at=EXCLUDED.expires_at,
                  updated_at=EXCLUDED.updated_at
                """,
                (user_id, free_weekly_eff, free_daily_eff, _week_key(now), _day_key(now), now),
            )
        else:
            conn.execute(
                """
                INSERT INTO quota(
                  user_id, plan, monthly_limit, daily_limit,
                  monthly_used, daily_used, month_key, day_key, expires_at, updated_at
                ) VALUES (?, 'free', ?, ?, 0, 0, ?, ?, NULL, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                  plan=excluded.plan,
                  monthly_limit=excluded.monthly_limit,
                  daily_limit=excluded.daily_limit,
                  monthly_used=excluded.monthly_used,
                  daily_used=excluded.daily_used,
                  month_key=excluded.month_key,
                  day_key=excluded.day_key,
                  expires_at=excluded.expires_at,
                  updated_at=excluded.updated_at
                """,
                (user_id, free_weekly_eff, free_daily_eff, _week_key(now), _day_key(now), now),
            )
        return User(id=user_id, email=email, phone=phone)


def ensure_platform_user(platform_user_id: int, email: str | None, phone: str | None) -> None:
    """
    将主站 `api/` auth_users.id 同步为本地 users.id（配额/邀请等仍用本地表）。
    JWT 的 sub 须与平台用户 id 一致；email/phone 来自 token 声明。
    """
    email_n = (email or "").strip().lower() or None
    phone_n = (phone or "").strip() or None
    if email_n == "":
        email_n = None
    if phone_n == "":
        phone_n = None
    now = int(time.time())
    with connect() as conn:
        # Avoid breaking /api/me when admin edited email/phone into conflicts.
        # If email/phone is already bound to a different user, skip syncing that field.
        try:
            if email_n:
                r = conn.execute(
                    _adapt_sql("SELECT id FROM users WHERE email = ? AND id <> ?"),
                    (email_n, int(platform_user_id)),
                ).fetchone()
                if r:
                    email_n = None
            if phone_n:
                r = conn.execute(
                    _adapt_sql("SELECT id FROM users WHERE phone = ? AND id <> ?"),
                    (phone_n, int(platform_user_id)),
                ).fetchone()
                if r:
                    phone_n = None
        except Exception:
            # Best-effort only; never block login path.
            pass
        free_weekly_eff, free_daily_eff = _effective_free_limits()
        row = conn.execute(_adapt_sql("SELECT id FROM users WHERE id = ?"), (int(platform_user_id),)).fetchone()
        if row:
            try:
                if _is_pg():
                    conn.execute(
                        """
                        UPDATE users SET
                          email = COALESCE(%s, email),
                          phone = COALESCE(%s, phone)
                        WHERE id = %s
                        """,
                        (email_n, phone_n, int(platform_user_id)),
                    )
                else:
                    conn.execute(
                        """
                        UPDATE users SET
                          email = COALESCE(?, email),
                          phone = COALESCE(?, phone)
                        WHERE id = ?
                        """,
                        (email_n, phone_n, int(platform_user_id)),
                    )
            except Exception:
                # Do not block auth if contact info cannot be synced.
                pass
        else:
            try:
                if _is_pg():
                    conn.execute(
                        """
                        INSERT INTO users (id, email, phone, created_at)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (id) DO UPDATE SET
                          email = COALESCE(EXCLUDED.email, users.email),
                          phone = COALESCE(EXCLUDED.phone, users.phone)
                        """,
                        (int(platform_user_id), email_n, phone_n, now),
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO users (id, email, phone, created_at) VALUES (?, ?, ?, ?)
                        ON CONFLICT(id) DO UPDATE SET
                          email = COALESCE(excluded.email, users.email),
                          phone = COALESCE(excluded.phone, users.phone)
                        """,
                        (int(platform_user_id), email_n, phone_n, now),
                    )
            except Exception:
                pass
        if _is_pg():
            conn.execute(
                """
                INSERT INTO quota(
                  user_id, plan, monthly_limit, daily_limit,
                  monthly_used, daily_used, month_key, day_key, expires_at, updated_at
                ) VALUES (%s, 'free', %s, %s, 0, 0, %s, %s, NULL, %s)
                ON CONFLICT (user_id) DO NOTHING
                """,
                (
                    int(platform_user_id),
                    free_weekly_eff,
                    free_daily_eff,
                    _week_key(now),
                    _day_key(now),
                    now,
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO quota(
                  user_id, plan, monthly_limit, daily_limit,
                  monthly_used, daily_used, month_key, day_key, expires_at, updated_at
                ) VALUES (?, 'free', ?, ?, 0, 0, ?, ?, NULL, ?)
                ON CONFLICT(user_id) DO NOTHING
                """,
                (
                    int(platform_user_id),
                    free_weekly_eff,
                    free_daily_eff,
                    _week_key(now),
                    _day_key(now),
                    now,
                ),
            )


def get_quota_status(user_id: int) -> dict:
    now = int(time.time())
    with connect() as conn:
        row = conn.execute("SELECT * FROM quota WHERE user_id = ?", (user_id,)).fetchone()
        if not row:
            # should not happen; create default
            free_weekly_eff, free_daily_eff = _effective_free_limits()
            conn.execute(
                """
                INSERT INTO quota(
                  user_id, plan, monthly_limit, daily_limit,
                  monthly_used, daily_used, month_key, day_key, expires_at, updated_at
                ) VALUES (?, 'free', ?, ?, 0, 0, ?, ?, NULL, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                  plan=excluded.plan,
                  monthly_limit=excluded.monthly_limit,
                  daily_limit=excluded.daily_limit,
                  monthly_used=excluded.monthly_used,
                  daily_used=excluded.daily_used,
                  month_key=excluded.month_key,
                  day_key=excluded.day_key,
                  expires_at=excluded.expires_at,
                  updated_at=excluded.updated_at
                """,
                (user_id, free_weekly_eff, free_daily_eff, _week_key(now), _day_key(now), now),
            )
            row = conn.execute("SELECT * FROM quota WHERE user_id = ?", (user_id,)).fetchone()

        week_key = str(row["month_key"])
        day_key = str(row["day_key"])
        weekly_used = int(row["monthly_used"])
        daily_used = int(row["daily_used"])

        # IMPORTANT (MVP ops): do NOT auto-sync per-user limits for free plan here.
        # Admin UI supports raising day/week limits for specific users (e.g. manual grants),
        # and auto-sync would immediately revert those overrides back to defaults (day=5/week=10).
        plan = str(row["plan"])
        cur_weekly_limit = int(row["monthly_limit"])
        cur_daily_limit = int(row["daily_limit"])

        if week_key != _week_key(now) or day_key != _day_key(now):
            # reset counters if needed
            if week_key != _week_key(now):
                weekly_used = 0
                week_key = _week_key(now)
            if day_key != _day_key(now):
                daily_used = 0
                day_key = _day_key(now)
            conn.execute(
                """
                UPDATE quota SET month_key=?, day_key=?, monthly_used=?, daily_used=?, updated_at=?
                WHERE user_id=?
                """,
                (week_key, day_key, weekly_used, daily_used, now, user_id),
            )

        weekly_limit_base = int(cur_weekly_limit)
        daily_limit_base = int(cur_daily_limit)
        expires_at = row["expires_at"]
        # Weekly bonus from invite rewards (per-week, capped)
        wk_start = _week_start_ts(now)
        day_start = _day_start_ts(now)
        bonus_week = 0
        bonus_day = 0
        try:
            rr = conn.execute(
                """
                SELECT COALESCE(SUM(amount), 0) AS s
                FROM reward_ledger
                WHERE inviter_id=? AND created_at>=?
                """,
                (user_id, wk_start),
            ).fetchone()
            bonus_week = int(rr["s"] or 0) if rr else 0
        except Exception:
            bonus_week = 0
        try:
            rr2 = conn.execute(
                """
                SELECT COALESCE(SUM(amount), 0) AS s
                FROM reward_ledger
                WHERE inviter_id=? AND reward_type='invite_first_query_inviter_daily' AND created_at>=?
                """,
                (user_id, day_start),
            ).fetchone()
            bonus_day = int(rr2["s"] or 0) if rr2 else 0
        except Exception:
            bonus_day = 0
        weekly_limit = max(0, weekly_limit_base + max(0, bonus_week))
        daily_limit = max(0, daily_limit_base + max(0, bonus_day))

        remaining_week = max(0, weekly_limit - weekly_used)
        remaining_day = max(0, daily_limit - daily_used)
        remaining = min(remaining_week, remaining_day)
        return {
            "plan": str(row["plan"]),
            "remaining": remaining,
            "remaining_day": remaining_day,
            "remaining_week": remaining_week,
            # backward-compat alias (older UI may show "month")
            "remaining_month": remaining_week,
            "daily_used": daily_used,
            "weekly_used": weekly_used,
            "monthly_used": weekly_used,
            "daily_limit": daily_limit,
            "weekly_limit": weekly_limit,
            "monthly_limit": weekly_limit,
            "weekly_limit_base": weekly_limit_base,
            "weekly_bonus": max(0, bonus_week),
            "daily_limit_base": daily_limit_base,
            "daily_bonus": max(0, bonus_day),
            "expires_at": int(expires_at) if expires_at is not None else None,
        }


def consume_quota(user_id: int, secid: str, period: str, idempotency_key: str, ok: bool) -> dict:
    """
    扣次：由上层决定是否“成功”。
    - 调用方 idempotency_key 命中则去重；
    - 另：同一用户同一 secid 在自然日内已成功扣过，则不再扣（换日/周/月、刷新、旧前端键均兜底）。
    """
    now = int(time.time())
    secid_n = str(secid or "").strip()
    downgrade_expired_vip_plan(int(user_id))
    with connect() as conn:
        # idempotency
        existing = conn.execute(
            "SELECT result, consumed_at FROM quota_ledger WHERE user_id=? AND idempotency_key=?",
            (user_id, idempotency_key),
        ).fetchone()
        if existing:
            return {
                "deduped": True,
                "result": str(existing["result"]),
                "consumed_at": int(existing["consumed_at"]),
                "quota": get_quota_status(user_id),
            }

        # Free whitelist (MVP): core indices are always free and should never consume quota.
        # Keep it server-enforced to avoid client-side bypass or UI inconsistencies.
        free_whitelist = {"1.000001", "0.399001", "0.399006", "0.899050", "0.000977"}  # 上证/深成/创业/北证50/浪潮信息
        if ok and secid_n in free_whitelist:
            conn.execute(
                """
                INSERT INTO quota_ledger(user_id, secid, period, idempotency_key, consumed_at, result)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, secid_n, period, idempotency_key, now, "free"),
            )
            return {"deduped": False, "result": "free", "consumed_at": now, "quota": get_quota_status(user_id)}

        # Same symbol already charged today → no second charge (period switch / refresh / old clients).
        if ok and secid_n:
            try:
                today = _day_key(now)
                prev_rows = conn.execute(
                    """
                    SELECT result, consumed_at FROM quota_ledger
                    WHERE user_id=? AND secid=? AND result='ok'
                    ORDER BY consumed_at DESC
                    LIMIT 30
                    """,
                    (user_id, secid_n),
                ).fetchall()
                for pr in prev_rows or []:
                    try:
                        if _day_key(int(pr["consumed_at"])) == today:
                            return {
                                "deduped": True,
                                "result": "ok",
                                "consumed_at": int(pr["consumed_at"]),
                                "quota": get_quota_status(user_id),
                            }
                    except Exception:
                        continue
            except Exception:
                pass

        had_ok_before = False
        try:
            r0 = conn.execute(
                "SELECT 1 FROM quota_ledger WHERE user_id=? AND result='ok' LIMIT 1",
                (user_id,),
            ).fetchone()
            had_ok_before = bool(r0)
        except Exception:
            had_ok_before = False

        status = get_quota_status(user_id)
        if not ok:
            conn.execute(
                """
                INSERT INTO quota_ledger(user_id, secid, period, idempotency_key, consumed_at, result)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, secid_n, period, idempotency_key, now, "failed"),
            )
            return {"deduped": False, "result": "failed", "consumed_at": now, "quota": status}

        if status["remaining"] <= 0:
            conn.execute(
                """
                INSERT INTO quota_ledger(user_id, secid, period, idempotency_key, consumed_at, result)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, secid_n, period, idempotency_key, now, "exhausted"),
            )
            return {"deduped": False, "result": "exhausted", "consumed_at": now, "quota": status}

        # update counters
        conn.execute(
            """
            UPDATE quota
            SET monthly_used = monthly_used + 1,
                daily_used = daily_used + 1,
                updated_at = ?
            WHERE user_id = ?
            """,
            (now, user_id),
        )
        conn.execute(
            """
            INSERT INTO quota_ledger(user_id, secid, period, idempotency_key, consumed_at, result)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, secid_n, period, idempotency_key, now, "ok"),
        )

        # Invite reward trigger: first successful query after binding
        if not had_ok_before:
            try:
                rel = conn.execute(
                    "SELECT inviter_id FROM invite_relations WHERE invitee_id=?",
                    (user_id,),
                ).fetchone()
                if rel and rel["inviter_id"] is not None:
                    inviter_id = int(rel["inviter_id"])
                    wk_start = _week_start_ts(now)

                    def inviter_awarded_this_week(uid: int) -> int:
                        rr = conn.execute(
                            """
                            SELECT COALESCE(SUM(amount), 0) AS s
                            FROM reward_ledger
                            WHERE inviter_id=? AND reward_type='invite_first_query_inviter' AND created_at>=?
                            """,
                            (uid, wk_start),
                        ).fetchone()
                        return int(rr["s"] or 0) if rr else 0

                    # inviter weekly cap
                    cfg = invite_cfg_effective()
                    cap = max(0, int(cfg.get("invite_weekly_cap", 0)))
                    already = inviter_awarded_this_week(inviter_id)
                    grant_inviter = max(0, int(cfg.get("invite_reward_inviter_weekly", 0)))
                    if cap > 0:
                        grant_inviter = min(grant_inviter, max(0, cap - already))

                    if grant_inviter > 0:
                        # receiver=inviter_id, source=invitee(user_id)
                        if _is_pg():
                            conn.execute(
                                """
                                INSERT INTO reward_ledger(inviter_id, invitee_id, reward_type, amount, created_at)
                                VALUES (?, ?, ?, ?, ?)
                                ON CONFLICT (inviter_id, invitee_id, reward_type) DO NOTHING
                                """,
                                (inviter_id, user_id, "invite_first_query_inviter", grant_inviter, now),
                            )
                        else:
                            conn.execute(
                                """
                                INSERT OR IGNORE INTO reward_ledger(inviter_id, invitee_id, reward_type, amount, created_at)
                                VALUES (?, ?, ?, ?, ?)
                                """,
                                (inviter_id, user_id, "invite_first_query_inviter", grant_inviter, now),
                            )

                    # inviter daily bonus (optional)
                    grant_inviter_day = max(0, int(cfg.get("invite_reward_inviter_daily", 0)))
                    if grant_inviter_day > 0:
                        if _is_pg():
                            conn.execute(
                                """
                                INSERT INTO reward_ledger(inviter_id, invitee_id, reward_type, amount, created_at)
                                VALUES (?, ?, ?, ?, ?)
                                ON CONFLICT (inviter_id, invitee_id, reward_type) DO NOTHING
                                """,
                                (inviter_id, user_id, "invite_first_query_inviter_daily", grant_inviter_day, now),
                            )
                        else:
                            conn.execute(
                                """
                                INSERT OR IGNORE INTO reward_ledger(inviter_id, invitee_id, reward_type, amount, created_at)
                                VALUES (?, ?, ?, ?, ?)
                                """,
                                (inviter_id, user_id, "invite_first_query_inviter_daily", grant_inviter_day, now),
                            )

                    # invitee welcome bonus (not capped by inviter cap)
                    grant_invitee = max(0, int(cfg.get("invite_reward_invitee_weekly", 0)))
                    if grant_invitee > 0:
                        # receiver=user_id, source=inviter_id
                        if _is_pg():
                            conn.execute(
                                """
                                INSERT INTO reward_ledger(inviter_id, invitee_id, reward_type, amount, created_at)
                                VALUES (?, ?, ?, ?, ?)
                                ON CONFLICT (inviter_id, invitee_id, reward_type) DO NOTHING
                                """,
                                (user_id, inviter_id, "invite_first_query_invitee", grant_invitee, now),
                            )
                        else:
                            conn.execute(
                                """
                                INSERT OR IGNORE INTO reward_ledger(inviter_id, invitee_id, reward_type, amount, created_at)
                                VALUES (?, ?, ?, ?, ?)
                                """,
                                (user_id, inviter_id, "invite_first_query_invitee", grant_invitee, now),
                            )

                    grant_invitee_day = max(0, int(cfg.get("invite_reward_invitee_daily", 0)))
                    if grant_invitee_day > 0:
                        if _is_pg():
                            conn.execute(
                                """
                                INSERT INTO reward_ledger(inviter_id, invitee_id, reward_type, amount, created_at)
                                VALUES (?, ?, ?, ?, ?)
                                ON CONFLICT (inviter_id, invitee_id, reward_type) DO NOTHING
                                """,
                                (user_id, inviter_id, "invite_first_query_invitee_daily", grant_invitee_day, now),
                            )
                        else:
                            conn.execute(
                                """
                                INSERT OR IGNORE INTO reward_ledger(inviter_id, invitee_id, reward_type, amount, created_at)
                                VALUES (?, ?, ?, ?, ?)
                                """,
                                (user_id, inviter_id, "invite_first_query_invitee_daily", grant_invitee_day, now),
                            )
            except Exception:
                # reward is best-effort; do not break quota consumption
                pass

        return {"deduped": False, "result": "ok", "consumed_at": now, "quota": get_quota_status(user_id)}


def kline_cache_get(cache_key: str) -> dict[str, Any] | None:
    now = int(time.time())
    key = str(cache_key or "").strip()
    if not key:
        return None
    with connect() as conn:
        row = conn.execute(
            "SELECT expire_ts, payload_json FROM kline_cache WHERE cache_key=?",
            (key,),
        ).fetchone()
        if not row:
            return None
        exp = int(row["expire_ts"])
        if exp <= now:
            try:
                conn.execute("DELETE FROM kline_cache WHERE cache_key=?", (key,))
            except Exception:
                pass
            return None
        try:
            return json.loads(str(row["payload_json"]))
        except Exception:
            return None


def kline_cache_put(cache_key: str, payload: dict[str, Any], ttl_s: float) -> None:
    key = str(cache_key or "").strip()
    if not key:
        return
    ttl = float(ttl_s or 0)
    if ttl <= 0:
        return
    now = int(time.time())
    exp = now + max(1, int(ttl))
    try:
        s = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        return
    with connect() as conn:
        try:
            if _is_pg():
                conn.execute(
                    """
                    INSERT INTO kline_cache(cache_key, expire_ts, payload_json, updated_at)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (cache_key) DO UPDATE SET
                      expire_ts=EXCLUDED.expire_ts,
                      payload_json=EXCLUDED.payload_json,
                      updated_at=EXCLUDED.updated_at
                    """,
                    (key, exp, s, now),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO kline_cache(cache_key, expire_ts, payload_json, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(cache_key) DO UPDATE SET
                      expire_ts=excluded.expire_ts,
                      payload_json=excluded.payload_json,
                      updated_at=excluded.updated_at
                    """,
                    (key, exp, s, now),
                )
        except Exception:
            pass


def admin_list_users(q: str = "", limit: int = 50, offset: int = 0) -> dict[str, Any]:
    qq = (q or "").strip()
    limit = max(1, min(int(limit or 50), 200))
    offset = max(0, int(offset or 0))
    with connect() as conn:
        where = ""
        params: list[Any] = []
        if qq:
            if qq.isdigit():
                where = "WHERE u.id = ? OR u.phone LIKE ?"
                params.extend([int(qq), f"%{qq}%"])
            else:
                where = "WHERE u.email LIKE ? OR u.phone LIKE ?"
                params.extend([f"%{qq}%", f"%{qq}%"])
        rows = conn.execute(
            f"""
            SELECT u.id, u.email, u.phone, u.created_at,
                   q.plan, q.monthly_limit, q.daily_limit, q.monthly_used, q.daily_used, q.month_key, q.day_key, q.expires_at
            FROM users u
            LEFT JOIN quota q ON q.user_id = u.id
            {where}
            ORDER BY u.id DESC
            LIMIT ? OFFSET ?
            """,
            (*params, limit, offset),
        ).fetchall()

        items = []
        for r in rows:
            uid = int(r["id"])
            items.append(
                {
                    "id": uid,
                    "email": str(r["email"]) if r["email"] is not None else "",
                    "phone": str(r["phone"]) if r["phone"] is not None else "",
                    "created_at": int(r["created_at"]),
                    "quota": get_quota_status(uid) if r["plan"] is not None else None,
                }
            )
        return {"items": items, "limit": limit, "offset": offset}


def admin_get_user(uid: int) -> dict[str, Any]:
    uid = int(uid)
    with connect() as conn:
        u = conn.execute("SELECT id, email, phone, created_at FROM users WHERE id=?", (uid,)).fetchone()
        if not u:
            raise ValueError("user not found")
        invite_code = conn.execute("SELECT code FROM invite_codes WHERE user_id=?", (uid,)).fetchone()
        inviter = conn.execute("SELECT inviter_id FROM invite_relations WHERE invitee_id=?", (uid,)).fetchone()
        return {
            "user": {
                "id": int(u["id"]),
                "email": str(u["email"]) if u["email"] is not None else "",
                "phone": str(u["phone"]) if u["phone"] is not None else "",
                "created_at": int(u["created_at"]),
            },
            "quota": get_quota_status(uid),
            "invite": {
                "my_code": str(invite_code["code"]) if invite_code else None,
                "inviter_id": int(inviter["inviter_id"]) if inviter else None,
            },
        }


def admin_update_user_basic(uid: int, *, email: str | None = None, phone: str | None = None) -> dict[str, Any]:
    """
    Update user basic contact fields (email/phone).
    - email normalized to lowercase; empty -> NULL
    - phone trimmed; empty -> NULL
    Uniqueness is enforced by DB constraints.
    """
    uid = int(uid)
    email_n = (email or "").strip().lower() or None
    phone_n = (phone or "").strip().replace(" ", "") or None
    # Basic format guardrails (keep permissive; identity system may use various formats).
    if email_n is not None and ("@" not in email_n or len(email_n) < 6):
        raise ValueError("邮箱格式不正确")
    if phone_n is not None and (len(phone_n) < 6 or len(phone_n) > 32):
        raise ValueError("手机号格式不正确")

    with connect() as conn:
        u = conn.execute("SELECT id FROM users WHERE id=?", (uid,)).fetchone()
        if not u:
            raise ValueError("user not found")
        try:
            conn.execute(
                "UPDATE users SET email=?, phone=? WHERE id=?",
                (email_n, phone_n, uid),
            )
        except Exception as e:
            msg = str(e).lower()
            if "unique" in msg or "unique constraint" in msg:
                raise ValueError("邮箱或手机号已被占用")
            raise
    return admin_get_user(uid)


def admin_user_reset(
    uid: int,
    *,
    actor: str = "admin",
    invite_binding: bool = False,
    quota_reset: bool = False,
    quota_ledger: bool = False,
    pay_orders: bool = False,
    reward_ledger: bool = False,
    commission_ledger: bool = False,
    note: str = "",
) -> dict[str, Any]:
    """
    Soft reset user for testing: keep user_id but clear selected business data.
    Intended for non-prod usage. Caller must enforce environment guardrails.
    """
    uid = int(uid)
    now = int(time.time())
    note = str(note or "")[:200]

    with connect() as conn:
        u = conn.execute("SELECT id FROM users WHERE id=?", (uid,)).fetchone()
        if not u:
            raise ValueError("user not found")

        # Snapshot before (counts only; keep privacy).
        before = {
            "invite_binding": bool(conn.execute("SELECT 1 AS x FROM invite_relations WHERE invitee_id=? LIMIT 1", (uid,)).fetchone()),
            "quota": None,
            "quota_ledger": 0,
            "pay_orders": 0,
            "reward_ledger": 0,
            "commission_ledger": 0,
        }
        try:
            before["quota"] = get_quota_status(uid)
        except Exception:
            before["quota"] = None
        try:
            r = conn.execute("SELECT COUNT(1) AS c FROM quota_ledger WHERE user_id=?", (uid,)).fetchone()
            before["quota_ledger"] = int(_row_get(r, "c") or 0) if r else 0
        except Exception:
            before["quota_ledger"] = 0
        try:
            r = conn.execute("SELECT COUNT(1) AS c FROM pay_orders WHERE user_id=?", (uid,)).fetchone()
            before["pay_orders"] = int(_row_get(r, "c") or 0) if r else 0
        except Exception:
            before["pay_orders"] = 0
        try:
            r = conn.execute(
                "SELECT COUNT(1) AS c FROM reward_ledger WHERE inviter_id=? OR invitee_id=?",
                (uid, uid),
            ).fetchone()
            before["reward_ledger"] = int(_row_get(r, "c") or 0) if r else 0
        except Exception:
            before["reward_ledger"] = 0
        try:
            r = conn.execute(
                "SELECT COUNT(1) AS c FROM commission_ledger WHERE agent_user_id=? OR buyer_user_id=?",
                (uid, uid),
            ).fetchone()
            before["commission_ledger"] = int(_row_get(r, "c") or 0) if r else 0
        except Exception:
            before["commission_ledger"] = 0

        deleted: dict[str, int] = {}
        if invite_binding:
            try:
                cur = conn.execute("DELETE FROM invite_relations WHERE invitee_id=?", (uid,))
                deleted["invite_binding"] = int(getattr(cur, "rowcount", 0) or 0)
            except Exception:
                deleted["invite_binding"] = 0

        if quota_ledger:
            try:
                cur = conn.execute("DELETE FROM quota_ledger WHERE user_id=?", (uid,))
                deleted["quota_ledger"] = int(getattr(cur, "rowcount", 0) or 0)
            except Exception:
                deleted["quota_ledger"] = 0

        if pay_orders:
            try:
                cur = conn.execute("DELETE FROM pay_orders WHERE user_id=?", (uid,))
                deleted["pay_orders"] = int(getattr(cur, "rowcount", 0) or 0)
            except Exception:
                deleted["pay_orders"] = 0

        if reward_ledger:
            try:
                cur = conn.execute(
                    "DELETE FROM reward_ledger WHERE inviter_id=? OR invitee_id=?",
                    (uid, uid),
                )
                deleted["reward_ledger"] = int(getattr(cur, "rowcount", 0) or 0)
            except Exception:
                deleted["reward_ledger"] = 0

        if commission_ledger:
            try:
                cur = conn.execute(
                    "DELETE FROM commission_ledger WHERE agent_user_id=? OR buyer_user_id=?",
                    (uid, uid),
                )
                deleted["commission_ledger"] = int(getattr(cur, "rowcount", 0) or 0)
            except Exception:
                deleted["commission_ledger"] = 0

        if quota_reset:
            fp, fw, fd, _ = _plan_defaults("free")
            wk = _week_key(now)
            dk = _day_key(now)
            # reset used to 0 and expiry cleared
            try:
                if _is_pg():
                    conn.execute(
                        """
                        INSERT INTO quota(
                          user_id, plan, monthly_limit, daily_limit,
                          monthly_used, daily_used, month_key, day_key, expires_at, updated_at
                        ) VALUES (%s, %s, %s, %s, 0, 0, %s, %s, NULL, %s)
                        ON CONFLICT (user_id) DO UPDATE SET
                          plan=EXCLUDED.plan,
                          monthly_limit=EXCLUDED.monthly_limit,
                          daily_limit=EXCLUDED.daily_limit,
                          monthly_used=EXCLUDED.monthly_used,
                          daily_used=EXCLUDED.daily_used,
                          month_key=EXCLUDED.month_key,
                          day_key=EXCLUDED.day_key,
                          expires_at=NULL,
                          updated_at=EXCLUDED.updated_at
                        """,
                        (uid, fp, int(fw), int(fd), wk, dk, now),
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO quota(
                          user_id, plan, monthly_limit, daily_limit,
                          monthly_used, daily_used, month_key, day_key, expires_at, updated_at
                        ) VALUES (?, ?, ?, ?, 0, 0, ?, ?, NULL, ?)
                        ON CONFLICT(user_id) DO UPDATE SET
                          plan=excluded.plan,
                          monthly_limit=excluded.monthly_limit,
                          daily_limit=excluded.daily_limit,
                          monthly_used=excluded.monthly_used,
                          daily_used=excluded.daily_used,
                          month_key=excluded.month_key,
                          day_key=excluded.day_key,
                          expires_at=NULL,
                          updated_at=excluded.updated_at
                        """,
                        (uid, fp, int(fw), int(fd), wk, dk, now),
                    )
            except Exception:
                # best-effort; do not block other resets
                pass

        after = {
            "deleted": deleted,
            "quota": None,
        }
        try:
            after["quota"] = get_quota_status(uid)
        except Exception:
            after["quota"] = None

        try:
            conn.execute(
                """
                INSERT INTO admin_ops_ledger(user_id, actor, action, before_json, after_json, note, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uid,
                    str(actor or "admin"),
                    "user:reset",
                    json.dumps(before, ensure_ascii=False, separators=(",", ":")),
                    json.dumps(after, ensure_ascii=False, separators=(",", ":")),
                    note,
                    now,
                ),
            )
        except Exception:
            pass

    return admin_get_user(uid)


def get_user_basic(uid: int) -> dict[str, Any]:
    uid = int(uid)
    with connect() as conn:
        u = conn.execute("SELECT id, email, phone, created_at FROM users WHERE id=?", (uid,)).fetchone()
        if not u:
            raise ValueError("user not found")
        return {
            "id": int(u["id"]),
            "email": str(u["email"]) if u["email"] is not None else "",
            "phone": str(u["phone"]) if u["phone"] is not None else "",
            "created_at": int(u["created_at"]),
        }


def admin_set_remaining(uid: int, remaining: int) -> dict[str, Any]:
    uid = int(uid)
    remaining = max(0, int(remaining))
    now = int(time.time())
    status = get_quota_status(uid)
    daily_limit = int(status["daily_limit"])
    monthly_limit = int(status["monthly_limit"])
    # remaining 受 day/month 两个口径共同限制，因此这里把 day/month 都设置到 >= remaining
    new_daily_used = max(0, daily_limit - remaining)
    new_monthly_used = max(0, monthly_limit - remaining)
    with connect() as conn:
        conn.execute(
            """
            UPDATE quota
            SET daily_used=?, monthly_used=?, updated_at=?
            WHERE user_id=?
            """,
            (new_daily_used, new_monthly_used, now, uid),
        )
    return {"quota": get_quota_status(uid)}


def _plan_defaults(plan: str) -> tuple[str, int, int, int | None]:
    """
    Return (normalized_plan, weekly_limit_base, daily_limit_base, expires_at_ts)
    Note: week/month are unified as "weekly" in this MVP schema.
    """
    now = int(time.time())
    p = str(plan or "").strip().lower()
    if not p:
        p = "free"
    if p in ("free", "anon"):
        fw, fd = _effective_free_limits()
        return ("free", int(fw), int(fd), None)
    if p in ("vip", "vip_month", "month", "monthly"):
        # 30 days validity (soft; only used for UI display currently)
        vc = vip_quota_cfg_effective()
        return ("vip_month", int(vc["vip_weekly"]), int(vc["vip_daily_cap"]), now + 30 * 86400)
    if p in ("vip_year_999", "vip_year", "year", "yearly"):
        vc = vip_quota_cfg_effective()
        return ("vip_year_999", int(vc["vip_weekly"]), int(vc["vip_daily_cap"]), now + 365 * 86400)
    if p in ("vip_trial_99", "vip_trial", "trial", "trial_99"):
        # 体验卡：7 天；额度低于月卡（默认 100/周 + 20/天，约≤100 次/首周），单价不低于月卡折算
        vc = vip_quota_cfg_effective()
        return (
            "vip_trial_99",
            int(vc["vip_trial_weekly"]),
            int(vc["vip_trial_daily_cap"]),
            now + 7 * 86400,
        )
    # Custom/legacy plan: keep current limits, do not set expiry.
    return (p, -1, -1, None)


def downgrade_expired_vip_plan(user_id: int) -> None:
    """
    若 VIP 已过期（expires_at < now），单事务写回 free 并记 ops 流水。
    供扣次前与 /api/me 等读路径调用，避免「到期仍显示 VIP」。
    """
    uid = int(user_id)
    now = int(time.time())
    with connect() as conn:
        row = conn.execute(
            "SELECT plan, expires_at, monthly_used, daily_used FROM quota WHERE user_id=?",
            (uid,),
        ).fetchone()
        if not row:
            return
        plan = str(row["plan"])
        if plan not in ("vip_month", "vip_year_999", "vip_trial_99"):
            return
        exp = row["expires_at"]
        if exp is None or int(exp) >= now:
            return
        fp, fw, fd, _ = _plan_defaults("free")
        mu = int(row["monthly_used"])
        du = int(row["daily_used"])
        nu_w = max(0, min(mu, int(fw)))
        nu_d = max(0, min(du, int(fd)))
        before = {"plan": plan, "expires_at": int(exp), "monthly_used": mu, "daily_used": du}
        conn.execute(
            """
            UPDATE quota
            SET plan=?, monthly_limit=?, daily_limit=?, monthly_used=?, daily_used=?, expires_at=NULL, updated_at=?
            WHERE user_id=?
            """,
            (fp, fw, fd, nu_w, nu_d, now, uid),
        )
        after = {"plan": fp, "expires_at": None, "monthly_used": nu_w, "daily_used": nu_d}
        conn.execute(
            """
            INSERT INTO admin_ops_ledger(user_id, actor, action, before_json, after_json, note, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                uid,
                "system",
                "vip_expire",
                json.dumps(before, ensure_ascii=False, separators=(",", ":")),
                json.dumps(after, ensure_ascii=False, separators=(",", ":")),
                "auto downgrade: expires_at passed",
                now,
            ),
        )


def admin_quota_adjust(
    uid: int,
    *,
    actor: str = "admin",
    set_remaining_day: int | None = None,
    set_remaining_week: int | None = None,
    delta_day: int | None = None,
    delta_week: int | None = None,
    plan: str | None = None,
    note: str = "",
) -> dict[str, Any]:
    """
    Admin-only quota adjustment with audit log.
    - set_remaining_*: absolute set remaining counts (>=0)
    - delta_*: relative adjustment on remaining counts (can be negative)
    - plan: switch plan preset (free/vip_month/vip_year_999/vip_trial_99)
    """
    uid = int(uid)
    now = int(time.time())
    actor = str(actor or "admin").strip()[:64] or "admin"
    note = str(note or "").strip()[:200]

    before = get_quota_status(uid)

    with connect() as conn:
        # Fetch raw quota row (we need base limits/used)
        row = conn.execute("SELECT * FROM quota WHERE user_id=?", (uid,)).fetchone()
        if not row:
            raise ValueError("quota not found")

        cur_plan = str(row["plan"])
        cur_weekly_limit_base = int(row["monthly_limit"])
        cur_daily_limit_base = int(row["daily_limit"])
        cur_weekly_used = int(row["monthly_used"])
        cur_daily_used = int(row["daily_used"])

        new_plan = cur_plan
        new_weekly_limit_base = cur_weekly_limit_base
        new_daily_limit_base = cur_daily_limit_base
        new_expires_at = row["expires_at"]

        action_bits: list[str] = []

        if plan is not None:
            np, wk, dy, exp = _plan_defaults(str(plan))
            new_plan = np
            if wk >= 0:
                new_weekly_limit_base = int(wk)
            if dy >= 0:
                new_daily_limit_base = int(dy)
            if exp is not None:
                new_expires_at = int(exp)
            else:
                # free plan clears expiry
                if new_plan == "free":
                    new_expires_at = None
            action_bits.append(f"plan:{cur_plan}->{new_plan}")

        # After potential plan change, recompute remaining based on base limits (ignore bonuses for admin ops)
        def _clamp_used(limit_base: int, used: int) -> int:
            if limit_base < 0:
                return max(0, used)
            return max(0, min(int(used), int(limit_base)))

        new_weekly_used = _clamp_used(new_weekly_limit_base, cur_weekly_used)
        new_daily_used = _clamp_used(new_daily_limit_base, cur_daily_used)

        def _apply_set_remaining(limit_base: int, used: int, remaining: int) -> int:
            if limit_base < 0:
                # unknown limit: treat remaining as "best effort" by adjusting used down/up around 0
                return max(0, int(used))
            # If admin sets remaining beyond current limit, auto-raise the base limit so it can take effect.
            rem = max(0, int(remaining))
            return max(0, int(limit_base) - min(rem, int(limit_base)))

        def _apply_delta_remaining(limit_base: int, used: int, delta: int) -> int:
            if limit_base < 0:
                return max(0, int(used))
            cur_rem = max(0, int(limit_base) - int(used))
            tgt_rem = cur_rem + int(delta)
            tgt_rem = max(0, min(int(tgt_rem), int(limit_base)))
            return max(0, int(limit_base) - int(tgt_rem))

        if set_remaining_day is not None:
            # Auto-raise daily limit if needed so the target remaining is achievable.
            if new_daily_limit_base >= 0:
                new_daily_limit_base = max(int(new_daily_limit_base), max(0, int(set_remaining_day)))
                new_daily_used = _clamp_used(new_daily_limit_base, new_daily_used)
            new_daily_used = _apply_set_remaining(new_daily_limit_base, new_daily_used, int(set_remaining_day))
            action_bits.append("set_remaining_day")
        if set_remaining_week is not None:
            if new_weekly_limit_base >= 0:
                new_weekly_limit_base = max(int(new_weekly_limit_base), max(0, int(set_remaining_week)))
                new_weekly_used = _clamp_used(new_weekly_limit_base, new_weekly_used)
            new_weekly_used = _apply_set_remaining(new_weekly_limit_base, new_weekly_used, int(set_remaining_week))
            action_bits.append("set_remaining_week")
        if delta_day is not None and int(delta_day) != 0:
            if new_daily_limit_base >= 0:
                cur_rem0 = max(0, int(new_daily_limit_base) - int(new_daily_used))
                tgt_rem0 = max(0, cur_rem0 + int(delta_day))
                # Expand limit if needed so +delta can take effect.
                if tgt_rem0 > int(new_daily_limit_base):
                    new_daily_limit_base = int(new_daily_used) + int(tgt_rem0)
                tgt_rem0 = max(0, min(int(tgt_rem0), int(new_daily_limit_base)))
                new_daily_used = max(0, int(new_daily_limit_base) - int(tgt_rem0))
            else:
                new_daily_used = _apply_delta_remaining(new_daily_limit_base, new_daily_used, int(delta_day))
            action_bits.append(f"delta_day:{int(delta_day)}")
        if delta_week is not None and int(delta_week) != 0:
            if new_weekly_limit_base >= 0:
                cur_rem1 = max(0, int(new_weekly_limit_base) - int(new_weekly_used))
                tgt_rem1 = max(0, cur_rem1 + int(delta_week))
                if tgt_rem1 > int(new_weekly_limit_base):
                    new_weekly_limit_base = int(new_weekly_used) + int(tgt_rem1)
                tgt_rem1 = max(0, min(int(tgt_rem1), int(new_weekly_limit_base)))
                new_weekly_used = max(0, int(new_weekly_limit_base) - int(tgt_rem1))
            else:
                new_weekly_used = _apply_delta_remaining(new_weekly_limit_base, new_weekly_used, int(delta_week))
            action_bits.append(f"delta_week:{int(delta_week)}")

        if not action_bits:
            # no-op but still return current quota
            return {"quota": get_quota_status(uid)}

        # Persist quota changes
        conn.execute(
            """
            UPDATE quota
            SET plan=?,
                monthly_limit=?,
                daily_limit=?,
                monthly_used=?,
                daily_used=?,
                expires_at=?,
                updated_at=?
            WHERE user_id=?
            """,
            (
                str(new_plan),
                int(new_weekly_limit_base),
                int(new_daily_limit_base),
                int(new_weekly_used),
                int(new_daily_used),
                new_expires_at,
                now,
                uid,
            ),
        )

        after = get_quota_status(uid)
        conn.execute(
            """
            INSERT INTO admin_ops_ledger(user_id, actor, action, before_json, after_json, note, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                uid,
                actor,
                ",".join(action_bits)[:120],
                json.dumps(before, ensure_ascii=False, separators=(",", ":")),
                json.dumps(after, ensure_ascii=False, separators=(",", ":")),
                note,
                now,
            ),
        )

    return {"quota": get_quota_status(uid)}


def admin_list_ops_ledger(user_id: int, limit: int = 50) -> dict[str, Any]:
    user_id = int(user_id)
    limit = max(1, min(int(limit or 50), 200))
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, user_id, actor, action, before_json, after_json, note, created_at
            FROM admin_ops_ledger
            WHERE user_id=?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
        items = []
        for r in rows:
            items.append(
                {
                    "id": int(r["id"]),
                    "user_id": int(r["user_id"]),
                    "actor": str(r["actor"]),
                    "action": str(r["action"]),
                    "note": str(r["note"] or ""),
                    "created_at": int(r["created_at"]),
                }
            )
        return {"items": items, "limit": limit}


def admin_list_quota_ledger(user_id: int, limit: int = 50) -> dict[str, Any]:
    user_id = int(user_id)
    limit = max(1, min(int(limit or 50), 200))
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, user_id, secid, period, consumed_at, result
            FROM quota_ledger
            WHERE user_id=?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
        items = [
            {
                "id": int(r["id"]),
                "user_id": int(r["user_id"]),
                "secid": str(r["secid"]),
                "period": str(r["period"]),
                "consumed_at": int(r["consumed_at"]),
                "result": str(r["result"]),
            }
            for r in rows
        ]
        return {"items": items, "limit": limit}


def _admin_pay_orders_where_params(
    *,
    user_id: int = 0,
    status: str = "",
    plan: str = "",
    q: str = "",
) -> tuple[str, list[Any]]:
    """构建 pay_orders 管理端筛选 WHERE 与参数（SQLite / PG 占位符由 connect 适配）。"""
    uid_f = int(user_id or 0)
    st = (status or "").strip()
    pl = (plan or "").strip()
    qq = (q or "").strip()
    clauses: list[str] = []
    params: list[Any] = []
    if uid_f > 0:
        clauses.append("user_id = ?")
        params.append(uid_f)
    if st:
        clauses.append("status = ?")
        params.append(st)
    if pl:
        clauses.append("plan = ?")
        params.append(pl)
    if qq:
        like = f"%{qq}%"
        or_parts = ["out_trade_no LIKE ?", "COALESCE(CAST(transaction_id AS TEXT), '') LIKE ?"]
        params.extend([like, like])
        if qq.isdigit():
            try:
                n = int(qq)
                if n > 0:
                    or_parts.append("user_id = ?")
                    params.append(n)
            except ValueError:
                pass
        clauses.append("(" + " OR ".join(or_parts) + ")")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


def _admin_pay_order_row_dict(r: Any) -> dict[str, Any]:
    return {
        "id": int(r["id"]),
        "out_trade_no": str(r["out_trade_no"] or ""),
        "user_id": int(r["user_id"]),
        "user_phone": str(_row_get(r, "user_phone") or ""),
        "user_email": str(_row_get(r, "user_email") or ""),
        "plan": str(r["plan"] or ""),
        "amount_fen": int(r["amount_fen"] or 0),
        "channel": str(r["channel"] or ""),
        "status": str(r["status"] or ""),
        "transaction_id": str(r["transaction_id"] or "") if r["transaction_id"] is not None else "",
        "created_at": int(r["created_at"] or 0),
        "updated_at": int(r["updated_at"] or 0),
        "has_code_url": bool(int(_row_get(r, "has_code_url") or 0)),
    }


def admin_list_pay_orders(
    *,
    user_id: int = 0,
    status: str = "",
    plan: str = "",
    q: str = "",
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """管理端：VIP/支付订单列表（pay_orders）；q 匹配商户单号 / 微信单号 / 纯数字时 user_id。"""
    limit = max(1, min(int(limit or 50), 200))
    offset = max(0, int(offset or 0))
    where, params = _admin_pay_orders_where_params(user_id=user_id, status=status, plan=plan, q=q)
    with connect() as conn:
        cnt_row = conn.execute(f"SELECT COUNT(1) AS c FROM pay_orders{where}", tuple(params)).fetchone()
        total = int(_row_get(cnt_row, "c") or 0)
        rows = conn.execute(
            f"""
            SELECT o.id, o.out_trade_no, o.user_id,
                   u.phone AS user_phone, u.email AS user_email,
                   o.plan, o.amount_fen, o.channel, o.status,
                   o.transaction_id, o.created_at, o.updated_at,
                   CASE WHEN o.code_url IS NOT NULL AND LENGTH(TRIM(CAST(o.code_url AS TEXT))) > 0 THEN 1 ELSE 0 END AS has_code_url
            FROM pay_orders o
            LEFT JOIN users u ON u.id = o.user_id
            {where}
            ORDER BY o.id DESC
            LIMIT ? OFFSET ?
            """,
            (*params, limit, offset),
        ).fetchall()
        items = [_admin_pay_order_row_dict(r) for r in rows]
        return {"items": items, "total": total, "limit": limit, "offset": offset}


def admin_export_pay_orders_rows(
    *,
    user_id: int = 0,
    status: str = "",
    plan: str = "",
    q: str = "",
    cap: int = 5000,
) -> list[dict[str, Any]]:
    """导出用：同筛选条件，按 id 倒序最多 cap 条。"""
    cap = max(1, min(int(cap or 5000), 10000))
    where, params = _admin_pay_orders_where_params(user_id=user_id, status=status, plan=plan, q=q)
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT o.id, o.out_trade_no, o.user_id,
                   u.phone AS user_phone, u.email AS user_email,
                   o.plan, o.amount_fen, o.channel, o.status,
                   o.transaction_id, o.created_at, o.updated_at,
                   CASE WHEN o.code_url IS NOT NULL AND LENGTH(TRIM(CAST(o.code_url AS TEXT))) > 0 THEN 1 ELSE 0 END AS has_code_url
            FROM pay_orders o
            LEFT JOIN users u ON u.id = o.user_id
            {where}
            ORDER BY o.id DESC
            LIMIT ?
            """,
            (*params, cap),
        ).fetchall()
        return [_admin_pay_order_row_dict(r) for r in rows]


def admin_export_payout_requests_alipay_rows(
    *,
    status: str = "",
    cap: int = 5000,
    mark_exported: bool = True,
    exported_note: str = "alipay_batch",
) -> list[dict[str, Any]]:
    """
    Export payout requests as a finance-friendly CSV (Alipay batch transfer).
    Only exports status=approved by default when status is empty (safe default).
    Joins current payout account to provide full account_no for transfer.
    """
    st = str(status or "").strip().lower()
    if not st:
        st = "approved"
    if st not in ("pending", "approved", "paid", "rejected"):
        st = "approved"
    cap = max(1, min(int(cap or 5000), 10000))
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT r.id AS request_id,
                   r.user_id AS user_id,
                   r.amount_fen AS amount_fen,
                   r.status AS status,
                   r.note AS note,
                   r.transfer_ref AS transfer_ref,
                   r.created_at AS created_at,
                   a.channel AS channel,
                   a.account_name AS account_name,
                   a.account_no AS account_no,
                   a.phone AS phone
            FROM agent_payout_requests r
            LEFT JOIN agent_payout_account a ON a.user_id = r.user_id
            WHERE r.status = ?
            ORDER BY r.id ASC
            LIMIT ?
            """,
            (st, cap),
        ).fetchall()
        out: list[dict[str, Any]] = []
        exported_ids: list[int] = []
        for r in rows or []:
            rid = int(_row_get(r, "request_id") or 0)
            if rid > 0:
                exported_ids.append(rid)
            out.append(
                {
                    "request_id": rid,
                    "user_id": int(_row_get(r, "user_id") or 0),
                    "status": str(_row_get(r, "status") or ""),
                    "amount_yuan": f"{(int(_row_get(r,'amount_fen') or 0) / 100):.2f}",
                    # Alipay batch friendly columns
                    "收款方账号": str(_row_get(r, "account_no") or ""),
                    "收款方姓名": str(_row_get(r, "account_name") or ""),
                    "转账金额(元)": f"{(int(_row_get(r,'amount_fen') or 0) / 100):.2f}",
                    "备注": str(_row_get(r, "note") or ""),
                    # extra columns for reconciliation
                    "手机号": str(_row_get(r, "phone") or ""),
                    "申请ID": str(_row_get(r, "request_id") or ""),
                    "用户ID": str(_row_get(r, "user_id") or ""),
                    "渠道": str(_row_get(r, "channel") or ""),
                    "申请时间": str(_row_get(r, "created_at") or ""),
                    "打款流水": str(_row_get(r, "transfer_ref") or ""),
                    "状态": str(_row_get(r, "status") or ""),
                    "是否完结": "是" if str(_row_get(r, "status") or "").lower() in ("paid", "rejected") else "否",
                }
            )
        if mark_exported and exported_ids:
            now = int(time.time())
            note = str(exported_note or "").strip()[:64]
            qmarks = ",".join(["?"] * len(exported_ids))
            try:
                conn.execute(
                    f"UPDATE agent_payout_requests SET exported_at=?, exported_note=?, updated_at=? WHERE id IN ({qmarks})",
                    (now, note, now, *exported_ids),
                )
            except Exception:
                pass
        return out


def admin_operator_list_enabled_phones_from_db() -> list[str]:
    """启用的分管/总管（库表）；手机号已规范为纯数字。"""
    from .admin_otp import normalize_admin_phone

    with connect() as conn:
        rows = conn.execute(
            _adapt_sql("SELECT phone FROM admin_operators WHERE enabled = 1"),
            (),
        ).fetchall()
    out: list[str] = []
    for r in rows or []:
        ph = _row_get(r, "phone")
        if not ph:
            continue
        p = normalize_admin_phone(str(ph))
        if p:
            out.append(p)
    return out


def admin_operator_role_for_phone(phone: str) -> tuple[str, int]:
    """返回 (role, perm_flags)。仅 env 白名单、无表行时视为 super。"""
    from .admin_otp import normalize_admin_phone, parse_admin_otp_env_phones

    p = normalize_admin_phone(phone)
    with connect() as conn:
        row = conn.execute(
            _adapt_sql(
                "SELECT role, perm_flags FROM admin_operators WHERE phone = ? AND enabled = 1 LIMIT 1"
            ),
            (p,),
        ).fetchone()
    if row:
        return str(_row_get(row, "role") or "deputy"), int(_row_get(row, "perm_flags") or 0)
    if p in parse_admin_otp_env_phones():
        return "super", 0x7FFFFFFF
    return "deputy", 0


def admin_config_get_all() -> dict[str, str]:
    with connect() as conn:
        rows = conn.execute("SELECT key, value FROM admin_config").fetchall()
    out: dict[str, str] = {}
    for r in rows:
        out[str(r["key"])] = str(r["value"])
    return out


def admin_config_get(key: str) -> str | None:
    k = str(key or "").strip()
    if not k:
        return None
    with connect() as conn:
        row = conn.execute("SELECT value FROM admin_config WHERE key=?", (k,)).fetchone()
    if not row:
        return None
    return str(row["value"])


def _effective_free_limits() -> tuple[int, int]:
    """
    Effective defaults for free plan (weekly, daily).
    Priority: admin_config overrides > .env defaults.
    Keys:
    - free_weekly
    - free_daily_cap
    """
    fw = int(getattr(settings, "free_weekly", 50) or 50)
    fd = int(getattr(settings, "free_daily_cap", 10) or 10)
    try:
        v = admin_config_get("free_weekly")
        if v is not None and str(v).strip() != "":
            fw2 = int(str(v).strip())
            if fw2 >= 0:
                fw = fw2
    except Exception:
        pass
    try:
        v = admin_config_get("free_daily_cap")
        if v is not None and str(v).strip() != "":
            fd2 = int(str(v).strip())
            if fd2 >= 0:
                fd = fd2
    except Exception:
        pass
    return fw, fd


def admin_config_set(key: str, value: str) -> dict[str, Any]:
    k = str(key or "").strip()
    if not k:
        raise ValueError("missing key")
    v = str(value if value is not None else "").strip()
    if not v:
        with connect() as conn:
            conn.execute("DELETE FROM admin_config WHERE key=?", (k,))
        return {"item": None, "deleted": True, "key": k}
    now = int(time.time())
    with connect() as conn:
        if _is_pg():
            conn.execute(
                """
                INSERT INTO admin_config(key, value, updated_at)
                VALUES (%s, %s, %s)
                ON CONFLICT (key) DO UPDATE SET
                  value=EXCLUDED.value,
                  updated_at=EXCLUDED.updated_at
                """,
                (k, v, now),
            )
            row = conn.execute("SELECT key, value, updated_at FROM admin_config WHERE key=%s", (k,)).fetchone()
        else:
            conn.execute(
                """
                INSERT INTO admin_config(key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                  value=excluded.value,
                  updated_at=excluded.updated_at
                """,
                (k, v, now),
            )
            row = conn.execute("SELECT key, value, updated_at FROM admin_config WHERE key=?", (k,)).fetchone()
    return {"item": dict(row) if row else {"key": k, "value": v, "updated_at": now}}


def _cfg_int(key: str, default: int) -> int:
    try:
        v = admin_config_get(key)
        if v is None or str(v).strip() == "":
            return int(default)
        return int(float(str(v).strip()))
    except Exception:
        return int(default)


def _cfg_float(key: str, default: float) -> float:
    try:
        v = admin_config_get(key)
        if v is None or str(v).strip() == "":
            return float(default)
        return float(str(v).strip())
    except Exception:
        return float(default)


def _agent_commission_enabled() -> bool:
    return bool(_cfg_int("agent_commission_enabled", 1) == 1)


def _agent_upgrade_commission_enabled() -> bool:
    """
    Whether paid agent tier upgrade orders (agent_growth/agent_pro) should generate commissions.
    Default off for safer rollout; can be enabled via admin_config.
    """
    return bool(_cfg_int("agent_upgrade_commission_enabled", 0) == 1)


def _agent_commission_rate_normal() -> float:
    # Backward-compatible alias for L1 rate.
    return float(_agent_commission_rate_l1())


def _clamp_rate(r: float) -> float:
    try:
        rr = float(r)
    except Exception:
        rr = 0.0
    if rr < 0.0:
        rr = 0.0
    if rr > 0.9:
        rr = 0.9
    return float(rr)


def _agent_commission_rate_l1() -> float:
    # Default: keep MVP behavior (20%) on direct referrer.
    v = _cfg_float("agent_commission_rate_l1", _cfg_float("agent_commission_rate_normal", 0.20))
    return _clamp_rate(float(v))


def _agent_commission_rate_l2() -> float:
    v = _cfg_float("agent_commission_rate_l2", 0.05)
    return _clamp_rate(float(v))


def _agent_commission_rate_l3() -> float:
    v = _cfg_float("agent_commission_rate_l3", 0.02)
    return _clamp_rate(float(v))


def _agent_commission_rate_cap_total() -> float:
    # Safety cap: sum of (l1+l2+l3) must not exceed this cap.
    v = _cfg_float("agent_commission_rate_cap_total", 0.30)
    return _clamp_rate(float(v))


def _agent_commission_l3_min_level() -> str:
    """
    Minimum agent level required to receive L3 (team) commission.
    Default: growth (starter/normal won't receive team commission).
    """
    try:
        v = admin_config_get("agent_commission_l3_min_level")
        s = str(v or "").strip().lower()
        if s in ("starter", "normal", ""):
            return "starter"
        if s in ("growth", "senior"):
            return "growth"
        if s in ("pro", "gold"):
            return "pro"
    except Exception:
        pass
    return "growth"


def _agent_commission_rates_effective() -> dict[str, float]:
    l1 = _agent_commission_rate_l1()
    l2 = _agent_commission_rate_l2()
    l3 = _agent_commission_rate_l3()
    cap = _agent_commission_rate_cap_total()
    s = float(l1 + l2 + l3)
    if cap > 0 and s > cap:
        # Scale down proportionally to satisfy cap; keep relative weights.
        k = cap / s if s > 0 else 0.0
        l1, l2, l3 = float(l1 * k), float(l2 * k), float(l3 * k)
    return {"l1": float(l1), "l2": float(l2), "l3": float(l3), "cap_total": float(cap)}


def _agent_tier_enabled() -> bool:
    return bool(_cfg_int("agent_tier_enabled", 1) == 1)


def _agent_tier_window_days() -> int:
    d = int(_cfg_int("agent_tier_window_days", 30))
    return max(7, min(d, 180))


def _agent_tier_thresholds() -> dict[str, int]:
    # Amounts are fen.
    return {
        "growth_team_gmv_fen": int(_cfg_int("agent_tier_growth_team_gmv_fen", 3000 * 100)),
        "growth_active_direct": int(_cfg_int("agent_tier_growth_active_direct", 3)),
        "pro_team_gmv_fen": int(_cfg_int("agent_tier_pro_team_gmv_fen", 20000 * 100)),
        "pro_active_direct": int(_cfg_int("agent_tier_pro_active_direct", 10)),
    }


def _agent_settle_delay_days() -> int:
    d = int(_cfg_int("agent_settle_delay_days", 7))
    return max(0, min(d, 90))


def _invite_chain_for_user_in_conn(conn: Any, user_id: int) -> tuple[int | None, int | None, int | None]:
    """
    Return (l1, l2, l3) inviter user_ids for a given invitee.
    Uses cached columns when present; falls back to recursive lookup.
    """
    uid = int(user_id)
    try:
        row = conn.execute(
            "SELECT inviter_id, inviter_l1_id, inviter_l2_id, inviter_l3_id FROM invite_relations WHERE invitee_id=?",
            (uid,),
        ).fetchone()
        if not row:
            return (None, None, None)
        l1 = row["inviter_l1_id"] if row["inviter_l1_id"] is not None else row["inviter_id"]
        l2 = row["inviter_l2_id"]
        l3 = row["inviter_l3_id"]
        l1i = int(l1) if l1 is not None else None
        l2i = int(l2) if l2 is not None else None
        l3i = int(l3) if l3 is not None else None
        return (l1i, l2i, l3i)
    except Exception:
        pass
    # Fallback: manual chain traversal on inviter_id only.
    l1 = None
    l2 = None
    l3 = None
    try:
        r1 = conn.execute("SELECT inviter_id FROM invite_relations WHERE invitee_id=?", (uid,)).fetchone()
        if r1 and r1["inviter_id"] is not None:
            l1 = int(r1["inviter_id"])
        if l1:
            r2 = conn.execute("SELECT inviter_id FROM invite_relations WHERE invitee_id=?", (l1,)).fetchone()
            if r2 and r2["inviter_id"] is not None:
                l2 = int(r2["inviter_id"])
        if l2:
            r3 = conn.execute("SELECT inviter_id FROM invite_relations WHERE invitee_id=?", (l2,)).fetchone()
            if r3 and r3["inviter_id"] is not None:
                l3 = int(r3["inviter_id"])
    except Exception:
        return (l1, l2, l3)
    return (l1, l2, l3)


def _invite_backfill_ancestors_in_conn(conn: Any) -> None:
    now = int(time.time())
    try:
        rows = conn.execute("SELECT invitee_id, inviter_id FROM invite_relations").fetchall()
    except Exception:
        return
    for r in rows or []:
        try:
            invitee_id = int(r["invitee_id"])
            inviter_id = int(r["inviter_id"])
        except Exception:
            continue
        l1 = inviter_id
        l2 = None
        l3 = None
        seen = {invitee_id, inviter_id}
        try:
            rr = conn.execute("SELECT inviter_id FROM invite_relations WHERE invitee_id=?", (inviter_id,)).fetchone()
            if rr and rr["inviter_id"] is not None:
                v2 = int(rr["inviter_id"])
                if v2 not in seen:
                    l2 = v2
                    seen.add(v2)
        except Exception:
            l2 = None
        try:
            if l2:
                rr = conn.execute("SELECT inviter_id FROM invite_relations WHERE invitee_id=?", (l2,)).fetchone()
                if rr and rr["inviter_id"] is not None:
                    v3 = int(rr["inviter_id"])
                    if v3 not in seen:
                        l3 = v3
        except Exception:
            l3 = None
        depth = 1 + (1 if l2 else 0) + (1 if l3 else 0)
        try:
            conn.execute(
                """
                UPDATE invite_relations
                SET inviter_l1_id=?, inviter_l2_id=?, inviter_l3_id=?, depth=?, updated_at=?
                WHERE invitee_id=?
                """,
                (l1, l2, l3, int(depth), now, invitee_id),
            )
        except Exception:
            # columns may not exist on very old schema; ignore
            pass


def agent_get_status(user_id: int) -> dict[str, Any] | None:
    uid = int(user_id)
    with connect() as conn:
        row = conn.execute(
            "SELECT user_id, level, expires_at, tier_points, tier_updated_at, tier_locked, updated_at FROM agent_status WHERE user_id=?",
            (uid,),
        ).fetchone()
        if not row:
            return None
        return {
            "user_id": int(row["user_id"]),
            "level": str(row["level"]),
            "expires_at": int(row["expires_at"]) if row["expires_at"] is not None else None,
            "tier_points": int(_row_get(row, "tier_points") or 0),
            "tier_updated_at": int(_row_get(row, "tier_updated_at") or 0),
            "tier_locked": bool(int(_row_get(row, "tier_locked") or 0) == 1),
            "updated_at": int(row["updated_at"]),
        }


def _agent_is_active_in_conn(conn: Any, user_id: int, now: int) -> bool:
    uid = int(user_id)
    row = conn.execute("SELECT level, expires_at FROM agent_status WHERE user_id=?", (uid,)).fetchone()
    if not row:
        return False
    lvl = str(row["level"] or "").strip().lower()
    # Accept both legacy names (normal/senior/gold) and new names (starter/growth/pro).
    if lvl not in ("normal", "senior", "gold", "starter", "growth", "pro"):
        return False
    exp = row["expires_at"]
    if exp is None:
        return True
    try:
        return int(exp) >= int(now)
    except Exception:
        return False


def _agent_upsert_in_conn(conn: Any, user_id: int, level: str, expires_at: int | None, now: int) -> None:
    uid = int(user_id)
    lvl = str(level or "").strip().lower() or "normal"
    if _is_pg():
        conn.execute(
            """
            INSERT INTO agent_status(user_id, level, expires_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (user_id) DO UPDATE SET
              level=EXCLUDED.level,
              expires_at=EXCLUDED.expires_at,
              updated_at=EXCLUDED.updated_at
            """,
            (uid, lvl, int(expires_at) if expires_at is not None else None, int(now)),
        )
    else:
        conn.execute(
            """
            INSERT INTO agent_status(user_id, level, expires_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
              level=excluded.level,
              expires_at=excluded.expires_at,
              updated_at=excluded.updated_at
            """,
            (uid, lvl, int(expires_at) if expires_at is not None else None, int(now)),
        )


def _commission_insert_in_conn(
    conn: Any,
    *,
    out_trade_no: str,
    agent_user_id: int,
    level_depth: int = 1,
    buyer_user_id: int,
    plan: str,
    amount_fen: int,
    rate: float,
    commission_fen: int,
    eligible_at: int,
    now: int,
    rule_version: str = "v1",
    rate_source: str = "base",
    calc_meta: str = "{}",
) -> bool:
    """Return True if inserted, False if already exists (idempotent)."""
    otn = str(out_trade_no or "").strip()
    if not otn:
        return False
    depth = int(level_depth or 1)
    if depth < 1:
        depth = 1
    if depth > 3:
        depth = 3
    rv = str(rule_version or "v1").strip()[:20] or "v1"
    rs = str(rate_source or "base").strip()[:20] or "base"
    cm = str(calc_meta or "{}")
    if _is_pg():
        row = conn.execute(
            """
            INSERT INTO commission_ledger(
              out_trade_no, agent_user_id, level_depth, buyer_user_id, plan, amount_fen, rate, commission_fen,
              rule_version, rate_source, calc_meta,
              eligible_at, status, paid_at, paid_note, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', NULL, '', ?, ?)
            ON CONFLICT (out_trade_no, agent_user_id, level_depth) DO NOTHING
            RETURNING out_trade_no
            """,
            (
                otn,
                int(agent_user_id),
                int(depth),
                int(buyer_user_id),
                str(plan),
                int(amount_fen),
                float(rate),
                int(commission_fen),
                rv,
                rs,
                cm,
                int(eligible_at),
                int(now),
                int(now),
            ),
        ).fetchone()
        return bool(row)
    conn.execute(
        """
        INSERT OR IGNORE INTO commission_ledger(
          out_trade_no, agent_user_id, level_depth, buyer_user_id, plan, amount_fen, rate, commission_fen,
          rule_version, rate_source, calc_meta,
          eligible_at, status, paid_at, paid_note, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', NULL, '', ?, ?)
        """,
        (
            otn,
            int(agent_user_id),
            int(depth),
            int(buyer_user_id),
            str(plan),
            int(amount_fen),
            float(rate),
            int(commission_fen),
            rv,
            rs,
            cm,
            int(eligible_at),
            int(now),
            int(now),
        ),
    )
    return True


def _agent_calc_meta_json(*, buyer_id: int, chain: tuple[int | None, int | None, int | None]) -> str:
    try:
        return json.dumps(
            {"buyer_user_id": int(buyer_id), "chain": {"l1": chain[0], "l2": chain[1], "l3": chain[2]}},
            ensure_ascii=False,
            separators=(",", ":"),
        )
    except Exception:
        return "{}"


def _commission_generate_for_paid_order_in_conn(conn: Any, *, out_trade_no: str, buyer_id: int, plan: str, amount_fen: int, paid_at: int, now: int) -> None:
    if not _agent_commission_enabled():
        return
    p = str(plan or "").strip().lower()
    if p in ("agent_growth", "agent_pro") and not _agent_upgrade_commission_enabled():
        return
    chain = _invite_chain_for_user_in_conn(conn, buyer_id)
    rates = _agent_commission_rates_effective()
    meta = _agent_calc_meta_json(buyer_id=buyer_id, chain=chain)
    delay_days = _agent_settle_delay_days()
    eligible_at = int((paid_at or now) + delay_days * 86400)

    pairs: list[tuple[int, int, float]] = []
    if chain[0]:
        pairs.append((1, int(chain[0]), float(rates["l1"])))
    if chain[1]:
        pairs.append((2, int(chain[1]), float(rates["l2"])))
    if chain[2]:
        # L3 (team) commission is a management allowance: require minimum agent level.
        try:
            min_lvl = _agent_commission_l3_min_level()
            cur_lvl = _agent_level_for_user_in_conn(conn, int(chain[2]), now)
            if _agent_level_rank(cur_lvl) >= _agent_level_rank(min_lvl):
                pairs.append((3, int(chain[2]), float(rates["l3"])))
        except Exception:
            # Fail-closed: if level lookup fails, skip L3 to avoid unintended leakage.
            pass

    for depth, agent_uid, rate in pairs:
        if agent_uid <= 0 or rate <= 0:
            continue
        try:
            if not _agent_is_active_in_conn(conn, int(agent_uid), now):
                continue
        except Exception:
            continue
        commission_fen = int(round(float(amount_fen) * float(rate)))
        if commission_fen <= 0:
            continue
        _commission_insert_in_conn(
            conn,
            out_trade_no=str(out_trade_no),
            agent_user_id=int(agent_uid),
            level_depth=int(depth),
            buyer_user_id=int(buyer_id),
            plan=str(plan),
            amount_fen=int(amount_fen),
            rate=float(rate),
            commission_fen=int(commission_fen),
            eligible_at=int(eligible_at),
            now=int(now),
            rule_version="v2",
            rate_source="base",
            calc_meta=meta,
        )


def commission_generate_for_order(out_trade_no: str) -> dict[str, Any]:
    """Admin/manual: generate ledger for a paid order (idempotent)."""
    now = int(time.time())
    otn = str(out_trade_no or "").strip()
    if not otn:
        raise ValueError("missing out_trade_no")
    with connect() as conn:
        row = conn.execute("SELECT * FROM pay_orders WHERE out_trade_no=?", (otn,)).fetchone()
        if not row:
            raise ValueError("order_not_found")
        if str(row["status"]) != "paid":
            raise ValueError("order_not_paid")
        plan = str(row["plan"])
        buyer_id = int(row["user_id"])
        if not _agent_commission_enabled():
            return {"ok": True, "skipped": True, "reason": "commission_disabled"}
        p = str(plan or "").strip().lower()
        if p in ("agent_growth", "agent_pro") and not _agent_upgrade_commission_enabled():
            return {"ok": True, "skipped": True, "reason": "agent_upgrade_commission_disabled"}
        amount_fen = int(row["amount_fen"])
        paid_at = int(row["paid_at"] or now)
        _commission_generate_for_paid_order_in_conn(
            conn,
            out_trade_no=otn,
            buyer_id=int(buyer_id),
            plan=str(plan),
            amount_fen=int(amount_fen),
            paid_at=int(paid_at),
            now=int(now),
        )
        return {
            "ok": True,
            "buyer_user_id": int(buyer_id),
        }


def admin_list_commissions(
    *,
    status: str = "",
    agent_user_id: int = 0,
    q: str = "",
    limit: int = 50,
    offset: int = 0,
    eligible_only: bool = False,
) -> dict[str, Any]:
    limit = max(1, min(int(limit or 50), 200))
    offset = max(0, int(offset or 0))
    st = str(status or "").strip().lower()
    uid = int(agent_user_id or 0)
    qv = str(q or "").strip()
    now = int(time.time())
    clauses: list[str] = []
    params: list[Any] = []
    if st:
        clauses.append("status = ?")
        params.append(st)
    if uid > 0:
        clauses.append("agent_user_id = ?")
        params.append(uid)
    if qv:
        clauses.append("(out_trade_no LIKE ? OR CAST(agent_user_id AS TEXT)=? OR CAST(buyer_user_id AS TEXT)=?)")
        params.extend([f"%{qv}%", qv, qv])
    if eligible_only:
        clauses.append("status='pending' AND eligible_at <= ?")
        params.append(now)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT id, out_trade_no, agent_user_id, level_depth, buyer_user_id, plan, amount_fen, rate, commission_fen,
                   rule_version, rate_source, calc_meta,
                   eligible_at, status, paid_at, paid_note, created_at, updated_at
            FROM commission_ledger
            {where}
            ORDER BY id DESC
            LIMIT ? OFFSET ?
            """,
            (*params, limit, offset),
        ).fetchall()
        items = []
        for r in rows:
            items.append(
                {
                    "id": int(r["id"]),
                    "out_trade_no": str(r["out_trade_no"]),
                    "agent_user_id": int(r["agent_user_id"]),
                    "level_depth": int(r["level_depth"] or 1),
                    "buyer_user_id": int(r["buyer_user_id"]),
                    "plan": str(r["plan"]),
                    "amount_fen": int(r["amount_fen"]),
                    "rate": float(r["rate"]),
                    "commission_fen": int(r["commission_fen"]),
                    "rule_version": str(r.get("rule_version") or "v1") if hasattr(r, "get") else str(r["rule_version"] or "v1"),
                    "rate_source": str(r.get("rate_source") or "base") if hasattr(r, "get") else str(r["rate_source"] or "base"),
                    "eligible_at": int(r["eligible_at"]),
                    "status": str(r["status"]),
                    "paid_at": int(r["paid_at"]) if r["paid_at"] is not None else None,
                    "paid_note": str(r["paid_note"] or ""),
                    "created_at": int(r["created_at"]),
                    "updated_at": int(r["updated_at"]),
                }
            )
        return {"items": items, "limit": limit, "offset": offset}


def admin_mark_commissions_paid(agent_user_id: int, *, note: str = "") -> dict[str, Any]:
    """Mark all eligible pending commissions for agent as paid (manual settlement)."""
    now = int(time.time())
    uid = int(agent_user_id)
    if uid <= 0:
        raise ValueError("invalid agent_user_id")
    note2 = str(note or "").strip()[:120]
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, commission_fen FROM commission_ledger
            WHERE agent_user_id=? AND status='pending' AND eligible_at<=?
            """,
            (uid, now),
        ).fetchall()
        total = sum(int(r["commission_fen"]) for r in rows)
        if not rows:
            return {"ok": True, "count": 0, "total_fen": 0}
        conn.execute(
            """
            UPDATE commission_ledger
            SET status='paid', paid_at=?, paid_note=?, updated_at=?
            WHERE agent_user_id=? AND status='pending' AND eligible_at<=?
            """,
            (now, note2, now, uid, now),
        )
        return {"ok": True, "count": len(rows), "total_fen": int(total), "paid_at": now}


def _mask_account_no(v: str) -> str:
    s = str(v or "").strip()
    if not s:
        return ""
    if len(s) <= 6:
        return s[0:1] + "***" + s[-1:]
    return s[0:2] + "***" + s[-4:]


def _mask_identity(v: str) -> str:
    """
    Mask buyer identity for user-facing pages.
    Accepts phone/email/other and returns a privacy-safe string.
    """
    s = str(v or "").strip()
    if not s:
        return ""
    # Phone (accepts +86, spaces, dashes; normalize to last 11 digits)
    try:
        digits = "".join([c for c in s if c.isdigit()])
    except Exception:
        digits = ""
    if digits and len(digits) >= 11:
        p = digits[-11:]
        return p[:3] + "****" + p[-4:]
    if "@" in s:
        try:
            name, domain = s.split("@", 1)
            name = name.strip()
            domain = domain.strip()
            if not name:
                return "…@" + domain
            if len(name) <= 1:
                return name + "…@" + domain
            if len(name) == 2:
                return name[0] + "…@" + domain
            return name[:2] + "…" + name[-1:] + "@" + domain
        except Exception:
            return s[:2] + "…" + s[-2:] if len(s) > 6 else s
    return s[:2] + "…" + s[-2:] if len(s) > 6 else s


def agent_commission_overview(user_id: int) -> dict[str, Any]:
    """User-facing overview for agent/commissions/payout."""
    now = int(time.time())
    uid = int(user_id)
    with connect() as conn:
        st = agent_get_status(uid)
        inv_total = 0
        try:
            r = conn.execute("SELECT COUNT(1) AS c FROM invite_relations WHERE inviter_id=?", (uid,)).fetchone()
            inv_total = int(r["c"] or 0) if r else 0
        except Exception:
            inv_total = 0

        # Metrics for "直推/团队/成长等级" (no level words in user UI).
        win_days = _agent_tier_window_days()
        since_ts = int(now - win_days * 86400)
        direct_paid_orders = 0
        direct_paid_amount_fen = 0
        team_paid_amount_fen = 0
        active_direct = 0
        team_size = 0
        try:
            # Direct buyers are invitees where inviter_id = uid.
            r = conn.execute(
                """
                SELECT COUNT(1) AS c, COALESCE(SUM(o.amount_fen),0) AS s
                FROM pay_orders o
                JOIN invite_relations ir ON ir.invitee_id = o.user_id
                WHERE o.status='paid' AND o.paid_at>=? AND ir.inviter_id=?
                """,
                (since_ts, uid),
            ).fetchone()
            direct_paid_orders = int(_row_get(r, "c") or 0) if r else 0
            direct_paid_amount_fen = int(_row_get(r, "s") or 0) if r else 0
        except Exception:
            pass
        try:
            # Active direct referrals: number of direct invitees with at least 1 paid order in window.
            r = conn.execute(
                """
                SELECT COUNT(1) AS c
                FROM (
                  SELECT o.user_id
                  FROM pay_orders o
                  JOIN invite_relations ir ON ir.invitee_id = o.user_id
                  WHERE o.status='paid' AND o.paid_at>=? AND ir.inviter_id=?
                  GROUP BY o.user_id
                ) t
                """,
                (since_ts, uid),
            ).fetchone()
            active_direct = int(_row_get(r, "c") or 0) if r else 0
        except Exception:
            pass
        try:
            r = conn.execute(
                """
                SELECT COALESCE(SUM(o.amount_fen),0) AS s
                FROM pay_orders o
                JOIN invite_relations ir ON ir.invitee_id = o.user_id
                WHERE o.status='paid' AND o.paid_at>=?
                  AND (ir.inviter_l1_id=? OR ir.inviter_l2_id=? OR ir.inviter_l3_id=?)
                """,
                (since_ts, uid, uid, uid),
            ).fetchone()
            team_paid_amount_fen = int(_row_get(r, "s") or 0) if r else 0
        except Exception:
            pass
        try:
            r = conn.execute(
                """
                SELECT COUNT(1) AS c
                FROM invite_relations
                WHERE inviter_l1_id=? OR inviter_l2_id=? OR inviter_l3_id=?
                """,
                (uid, uid, uid),
            ).fetchone()
            team_size = int(_row_get(r, "c") or 0) if r else 0
        except Exception:
            pass

        # Tier evaluation (auto-upgrade unless locked).
        tier = {"level": (st or {}).get("level") if isinstance(st, dict) else None, "locked": False, "updated": False}
        try:
            if _agent_tier_enabled():
                thr = _agent_tier_thresholds()
                target = "starter"
                if team_paid_amount_fen >= int(thr["pro_team_gmv_fen"]) and active_direct >= int(thr["pro_active_direct"]):
                    target = "pro"
                elif team_paid_amount_fen >= int(thr["growth_team_gmv_fen"]) or active_direct >= int(thr["growth_active_direct"]):
                    target = "growth"
                # Read lock flag from agent_status if present; normalize legacy level strings.
                row_lock = conn.execute(
                    "SELECT tier_locked, level FROM agent_status WHERE user_id=?",
                    (uid,),
                ).fetchone()
                locked = bool(int(_row_get(row_lock, "tier_locked") or 0) == 1) if row_lock else False
                cur_lvl = str(_row_get(row_lock, "level") or (st or {}).get("level") or "").strip().lower() if row_lock else str((st or {}).get("level") or "").strip().lower()
                if cur_lvl in ("normal", ""):
                    cur_lvl = "starter"
                if cur_lvl == "senior":
                    cur_lvl = "growth"
                if cur_lvl == "gold":
                    cur_lvl = "pro"
                tier["locked"] = locked
                tier["target"] = target
                tier["window_days"] = win_days
                tier["team_gmv_fen"] = int(team_paid_amount_fen)
                tier["active_direct"] = int(active_direct)
                if not locked and target and cur_lvl and target != cur_lvl:
                    # Update level in-place; keep expires_at unchanged.
                    conn.execute(
                        "UPDATE agent_status SET level=?, tier_points=?, tier_updated_at=?, updated_at=? WHERE user_id=?",
                        (target, int(team_paid_amount_fen), now, now, uid),
                    )
                    tier["updated"] = True
                    tier["level"] = target
                else:
                    tier["level"] = cur_lvl or target
                    try:
                        conn.execute(
                            "UPDATE agent_status SET tier_points=?, tier_updated_at=?, updated_at=? WHERE user_id=?",
                            (int(team_paid_amount_fen), now, now, uid),
                        )
                    except Exception:
                        pass
        except Exception:
            pass

        sums = {"pending": 0, "requested": 0, "paid": 0}
        rows = conn.execute(
            """
            SELECT status, SUM(commission_fen) AS s
            FROM commission_ledger
            WHERE agent_user_id=?
            GROUP BY status
            """,
            (uid,),
        ).fetchall()
        for r in rows or []:
            k = str(r["status"] or "").strip().lower()
            if k in sums:
                sums[k] = int(r["s"] or 0)

        withdrawable_row = conn.execute(
            """
            SELECT SUM(commission_fen) AS s
            FROM commission_ledger
            WHERE agent_user_id=? AND status='pending' AND eligible_at<=?
            """,
            (uid, now),
        ).fetchone()
        withdrawable = int(withdrawable_row["s"] or 0) if withdrawable_row else 0

        acct = conn.execute(
            "SELECT channel, account_name, account_no, phone, updated_at FROM agent_payout_account WHERE user_id=?",
            (uid,),
        ).fetchone()
        acct_out = None
        if acct:
            acct_out = {
                "channel": str(acct["channel"] or ""),
                "account_name": str(acct["account_name"] or ""),
                "account_no_masked": _mask_account_no(str(acct["account_no"] or "")),
                "phone": str(acct["phone"] or ""),
                "updated_at": int(acct["updated_at"] or 0),
            }

        return {
            "ok": True,
            "now": now,
            "agent": st,
            "invites_total": int(inv_total),
            "direct_paid_orders": int(direct_paid_orders),
            "direct_paid_amount_fen": int(direct_paid_amount_fen),
            "team_paid_amount_fen": int(team_paid_amount_fen),
            "active_direct_referrals": int(active_direct),
            "team_size": int(team_size),
            "tier": tier,
            "commission_sum_fen": sums,
            "withdrawable_fen": int(withdrawable),
            "settle_delay_days": int(_agent_settle_delay_days()),
            "payout_account": acct_out,
        }


def agent_set_payout_account(
    *,
    user_id: int,
    channel: str,
    account_name: str,
    account_no: str,
    phone: str = "",
    qr_image: str = "",
) -> dict[str, Any]:
    uid = int(user_id)
    ch = str(channel or "").strip().lower()
    # MVP: unify payout channel to Alipay to keep ops simple (admin manual transfer / enterprise batch payout).
    if ch not in ("alipay",):
        raise ValueError("invalid_channel")
    name = str(account_name or "").strip()[:64]
    no = str(account_no or "").strip()[:80]
    if not name or not no:
        raise ValueError("missing_account")
    ph = str(phone or "").strip()
    ph = "".join([c for c in ph if c.isdigit()])
    if len(ph) != 11:
        raise ValueError("invalid_phone")
    img = ""
    now = int(time.time())
    with connect() as conn:
        if _is_pg():
            conn.execute(
                """
                INSERT INTO agent_payout_account(user_id, channel, account_name, account_no, phone, qr_image, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (user_id) DO UPDATE SET
                  channel=EXCLUDED.channel,
                  account_name=EXCLUDED.account_name,
                  account_no=EXCLUDED.account_no,
                  phone=EXCLUDED.phone,
                  qr_image=EXCLUDED.qr_image,
                  updated_at=EXCLUDED.updated_at
                """,
                (uid, ch, name, no, ph, img, now),
            )
        else:
            conn.execute(
                """
                INSERT INTO agent_payout_account(user_id, channel, account_name, account_no, phone, qr_image, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                  channel=excluded.channel,
                  account_name=excluded.account_name,
                  account_no=excluded.account_no,
                  phone=excluded.phone,
                  qr_image=excluded.qr_image,
                  updated_at=excluded.updated_at
                """,
                (uid, ch, name, no, ph, img, now),
            )
    return {"ok": True, "updated_at": now}


def agent_get_payout_account_full(user_id: int) -> dict[str, Any]:
    """User-only: return full payout account for editing (includes unmasked account_no)."""
    uid = int(user_id)
    with connect() as conn:
        acct = conn.execute(
            "SELECT channel, account_name, account_no, phone, updated_at FROM agent_payout_account WHERE user_id=?",
            (uid,),
        ).fetchone()
        if not acct:
            return {"ok": True, "payout_account": None}
        out = {
            "channel": str(acct["channel"] or ""),
            "account_name": str(acct["account_name"] or ""),
            "account_no": str(acct["account_no"] or ""),
            "phone": str(acct["phone"] or ""),
            "updated_at": int(acct["updated_at"] or 0),
        }
        return {"ok": True, "payout_account": out}


def agent_list_commissions(user_id: int, *, status: str = "", limit: int = 50, offset: int = 0) -> dict[str, Any]:
    uid = int(user_id)
    limit = max(1, min(int(limit or 50), 100))
    offset = max(0, int(offset or 0))
    st = str(status or "").strip().lower()
    clauses = ["agent_user_id=?"]
    params: list[Any] = [uid]
    if st:
        clauses.append("status=?")
        params.append(st)
    where = " AND ".join(clauses)
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT id, out_trade_no, level_depth, buyer_user_id, plan, amount_fen, rate, commission_fen,
                   rule_version, rate_source,
                   eligible_at, status, request_id, paid_at, paid_note, created_at
            FROM commission_ledger
            WHERE {where}
            ORDER BY id DESC
            LIMIT ? OFFSET ?
            """,
            (*params, limit, offset),
        ).fetchall()
        buyer_ids = sorted({int(r["buyer_user_id"]) for r in (rows or []) if r and r["buyer_user_id"] is not None})
        buyer_map: dict[int, dict[str, str]] = {}
        if buyer_ids:
            qmarks = ",".join(["?"] * len(buyer_ids))
            urows = conn.execute(
                f"SELECT id, phone, email FROM users WHERE id IN ({qmarks})",
                tuple(buyer_ids),
            ).fetchall()
            for u in urows or []:
                bid = int(_row_get(u, "id") or 0)
                buyer_map[bid] = {"phone": str(_row_get(u, "phone") or ""), "email": str(_row_get(u, "email") or "")}
        items = []
        for r in rows or []:
            bid = int(r["buyer_user_id"])
            bu = buyer_map.get(bid) or {}
            who = str(bu.get("phone") or "").strip() or str(bu.get("email") or "").strip()
            items.append(
                {
                    "id": int(r["id"]),
                    "out_trade_no": str(r["out_trade_no"]),
                    "level_depth": int(r["level_depth"] or 1),
                    "buyer_user_id": int(r["buyer_user_id"]),
                    "buyer_masked": _mask_identity(who) if who else "",
                    "plan": str(r["plan"]),
                    "amount_fen": int(r["amount_fen"]),
                    "rate": float(r["rate"]),
                    "commission_fen": int(r["commission_fen"]),
                    "rule_version": str(_row_get(r, "rule_version") or "v1"),
                    "rate_source": str(_row_get(r, "rate_source") or "base"),
                    "eligible_at": int(r["eligible_at"]),
                    "status": str(r["status"]),
                    "request_id": int(r["request_id"]) if r["request_id"] is not None else None,
                    "paid_at": int(r["paid_at"]) if r["paid_at"] is not None else None,
                    "paid_note": str(r["paid_note"] or ""),
                    "created_at": int(r["created_at"]),
                }
            )
        return {"ok": True, "items": items, "limit": limit, "offset": offset}


def agent_create_payout_request(user_id: int, *, amount_fen: int | None = None, note: str = "") -> dict[str, Any]:
    """
    Create a payout request:
    - locks eligible commissions (pending, eligible_at<=now) into status=requested with request_id
    - creates request row with account snapshot
    """
    uid = int(user_id)
    now = int(time.time())
    note2 = str(note or "").strip()[:200]
    with connect() as conn:
        acct = conn.execute(
            "SELECT channel, account_name, account_no, phone FROM agent_payout_account WHERE user_id=?",
            (uid,),
        ).fetchone()
        if not acct:
            raise ValueError("missing_payout_account")
        ch = str(acct["channel"] or "")
        snap = {
            "channel": ch,
            "account_name": str(acct["account_name"] or ""),
            "account_no_masked": _mask_account_no(str(acct["account_no"] or "")),
            "phone": str(acct["phone"] or ""),
        }

        rsum = conn.execute(
            "SELECT SUM(commission_fen) AS s FROM commission_ledger WHERE agent_user_id=? AND status='pending' AND eligible_at<=?",
            (uid, now),
        ).fetchone()
        avail = int(rsum["s"] or 0) if rsum else 0
        if avail <= 0:
            raise ValueError("no_withdrawable")
        req_amount = avail if amount_fen is None or int(amount_fen) <= 0 else int(amount_fen)
        if req_amount > avail:
            req_amount = avail

        if _is_pg():
            row = conn.execute(
                """
                INSERT INTO agent_payout_requests(user_id, amount_fen, channel, account_snapshot, status, note, transfer_ref, created_at, approved_at, paid_at, updated_at)
                VALUES (?, ?, ?, ?, 'pending', ?, '', ?, NULL, NULL, ?)
                RETURNING id
                """,
                (uid, int(req_amount), ch, json.dumps(snap, ensure_ascii=False, separators=(",", ":")), note2, now, now),
            ).fetchone()
            rid = int(row["id"])
        else:
            cur = conn.execute(
                """
                INSERT INTO agent_payout_requests(user_id, amount_fen, channel, account_snapshot, status, note, transfer_ref, created_at, approved_at, paid_at, updated_at)
                VALUES (?, ?, ?, ?, 'pending', ?, '', ?, NULL, NULL, ?)
                """,
                (uid, int(req_amount), ch, json.dumps(snap, ensure_ascii=False, separators=(",", ":")), note2, now, now),
            )
            rid = int(cur.lastrowid)

        rows = conn.execute(
            """
            SELECT id, commission_fen FROM commission_ledger
            WHERE agent_user_id=? AND status='pending' AND eligible_at<=?
            ORDER BY id DESC
            """,
            (uid, now),
        ).fetchall()
        left = int(req_amount)
        locked_ids: list[int] = []
        for r in rows or []:
            if left <= 0:
                break
            cf = int(r["commission_fen"] or 0)
            locked_ids.append(int(r["id"]))
            left -= cf
        if not locked_ids:
            raise ValueError("lock_failed")
        qmarks = ",".join(["?"] * len(locked_ids))
        conn.execute(
            f"UPDATE commission_ledger SET status='requested', request_id=?, updated_at=? WHERE id IN ({qmarks})",
            (rid, now, *locked_ids),
        )
        return {"ok": True, "request_id": rid, "amount_fen": int(req_amount), "locked_count": len(locked_ids)}


def admin_list_payout_requests(*, status: str = "", user_id: int = 0, limit: int = 50, offset: int = 0) -> dict[str, Any]:
    st = str(status or "").strip().lower()
    uid = int(user_id or 0)
    limit = max(1, min(int(limit or 50), 200))
    offset = max(0, int(offset or 0))
    clauses: list[str] = []
    params: list[Any] = []
    if st:
        clauses.append("status=?")
        params.append(st)
    if uid > 0:
        clauses.append("user_id=?")
        params.append(uid)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT id, user_id, amount_fen, channel, status, note, transfer_ref,
                   exported_at, exported_note,
                   created_at, approved_at, paid_at, updated_at, account_snapshot
            FROM agent_payout_requests
            {where}
            ORDER BY id DESC
            LIMIT ? OFFSET ?
            """,
            (*params, limit, offset),
        ).fetchall()
        items = []
        for r in rows or []:
            items.append(
                {
                    "id": int(r["id"]),
                    "user_id": int(r["user_id"]),
                    "amount_fen": int(r["amount_fen"]),
                    "channel": str(r["channel"]),
                    "status": str(r["status"]),
                    "note": str(r["note"] or ""),
                    "transfer_ref": str(r["transfer_ref"] or ""),
                    "exported_at": int(r["exported_at"]) if r["exported_at"] is not None else None,
                    "exported_note": str(r["exported_note"] or ""),
                    "created_at": int(r["created_at"]),
                    "approved_at": int(r["approved_at"]) if r["approved_at"] is not None else None,
                    "paid_at": int(r["paid_at"]) if r["paid_at"] is not None else None,
                    "updated_at": int(r["updated_at"]),
                    "account_snapshot": str(r["account_snapshot"] or ""),
                }
            )
        return {"ok": True, "items": items, "limit": limit, "offset": offset}


def admin_payout_request_set_status(req_id: int, *, status: str, note: str = "", transfer_ref: str = "") -> dict[str, Any]:
    rid = int(req_id)
    if rid <= 0:
        raise ValueError("invalid_request_id")
    st = str(status or "").strip().lower()
    if st not in ("approved", "paid", "rejected"):
        raise ValueError("invalid_status")
    now = int(time.time())
    note2 = str(note or "").strip()[:200]
    tref = str(transfer_ref or "").strip()[:120]
    with connect() as conn:
        row = conn.execute("SELECT id, status FROM agent_payout_requests WHERE id=?", (rid,)).fetchone()
        if not row:
            raise ValueError("request_not_found")
        cur = str(row["status"] or "").strip().lower()
        if cur in ("paid", "rejected") and st != cur:
            raise ValueError("request_already_final")
        conn.execute(
            """
            UPDATE agent_payout_requests
            SET status=?, note=?, transfer_ref=?,
                approved_at=CASE WHEN approved_at IS NULL AND ?='approved' THEN ? ELSE approved_at END,
                paid_at=CASE WHEN paid_at IS NULL AND ?='paid' THEN ? ELSE paid_at END,
                updated_at=?
            WHERE id=?
            """,
            (st, note2, tref, st, now, st, now, now, rid),
        )
        if st == "paid":
            conn.execute(
                """
                UPDATE commission_ledger
                SET status='paid', paid_at=?, paid_note=?, updated_at=?
                WHERE request_id=? AND status='requested'
                """,
                (now, f"payout:{rid}" if not note2 else note2, now, rid),
            )
        if st == "rejected":
            conn.execute(
                """
                UPDATE commission_ledger
                SET status='pending', request_id=NULL, updated_at=?
                WHERE request_id=? AND status='requested'
                """,
                (now, rid),
            )
        return {"ok": True, "id": rid, "status": st, "updated_at": now}


def _mask_account_no(v: str) -> str:
    s = str(v or "").strip()
    if not s:
        return ""
    if len(s) <= 6:
        return s[0:1] + "***" + s[-1:]
    return s[0:2] + "***" + s[-4:]


def agent_commission_overview(user_id: int) -> dict[str, Any]:
    """User-facing overview for agent/commissions/payout."""
    now = int(time.time())
    uid = int(user_id)
    with connect() as conn:
        st = agent_get_status(uid)
        inv_total = 0
        try:
            r = conn.execute("SELECT COUNT(1) AS c FROM invite_relations WHERE inviter_id=?", (uid,)).fetchone()
            inv_total = int(r["c"] or 0) if r else 0
        except Exception:
            inv_total = 0

        # Metrics for "直推/团队/成长等级" (used in UI cards).
        win_days = _agent_tier_window_days()
        since_ts = int(now - win_days * 86400)
        direct_paid_orders = 0
        direct_paid_amount_fen = 0
        team_paid_amount_fen = 0
        active_direct = 0
        team_size = 0
        try:
            r = conn.execute(
                """
                SELECT COUNT(1) AS c, COALESCE(SUM(o.amount_fen),0) AS s
                FROM pay_orders o
                JOIN invite_relations ir ON ir.invitee_id = o.user_id
                WHERE o.status='paid' AND o.paid_at>=? AND ir.inviter_id=?
                """,
                (since_ts, uid),
            ).fetchone()
            direct_paid_orders = int(_row_get(r, "c") or 0) if r else 0
            direct_paid_amount_fen = int(_row_get(r, "s") or 0) if r else 0
        except Exception:
            pass
        try:
            r = conn.execute(
                """
                SELECT COUNT(1) AS c
                FROM (
                  SELECT o.user_id
                  FROM pay_orders o
                  JOIN invite_relations ir ON ir.invitee_id = o.user_id
                  WHERE o.status='paid' AND o.paid_at>=? AND ir.inviter_id=?
                  GROUP BY o.user_id
                ) t
                """,
                (since_ts, uid),
            ).fetchone()
            active_direct = int(_row_get(r, "c") or 0) if r else 0
        except Exception:
            pass
        try:
            r = conn.execute(
                """
                SELECT COALESCE(SUM(o.amount_fen),0) AS s
                FROM pay_orders o
                JOIN invite_relations ir ON ir.invitee_id = o.user_id
                WHERE o.status='paid' AND o.paid_at>=?
                  AND (ir.inviter_l1_id=? OR ir.inviter_l2_id=? OR ir.inviter_l3_id=?)
                """,
                (since_ts, uid, uid, uid),
            ).fetchone()
            team_paid_amount_fen = int(_row_get(r, "s") or 0) if r else 0
        except Exception:
            pass
        try:
            r = conn.execute(
                """
                SELECT COUNT(1) AS c
                FROM invite_relations
                WHERE inviter_l1_id=? OR inviter_l2_id=? OR inviter_l3_id=?
                """,
                (uid, uid, uid),
            ).fetchone()
            team_size = int(_row_get(r, "c") or 0) if r else 0
        except Exception:
            pass

        # Tier evaluation (best-effort; can be disabled by config).
        tier = {"level": (st or {}).get("level") if isinstance(st, dict) else None, "locked": False, "updated": False}
        try:
            if _agent_tier_enabled():
                thr = _agent_tier_thresholds()
                target = "starter"
                if team_paid_amount_fen >= int(thr["pro_team_gmv_fen"]) and active_direct >= int(thr["pro_active_direct"]):
                    target = "pro"
                elif team_paid_amount_fen >= int(thr["growth_team_gmv_fen"]) or active_direct >= int(thr["growth_active_direct"]):
                    target = "growth"
                row_lock = conn.execute(
                    "SELECT tier_locked, level FROM agent_status WHERE user_id=?",
                    (uid,),
                ).fetchone()
                locked = bool(int(_row_get(row_lock, "tier_locked") or 0) == 1) if row_lock else False
                cur_lvl = (
                    str(_row_get(row_lock, "level") or (st or {}).get("level") or "").strip().lower()
                    if row_lock
                    else str((st or {}).get("level") or "").strip().lower()
                )
                if cur_lvl in ("normal", ""):
                    cur_lvl = "starter"
                if cur_lvl == "senior":
                    cur_lvl = "growth"
                if cur_lvl == "gold":
                    cur_lvl = "pro"
                tier["locked"] = locked
                tier["target"] = target
                tier["window_days"] = win_days
                tier["team_gmv_fen"] = int(team_paid_amount_fen)
                tier["active_direct"] = int(active_direct)
                tier["level"] = cur_lvl or target
        except Exception:
            pass

        sums = {"pending": 0, "requested": 0, "paid": 0}
        rows = conn.execute(
            """
            SELECT status, SUM(commission_fen) AS s
            FROM commission_ledger
            WHERE agent_user_id=?
            GROUP BY status
            """,
            (uid,),
        ).fetchall()
        for r in rows or []:
            k = str(r["status"] or "").strip().lower()
            if k in sums:
                sums[k] = int(r["s"] or 0)

        withdrawable_row = conn.execute(
            """
            SELECT SUM(commission_fen) AS s
            FROM commission_ledger
            WHERE agent_user_id=? AND status='pending' AND eligible_at<=?
            """,
            (uid, now),
        ).fetchone()
        withdrawable = int(withdrawable_row["s"] or 0) if withdrawable_row else 0

        acct = conn.execute(
            "SELECT channel, account_name, account_no, phone, updated_at FROM agent_payout_account WHERE user_id=?",
            (uid,),
        ).fetchone()
        acct_out = None
        if acct:
            acct_out = {
                "channel": str(acct["channel"] or ""),
                "account_name": str(acct["account_name"] or ""),
                "account_no_masked": _mask_account_no(str(acct["account_no"] or "")),
                "phone": str(acct["phone"] or ""),
                "updated_at": int(acct["updated_at"] or 0),
            }

        return {
            "ok": True,
            "now": now,
            "agent": st,
            "invites_total": int(inv_total),
            "direct_paid_orders": int(direct_paid_orders),
            "direct_paid_amount_fen": int(direct_paid_amount_fen),
            "team_paid_amount_fen": int(team_paid_amount_fen),
            "active_direct_referrals": int(active_direct),
            "team_size": int(team_size),
            "tier": tier,
            "commission_sum_fen": sums,
            "withdrawable_fen": int(withdrawable),
            "payout_account": acct_out,
        }


def agent_set_payout_account(
    *,
    user_id: int,
    channel: str,
    account_name: str,
    account_no: str,
    phone: str = "",
    qr_image: str = "",
) -> dict[str, Any]:
    uid = int(user_id)
    ch = str(channel or "").strip().lower()
    # MVP: unify payout channel to Alipay to keep ops simple (admin manual transfer / enterprise batch payout).
    if ch not in ("alipay",):
        raise ValueError("invalid_channel")
    name = str(account_name or "").strip()[:64]
    no = str(account_no or "").strip()[:80]
    if not name or not no:
        raise ValueError("missing_account")
    ph = str(phone or "").strip()
    ph = "".join([c for c in ph if c.isdigit()])
    if len(ph) != 11:
        raise ValueError("invalid_phone")
    img = ""
    now = int(time.time())
    with connect() as conn:
        if _is_pg():
            conn.execute(
                """
                INSERT INTO agent_payout_account(user_id, channel, account_name, account_no, phone, qr_image, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (user_id) DO UPDATE SET
                  channel=EXCLUDED.channel,
                  account_name=EXCLUDED.account_name,
                  account_no=EXCLUDED.account_no,
                  phone=EXCLUDED.phone,
                  qr_image=EXCLUDED.qr_image,
                  updated_at=EXCLUDED.updated_at
                """,
                (uid, ch, name, no, ph, img, now),
            )
        else:
            conn.execute(
                """
                INSERT INTO agent_payout_account(user_id, channel, account_name, account_no, phone, qr_image, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                  channel=excluded.channel,
                  account_name=excluded.account_name,
                  account_no=excluded.account_no,
                  phone=excluded.phone,
                  qr_image=excluded.qr_image,
                  updated_at=excluded.updated_at
                """,
                (uid, ch, name, no, ph, img, now),
            )
    return {"ok": True, "updated_at": now}


def agent_get_payout_account_full(user_id: int) -> dict[str, Any]:
    """User-only: return full payout account for editing (includes unmasked account_no)."""
    uid = int(user_id)
    with connect() as conn:
        acct = conn.execute(
            "SELECT channel, account_name, account_no, phone, updated_at FROM agent_payout_account WHERE user_id=?",
            (uid,),
        ).fetchone()
        if not acct:
            return {"ok": True, "payout_account": None}
        out = {
            "channel": str(acct["channel"] or ""),
            "account_name": str(acct["account_name"] or ""),
            "account_no": str(acct["account_no"] or ""),
            "phone": str(acct["phone"] or ""),
            "updated_at": int(acct["updated_at"] or 0),
        }
        return {"ok": True, "payout_account": out}


def agent_list_commissions(user_id: int, *, status: str = "", limit: int = 50, offset: int = 0) -> dict[str, Any]:
    uid = int(user_id)
    limit = max(1, min(int(limit or 50), 100))
    offset = max(0, int(offset or 0))
    st = str(status or "").strip().lower()
    clauses = ["agent_user_id=?"]
    params: list[Any] = [uid]
    if st:
        clauses.append("status=?")
        params.append(st)
    where = " AND ".join(clauses)
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT id, out_trade_no, level_depth, buyer_user_id, plan, amount_fen, rate, commission_fen,
                   rule_version, rate_source,
                   eligible_at, status, request_id, paid_at, paid_note, created_at
            FROM commission_ledger
            WHERE {where}
            ORDER BY id DESC
            LIMIT ? OFFSET ?
            """,
            (*params, limit, offset),
        ).fetchall()
        buyer_ids = sorted({int(r["buyer_user_id"]) for r in (rows or []) if r and r["buyer_user_id"] is not None})
        buyer_map: dict[int, dict[str, str]] = {}
        if buyer_ids:
            qmarks = ",".join(["?"] * len(buyer_ids))
            urows = conn.execute(
                f"SELECT id, phone, email FROM users WHERE id IN ({qmarks})",
                tuple(buyer_ids),
            ).fetchall()
            for u in urows or []:
                bid = int(_row_get(u, "id") or 0)
                buyer_map[bid] = {"phone": str(_row_get(u, "phone") or ""), "email": str(_row_get(u, "email") or "")}
        items = []
        for r in rows or []:
            bid = int(r["buyer_user_id"])
            bu = buyer_map.get(bid) or {}
            who = str(bu.get("phone") or "").strip() or str(bu.get("email") or "").strip()
            items.append(
                {
                    "id": int(r["id"]),
                    "out_trade_no": str(r["out_trade_no"]),
                    "level_depth": int(r["level_depth"] or 1),
                    "buyer_user_id": int(r["buyer_user_id"]),
                    "buyer_masked": _mask_identity(who) if who else "",
                    "plan": str(r["plan"]),
                    "amount_fen": int(r["amount_fen"]),
                    "rate": float(r["rate"]),
                    "commission_fen": int(r["commission_fen"]),
                    "rule_version": str(_row_get(r, "rule_version") or "v1"),
                    "rate_source": str(_row_get(r, "rate_source") or "base"),
                    "eligible_at": int(r["eligible_at"]),
                    "status": str(r["status"]),
                    "request_id": int(r["request_id"]) if r["request_id"] is not None else None,
                    "paid_at": int(r["paid_at"]) if r["paid_at"] is not None else None,
                    "paid_note": str(r["paid_note"] or ""),
                    "created_at": int(r["created_at"]),
                }
            )
        return {"ok": True, "items": items, "limit": limit, "offset": offset}


def agent_create_payout_request(user_id: int, *, amount_fen: int | None = None, note: str = "") -> dict[str, Any]:
    """
    Create a payout request:
    - locks eligible commissions (pending, eligible_at<=now) into status=requested with request_id
    - creates request row with account snapshot
    """
    uid = int(user_id)
    now = int(time.time())
    note2 = str(note or "").strip()[:200]
    with connect() as conn:
        acct = conn.execute(
            "SELECT channel, account_name, account_no, phone FROM agent_payout_account WHERE user_id=?",
            (uid,),
        ).fetchone()
        if not acct:
            raise ValueError("missing_payout_account")
        ch = str(acct["channel"] or "")
        snap = {
            "channel": ch,
            "account_name": str(acct["account_name"] or ""),
            "account_no_masked": _mask_account_no(str(acct["account_no"] or "")),
            "phone": str(acct["phone"] or ""),
        }

        # sum eligible pending commissions
        rsum = conn.execute(
            "SELECT SUM(commission_fen) AS s FROM commission_ledger WHERE agent_user_id=? AND status='pending' AND eligible_at<=?",
            (uid, now),
        ).fetchone()
        avail = int(rsum["s"] or 0) if rsum else 0
        if avail <= 0:
            raise ValueError("no_withdrawable")
        req_amount = avail if amount_fen is None or int(amount_fen) <= 0 else int(amount_fen)
        if req_amount > avail:
            req_amount = avail

        # create request
        if _is_pg():
            row = conn.execute(
                """
                INSERT INTO agent_payout_requests(user_id, amount_fen, channel, account_snapshot, status, note, transfer_ref, created_at, approved_at, paid_at, updated_at)
                VALUES (?, ?, ?, ?, 'pending', ?, '', ?, NULL, NULL, ?)
                RETURNING id
                """,
                (uid, int(req_amount), ch, json.dumps(snap, ensure_ascii=False, separators=(",", ":")), note2, now, now),
            ).fetchone()
            rid = int(row["id"])
        else:
            cur = conn.execute(
                """
                INSERT INTO agent_payout_requests(user_id, amount_fen, channel, account_snapshot, status, note, transfer_ref, created_at, approved_at, paid_at, updated_at)
                VALUES (?, ?, ?, ?, 'pending', ?, '', ?, NULL, NULL, ?)
                """,
                (uid, int(req_amount), ch, json.dumps(snap, ensure_ascii=False, separators=(",", ":")), note2, now, now),
            )
            rid = int(cur.lastrowid)

        # lock eligible commissions into this request (cap by amount_fen, newest first is ok for MVP)
        rows = conn.execute(
            """
            SELECT id, commission_fen FROM commission_ledger
            WHERE agent_user_id=? AND status='pending' AND eligible_at<=?
            ORDER BY id DESC
            """,
            (uid, now),
        ).fetchall()
        left = int(req_amount)
        locked_ids: list[int] = []
        for r in rows or []:
            if left <= 0:
                break
            cf = int(r["commission_fen"] or 0)
            locked_ids.append(int(r["id"]))
            left -= cf
        if not locked_ids:
            raise ValueError("lock_failed")
        # update locked rows
        qmarks = ",".join(["?"] * len(locked_ids))
        conn.execute(
            f"UPDATE commission_ledger SET status='requested', request_id=?, updated_at=? WHERE id IN ({qmarks})",
            (rid, now, *locked_ids),
        )
        return {"ok": True, "request_id": rid, "amount_fen": int(req_amount), "locked_count": len(locked_ids)}


def admin_list_payout_requests(*, status: str = "", user_id: int = 0, limit: int = 50, offset: int = 0) -> dict[str, Any]:
    st = str(status or "").strip().lower()
    uid = int(user_id or 0)
    limit = max(1, min(int(limit or 50), 200))
    offset = max(0, int(offset or 0))
    clauses: list[str] = []
    params: list[Any] = []
    if st:
        clauses.append("status=?")
        params.append(st)
    if uid > 0:
        clauses.append("user_id=?")
        params.append(uid)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT id, user_id, amount_fen, channel, status, note, transfer_ref,
                   exported_at, exported_note,
                   created_at, approved_at, paid_at, updated_at, account_snapshot
            FROM agent_payout_requests
            {where}
            ORDER BY id DESC
            LIMIT ? OFFSET ?
            """,
            (*params, limit, offset),
        ).fetchall()
        items = []
        for r in rows or []:
            items.append(
                {
                    "id": int(r["id"]),
                    "user_id": int(r["user_id"]),
                    "amount_fen": int(r["amount_fen"]),
                    "channel": str(r["channel"]),
                    "status": str(r["status"]),
                    "note": str(r["note"] or ""),
                    "transfer_ref": str(r["transfer_ref"] or ""),
                    "exported_at": int(r["exported_at"]) if r["exported_at"] is not None else None,
                    "exported_note": str(r["exported_note"] or ""),
                    "created_at": int(r["created_at"]),
                    "approved_at": int(r["approved_at"]) if r["approved_at"] is not None else None,
                    "paid_at": int(r["paid_at"]) if r["paid_at"] is not None else None,
                    "updated_at": int(r["updated_at"]),
                    "account_snapshot": str(r["account_snapshot"] or ""),
                }
            )
        return {"ok": True, "items": items, "limit": limit, "offset": offset}


def admin_payout_request_set_status(req_id: int, *, status: str, note: str = "", transfer_ref: str = "") -> dict[str, Any]:
    rid = int(req_id)
    if rid <= 0:
        raise ValueError("invalid_request_id")
    st = str(status or "").strip().lower()
    if st not in ("approved", "paid", "rejected"):
        raise ValueError("invalid_status")
    now = int(time.time())
    note2 = str(note or "").strip()[:200]
    tref = str(transfer_ref or "").strip()[:120]
    with connect() as conn:
        row = conn.execute("SELECT id, status FROM agent_payout_requests WHERE id=?", (rid,)).fetchone()
        if not row:
            raise ValueError("request_not_found")
        cur = str(row["status"] or "").strip().lower()
        if cur in ("paid", "rejected") and st != cur:
            raise ValueError("request_already_final")
        approved_at = now if st == "approved" else None
        paid_at = now if st == "paid" else None
        # keep existing timestamps if already set
        old = conn.execute("SELECT approved_at, paid_at FROM agent_payout_requests WHERE id=?", (rid,)).fetchone()
        if old:
            if old["approved_at"] is not None:
                approved_at = int(old["approved_at"])
            if old["paid_at"] is not None:
                paid_at = int(old["paid_at"])
        conn.execute(
            """
            UPDATE agent_payout_requests
            SET status=?, note=?, transfer_ref=?, approved_at=COALESCE(approved_at, ?), paid_at=COALESCE(paid_at, ?), updated_at=?
            WHERE id=?
            """,
            (st, note2, tref, approved_at, paid_at, now, rid),
        )
        if st == "paid":
            # mark locked commissions as paid
            conn.execute(
                """
                UPDATE commission_ledger
                SET status='paid', paid_at=?, paid_note=?, updated_at=?
                WHERE request_id=? AND status='requested'
                """,
                (now, f"payout:{rid}" if not note2 else note2, now, rid),
            )
        if st == "rejected":
            # unlock commissions back to pending
            conn.execute(
                """
                UPDATE commission_ledger
                SET status='pending', request_id=NULL, updated_at=?
                WHERE request_id=? AND status='requested'
                """,
                (now, rid),
            )
        return {"ok": True, "id": rid, "status": st, "updated_at": now}


def invite_summary_for_user(inviter_id: int) -> dict[str, int]:
    inviter_id = int(inviter_id)
    with connect() as conn:
        total_row = conn.execute(
            "SELECT COUNT(1) AS c FROM invite_relations WHERE inviter_id=?",
            (inviter_id,),
        ).fetchone()
        total = int(total_row["c"] or 0) if total_row else 0

        activated_row = conn.execute(
            """
            SELECT COUNT(1) AS c
            FROM invite_relations r
            WHERE r.inviter_id=?
              AND EXISTS (
                SELECT 1 FROM quota_ledger q
                WHERE q.user_id=r.invitee_id AND q.result='ok'
                LIMIT 1
              )
            """,
            (inviter_id,),
        ).fetchone()
        activated = int(activated_row["c"] or 0) if activated_row else 0

        rewarded_row = conn.execute(
            """
            SELECT COUNT(DISTINCT invitee_id) AS c
            FROM reward_ledger
            WHERE inviter_id=?
              AND reward_type='invite_first_query_inviter'
            """,
            (inviter_id,),
        ).fetchone()
        rewarded = int(rewarded_row["c"] or 0) if rewarded_row else 0

    return {"total": total, "activated": activated, "rewarded": rewarded}


def invite_list_for_user(inviter_id: int, limit: int = 50) -> list[dict[str, Any]]:
    inviter_id = int(inviter_id)
    limit = max(1, min(int(limit or 50), 200))
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT
              r.invitee_id,
              r.created_at,
              u.email AS invitee_email,
              u.phone AS invitee_phone,
              EXISTS(SELECT 1 FROM quota_ledger q WHERE q.user_id=r.invitee_id AND q.result='ok' LIMIT 1) AS activated,
              EXISTS(SELECT 1 FROM reward_ledger w WHERE w.inviter_id=r.inviter_id AND w.invitee_id=r.invitee_id AND w.reward_type='invite_first_query_inviter' LIMIT 1) AS rewarded,
              (
                SELECT COALESCE(SUM(w2.amount), 0)
                FROM reward_ledger w2
                WHERE w2.inviter_id=r.inviter_id
                  AND w2.invitee_id=r.invitee_id
                  AND w2.reward_type IN ('invite_first_query_inviter','invite_first_query_inviter_daily')
              ) AS reward_amount
            FROM invite_relations r
            LEFT JOIN users u ON u.id=r.invitee_id
            WHERE r.inviter_id=?
            ORDER BY r.created_at DESC
            LIMIT ?
            """,
            (inviter_id, limit),
        ).fetchall()

    items: list[dict[str, Any]] = []
    for r in rows:
        email = str(r["invitee_email"] or "")
        phone = str(r["invitee_phone"] or "")
        def mask_phone(p: str) -> str:
            p = str(p or "").strip()
            if len(p) >= 11 and p.isdigit():
                return p[:3] + "****" + p[-4:]
            if len(p) >= 7 and p.isdigit():
                return p[:3] + "****" + p[-2:]
            return p[:2] + "…" + p[-2:] if len(p) > 6 else p

        def mask_email(e: str) -> str:
            e = str(e or "").strip()
            if "@" not in e:
                return e[:2] + "…" + e[-2:] if len(e) > 6 else e
            name, domain = e.split("@", 1)
            name = name.strip()
            domain = domain.strip()
            if len(name) <= 1:
                return name + "…@" + domain
            if len(name) == 2:
                return name[0] + "…@" + domain
            return name[:2] + "…" + name[-1:] + "@" + domain

        phone_m = mask_phone(phone) if phone else ""
        email_m = mask_email(email) if email else ""
        invitee = phone_m or email_m or f"user#{int(r['invitee_id'])}"
        items.append(
            {
                "invitee_id": int(r["invitee_id"]),
                "invitee": invitee,
                "invitee_phone_masked": phone_m,
                "invitee_email_masked": email_m,
                "created_at": int(r["created_at"]),
                "activated": bool(int(r["activated"] or 0)),
                "rewarded": bool(int(r["rewarded"] or 0)),
                "reward_amount": int(r["reward_amount"] or 0),
            }
        )
    return items


def admin_invite_tree(
    root_user_id: int,
    *,
    depth: int = 2,
    limit: int = 200,
) -> dict[str, Any]:
    """
    Admin: build invite relationship tree (BFS) up to depth.
    Returns nodes + edges; per-node includes light self stats for quick ops.
    """
    root_user_id = int(root_user_id)
    depth = max(1, min(int(depth or 2), 5))
    limit = max(1, min(int(limit or 200), 2000))
    now = int(time.time())

    with connect() as conn:
        u0 = conn.execute("SELECT id FROM users WHERE id=?", (root_user_id,)).fetchone()
        if not u0:
            raise ValueError("user not found")

        edges: list[dict[str, int]] = []
        nodes_set: set[int] = set([root_user_id])
        frontier: list[int] = [root_user_id]

        for _d in range(depth):
            if not frontier or len(nodes_set) >= limit:
                break
            ph = ",".join(["?"] * len(frontier))
            rows = conn.execute(
                f"""
                SELECT inviter_id, invitee_id
                FROM invite_relations
                WHERE inviter_id IN ({ph})
                ORDER BY created_at ASC
                """,
                tuple(frontier),
            ).fetchall()
            nxt: list[int] = []
            for r in rows:
                inv = int(_row_get(r, "inviter_id") or 0)
                ie = int(_row_get(r, "invitee_id") or 0)
                if not inv or not ie:
                    continue
                edges.append({"inviter_id": inv, "invitee_id": ie})
                if ie not in nodes_set and len(nodes_set) < limit:
                    nodes_set.add(ie)
                    nxt.append(ie)
            frontier = nxt

        node_ids = sorted(list(nodes_set))

        # Fetch user basics (privacy: mask phone/email).
        ph2 = ",".join(["?"] * len(node_ids))
        user_rows = conn.execute(
            f"SELECT id, phone, email, created_at FROM users WHERE id IN ({ph2})",
            tuple(node_ids),
        ).fetchall()
        user_map: dict[int, dict[str, Any]] = {}
        for r in user_rows:
            uid = int(_row_get(r, "id") or 0)
            phone = str(_row_get(r, "phone") or "")
            email = str(_row_get(r, "email") or "")

            def mask_phone(p: str) -> str:
                p = str(p or "").strip()
                if len(p) >= 11 and p.isdigit():
                    return p[:3] + "****" + p[-4:]
                return p[:2] + "…" + p[-2:] if len(p) > 6 else p

            def mask_email(e: str) -> str:
                e = str(e or "").strip()
                if "@" not in e:
                    return e[:2] + "…" + e[-2:] if len(e) > 6 else e
                name, domain = e.split("@", 1)
                name = name.strip()
                domain = domain.strip()
                if len(name) <= 1:
                    return name + "…@" + domain
                if len(name) == 2:
                    return name[0] + "…@" + domain
                return name[:2] + "…" + name[-1:] + "@" + domain

            user_map[uid] = {
                "id": uid,
                "phone_masked": mask_phone(phone) if phone else "",
                "email_masked": mask_email(email) if email else "",
                "created_at": int(_row_get(r, "created_at") or 0),
            }

        # Direct invite counts
        direct_counts: dict[int, int] = {}
        if node_ids:
            rows = conn.execute(
                f"SELECT inviter_id, COUNT(1) AS c FROM invite_relations WHERE inviter_id IN ({ph2}) GROUP BY inviter_id",
                tuple(node_ids),
            ).fetchall()
            for r in rows:
                direct_counts[int(_row_get(r, "inviter_id") or 0)] = int(_row_get(r, "c") or 0)

        # Self order stats (paid)
        paid_counts: dict[int, int] = {}
        paid_amounts: dict[int, int] = {}
        year_counts: dict[int, int] = {}
        try:
            rows = conn.execute(
                f"""
                SELECT user_id, COUNT(1) AS c, COALESCE(SUM(amount_fen),0) AS s,
                       COALESCE(SUM(CASE WHEN plan='vip_year_999' THEN 1 ELSE 0 END),0) AS y
                FROM pay_orders
                WHERE status='paid' AND user_id IN ({ph2})
                GROUP BY user_id
                """,
                tuple(node_ids),
            ).fetchall()
            for r in rows:
                uid = int(_row_get(r, "user_id") or 0)
                paid_counts[uid] = int(_row_get(r, "c") or 0)
                paid_amounts[uid] = int(_row_get(r, "s") or 0)
                year_counts[uid] = int(_row_get(r, "y") or 0)
        except Exception:
            pass

        # Self commission stats (as agent)
        comm_pending: dict[int, int] = {}
        comm_paid: dict[int, int] = {}
        try:
            rows = conn.execute(
                f"""
                SELECT agent_user_id,
                       COALESCE(SUM(CASE WHEN status='pending' THEN commission_fen ELSE 0 END),0) AS pend,
                       COALESCE(SUM(CASE WHEN status='paid' THEN commission_fen ELSE 0 END),0) AS paid
                FROM commission_ledger
                WHERE agent_user_id IN ({ph2})
                GROUP BY agent_user_id
                """,
                tuple(node_ids),
            ).fetchall()
            for r in rows:
                uid = int(_row_get(r, "agent_user_id") or 0)
                comm_pending[uid] = int(_row_get(r, "pend") or 0)
                comm_paid[uid] = int(_row_get(r, "paid") or 0)
        except Exception:
            pass

        # Activated flag (self): has any ok quota_ledger
        activated_self: set[int] = set()
        try:
            rows = conn.execute(
                f"""
                SELECT DISTINCT user_id
                FROM quota_ledger
                WHERE result='ok' AND user_id IN ({ph2})
                """,
                tuple(node_ids),
            ).fetchall()
            for r in rows:
                activated_self.add(int(_row_get(r, "user_id") or 0))
        except Exception:
            activated_self = set()

    nodes: list[dict[str, Any]] = []
    for uid in node_ids:
        u = user_map.get(uid) or {"id": uid, "phone_masked": "", "email_masked": "", "created_at": 0}
        nodes.append(
            {
                "user_id": uid,
                "phone_masked": u.get("phone_masked") or "",
                "email_masked": u.get("email_masked") or "",
                "created_at": int(u.get("created_at") or 0),
                "direct_invites": int(direct_counts.get(uid, 0)),
                "activated": bool(uid in activated_self),
                "paid_orders": int(paid_counts.get(uid, 0)),
                "paid_amount_fen": int(paid_amounts.get(uid, 0)),
                "vip_year_paid_orders": int(year_counts.get(uid, 0)),
                "commission_pending_fen": int(comm_pending.get(uid, 0)),
                "commission_paid_fen": int(comm_paid.get(uid, 0)),
            }
        )

    return {
        "ok": True,
        "root_user_id": root_user_id,
        "depth": depth,
        "limit": limit,
        "generated_at": now,
        "nodes": nodes,
        "edges": edges,
    }


def admin_agent_rank(
    *,
    metric: str = "direct_invites",
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """
    Admin: rank inviters/agents by direct invite and related KPIs (depth=1).
    Metrics:
    - direct_invites
    - activated_direct
    - paid_amount_direct_fen
    - paid_orders_direct
    - commission_pending_fen
    - commission_paid_fen
    """
    metric = str(metric or "direct_invites").strip().lower()
    limit = max(1, min(int(limit or 50), 200))
    offset = max(0, int(offset or 0))

    order_map = {
        "direct_invites": "direct_invites DESC, inviter_id DESC",
        "activated_direct": "activated_direct DESC, direct_invites DESC, inviter_id DESC",
        "paid_amount_direct_fen": "paid_amount_direct_fen DESC, direct_invites DESC, inviter_id DESC",
        "paid_orders_direct": "paid_orders_direct DESC, direct_invites DESC, inviter_id DESC",
        "commission_pending_fen": "commission_pending_fen DESC, direct_invites DESC, inviter_id DESC",
        "commission_paid_fen": "commission_paid_fen DESC, direct_invites DESC, inviter_id DESC",
    }
    order_by = order_map.get(metric, order_map["direct_invites"])

    with connect() as conn:
        rows = conn.execute(
            f"""
            WITH direct AS (
              SELECT inviter_id, COUNT(1) AS direct_invites
              FROM invite_relations
              GROUP BY inviter_id
            ),
            activated AS (
              SELECT r.inviter_id, COUNT(DISTINCT r.invitee_id) AS activated_direct
              FROM invite_relations r
              WHERE EXISTS(
                SELECT 1 FROM quota_ledger q
                WHERE q.user_id=r.invitee_id AND q.result='ok'
                LIMIT 1
              )
              GROUP BY r.inviter_id
            ),
            paid_direct AS (
              SELECT referrer_user_id AS inviter_id,
                     COUNT(1) AS paid_orders_direct,
                     COALESCE(SUM(amount_fen),0) AS paid_amount_direct_fen
              FROM pay_orders
              WHERE status='paid' AND referrer_user_id IS NOT NULL
              GROUP BY referrer_user_id
            ),
            comm AS (
              SELECT agent_user_id AS inviter_id,
                     COALESCE(SUM(CASE WHEN status='pending' THEN commission_fen ELSE 0 END),0) AS commission_pending_fen,
                     COALESCE(SUM(CASE WHEN status='paid' THEN commission_fen ELSE 0 END),0) AS commission_paid_fen
              FROM commission_ledger
              GROUP BY agent_user_id
            )
            SELECT
              d.inviter_id AS inviter_id,
              d.direct_invites AS direct_invites,
              COALESCE(a.activated_direct,0) AS activated_direct,
              COALESCE(p.paid_orders_direct,0) AS paid_orders_direct,
              COALESCE(p.paid_amount_direct_fen,0) AS paid_amount_direct_fen,
              COALESCE(c.commission_pending_fen,0) AS commission_pending_fen,
              COALESCE(c.commission_paid_fen,0) AS commission_paid_fen,
              u.phone AS phone,
              u.email AS email
            FROM direct d
            LEFT JOIN activated a ON a.inviter_id=d.inviter_id
            LEFT JOIN paid_direct p ON p.inviter_id=d.inviter_id
            LEFT JOIN comm c ON c.inviter_id=d.inviter_id
            LEFT JOIN users u ON u.id=d.inviter_id
            ORDER BY {order_by}
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()

    def _mask_phone(p: str) -> str:
        p = str(p or "").strip()
        if len(p) >= 11 and p.isdigit():
            return p[:3] + "****" + p[-4:]
        return p[:2] + "…" + p[-2:] if len(p) > 6 else p

    def _mask_email(e: str) -> str:
        e = str(e or "").strip()
        if "@" not in e:
            return e[:2] + "…" + e[-2:] if len(e) > 6 else e
        name, domain = e.split("@", 1)
        name = name.strip()
        domain = domain.strip()
        if len(name) <= 1:
            return name + "…@" + domain
        if len(name) == 2:
            return name[0] + "…@" + domain
        return name[:2] + "…" + name[-1:] + "@" + domain

    items: list[dict[str, Any]] = []
    for r in rows:
        uid = int(_row_get(r, "inviter_id") or 0)
        phone = str(_row_get(r, "phone") or "")
        email = str(_row_get(r, "email") or "")
        items.append(
            {
                "user_id": uid,
                "phone_masked": _mask_phone(phone) if phone else "",
                "email_masked": _mask_email(email) if email else "",
                "direct_invites": int(_row_get(r, "direct_invites") or 0),
                "activated_direct": int(_row_get(r, "activated_direct") or 0),
                "paid_orders_direct": int(_row_get(r, "paid_orders_direct") or 0),
                "paid_amount_direct_fen": int(_row_get(r, "paid_amount_direct_fen") or 0),
                "commission_pending_fen": int(_row_get(r, "commission_pending_fen") or 0),
                "commission_paid_fen": int(_row_get(r, "commission_paid_fen") or 0),
            }
        )
    return {"items": items, "metric": metric, "limit": limit, "offset": offset}


def admin_agent_detail(*, user_id: int, depth: int = 3, limit: int = 300) -> dict[str, Any]:
    """
    Admin: agent detail (invite tree + commission + payout + direct-paid summary).
    """
    uid = int(user_id or 0)
    if uid <= 0:
        raise ValueError("invalid user_id")
    depth = max(1, min(int(depth or 3), 6))
    limit = max(50, min(int(limit or 300), 2000))

    tree = admin_invite_tree(uid, depth=depth, limit=limit)

    with connect() as conn:
        st = None
        try:
            st = agent_get_status(uid)
        except Exception:
            st = None
        r1 = conn.execute(
            """
            SELECT
              COALESCE(SUM(CASE WHEN status='pending' THEN commission_fen ELSE 0 END),0) AS pending_fen,
              COALESCE(SUM(CASE WHEN status='requested' THEN commission_fen ELSE 0 END),0) AS requested_fen,
              COALESCE(SUM(CASE WHEN status='paid' THEN commission_fen ELSE 0 END),0) AS paid_fen
            FROM commission_ledger
            WHERE agent_user_id=?
            """,
            (uid,),
        ).fetchone()
        pending_fen = int(_row_get(r1, "pending_fen") or 0) if r1 else 0
        requested_fen = int(_row_get(r1, "requested_fen") or 0) if r1 else 0
        paid_fen = int(_row_get(r1, "paid_fen") or 0) if r1 else 0

        r2 = conn.execute(
            """
            SELECT
              COALESCE(SUM(CASE WHEN status='pending' THEN amount_fen ELSE 0 END),0) AS pr_pending_fen,
              COALESCE(SUM(CASE WHEN status='approved' THEN amount_fen ELSE 0 END),0) AS pr_approved_fen,
              COALESCE(SUM(CASE WHEN status='paid' THEN amount_fen ELSE 0 END),0) AS pr_paid_fen
            FROM agent_payout_requests
            WHERE user_id=?
            """,
            (uid,),
        ).fetchone()
        pr_pending_fen = int(_row_get(r2, "pr_pending_fen") or 0) if r2 else 0
        pr_approved_fen = int(_row_get(r2, "pr_approved_fen") or 0) if r2 else 0
        pr_paid_fen = int(_row_get(r2, "pr_paid_fen") or 0) if r2 else 0

        r3 = conn.execute(
            """
            SELECT
              COUNT(1) AS paid_orders_direct,
              COALESCE(SUM(amount_fen),0) AS paid_amount_direct_fen
            FROM pay_orders
            WHERE status='paid' AND referrer_user_id=?
            """,
            (uid,),
        ).fetchone()
        paid_orders_direct = int(_row_get(r3, "paid_orders_direct") or 0) if r3 else 0
        paid_amount_direct_fen = int(_row_get(r3, "paid_amount_direct_fen") or 0) if r3 else 0

    return {
        "ok": True,
        "user_id": uid,
        "agent_status": st,
        "tree": tree,
        "summary": {
            "paid_orders_direct": paid_orders_direct,
            "paid_amount_direct_fen": paid_amount_direct_fen,
            "commission_pending_fen": pending_fen,
            "commission_requested_fen": requested_fen,
            "commission_paid_fen": paid_fen,
            "payout_pending_fen": pr_pending_fen,
            "payout_approved_fen": pr_approved_fen,
            "payout_paid_fen": pr_paid_fen,
        },
    }


def admin_agent_tier_set(*, user_id: int, level: str | None = None, locked: int | None = None, note: str = "") -> dict[str, Any]:
    """
    Admin: set agent tier (level) and/or lock flag.
    - level: starter/growth/pro (also accepts legacy normal/senior/gold)
    - locked: 0/1
    """
    uid = int(user_id or 0)
    if uid <= 0:
        raise ValueError("invalid_user_id")
    lvl_in = None if level is None else str(level or "").strip().lower()
    if lvl_in is not None:
        if lvl_in in ("normal", ""):
            lvl_in = "starter"
        if lvl_in == "senior":
            lvl_in = "growth"
        if lvl_in == "gold":
            lvl_in = "pro"
        if lvl_in not in ("starter", "growth", "pro"):
            raise ValueError("invalid_level")
    lk_in = None if locked is None else (1 if int(locked or 0) == 1 else 0)
    now = int(time.time())
    with connect() as conn:
        row = conn.execute("SELECT user_id, level, expires_at FROM agent_status WHERE user_id=?", (uid,)).fetchone()
        if not row:
            # bootstrap: create a non-expiring tier row for ops
            _agent_upsert_in_conn(conn, uid, lvl_in or "starter", None, now)
        if lvl_in is not None:
            conn.execute("UPDATE agent_status SET level=?, updated_at=? WHERE user_id=?", (lvl_in, now, uid))
        if lk_in is not None:
            conn.execute("UPDATE agent_status SET tier_locked=?, updated_at=? WHERE user_id=?", (int(lk_in), now, uid))
        # audit
        try:
            conn.execute(
                """
                INSERT INTO admin_ops_ledger(user_id, actor, action, before_json, after_json, note, created_at)
                VALUES (?, 'admin', 'agent:tier_set', '{}', '{}', ?, ?)
                """,
                (uid, str(note or "")[:200], now),
            )
        except Exception:
            pass
    st = agent_get_status(uid)
    return {"ok": True, "user_id": uid, "agent_status": st}


def pay_user_has_paid_trial(user_id: int) -> bool:
    """同一用户是否已成功购买过体验卡（以已支付订单为准，限购 1 次）。"""
    uid = int(user_id)
    with connect() as conn:
        row = conn.execute(
            "SELECT 1 AS x FROM pay_orders WHERE user_id=? AND plan=? AND status='paid' LIMIT 1",
            (uid, "vip_trial_99"),
        ).fetchone()
        return bool(row)


def pay_mk_out_trade_no(user_id: int) -> str:
    now = int(time.time())
    tail = secrets.token_hex(4)
    s = f"M{int(user_id)}{now}{tail}"
    return s[:32]


def pay_order_create(
    user_id: int,
    *,
    out_trade_no: str,
    plan: str,
    amount_fen: int,
    channel: str = "wechat",
    code_url: str | None,
) -> None:
    now = int(time.time())
    uid = int(user_id)
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO pay_orders(
              out_trade_no, user_id, plan, amount_fen, channel, status, code_url, transaction_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'pending', ?, NULL, ?, ?)
            """,
            (str(out_trade_no), uid, str(plan), int(amount_fen), str(channel or "wechat"), code_url, now, now),
        )


def pay_order_attach_code_url(out_trade_no: str, code_url: str) -> None:
    now = int(time.time())
    with connect() as conn:
        conn.execute(
            "UPDATE pay_orders SET code_url=?, updated_at=? WHERE out_trade_no=?",
            (str(code_url), now, str(out_trade_no)),
        )


def pay_order_get_by_out_trade_no(out_trade_no: str) -> dict[str, Any] | None:
    otn = str(out_trade_no or "").strip()
    if not otn:
        return None
    with connect() as conn:
        row = conn.execute("SELECT * FROM pay_orders WHERE out_trade_no=?", (otn,)).fetchone()
        if not row:
            return None
        # Convert to plain dict for API layers.
        try:
            return {k: row[k] for k in row.keys()}
        except Exception:
            # sqlite Row supports mapping interface; fallback to selected fields
            return {
                "out_trade_no": row["out_trade_no"],
                "user_id": row["user_id"],
                "plan": row["plan"],
                "amount_fen": row["amount_fen"],
                "channel": row["channel"],
                "status": row["status"],
                "transaction_id": row["transaction_id"],
                "paid_at": row["paid_at"] if "paid_at" in row.keys() else None,
            }


def _paid_plan_period_seconds(np: str) -> int:
    if np == "vip_month":
        return 30 * 86400
    if np == "vip_year_999":
        return 365 * 86400
    if np == "vip_trial_99":
        return 7 * 86400
    if np in ("agent_growth", "agent_pro"):
        return 365 * 86400
    raise ValueError("unknown paid plan for period")


def _agent_level_rank(level: str) -> int:
    lvl = str(level or "").strip().lower()
    # keep legacy names compatible
    if lvl in ("gold", "pro"):
        return 30
    if lvl in ("senior", "growth"):
        return 20
    if lvl in ("normal", "starter", ""):
        return 10
    return 0


def _notice_row_dict(row: Any, *, read: bool = False) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "title": str(row["title"] or ""),
        "body": str(row["body"] or ""),
        "scope": str(row["scope"] or "all"),
        "target_user_id": int(row["target_user_id"]) if _row_get(row, "target_user_id") is not None else None,
        "target_agent_level": str(_row_get(row, "target_agent_level") or ""),
        "pinned": bool(int(row["pinned"] or 0) == 1),
        "status": str(row["status"] or "active"),
        "starts_at": int(row["starts_at"]) if _row_get(row, "starts_at") is not None else None,
        "ends_at": int(row["ends_at"]) if _row_get(row, "ends_at") is not None else None,
        "created_by": str(_row_get(row, "created_by") or "admin"),
        "created_at": int(row["created_at"]),
        "updated_at": int(row["updated_at"]),
        "read": bool(read),
    }


def _agent_level_for_user_in_conn(conn: Any, user_id: int, now: int) -> str:
    """Return current agent level string for targeting checks; empty means none/expired."""
    uid = int(user_id)
    try:
        row = conn.execute("SELECT level, expires_at FROM agent_status WHERE user_id=?", (uid,)).fetchone()
        if not row:
            return ""
        lvl = str(row["level"] or "").strip().lower()
        exp = row["expires_at"]
        if exp is not None and int(exp) < int(now):
            return ""
        return lvl
    except Exception:
        return ""


def notices_list_for_user(user_id: int, *, limit: int = 20, offset: int = 0, unread_only: bool = False) -> dict[str, Any]:
    uid = int(user_id)
    lim = max(1, min(50, int(limit)))
    off = max(0, int(offset))
    now = int(time.time())
    with connect() as conn:
        lvl = _agent_level_for_user_in_conn(conn, uid, now)
        # active + time window
        base_where = """
          n.status='active'
          AND (n.starts_at IS NULL OR n.starts_at<=?)
          AND (n.ends_at IS NULL OR n.ends_at>=?)
          AND (
            n.scope='all'
            OR (n.scope='user' AND n.target_user_id=?)
            OR (n.scope='agent_level' AND n.target_agent_level<>'' AND ?<>'' AND n.target_agent_level=?)
          )
        """
        unread_join = "LEFT JOIN user_notice_reads r ON r.notice_id=n.id AND r.user_id=?"
        unread_cond = "AND r.notice_id IS NULL" if bool(unread_only) else ""
        sql = f"""
          SELECT n.*,
                 CASE WHEN r.notice_id IS NULL THEN 0 ELSE 1 END AS read_flag
          FROM user_notices n
          {unread_join}
          WHERE {base_where}
          {unread_cond}
          ORDER BY n.pinned DESC, n.created_at DESC
          LIMIT ? OFFSET ?
        """
        rows = conn.execute(sql, (uid, now, now, uid, lvl, lvl, lim, off)).fetchall()
        items = [_notice_row_dict(r, read=bool(int(r["read_flag"] or 0) == 1)) for r in (rows or [])]
        # unread count (cheap enough for MVP)
        csql = f"""
          SELECT COUNT(1) AS c
          FROM user_notices n
          LEFT JOIN user_notice_reads r ON r.notice_id=n.id AND r.user_id=?
          WHERE {base_where}
            AND r.notice_id IS NULL
        """
        crow = conn.execute(csql, (uid, now, now, uid, lvl, lvl)).fetchone()
        unread = int((crow or {}).get("c") or 0) if isinstance(crow, dict) else int(crow["c"] if crow else 0)
        return {"ok": True, "items": items, "unread": unread, "limit": lim, "offset": off}


def notice_mark_read(user_id: int, notice_id: int) -> dict[str, Any]:
    uid = int(user_id)
    nid = int(notice_id)
    now = int(time.time())
    if nid <= 0:
        raise ValueError("invalid_notice_id")
    with connect() as conn:
        if _is_pg():
            conn.execute(
                """
                INSERT INTO user_notice_reads(user_id, notice_id, read_at)
                VALUES (?, ?, ?)
                ON CONFLICT (user_id, notice_id) DO UPDATE SET read_at=EXCLUDED.read_at
                """,
                (uid, nid, now),
            )
        else:
            conn.execute(
                """
                INSERT INTO user_notice_reads(user_id, notice_id, read_at)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id, notice_id) DO UPDATE SET read_at=excluded.read_at
                """,
                (uid, nid, now),
            )
    return {"ok": True}


def admin_notice_create(
    *,
    title: str,
    body: str,
    scope: str = "all",
    target_user_id: int | None = None,
    target_agent_level: str = "",
    pinned: bool = False,
    starts_at: int | None = None,
    ends_at: int | None = None,
    created_by: str = "admin",
) -> dict[str, Any]:
    t = str(title or "").strip()[:120]
    b = str(body or "").strip()
    if not t or not b:
        raise ValueError("title_body_required")
    sc = str(scope or "all").strip().lower()
    if sc not in ("all", "user", "agent_level"):
        raise ValueError("invalid_scope")
    tu = None if target_user_id is None else int(target_user_id)
    al = str(target_agent_level or "").strip().lower()
    if sc == "user" and not (tu and tu > 0):
        raise ValueError("target_user_required")
    if sc == "agent_level" and al not in ("starter", "growth", "pro"):
        raise ValueError("target_agent_level_required")
    now = int(time.time())
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO user_notices(
              title, body, scope, target_user_id, target_agent_level, pinned, status,
              starts_at, ends_at, created_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?, ?)
            """,
            (
                t,
                b,
                sc,
                tu,
                al,
                1 if bool(pinned) else 0,
                int(starts_at) if starts_at is not None else None,
                int(ends_at) if ends_at is not None else None,
                str(created_by or "admin")[:64],
                now,
                now,
            ),
        )
        row = conn.execute("SELECT * FROM user_notices ORDER BY id DESC LIMIT 1").fetchone()
        return {"ok": True, "notice": _notice_row_dict(row) if row else None}


def admin_notice_list(*, status: str = "", limit: int = 50, offset: int = 0) -> dict[str, Any]:
    st = str(status or "").strip().lower()
    lim = max(1, min(200, int(limit)))
    off = max(0, int(offset))
    with connect() as conn:
        where = ""
        params: list[Any] = []
        if st:
            where = "WHERE status=?"
            params.append(st)
        total_row = conn.execute(f"SELECT COUNT(1) AS c FROM user_notices {where}", tuple(params)).fetchone()
        total = int(total_row["c"]) if total_row else 0
        rows = conn.execute(
            f"SELECT * FROM user_notices {where} ORDER BY pinned DESC, created_at DESC LIMIT ? OFFSET ?",
            tuple(params + [lim, off]),
        ).fetchall()
        items = [_notice_row_dict(r) for r in (rows or [])]
        return {"ok": True, "items": items, "total": total, "limit": lim, "offset": off}


def admin_notice_set_status(notice_id: int, status: str) -> dict[str, Any]:
    nid = int(notice_id)
    st = str(status or "").strip().lower()
    if nid <= 0:
        raise ValueError("invalid_notice_id")
    if st not in ("active", "archived"):
        raise ValueError("invalid_status")
    now = int(time.time())
    with connect() as conn:
        conn.execute("UPDATE user_notices SET status=?, updated_at=? WHERE id=?", (st, now, nid))
    return {"ok": True}


def admin_notice_pin(notice_id: int, pinned: bool) -> dict[str, Any]:
    nid = int(notice_id)
    if nid <= 0:
        raise ValueError("invalid_notice_id")
    now = int(time.time())
    with connect() as conn:
        conn.execute("UPDATE user_notices SET pinned=?, updated_at=? WHERE id=?", (1 if pinned else 0, now, nid))
    return {"ok": True}


def admin_notice_update(
    notice_id: int,
    *,
    title: str,
    body: str,
    scope: str = "all",
    target_user_id: int | None = None,
    target_agent_level: str = "",
    pinned: bool = False,
    starts_at: int | None = None,
    ends_at: int | None = None,
) -> dict[str, Any]:
    nid = int(notice_id)
    if nid <= 0:
        raise ValueError("invalid_notice_id")
    t = str(title or "").strip()[:120]
    b = str(body or "").strip()
    if not t or not b:
        raise ValueError("title_body_required")
    sc = str(scope or "all").strip().lower()
    if sc not in ("all", "user", "agent_level"):
        raise ValueError("invalid_scope")
    tu = None if target_user_id is None else int(target_user_id)
    al = str(target_agent_level or "").strip().lower()
    if sc == "user" and not (tu and tu > 0):
        raise ValueError("target_user_required")
    if sc == "agent_level" and al not in ("starter", "growth", "pro"):
        raise ValueError("target_agent_level_required")
    now = int(time.time())
    with connect() as conn:
        conn.execute(
            """
            UPDATE user_notices
            SET title=?,
                body=?,
                scope=?,
                target_user_id=?,
                target_agent_level=?,
                pinned=?,
                starts_at=?,
                ends_at=?,
                updated_at=?
            WHERE id=?
            """,
            (
                t,
                b,
                sc,
                tu,
                al,
                1 if bool(pinned) else 0,
                int(starts_at) if starts_at is not None else None,
                int(ends_at) if ends_at is not None else None,
                now,
                nid,
            ),
        )
        row = conn.execute("SELECT * FROM user_notices WHERE id=?", (nid,)).fetchone()
        return {"ok": True, "notice": _notice_row_dict(row) if row else None}


def _agent_upgrade_target_level(plan_norm: str) -> str:
    p = str(plan_norm or "").strip().lower()
    if p == "agent_pro":
        return "pro"
    if p == "agent_growth":
        return "growth"
    raise ValueError("invalid agent upgrade plan")


def _fulfill_agent_upgrade_in_conn(conn: Any, user_id: int, plan_norm: str, note: str, now: int) -> None:
    uid = int(user_id)
    period = _paid_plan_period_seconds(str(plan_norm))
    target = _agent_upgrade_target_level(plan_norm)

    # Read current agent status (if any) to decide upgrade & extension.
    cur_level = ""
    cur_exp = None
    try:
        row = conn.execute("SELECT level, expires_at FROM agent_status WHERE user_id=?", (uid,)).fetchone()
        if row:
            cur_level = str(row["level"] or "")
            cur_exp = row["expires_at"]
    except Exception:
        cur_level = ""
        cur_exp = None

    # If user already has an active higher tier, do not allow buying a lower-tier plan (avoid confusion).
    try:
        cur_rank0 = _agent_level_rank(cur_level)
        tgt_rank0 = _agent_level_rank(target)
        active0 = cur_exp is not None and int(cur_exp) > int(now)
        if bool(active0) and int(cur_rank0) > int(tgt_rank0):
            raise ValueError("higher_tier_active")
    except ValueError:
        raise
    except Exception:
        pass

    # Don't downgrade: keep higher level if already achieved.
    new_level = target
    if _agent_level_rank(cur_level) > _agent_level_rank(target):
        new_level = str(cur_level or "").strip().lower() or target

    # Scheme A:
    # - Same-level renewal: extend from expires_at (if any).
    # - Upgrade to a higher level: take effect immediately from now (do NOT stack old remaining time).
    base = int(now)
    try:
        cur_rank = _agent_level_rank(cur_level)
        tgt_rank = _agent_level_rank(target)
        if cur_exp is not None and cur_rank >= tgt_rank:
            base = max(int(now), int(cur_exp))
        else:
            base = int(now)
    except Exception:
        base = int(now)
    new_exp = int(base + int(period))

    before = {"level": str(cur_level or ""), "expires_at": int(cur_exp) if cur_exp is not None else None}
    _agent_upsert_in_conn(conn, uid, new_level, int(new_exp), int(now))
    after = {"level": str(new_level or ""), "expires_at": int(new_exp)}

    try:
        conn.execute(
            """
            INSERT INTO admin_ops_ledger(user_id, actor, action, before_json, after_json, note, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                uid,
                "wechat_pay",
                "billing:agent_tier",
                json.dumps(before, ensure_ascii=False, separators=(",", ":")),
                json.dumps(after, ensure_ascii=False, separators=(",", ":")),
                str(note or "")[:200],
                int(now),
            ),
        )
    except Exception:
        pass


def _fulfill_paid_plan_in_conn(conn: Any, user_id: int, raw_plan: str, note: str, now: int) -> None:
    uid = int(user_id)
    np, wk, dy, _ = _plan_defaults(raw_plan)
    if np in ("agent_growth", "agent_pro"):
        _fulfill_agent_upgrade_in_conn(conn, uid, np, note, now)
        return
    if np not in ("vip_month", "vip_year_999", "vip_trial_99"):
        raise ValueError("invalid paid plan")
    period = _paid_plan_period_seconds(np)

    row = conn.execute("SELECT * FROM quota WHERE user_id=?", (uid,)).fetchone()
    if not row:
        raise ValueError("quota not found")

    cur_plan = str(row["plan"])
    cur_weekly_limit = int(row["monthly_limit"])
    cur_daily_limit = int(row["daily_limit"])
    cur_weekly_used = int(row["monthly_used"])
    cur_daily_used = int(row["daily_used"])
    exp = row["expires_at"]

    new_weekly = int(wk) if wk >= 0 else cur_weekly_limit
    new_daily = int(dy) if dy >= 0 else cur_daily_limit

    if cur_plan == np and exp is not None:
        base = max(now, int(exp))
        new_exp = int(base + period)
    else:
        new_exp = int(now + period)

    def _clamp_used(limit_base: int, used: int) -> int:
        if limit_base < 0:
            return max(0, int(used))
        return max(0, min(int(used), int(limit_base)))

    nu_w = _clamp_used(new_weekly, cur_weekly_used)
    nu_d = _clamp_used(new_daily, cur_daily_used)

    before = {
        "plan": cur_plan,
        "monthly_limit": cur_weekly_limit,
        "daily_limit": cur_daily_limit,
        "monthly_used": cur_weekly_used,
        "daily_used": cur_daily_used,
        "expires_at": int(exp) if exp is not None else None,
    }
    conn.execute(
        """
        UPDATE quota
        SET plan=?, monthly_limit=?, daily_limit=?, monthly_used=?, daily_used=?, expires_at=?, updated_at=?
        WHERE user_id=?
        """,
        (np, new_weekly, new_daily, nu_w, nu_d, new_exp, now, uid),
    )
    after = {
        "plan": np,
        "monthly_limit": new_weekly,
        "daily_limit": new_daily,
        "monthly_used": nu_w,
        "daily_used": nu_d,
        "expires_at": new_exp,
    }
    # Gift agent status for VIP year: buying vip_year_999 grants starter agent with same expiry.
    if np == "vip_year_999":
        _agent_upsert_in_conn(conn, uid, "starter", int(new_exp), now)
    conn.execute(
        """
        INSERT INTO admin_ops_ledger(user_id, actor, action, before_json, after_json, note, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            uid,
            "wechat_pay",
            "billing:vip",
            json.dumps(before, ensure_ascii=False, separators=(",", ":")),
            json.dumps(after, ensure_ascii=False, separators=(",", ":")),
            str(note or "")[:200],
            now,
        ),
    )


def pay_order_try_fulfill_wechat(out_trade_no: str, transaction_id: str, amount_fen: int) -> dict[str, Any]:
    """
    微信回调内调用：校验金额、幂等更新订单并发 VIP。
    """
    now = int(time.time())
    otn = str(out_trade_no or "").strip()
    txid = str(transaction_id or "").strip()
    if not otn or not txid:
        return {"ok": False, "error": "missing_trade_refs"}

    with connect() as conn:
        row = conn.execute("SELECT * FROM pay_orders WHERE out_trade_no=?", (otn,)).fetchone()
        if not row:
            return {"ok": False, "error": "order_not_found"}
        if str(row["status"]) == "paid":
            if row["transaction_id"] and str(row["transaction_id"]) == txid:
                return {"ok": True, "duplicate": True}
            return {"ok": False, "error": "order_already_paid"}

        if int(row["amount_fen"]) != int(amount_fen):
            return {"ok": False, "error": "amount_mismatch"}

        uid = int(row["user_id"])
        plan = str(row["plan"])
        _fulfill_paid_plan_in_conn(conn, uid, plan, f"wechat:{otn}", now)

        # Bind referrer (invite) into order for future settlement/reporting.
        inviter_id: int | None = None
        try:
            rel = conn.execute(
                "SELECT inviter_id FROM invite_relations WHERE invitee_id=?",
                (uid,),
            ).fetchone()
            if rel and rel["inviter_id"] is not None:
                inviter_id = int(rel["inviter_id"])
        except Exception:
            inviter_id = None
        conn.execute(
            "UPDATE pay_orders SET status=?, transaction_id=?, paid_at=?, referrer_user_id=?, updated_at=? WHERE out_trade_no=?",
            ("paid", txid, now, inviter_id, now, otn),
        )

        # Commission (multi-level): best-effort; never fail payment due to commission.
        try:
            _commission_generate_for_paid_order_in_conn(
                conn,
                out_trade_no=otn,
                buyer_id=int(uid),
                plan=str(plan),
                amount_fen=int(amount_fen),
                paid_at=int(now),
                now=int(now),
            )
        except Exception:
            pass

    return {"ok": True, "duplicate": False}


def pay_order_try_fulfill_alipay(out_trade_no: str, trade_no: str, amount_fen: int) -> dict[str, Any]:
    """
    支付宝回调内调用：校验金额、幂等更新订单并发 VIP。
    """
    now = int(time.time())
    otn = str(out_trade_no or "").strip()
    txid = str(trade_no or "").strip()
    if not otn or not txid:
        return {"ok": False, "error": "missing_trade_refs"}

    with connect() as conn:
        row = conn.execute("SELECT * FROM pay_orders WHERE out_trade_no=?", (otn,)).fetchone()
        if not row:
            return {"ok": False, "error": "order_not_found"}
        if str(row["status"]) == "paid":
            if row["transaction_id"] and str(row["transaction_id"]) == txid:
                return {"ok": True, "duplicate": True}
            return {"ok": False, "error": "order_already_paid"}

        if int(row["amount_fen"]) != int(amount_fen):
            return {"ok": False, "error": "amount_mismatch"}

        uid = int(row["user_id"])
        plan = str(row["plan"])
        _fulfill_paid_plan_in_conn(conn, uid, plan, f"alipay:{otn}", now)

        # Bind referrer (invite) into order for future settlement/reporting.
        inviter_id: int | None = None
        try:
            rel = conn.execute(
                "SELECT inviter_id FROM invite_relations WHERE invitee_id=?",
                (uid,),
            ).fetchone()
            if rel and rel["inviter_id"] is not None:
                inviter_id = int(rel["inviter_id"])
        except Exception:
            inviter_id = None

        conn.execute(
            "UPDATE pay_orders SET status=?, transaction_id=?, paid_at=?, referrer_user_id=?, updated_at=? WHERE out_trade_no=?",
            ("paid", txid, now, inviter_id, now, otn),
        )

        # Commission (multi-level): best-effort; never fail payment due to commission.
        try:
            _commission_generate_for_paid_order_in_conn(
                conn,
                out_trade_no=otn,
                buyer_id=int(uid),
                plan=str(plan),
                amount_fen=int(amount_fen),
                paid_at=int(now),
                now=int(now),
            )
        except Exception:
            pass

        # Keep ledger minimal (wechat path already writes detailed before/after in quota ledger).
        try:
            conn.execute(
                """
                INSERT INTO admin_ops_ledger(user_id, actor, action, before_json, after_json, note, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (uid, "alipay_pay", "billing:vip", "{}", "{}", str(f"alipay:{otn}")[:200], now),
            )
        except Exception:
            pass

    return {"ok": True, "duplicate": False}

