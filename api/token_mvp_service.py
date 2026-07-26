"""Token 聚合 MVP：API Keys / 钱包计费 / 推荐返利。"""

from __future__ import annotations

import secrets
import string
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models import (
    ApiKey,
    AuthUser,
    BillingLedger,
    BillingPlan,
    InviteCode,
    Referral,
    TokenWallet,
    User,
    UserType,
)

# —— 配额口径（MVP 简化；后续可配进 system_configs）——
FREE_MONTHLY_BONUS_TOKENS = 10_000
VIP_DAILY_BONUS_TOKENS = 500_000
REFERRAL_L1_BPS = 1000  # 10%（被邀请人充值时）
REFERRAL_L2_BPS = 200  # 2%
# 邀请注册即时奖励：双方各得（与总纲「邀请双方各得」对齐）
REFERRAL_REGISTER_BONUS_TOKENS = 5_000


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _period_month(now: Optional[datetime] = None) -> str:
    d = now or _utcnow()
    return f"{d.year:04d}-{d.month:02d}"


def _period_day(now: Optional[datetime] = None) -> str:
    d = now or _utcnow()
    return f"{d.year:04d}-{d.month:02d}-{d.day:02d}"


def _gen_api_key() -> str:
    return f"sk-{uuid.uuid4().hex}{secrets.token_hex(8)}"


def _gen_invite_code(n: int = 8) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(n))


# —— Wallet ——


def get_or_create_wallet(db: Session, auth_user_id: int) -> TokenWallet:
    w = db.query(TokenWallet).filter(TokenWallet.auth_user_id == int(auth_user_id)).first()
    if w:
        return w
    w = TokenWallet(
        auth_user_id=int(auth_user_id),
        plan=BillingPlan.FREE,
        balance_tokens=0,
        bonus_period=None,
    )
    db.add(w)
    db.commit()
    db.refresh(w)
    return w


def ensure_vip_status(db: Session, wallet: TokenWallet) -> TokenWallet:
    """VIP 过期则降级为 FREE（不删余额）。"""
    if wallet.plan != BillingPlan.VIP:
        return wallet
    exp = wallet.vip_expires_at
    if exp is None:
        return wallet
    now = _utcnow()
    exp_naive = exp.replace(tzinfo=None) if getattr(exp, "tzinfo", None) else exp
    if exp_naive > now:
        return wallet
    wallet.plan = BillingPlan.FREE
    wallet.updated_at = now
    db.commit()
    db.refresh(wallet)
    return wallet


def extend_vip(db: Session, auth_user_id: int, *, days: int = 30) -> TokenWallet:
    """从 max(now, 当前到期) 起延长 VIP。"""
    days = max(1, int(days))
    w = get_or_create_wallet(db, auth_user_id)
    now = _utcnow()
    base = now
    if w.vip_expires_at is not None:
        exp = w.vip_expires_at
        exp_naive = exp.replace(tzinfo=None) if getattr(exp, "tzinfo", None) else exp
        if exp_naive > now:
            base = exp_naive
    w.plan = BillingPlan.VIP
    w.vip_expires_at = base + timedelta(days=days)
    w.updated_at = now
    db.commit()
    db.refresh(w)
    return w


def ensure_period_bonus(db: Session, wallet: TokenWallet) -> TokenWallet:
    """FREE 按月赠送；VIP 按日补充额度（MVP：直接加余额并记账）。"""
    wallet = ensure_vip_status(db, wallet)
    now = _utcnow()
    if wallet.plan == BillingPlan.VIP:
        period = _period_day(now)
        amount = VIP_DAILY_BONUS_TOKENS
        note = "VIP 日额度"
    else:
        period = _period_month(now)
        amount = FREE_MONTHLY_BONUS_TOKENS
        note = "FREE 月赠额度"

    if wallet.bonus_period == period:
        return wallet

    wallet.balance_tokens = int(wallet.balance_tokens or 0) + int(amount)
    wallet.bonus_period = period
    wallet.updated_at = now
    db.add(
        BillingLedger(
            auth_user_id=int(wallet.auth_user_id),
            entry_type="bonus",
            amount=int(amount),
            tokens=int(amount),
            note=f"{note} {period}",
        )
    )
    db.commit()
    db.refresh(wallet)
    return wallet


