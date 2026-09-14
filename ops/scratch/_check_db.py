import psycopg2
try:
    conn = psycopg2.connect("postgresql://ai24x_a:Ai24x%402026@127.0.0.1:5432/ai24x_a_pre")
    cur = conn.cursor()
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND (table_name LIKE '%token%' OR table_name LIKE '%usage%' OR table_name LIKE '%ledger%' OR table_name LIKE '%billing%') ORDER BY table_name")
    tables = [t[0] for t in cur.fetchall()]
    print("Tables found:", tables)
    cur.close()
    conn.close()
except Exception as e:
    print("Error:", e)
