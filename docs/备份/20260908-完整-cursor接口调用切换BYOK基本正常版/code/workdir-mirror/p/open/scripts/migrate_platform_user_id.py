"""一次性迁移：open auth_users 增加 platform_user_id（国际版统一账号，DEC-0007）。

用法：python migrate_platform_user_id.py（在仓库根目录执行，自动定位 .env）。
"""
import os
import sys


def load_env(path):
    env = {}
    with open(path, "r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


candidates = [
    "p/open/api/.env",
    "C:/ai24x01/p/open/api/.env",
]
env_path = next((p for p in candidates if os.path.exists(p)), None)
if not env_path:
    print("NO_ENV_FOUND")
    sys.exit(1)

url = load_env(env_path).get("DATABASE_URL", "")
if not url:
    print("NO_DATABASE_URL")
    sys.exit(1)

import psycopg2

conn = psycopg2.connect(url)
conn.autocommit = True
cur = conn.cursor()
cur.execute(
    "ALTER TABLE auth_users ADD COLUMN IF NOT EXISTS platform_user_id INTEGER"
)
cur.execute(
    "CREATE UNIQUE INDEX IF NOT EXISTS ix_auth_users_platform_user_id "
    "ON auth_users (platform_user_id)"
)
cur.execute(
    "SELECT column_name FROM information_schema.columns "
    "WHERE table_name='auth_users' AND column_name='platform_user_id'"
)
print("column_exists=", bool(cur.fetchone()))
cur.close()
conn.close()
print("MIGRATE_OK")
