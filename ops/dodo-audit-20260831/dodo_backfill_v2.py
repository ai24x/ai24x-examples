"""
Dodo 补单脚本（v2）：查询 user 46 的 pending Dodo 订单，
通过 Dodo API 查实际支付状态，只补已支付的。

用法：python dodo_backfill_v2.py [--dry-run] [--fulfill]
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import asyncio
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
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "")
if not DATABASE_URL:
    # fallback: 直接读 .env
    for line in open(env_path, encoding="utf-8"):
        line = line.strip()
        if line.startswith("DATABASE_URL="):
            DATABASE_URL = line.split("=", 1)[1].strip().strip('"').strip("'")
            break

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)


def dodo_base():
    mode = os.environ.get("DODO_MODE", "test").strip().lower()
    return "https://live.dodopayments.com" if mode in ("live", "production", "prod") else "https://test.dodopayments.com"


async def query_dodo_session(api_key: str, session_id: str) -> dict:
    url = f"{dodo_base()}/checkouts/{session_id}"
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(url, headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        })
    try:
        return r.json()
    except Exception:
        return {"raw": r.text, "status_code": r.status_code}


async def main():
    dry_run = "--fulfill" not in sys.argv

    api_key = os.environ.get("DODO_API_KEY", "").strip()
    if not api_key:
        print("ERROR: DODO_API_KEY not set")
        return

    db = SessionLocal()

    # 查询 user 46 的所有 pending Dodo 订单
    rows = db.execute(text("""
        SELECT id, out_trade_no, plan, amount_fen, transaction_id, created_at, status
        FROM token_pay_orders
        WHERE auth_user_id = 46 AND channel = 'dodo' AND status = 'pending'
        ORDER BY id
    """)).fetchall()

    print(f"\n=== 找到 {len(rows)} 笔 pending Dodo 订单 (user 46) ===\n")

    paid_list = []
    unpaid_list = []

    for row in rows:
        oid, otn, plan, amount, txn_id, created, status = row
        print(f"--- id={oid} | {otn} | {plan} | ${amount/100:.2f} | {created} ---")

        if not txn_id:
            print(f"  ⚠️ 无 transaction_id，跳过")
            unpaid_list.append(row)
            continue

        result = await query_dodo_session(api_key, txn_id)
        dodo_status = str(result.get("status") or result.get("payment_status") or "").lower()
        payment_id = str(result.get("payment_id") or "").strip()
        print(f"  Dodo 状态: {dodo_status} | payment_id: {payment_id or 'N/A'}")
        print(f"  Dodo 原始: {result}")

        if dodo_status in ("paid", "succeeded", "completed"):
            paid_list.append((row, payment_id))
            print(f"  [PAID] will fulfill")
        else:
            unpaid_list.append(row)
            print(f"  [UNPAID] skip")

        await asyncio.sleep(0.3)

    print(f"\n=== 汇总 ===")
    print(f"已支付待补单: {len(paid_list)} 笔")
    print(f"未支付/跳过:  {len(unpaid_list)} 笔")

    if not paid_list:
        print("\n没有需要补单的订单。")
        db.close()
        return

    if dry_run:
        print("\n[DRY RUN] 不执行补单。加 --fulfill 参数执行实际补单。")
        db.close()
        return

    # 执行补单
    print("\n=== 开始补单 ===")
    from token_pay_service import try_fulfill

    for (row, payment_id) in paid_list:
        oid, otn, plan, amount, txn_id, created, status = row
        print(f"\n补单: id={oid} {otn} ({plan}) ...")

        # 幂等检查
        existing = db.execute(text("""
            SELECT id FROM billing_ledger
            WHERE note LIKE :pat AND entry_type = 'credit' LIMIT 1
        """), {"pat": f"%{otn}%"}).fetchone()
        if existing:
            print(f"  ⏭️ 已有 credit 记录 (id={existing[0]})，跳过")
            continue

        r = try_fulfill(
            db,
            out_trade_no=otn,
            transaction_id=payment_id or f"backfill_{otn}",
            amount_fen=int(amount),
            channel_tag="dodo_backfill",
        )
        if r.get("ok"):
            print(f"  ✅ 补单成功")
        else:
            print(f"  ❌ 补单失败: {r}")

    db.close()
    print("\n=== 补单完成 ===")


if __name__ == "__main__":
    asyncio.run(main())
