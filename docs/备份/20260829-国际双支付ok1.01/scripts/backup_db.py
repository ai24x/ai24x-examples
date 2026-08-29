#!/usr/bin/env python3
"""国际双支付 ok1.01 — 数据库备份（读 api/.env 的 DATABASE_URL，调用 pg_dump）。"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
API_DIR = ROOT / "api"
BUNDLE = Path(__file__).resolve().parents[1]
DB_DIR = BUNDLE / "db"

TABLES = (
    "token_pay_orders",
    "token_wallets",
    "billing_ledger",
    "token_credit_lots",
)


def _pg_bin(name: str) -> str:
    for ver in ("16", "15", "14", "13"):
        p = Path(rf"C:\Program Files\PostgreSQL\{ver}\bin") / f"{name}.exe"
        if p.is_file():
            return str(p)
    w = name
    return w


def main() -> int:
    sys.path.insert(0, str(API_DIR))
    os.chdir(API_DIR)
    from config import settings  # noqa: WPS433
    from sqlalchemy.engine import make_url

    url = make_url(settings.database_url)
    if url.drivername.startswith("sqlite"):
        print("SKIP: SQLite not supported for payment backup", file=sys.stderr)
        return 1

    DB_DIR.mkdir(parents=True, exist_ok=True)
    pg_dump = _pg_bin("pg_dump")
    env = os.environ.copy()
    if url.password:
        env["PGPASSWORD"] = str(url.password)

    host = url.host or "127.0.0.1"
    port = str(url.port or 5432)
    user = url.username or "postgres"
    db = url.database or ""

    full_out = DB_DIR / "full.dump"
    pay_out = DB_DIR / "payment_tables.dump"

    def run_dump(out: Path, extra: list[str]) -> None:
        cmd = [
            pg_dump,
            "-h",
            host,
            "-p",
            port,
            "-U",
            user,
            "-d",
            db,
            "-Fc",
            "-f",
            str(out),
            *extra,
        ]
        print("RUN", " ".join(cmd[:12]), "...")
        subprocess.run(cmd, check=True, env=env)

    run_dump(full_out, [])
    table_args: list[str] = []
    for t in TABLES:
        table_args.extend(["-t", t])
    run_dump(pay_out, table_args)

    meta = {
        "ok": True,
        "host": host,
        "database": db,
        "full": "db/full.dump",
        "payment_tables": "db/payment_tables.dump",
        "tables": list(TABLES),
        "backed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    (DB_DIR / "backup_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("OK", json.dumps(meta, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
