from __future__ import annotations

import sqlite3
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    paths = [
        root / "p" / "a" / "api" / "server" / "data" / "ai24x.db",
        root / "data" / "ai24x.db",
        root / "api" / "data" / "api_auth.db",
    ]
    needle_phone = "18958992226"
    needle_emails = {"lei@itxin.com", "sohodiy@qq.com"}

    for p in paths:
        print(f"\nDB: {p}")
        if not p.exists():
            print("  missing")
            continue
        conn = sqlite3.connect(str(p))
        conn.row_factory = sqlite3.Row
        try:
            has_users = conn.execute(
                "select 1 from sqlite_master where type='table' and name='users'"
            ).fetchone()
            print("  has_users:", bool(has_users))
            if has_users:
                cols = [r["name"] for r in conn.execute("pragma table_info(users)").fetchall()]
                print("  user_cols:", cols)
                sel_cols = [c for c in ["id", "email", "phone", "user_id"] if c in cols]
                where_parts = []
                params: list[str] = []
                if "phone" in cols:
                    where_parts.append("phone = ?")
                    params.append(needle_phone)
                    where_parts.append("phone LIKE ?")
                    params.append(f"%{needle_phone}%")
                if "email" in cols:
                    where_parts.append("lower(email) in (?,?)")
                    params.extend(sorted(needle_emails))
                    where_parts.append("lower(email) like ?")
                    params.append("%@itxin.com%")
                if where_parts:
                    sql = f"select {', '.join(sel_cols)} from users where " + " OR ".join(where_parts) + " limit 50"
                    rows = conn.execute(sql, tuple(params)).fetchall()
                    print("  matches:", [dict(r) for r in rows])
        finally:
            conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