def get_balance_snapshot(db: Session, auth_user_id: int) -> dict:
    w = ensure_period_bonus(db, get_or_create_wallet(db, auth_user_id))
    exp = w.vip_expires_at
    return {
        "auth_user_id": int(auth_user_id),
        "plan": w.plan.value if hasattr(w.plan, "value") else str(w.plan),
        "balance_tokens": int(w.balance_tokens or 0),
        "bonus_period": w.bonus_period,
        "free_monthly_bonus": FREE_MONTHLY_BONUS_TOKENS,
        "vip_daily_bonus": VIP_DAILY_BONUS_TOKENS,
        "vip_expires_at": exp.isoformat() if exp else None,
        "is_vip_active": bool(
            w.plan == BillingPlan.VIP
            and (exp is None or (exp.replace(tzinfo=None) if getattr(exp, "tzinfo", None) else exp) > _utcnow())
        ),
    }


def assert_can_spend(db: Session, auth_user_id: int, need_tokens: int = 1) -> TokenWallet:
    w = ensure_period_bonus(db, get_or_create_wallet(db, auth_user_id))
    bal = int(w.balance_tokens or 0)
    if bal <= 0:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="余额不足，请充值或等待下期赠送额度",
        )
    if bal < int(need_tokens):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"额度不足（余额 {bal} token，本次预估 {need_tokens}）",
        )
    return w


def consume_tokens(
    db: Session,
    *,
    auth_user_id: int,
    tokens: int,
    model: Optional[str] = None,
    request_id: Optional[str] = None,
) -> TokenWallet:
    tokens = max(0, int(tokens))
    w = ensure_period_bonus(db, get_or_create_wallet(db, auth_user_id))
    if tokens <= 0:
        return w
    bal = int(w.balance_tokens or 0)
    if bal < tokens:
        # 成功响应后尽量扣光，避免因估算偏差导致负账；不足部分记 0
        tokens = bal
    if tokens <= 0:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="余额不足，请充值",
        )
    w.balance_tokens = bal - tokens
    w.updated_at = _utcnow()
    db.add(
        BillingLedger(
            auth_user_id=int(auth_user_id),
            entry_type="consume",
            amount=-int(tokens),
            model=(model or "")[:64] or None,
            tokens=int(tokens),
            request_id=request_id,
            note="chat/run",
        )
    )
    db.commit()
    db.refresh(w)
    return w


def topup_tokens(
    db: Session,
    *,
    auth_user_id: int,
    amount: int,
    note: Optional[str] = None,
    set_vip: bool = False,
    vip_days: int = 30,
) -> dict:
    amount = int(amount)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="充值数量必须为正整数")
    u = db.query(AuthUser).filter(AuthUser.id == int(auth_user_id)).first()
    if not u:
        raise HTTPException(status_code=404, detail="用户不存在")
    w = get_or_create_wallet(db, auth_user_id)
    if set_vip:
        extend_vip(db, auth_user_id, days=int(vip_days) if vip_days else 30)
        w = get_or_create_wallet(db, auth_user_id)
    w.balance_tokens = int(w.balance_tokens or 0) + amount
    w.updated_at = _utcnow()
    ledger = BillingLedger(
        auth_user_id=int(auth_user_id),
        entry_type="topup",
        amount=amount,
        tokens=amount,
        note=(note or "topup")[:255],
    )
    db.add(ledger)
    db.commit()
    db.refresh(w)
    db.refresh(ledger)
    # 首次充值触发推荐返利
    try:
        settle_referral_on_topup(db, referee_id=int(auth_user_id), topup_amount=amount, topup_ledger_id=int(ledger.id))
    except Exception:
        pass
    return get_balance_snapshot(db, auth_user_id)


