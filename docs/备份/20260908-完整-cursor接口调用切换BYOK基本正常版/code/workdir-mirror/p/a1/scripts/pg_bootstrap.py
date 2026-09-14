import os

import psycopg
from psycopg import sql


def main() -> None:
    pg_pw = os.environ.get("AI24X_PG_BOOTSTRAP_PASSWORD", "")
    if not pg_pw:
        raise SystemExit("Missing env AI24X_PG_BOOTSTRAP_PASSWORD")

    # Connect as superuser to postgres maintenance DB.
    with psycopg.connect(
        host="127.0.0.1",
        port=5432,
        dbname="postgres",
        user="postgres",
        password=pg_pw,
        autocommit=True,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname='ai24x_a'")
            has_role = cur.fetchone() is not None
            if not has_role:
                cur.execute(
                    sql.SQL("CREATE ROLE ai24x_a LOGIN PASSWORD {}").format(
                        sql.Literal(pg_pw)
                    )
                )
            else:
                cur.execute(
                    sql.SQL("ALTER ROLE ai24x_a WITH LOGIN PASSWORD {}").format(
                        sql.Literal(pg_pw)
                    )
                )

            cur.execute("SELECT 1 FROM pg_database WHERE datname='ai24x_a_pre'")
            has_db = cur.fetchone() is not None
            if not has_db:
                cur.execute("CREATE DATABASE ai24x_a_pre OWNER ai24x_a")

    # Validate app user can connect to target DB.
    with psycopg.connect(
        host="127.0.0.1",
        port=5432,
        dbname="ai24x_a_pre",
        user="ai24x_a",
        password=pg_pw,
        connect_timeout=5,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            print(cur.fetchone())


if __name__ == "__main__":
    main()

