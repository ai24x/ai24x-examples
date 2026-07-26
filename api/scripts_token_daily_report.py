#!/usr/bin/env python3
"""
Token 用量/成本日报草稿（Phase 1）。

用法（在 api/ 目录）：
  python scripts_token_daily_report.py

默认打印到 stdout；设 FEISHU_WEBHOOK_URL 时可 POST（未配则跳过）。
不依赖飞书 SDK，失败不影响主流程。
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 保证可 import 同目录模块
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import func

from database import SessionLocal
from models import BillingLedger, ChatRequest, TokenPayOrder


def _cst_today_range():
    # 用 UTC 近似；生产可改为 Asia/Shanghai
    now = datetime.now(timezone.utc)
    start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    return start.replace(tzinfo=None), now.replace(tzinfo=None)


def build_report(db) -> dict:
    start, end = _cst_today_range()
    chats = (
        db.query(func.count(ChatRequest.id), func.coalesce(func.sum(ChatRequest.token_count), 0))
        .filter(ChatRequest.request_time >= start, ChatRequest.request_time < end)
        .first()
    )
    consume = (
        db.query(func.coalesce(func.sum(BillingLedger.amount), 0))
        .filter(
            BillingLedger.created_at >= start,
            BillingLedger.created_at < end,
            BillingLedger.entry_type == "consume",
        )
        .scalar()
    )
    topup = (
        db.query(func.coalesce(func.sum(BillingLedger.amount), 0))
        .filter(
            BillingLedger.created_at >= start,
            BillingLedger.created_at < end,
            BillingLedger.entry_type.in_(("topup", "bonus", "referral")),
        )
        .scalar()
    )
    paid_fen = (
        db.query(func.coalesce(func.sum(TokenPayOrder.amount_fen), 0))
        .filter(
            TokenPayOrder.created_at >= start,
            TokenPayOrder.created_at < end,
            TokenPayOrder.status == "paid",
        )
        .scalar()
    )
    chat_n = int(chats[0] or 0) if chats else 0
    chat_tokens = int(chats[1] or 0) if chats else 0
    return {
        "date_utc": start.date().isoformat(),
        "chat_requests": chat_n,
        "chat_tokens_recorded": chat_tokens,
        "ledger_consume_tokens": int(consume or 0),
        "ledger_credit_tokens": int(topup or 0),
        "paid_amount_fen": int(paid_fen or 0),
        "paid_amount_yuan": f"{int(paid_fen or 0) / 100:.2f}",
        "note": "上游真实成本需另接 DeepSeek/硅基账单；本报仅平台侧用量与收款。",
    }


def maybe_feishu(text: str) -> None:
    url = (os.getenv("FEISHU_WEBHOOK_URL") or "").strip()
    if not url:
        return
    try:
        import httpx

        httpx.post(url, json={"msg_type": "text", "content": {"text": text}}, timeout=10.0)
    except Exception as e:
        print(f"[feishu skipped] {e}", file=sys.stderr)


def main() -> int:
    db = SessionLocal()
    try:
        rep = build_report(db)
    finally:
        db.close()
    lines = [
        f"[AI24X Token 日报] {rep['date_utc']} UTC",
        f"chat 次数: {rep['chat_requests']}",
        f"chat 记录 token: {rep['chat_tokens_recorded']}",
        f"账本消耗: {rep['ledger_consume_tokens']}",
        f"账本入账: {rep['ledger_credit_tokens']}",
        f"支付到账: ¥{rep['paid_amount_yuan']}",
        rep["note"],
    ]
    text = "\n".join(lines)
    print(text)
    maybe_feishu(text)
    print("--- json ---")
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
