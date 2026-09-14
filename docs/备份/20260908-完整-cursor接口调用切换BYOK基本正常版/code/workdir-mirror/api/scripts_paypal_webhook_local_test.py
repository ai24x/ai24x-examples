"""
本机伪造 PayPal Webhook 履约路径（不依赖真商户推送）。

用法（在 api/ 目录，需能连库且 TOKEN_PAY_ENABLED=true）：
  python scripts_paypal_webhook_local_test.py --user-id 1
  python scripts_paypal_webhook_local_test.py --out-trade-no T...

sandbox / 本机：webhook 路由允许未验签进入履约。
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid

import httpx


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8000", help="API 根")
    ap.add_argument("--user-id", type=int, default=0, help="若无 out_trade_no，则先 mock 建 pending 需内部密钥")
    ap.add_argument("--out-trade-no", default="", help="已有 pending 单号（T 前缀）")
    ap.add_argument("--plan", default="token_pack_10k")
    ap.add_argument("--amount-cents", type=int, default=0, help="USD 美分；0 则从订单读")
    ap.add_argument("--internal-key", default="", help="X-SMS-Internal-Key（建单用）")
    args = ap.parse_args()
    base = args.base.rstrip("/")

    otn = (args.out_trade_no or "").strip()
    cents = int(args.amount_cents or 0)

    if not otn:
        if not args.user_id or not args.internal_key:
            print("需要 --out-trade-no，或同时提供 --user-id 与 --internal-key 以建 pending", file=sys.stderr)
            return 2
        # 走 mock 下单不现实（要真 PayPal）；直接 DB 插入太重。
        # 改用 admin 无法建 pending —— 用 create 需登录。
        # 简化：要求运维先有 pending，或用 token_pay_service 本地插入。
        from database import SessionLocal, init_db
        from token_pay_service import create_pending_order

        init_db()
        db = SessionLocal()
        try:
            row = create_pending_order(
                db, auth_user_id=int(args.user_id), plan=args.plan, channel="paypal"
            )
            otn = row.out_trade_no
            cents = int(row.amount_fen or 0)
            print("created pending", otn, "cents", cents)
        finally:
            db.close()

    if cents <= 0:
        from database import SessionLocal
        from models import TokenPayOrder

        db = SessionLocal()
        try:
            row = db.query(TokenPayOrder).filter(TokenPayOrder.out_trade_no == otn).first()
            if not row:
                print("order not found", otn, file=sys.stderr)
                return 3
            cents = int(row.amount_fen or 0)
        finally:
            db.close()

    cap_id = "LOCAL_CAP_" + uuid.uuid4().hex[:12]
    # PayPal CAPTURE.COMPLETED 风格：custom_id + amount.value
    event = {
        "event_type": "PAYMENT.CAPTURE.COMPLETED",
        "resource": {
            "id": cap_id,
            "custom_id": otn,
            "amount": {"currency_code": "USD", "value": f"{cents / 100:.2f}"},
            "status": "COMPLETED",
        },
    }
    url = f"{base}/v1/billing/paypal/webhook"
    r = httpx.post(url, content=json.dumps(event), headers={"Content-Type": "application/json"}, timeout=30.0)
    print("HTTP", r.status_code, r.text[:500])
    if r.status_code != 200:
        return 4
    try:
        j = r.json()
    except Exception:
        return 5
    if not j.get("ok"):
        print("fulfill not ok", j, file=sys.stderr)
        return 6
    print("OK webhook fulfill", j.get("out_trade_no") or otn)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
