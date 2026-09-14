#!/usr/bin/env python3
"""上线前遗留测试支付订单清理（只读默认，--apply 才改库）。

背景：本地/生产在正式上线前产生过大量测试支付单，会触发 pay_pending_backlog /
pay_failed_spike 等预警。本脚本把 created_at < --before 的 pending / failed 单
统一标记为 cancelled（不计入待履约与失败统计），paid 单一律不动。

用法（在 api/ 目录）：
  python scripts_clean_test_orders.py                    # dry-run 预览
  python scripts_clean_test_orders.py --apply            # 执行（默认清理 2026-08-05 前数据）
  python scripts_clean_test_orders.py --apply --before 2026-08-05 --reset-alerts
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

from sqlalchemy import func

from database import SessionLocal
from models import TokenPayOrder


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="真正执行（默认 dry-run 只预览）")
    ap.add_argument("--before", default="2026-08-05", help="只清理创建时间早于该日期的单（默认 2026-08-05 上线日）")
    ap.add_argument("--max", type=int, default=500, help="单次修改保护上限（默认 500）")
    ap.add_argument("--reset-alerts", action="store_true", help="清理后同时重置预警状态（active 标记清空）")
    args = ap.parse_args()

    before = dt.datetime.strptime(args.before, "%Y-%m-%d").replace(
        tzinfo=dt.timezone.utc
    )
    db = SessionLocal()
    try:
        rows = (
            db.query(TokenPayOrder)
            .filter(
                TokenPayOrder.created_at < before,
                TokenPayOrder.status.in_(("pending", "failed")),
            )
            .all()
        )
        by_status: dict[str, int] = {}
        by_channel: dict[str, int] = {}
        for r in rows:
            by_status[str(r.status)] = by_status.get(str(r.status), 0) + 1
            ch = str(r.channel or "?")
            by_channel[ch] = by_channel.get(ch, 0) + 1
        d0 = min((r.created_at for r in rows), default=None)
        d1 = max((r.created_at for r in rows), default=None)

        out = {
            "ok": True,
            "mode": "apply" if args.apply else "dry-run",
            "before": args.before,
            "candidates": len(rows),
            "by_status": by_status,
            "by_channel": by_channel,
            "date_range": [d0.date().isoformat() if d0 else None, d1.date().isoformat() if d1 else None],
            "paid_untouched": int(
                db.query(func.count(TokenPayOrder.id))
                .filter(TokenPayOrder.created_at < before, TokenPayOrder.status == "paid")
                .scalar()
                or 0
            ),
        }

        if args.apply and rows:
            if len(rows) > args.max:
                out["ok"] = False
                out["error"] = f"candidates {len(rows)} > 保护上限 {args.max}，已中止（可用 --max 调整）"
                print(json.dumps(out, ensure_ascii=False, indent=2))
                return 1
            for r in rows:
                r.status = "cancelled"
            db.commit()
            out["cancelled"] = len(rows)

        if args.apply and args.reset_alerts:
            from ops_alert import reset_state

            reset_state()
            out["alerts_reset"] = True

        print(json.dumps(out, ensure_ascii=False, indent=2))
        if not args.apply:
            print("\n[提示] dry-run 未修改任何订单；确认后加 --apply 执行。")
        return 0 if out.get("ok") else 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())