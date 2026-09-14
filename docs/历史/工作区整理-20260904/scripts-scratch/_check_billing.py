import psycopg2
conn = psycopg2.connect("postgresql://ai24x_a:Ai24x%402026@127.0.0.1:5432/ai24x_a_pre")
cur = conn.cursor()

# 查 billing_ledger 结构
cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='billing_ledger' ORDER BY ordinal_position")
cols = [(c[0], c[1]) for c in cur.fetchall()]
print("billing_ledger columns:", cols)

# 查有没有 ityizu
cur.execute("SELECT DISTINCT user_email FROM billing_ledger WHERE user_email LIKE '%itxin%' OR user_email LIKE '%foxmail%'")
emails = [r[0] for r in cur.fetchall()]
print("Matching emails:", emails)

# 查 token_pay_orders
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='token_pay_orders' ORDER BY ordinal_position")
pay_cols = [c[0] for c in cur.fetchall()]
print("token_pay_orders columns:", pay_cols)

cur.execute("SELECT * FROM token_pay_orders WHERE user_email LIKE '%itxin%' OR user_email LIKE '%foxmail%'")
orders = cur.fetchall()
print("Orders:", orders)

cur.close()
conn.close()