def list_usage(
    db: Session,
    auth_user_id: int,
    *,
    limit: int = 50,
    offset: int = 0,
    entry_type: Optional[str] = None,
) -> dict:
    q = db.query(BillingLedger).filter(BillingLedger.auth_user_id == int(auth_user_id))
    if entry_type:
        q = q.filter(BillingLedger.entry_type == entry_type)
    total = q.count()
    rows = (
        q.order_by(BillingLedger.id.desc())
        .offset(max(0, int(offset)))
        .limit(min(200, max(1, int(limit))))
        .all()
    )
    return {
        "total": total,
        "limit": min(200, max(1, int(limit))),
        "offset": max(0, int(offset)),
        "rows": [
            {
                "id": r.id,
                "type": r.entry_type,
                "amount": r.amount,
                "model": r.model,
                "tokens": r.tokens,
                "request_id": r.request_id,
                "note": r.note,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }


# —— API Keys ——


def list_api_keys(db: Session, auth_user_id: int) -> list[dict]:
    rows = (
        db.query(ApiKey)
        .filter(ApiKey.auth_user_id == int(auth_user_id), ApiKey.is_active.is_(True))
        .order_by(ApiKey.id.desc())
        .all()
    )
    return [
        {
            "id": r.id,
            "name": r.name,
            "key_prefix": r.key_prefix,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "last_used_at": r.last_used_at.isoformat() if r.last_used_at else None,
            "is_active": bool(r.is_active),
        }
        for r in rows
    ]


def create_api_key(db: Session, auth_user_id: int, name: str = "默认密钥") -> dict:
    from security_util import hash_api_key

    name = (name or "默认密钥").strip()[:64] or "默认密钥"
    raw = _gen_api_key()
    prefix = raw[:10]
    row = ApiKey(
        auth_user_id=int(auth_user_id),
        name=name,
        api_key=hash_api_key(raw),  # 仅存哈希，防拖库拷贝
        key_prefix=prefix,
        is_active=True,
    )
    db.add(row)
    # 确保网关 User 存在，便于 chat/run 兼容
    ensure_gateway_user(db, auth_user_id)
    get_or_create_wallet(db, auth_user_id)
    db.commit()
    db.refresh(row)
    return {
        "id": row.id,
        "name": row.name,
        "api_key": raw,  # 仅创建时返回完整密钥
        "key_prefix": row.key_prefix,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "is_active": True,
        "warning": "请立即保存完整 api_key，之后无法再次查看明文；列表仅显示前缀。禁止分享给他人。",
    }


def delete_api_key(db: Session, auth_user_id: int, key_id: int) -> dict:
    row = (
        db.query(ApiKey)
        .filter(ApiKey.id == int(key_id), ApiKey.auth_user_id == int(auth_user_id))
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="API Key 不存在")
    row.is_active = False
    db.commit()
    return {"ok": True, "id": int(key_id)}


def get_api_key_row(db: Session, api_key: str) -> Optional[ApiKey]:
    from security_util import hash_api_key, is_hashed_api_key

    k = (api_key or "").strip()
    if not k:
        return None
    hashed = hash_api_key(k)
    row = db.query(ApiKey).filter(ApiKey.api_key == hashed, ApiKey.is_active.is_(True)).first()
    if row:
        return row
    # 遗留明文：等值匹配后升级为哈希
    row = db.query(ApiKey).filter(ApiKey.api_key == k, ApiKey.is_active.is_(True)).first()
    if row and not is_hashed_api_key(str(row.api_key or "")):
        row.api_key = hashed
        db.commit()
        db.refresh(row)
        return row
    return None


def touch_api_key(db: Session, row: ApiKey) -> None:
    row.last_used_at = _utcnow()
    db.commit()


# 网关日/月请求上限（与总纲 Phase 1：FREE 日 100 防刷一致）
GATEWAY_FREE_DAILY_REQ = 100
GATEWAY_FREE_MONTHLY_REQ = 3_000
GATEWAY_VIP_DAILY_REQ = 100_000
GATEWAY_VIP_MONTHLY_REQ = 3_000_000


def _gateway_limits(ut: UserType) -> tuple[int, int]:
    if ut == UserType.VIP:
        return GATEWAY_VIP_DAILY_REQ, GATEWAY_VIP_MONTHLY_REQ
    return GATEWAY_FREE_DAILY_REQ, GATEWAY_FREE_MONTHLY_REQ


def ensure_gateway_user(db: Session, auth_user_id: int) -> User:
    """chat/run 仍走 User 表；用 auth_{id} 作为稳定 user_id。"""
    uid = f"auth_{int(auth_user_id)}"
    w = get_or_create_wallet(db, auth_user_id)
    ut = UserType.VIP if w.plan == BillingPlan.VIP else UserType.FREE
    daily, monthly = _gateway_limits(ut)
    u = db.query(User).filter(User.user_id == uid).first()
    if u:
        # 同步档位与限额（纠正历史 FREE=10000 等宽限）
        dirty = False
        if u.user_type != ut:
            u.user_type = ut
            dirty = True
        if int(u.daily_request_limit or 0) != daily:
            u.daily_request_limit = daily
            dirty = True
        if int(u.monthly_request_limit or 0) != monthly:
            u.monthly_request_limit = monthly
            dirty = True
        if dirty:
            db.commit()
            db.refresh(u)
        return u
    u = User(
        user_id=uid,
        user_type=ut,
        api_key=None,
        daily_request_limit=daily,
        monthly_request_limit=monthly,
        is_active=True,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def resolve_chat_user_from_api_key(db: Session, api_key: str) -> tuple[User, int]:
    """返回 (gateway User, auth_user_id)。"""
    row = get_api_key_row(db, api_key)
    if not row:
        raise HTTPException(status_code=401, detail="无效的 API Key")
    touch_api_key(db, row)
    gateway = ensure_gateway_user(db, int(row.auth_user_id))
    return gateway, int(row.auth_user_id)


# —— Referrals ——


def get_or_create_invite_code(db: Session, auth_user_id: int) -> InviteCode:
    row = db.query(InviteCode).filter(InviteCode.auth_user_id == int(auth_user_id)).first()
    if row:
        return row
    for _ in range(8):
        code = _gen_invite_code(8)
        if not db.query(InviteCode).filter(InviteCode.code == code).first():
            row = InviteCode(auth_user_id=int(auth_user_id), code=code)
            db.add(row)
            db.commit()
            db.refresh(row)
            return row
    raise HTTPException(status_code=500, detail="邀请码生成失败")


def _grant_register_invite_bonus(
    db: Session,
    *,
    referrer_id: int,
    referee_id: int,
    client_ip: Optional[str] = None,
) -> None:
    amount = int(REFERRAL_REGISTER_BONUS_TOKENS)
    if amount <= 0:
        return
    try:
        from referral_abuse import allow_register_invite_bonus

        ok, reason = allow_register_invite_bonus(referrer_id=int(referrer_id), client_ip=client_ip)
        if not ok:
            # 关系已绑定；仅跳过即时奖励（防刷）
            import logging

            logging.getLogger(__name__).info(
                "skip invite register bonus referrer=%s referee=%s reason=%s",
                referrer_id,
                referee_id,
                reason,
            )
            return
    except Exception:
        pass
    # 防重复：邀请人侧已有同 note 入账则跳过
    dup = (
        db.query(BillingLedger)
        .filter(
            BillingLedger.auth_user_id == int(referrer_id),
            BillingLedger.entry_type == "referral",
            BillingLedger.note == f"invite_register_bonus referee={int(referee_id)}",
        )
        .first()
    )
    if dup:
        return
    for uid, note in (
        (int(referrer_id), f"invite_register_bonus referee={int(referee_id)}"),
        (int(referee_id), f"invite_register_bonus referrer={int(referrer_id)}"),
    ):
        w = get_or_create_wallet(db, uid)
        w.balance_tokens = int(w.balance_tokens or 0) + amount
        w.updated_at = _utcnow()
        db.add(
            BillingLedger(
                auth_user_id=uid,
                entry_type="referral",
                amount=amount,
                tokens=amount,
                note=note,
            )
        )
    db.commit()


def bind_referral_on_register(
    db: Session,
    *,
    referee_id: int,
    invite_code: Optional[str],
    client_ip: Optional[str] = None,
) -> None:
    code = (invite_code or "").strip().upper()
    if not code:
        return
    inv = db.query(InviteCode).filter(InviteCode.code == code).first()
    if not inv or int(inv.auth_user_id) == int(referee_id):
        return
    exists = (
        db.query(Referral)
        .filter(Referral.referee_id == int(referee_id), Referral.level == 1)
        .first()
    )
    if exists:
        return
    referrer_id = int(inv.auth_user_id)
    # L1
    db.add(
        Referral(
            referrer_id=referrer_id,
            referee_id=int(referee_id),
            level=1,
            reward_tokens=0,
            status="pending",
        )
    )
    # L2：邀请人的上级
    parent = (
        db.query(Referral)
        .filter(Referral.referee_id == referrer_id, Referral.level == 1)
        .first()
    )
    if parent:
        db.add(
            Referral(
                referrer_id=int(parent.referrer_id),
                referee_id=int(referee_id),
                level=2,
                reward_tokens=0,
                status="pending",
            )
        )
    db.commit()
    # 注册即时奖励：双方各得（仅成功绑定一次；受反作弊频控）
    _grant_register_invite_bonus(
        db, referrer_id=referrer_id, referee_id=int(referee_id), client_ip=client_ip
    )


def settle_referral_on_topup(
    db: Session,
    *,
    referee_id: int,
    topup_amount: int,
    topup_ledger_id: int,
) -> None:
    """被邀请人首次充值后，给 L1/L2 发放 token 返利。"""
    # 仅首次成功充值触发：若已有 paid 记录则跳过
    paid = (
        db.query(Referral)
        .filter(Referral.referee_id == int(referee_id), Referral.status == "paid")
        .first()
    )
    if paid:
        return
    rows = (
        db.query(Referral)
        .filter(Referral.referee_id == int(referee_id), Referral.status == "pending")
        .all()
    )
    if not rows:
        return
    for r in rows:
        bps = REFERRAL_L1_BPS if int(r.level) == 1 else REFERRAL_L2_BPS
        reward = max(0, int(topup_amount) * int(bps) // 10000)
        r.reward_tokens = reward
        r.status = "paid"
        r.topup_ledger_id = int(topup_ledger_id)
        if reward > 0:
            w = get_or_create_wallet(db, int(r.referrer_id))
            w.balance_tokens = int(w.balance_tokens or 0) + reward
            w.updated_at = _utcnow()
            db.add(
                BillingLedger(
                    auth_user_id=int(r.referrer_id),
                    entry_type="referral",
                    amount=reward,
                    tokens=reward,
                    note=f"L{r.level} 返利 from user {referee_id}",
                )
            )
    db.commit()


def referral_stats(db: Session, auth_user_id: int) -> dict:
    rows = db.query(Referral).filter(Referral.referrer_id == int(auth_user_id)).all()
    l1 = [r for r in rows if int(r.level) == 1]
    l2 = [r for r in rows if int(r.level) == 2]
    earned = sum(int(r.reward_tokens or 0) for r in rows if r.status == "paid")
    pending = sum(1 for r in rows if r.status == "pending")
    return {
        "invitees_l1": len(l1),
        "invitees_l2": len(l2),
        "earned_tokens": earned,
        "pending_count": pending,
    }


def referral_earnings(db: Session, auth_user_id: int, *, limit: int = 50, offset: int = 0) -> dict:
    q = db.query(Referral).filter(Referral.referrer_id == int(auth_user_id))
    total = q.count()
    rows = (
        q.order_by(Referral.id.desc())
        .offset(max(0, int(offset)))
        .limit(min(200, max(1, int(limit))))
        .all()
    )
    return {
        "total": total,
        "rows": [
            {
                "id": r.id,
                "referee_id": r.referee_id,
                "level": r.level,
                "reward_tokens": r.reward_tokens,
                "status": r.status,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }
