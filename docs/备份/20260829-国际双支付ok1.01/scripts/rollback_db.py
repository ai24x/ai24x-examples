#!/usr/bin/env python3
"""国际双支付 ok1.01 — 数据库回滚（pg_restore）。"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
API_DIR = ROOT / "api"
BUNDLE = Path(__file__).resolve().parents[1]
DB_DIR = BUNDLE / "db"


def _pg_bin(name: str) -> str:
    candidates = [
        Path(rf"C:\AI24X\postgresql\pgsql\bin") / f"{name}.exe",
        Path(rf"C:\Program Files\PostgreSQL\16\bin") / f"{name}.exe",
        Path(rf"C:\Program Files\PostgreSQL\15\bin") / f"{name}.exe",
        Path(rf"C:\Program Files\PostgreSQL\14\bin") / f"{name}.exe",
        Path(rf"C:\Program Files\PostgreSQL\13\bin") / f"{name}.exe",
    ]
    for p in candidates:
        if p.is_file():
            return str(p)
    return name


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="execute restore (default dry-run)")
    ap.add_argument("--mode", choices=("payment", "full"), default="payment")
    args = ap.parse_args()

    dump = DB_DIR / ("full.dump" if args.mode == "full" else "payment_tables.dump")
    if not dump.is_file():
        print(f"MISSING {dump}", file=sys.stderr)
        return 1

    sys.path.insert(0, str(API_DIR))
    os.chdir(API_DIR)
    from config import settings  # noqa: WPS433
    from sqlalchemy.engine import make_url

    url = make_url(settings.database_url)
    env = os.environ.copy()
    if url.password:
        env["PGPASSWORD"] = str(url.password)

    cmd = [
        _pg_bin("pg_restore"),
        "-h",
        url.host or "127.0.0.1",
        "-p",
        str(url.port or 5432),
        "-U",
        url.username or "postgres",
        "-d",
        url.database or "",
        "--clean",
        "--if-exists",
        str(dump),
    ]
    if args.apply:
        print("RUN", " ".join(cmd))
        r = subprocess.run(cmd, env=env)
        print("exit", r.returncode)
        print("restart: Restart-Service AI24X-core -Force")
        return r.returncode
    print("[dry] would run:", " ".join(cmd))
    print("add --apply to execute")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
