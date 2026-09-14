from __future__ import annotations

import sqlite3
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: sqlite_search_value.py <db_path> <needle>")
        return 2
    db_path = Path(sys.argv[1])
    needle = sys.argv[2]
    if not db_path.exists():
        print("missing:", db_path)
        return 2

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        tables = [
            r["name"]
            for r in conn.execute(
                "select name from sqlite_master where type='table' and name not like 'sqlite_%'"
            ).fetchall()
        ]
        print("tables:", len(tables))
        hits = 0
        for t in tables:
            cols = conn.execute(f"pragma table_info({t})").fetchall()
            col_names = [c[1] for c in cols]
            if not col_names:
                continue
            # Search across all columns by casting to text; this is slower but robust for mixed schemas.
            where = " OR ".join([f"CAST({c} AS TEXT) LIKE ?" for c in col_names])
            sql = f"select rowid as _rowid_, * from {t} where {where} limit 20"
            params = tuple([f"%{needle}%"] * len(col_names))
            rows = conn.execute(sql, params).fetchall()
            if rows:
                print(f"\n== {t} ({len(rows)} rows) ==")
                for r in rows:
                    d = dict(r)
                    # keep output short
                    print({k: d.get(k) for k in list(d.keys())[:12]})
                hits += len(rows)
        print("\nhits:", hits)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

