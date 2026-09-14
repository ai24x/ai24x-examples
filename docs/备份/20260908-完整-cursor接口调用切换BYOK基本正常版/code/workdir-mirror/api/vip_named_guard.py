# -*- coding: utf-8 -*-
"""P2 保护：VIP 点名模每日用量上限（单模型次数 / 单用户 credits），超限 429。

表 vip_named_daily_usage 由 init_db() 自动建表；阈值可用环境变量覆盖：
VIP_NAMED_DAILY_CALLS_PER_MODEL / VIP_NAMED_DAILY_CREDITS_PER_USER。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from config import settings
from models import VipNamedDailyUsage


def usage_date(now: Optional[datetime] = None) -> str:
    return (now or datetime.now(timezone.utc)).strftime("%Y-%m-%d")


def _canonical_model_id(model_id: str) -> str:
    """别名归一为规范 vip id（gpt-5 / openai / gpt5 → vip-gpt5），防换别名绕过单模型日上限。"""
    try:
        from model_warehouse import resolve_vip_pick

        pick = resolve_vip_pick(str(model_id or ""))
        if pick and pick.get("id"):
            return str(pick["id"])
    except Exception:
        pass
    return str(model_id or "")


def _row(db: Session, auth_user_id: int, model_id: str, day: str) -> VipNamedDailyUsage:
    model_id = _canonical_model_id(model_id)
    row = (
        db.query(VipNamedDailyUsage)
        .filter(
            VipNamedDailyUsage.auth_user_id == int(auth_user_id),
            VipNamedDailyUsage.model_id == str(model_id),
            VipNamedDailyUsage.usage_date == day,
        )
        .first()
    )
    if row is None:
        row = VipNamedDailyUsage(
            auth_user_id=int(auth_user_id),
            model_id=str(model_id),
            usage_date=day,
            call_count=0,
            credits_used=0,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def check_named_daily_limit(db: Session, auth_user_id: int, model_id: str) -> None:
    """点名模请求前检查；超限抛 429（HTTPException），未超限静默通过。"""
    max_calls = max(1, int(settings.vip_named_daily_calls_per_model or 200))
    max_credits = max(1, int(settings.vip_named_daily_credits_per_user or 50000))
    day = usage_date()
    row = _row(db, int(auth_user_id), str(model_id), day)
    if int(row.call_count or 0) >= max_calls:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "message_zh": "该模型今日点名次数已达上限（{n} 次），请明日再试或改用 flash/pro。".format(n=max_calls),
                "message_en": "Daily named-model call limit reached for this model ({n}/day). Try flash/pro or come back tomorrow.".format(n=max_calls),
                "message": "Daily named-model call limit reached ({n}/day).".format(n=max_calls),
                "code": "named_daily_limit",
            },
        )
    if int(row.credits_used or 0) >= max_credits:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "message_zh": "今日点名模消耗已达上限（{n} credits），请明日再试或改用 flash/pro。".format(n=max_credits),
                "message_en": "Daily named-model credit limit reached ({n} credits). Try flash/pro or come back tomorrow.".format(n=max_credits),
                "message": "Daily named-model credit limit reached ({n} credits).".format(n=max_credits),
                "code": "named_daily_limit",
            },
        )


def record_named_usage(db: Session, auth_user_id: int, model_id: str, credits_used: int) -> None:
    """点名模请求成功后累加计数（请求前 check 已建行，此处直接累加）。"""
    day = usage_date()
    row = _row(db, int(auth_user_id), str(model_id), day)
    row.call_count = int(row.call_count or 0) + 1
    row.credits_used = int(row.credits_used or 0) + max(0, int(credits_used or 0))
    db.commit()
