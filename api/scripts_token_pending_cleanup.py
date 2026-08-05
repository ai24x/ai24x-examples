#!/usr/bin/env python3
"""Token 超时未付订单清理（防积压）。

默认 dry-run 只预览；--apply 才真正作废（无渠道交易号、或已确认未收款 confirmed_unpaid_at 非空的超时 pending 单）。

用法（在 api/ 目录）：
  python scripts_token_pending_cleanup.py            # dry-run 预览
  python scripts_token_pending_cleanup.py --apply    # 执行作废

配套计划任务：scripts/register_pending_cleanup_cron.ps1（每天 06:00 跑一次 --apply）。
有 transaction_id 且未确认未收款的超时单不会作废，保留 pending 待渠道对账（见返回 kept_for_reconcile）。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

from database import SessionLocal
from token_pay_service import cleanup_expired_pending_orders


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="真正作废（默认 dry-run 只预览）")
    ap.add_argument("--max-void", type=int, default=200, help="单次作废保护上限（默认 200）")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        result = cleanup_expired_pending_orders(
            db, dry_run=not args.apply, max_void=args.max_void
        )
    finally:
        db.close()

    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not args.apply:
        print("\n[提示] 当前为 dry-run 预览，未修改任何订单；确认无误后用 --apply 执行。")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
