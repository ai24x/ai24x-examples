#!/usr/bin/env python3
"""
从主站 core 库导出 auth_users 切片，供行情官 admin 导入（按 id 写入 password_hash）。

用法（在副脑04 / 有 core DATABASE_URL 的机器）：
  cd api
  python scripts_export_a1_auth_hashes.py -o auth_users_export.json

安全：输出含 password_hash，勿提交 git、勿公开传；经安全通道交给 03 导入后删除。
"""

from __future__ import annotations

import argparse
import json
import os
import sys


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--output", default="auth_users_export.json")
    ap.add_argument("--limit", type=int, default=0, help="0=全部")
    args = ap.parse_args()

    # Load .env if present
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
        pass

    url = (os.getenv("DATABASE_URL") or "").strip()
    if not url:
        print("DATABASE_URL missing", file=sys.stderr)
        return 2

    from sqlalchemy import create_engine, text

    eng = create_engine(url)
    q = "SELECT id, phone, email, password_hash FROM auth_users ORDER BY id"
    if args.limit and args.limit > 0:
        q += f" LIMIT {int(args.limit)}"
    rows = []
    with eng.connect() as conn:
        for r in conn.execute(text(q)):
            rows.append(
                {
                    "id": int(r[0]),
                    "phone": (r[1] or None),
                    "email": (r[2] or None),
                    "password_hash": (r[3] or ""),
                }
            )
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump({"rows": rows, "count": len(rows)}, f, ensure_ascii=False, indent=2)
    print(f"wrote {len(rows)} rows -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
