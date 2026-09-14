"""
Dodo 补单脚本：查询 user 46 (181721@qq.com) 的 pending Dodo 订单，
通过 Dodo API 查询每笔的实际支付状态，只补已支付的。

用法：python dodo_backfill.py [--dry-run] [--fulfill]
  --dry-run  只查询不补单（默认）
  --fulfill  实际执行补单
"""
import asyncio
import sys
import os

# 2026-08-31 迁移至 ops\dodo-tools 后，显式指向生产 api 目录（依赖 pay_dodo / token_pay_service）
sys.path.insert(0, r"C:\ai24x01\api")

# 加载 .env
env_path = r"C:\ai24x01\api\.env"
if os.path.exists(env_path):
    for line in open(env_path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

import httpx
from pay_dodo import dodo_api_base


async def query_dodo_session(api_key: str, session_id: str) -> dict:
    """通过 Dodo API 查询 checkout session 状态"""
    url = f"{_dodo_base()}/checkouts/{session_id}"
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
            },
        )
    try:
        return r.json()
    except Exception:
        return {"raw": r.text, "status_code": r.status_code}


def _dodo_base():
    mode = os.environ.get("DODO_MODE", "test").strip().lower()
    return "https://live.dodopayments.com" if mode in ("live", "production", "prod") else "https://test.dodopayments.com"


async def main():
    dry_run = "--fulfill" not in sys.argv

    import psycopg2
    conn = psycopg2.connect(
        host="127.0.0.1", dbname="ai24x_core_cn",
        user="ai24x_a", password=os.environ.get("PG_PASSWORD", "")
    )
    c = conn.cursor()

    api_key = os.environ.get("DODO_API_KEY", "").strip()
    if not api_key:
        print("ERROR: DODO_API_KEY not set")
        return

    # 查询 user 46 的所有 pending Dodo 订单
    c.execute("""
        SELECT id, out_trade_no, plan, amount_fen, transaction_id, created_at, status
        FROM token_pay_orders
        WHERE auth_user_id = 46 AND channel = 'dodo' AND status = 'pending'
        ORDER BY id
    """)
    orders = c.fetchall()
    print(f"\n=== 找到 {len(orders)} 笔 pending Dodo 订单 (user 46) ===\n")

    paid_orders = []
    unpaid_orders = []

    for row in orders:
        otn = row[1]
        plan = row[2]
        amount = row[3]
        txn_id = row[4]  # checkout session ID (cks_xxx)
        created = row[5]

        print(f"--- 订单 id={row[0]} | {otn} | {plan} | ${amount/100:.2f} | {created} ---")

        if not txn_id:
            print(f"  ⚠️ 无 transaction_id，跳过")
            unpaid_orders.append(row)
            continue

        # 查询 Dodo session 状态
        result = await query_dodo_session(api_key, txn_id)
        status = str(result.get("status") or result.get("payment_status") or "").lower()
        payment_id = str(result.get("payment_id") or "").strip()

        print(f"  Dodo 状态: {status} | payment_id: {payment_id or 'N/A'}")

        if status in ("paid", "succeeded", "completed"):
            paid_orders.append((row, payment_id))
            print(f"  ✅ 已支付 → 将补单")
        else:
            unpaid_orders.append(row)
            print(f"  ❌ 未支付 → 跳过")

        await asyncio.sleep(0.3)  # rate limit

    print(f"\n=== 汇总 ===")
    print(f"已支付待补单: {len(paid_orders)} 笔")
    print(f"未支付/跳过: {len(unpaid_orders)} 笔")

    if not paid_orders:
        print("\n没有需要补单的订单。")
        conn.close()
        return

    if dry_run:
        print("\n[DRY RUN] 不执行补单。加 --fulfill 参数执行实际补单。")
        conn.close()
        return

    # 执行补单
    print("\n=== 开始补单 ===")
    from token_pay_service import try_fulfill

    for (row, payment_id) in paid_orders:
        otn = row[1]
        amount = row[3]
        print(f"\n补单: {otn} ...")

        # 检查是否已补过（billing_ledger 有对应的 credit 记录）
        c.execute("""
            SELECT id FROM billing_ledger
            WHERE note LIKE %s AND entry_type = 'credit'
            LIMIT 1
        """, (f"%{otn}%",))
        already = c.fetchone()
        if already:
            print(f"  ⏭️ 已有 credit 记录 (id={already[0]})，跳过")
            continue

        r = try_fulfill(
            conn,
            out_trade_no=otn,
            transaction_id=payment_id or f"backfill_{otn}",
            amount_fen=int(amount),
            channel_tag="dodo_backfill",
        )
        if r.get("ok"):
            print(f"  ✅ 补单成功: {r}")
        else:
            print(f"  ❌ 补单失败: {r}")

    conn.close()
    print("\n=== 补单完成 ===")


if __name__ == "__main__":
    asyncio.run(main())
