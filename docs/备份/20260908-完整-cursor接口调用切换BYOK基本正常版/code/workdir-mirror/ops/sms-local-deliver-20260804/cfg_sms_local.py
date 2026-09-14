# -*- coding: utf-8 -*-
"""写入 a1 库(ai24x_a_cn) admin_config：sms_active_provider=local + sms_106_*（106参数取自 api/.env）"""
import os
from dotenv import load_dotenv
import psycopg2

load_dotenv(r"C:\ai24x01\api\.env", override=True)

vals = {
    "sms_active_provider": "local",
    "sms_106_endpoint": os.environ.get("SMS_106_ENDPOINT", "").strip(),
    "sms_106_account": os.environ.get("SMS_106_ACCOUNT", "").strip(),
    "sms_106_password": os.environ.get("SMS_106_PASSWORD", "").strip(),
    "sms_106_template": os.environ.get("SMS_106_TEMPLATE", "").strip(),
}
conn = psycopg2.connect(
    host="127.0.0.1", port=5432, dbname="ai24x_a_cn",
    user="ai24x_a", password=os.environ.get("AI24X_A_PW", "ai24x_a_password_2026"),
)
conn.autocommit = True
cur = conn.cursor()
for k, v in vals.items():
    cur.execute(
        "INSERT INTO admin_config (key, value, updated_at) VALUES (%s, %s, EXTRACT(EPOCH FROM now())::bigint) "
        "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = EXCLUDED.updated_at",
        (k, v),
    )
    print(f"upsert {k}: len={len(v)}")
cur.execute("SELECT key, value FROM admin_config WHERE key LIKE 'sms%' ORDER BY key")
for r in cur.fetchall():
    k, v = r
    print(f"  {k} = {'*' * min(len(v), 6)} (len={len(v)})")
cur.close()
conn.close()
print("DONE")
