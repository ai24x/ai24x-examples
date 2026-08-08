"""Token 聚合 MVP：API Keys / 钱包计费 / 推荐返利。"""

from __future__ import annotations

import secrets
import string
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from models import (
    ApiKey,
    AuthUser,
    BillingLedger,
    BillingPlan,
    InviteCode,
    Referral,
    TokenCreditLot,
    TokenWallet,
    User,
    UserType,
)

# —— 配额口径（2026-07-30：关掉 FREE 月赠叠礼；注册一次性小礼包）——
FREE_MONTHLY_BONUS_TOKENS = 0  # 已关闭：避免与注册礼包叠得过松
VIP_DAILY_BONUS_TOKENS = 0  # 2026-08-05 取消 VIP 日赠：套餐只卖资格+额度，简化核算
REFERRAL_L1_BPS = 1000  # 10%（被邀请人充值时）
REFERRAL_L2_BPS = 200  # 2%
# 邀请注册即时奖励：双方各得（与总纲「邀请双方各得」对齐）
REFERRAL_REGISTER_BONUS_TOKENS = 5_000
# 无邀请码也发：注册欢迎礼（一次性；防刷靠 OTP + 可选邀请频控）
SIGNUP_BONUS_TOKENS = 5_000
SIGNUP_BONUS_VALIDITY_DAYS = 365
# 预充值默认 12 个月；大包可在套餐里写 730
DEFAULT_PACK_VALIDITY_DAYS = 365
# 赠送窗口：FREE 月赠已关；VIP 日赠 2 天（跨日缓冲）
FREE_BONUS_VALIDITY_DAYS = 40
VIP_BONUS_VALIDITY_DAYS = 2
REFERRAL_VALIDITY_DAYS = 365
LEGACY_VALIDITY_DAYS = 365


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _as_naive(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    return dt.replace(tzinfo=None) if getattr(dt, "tzinfo", None) else dt


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


# —— Wallet / credit lots ——


def model_allows_vip_daily(model: Optional[str]) -> bool:
    """VIP 日赠仅可用于 flash/auto/共享档；pro/ultra/名模必须花预充额度。"""
    m = (model or "flash").strip().lower()
    if m.startswith("vip-"):
        return False
    if m in (
        "pro",
        "ultra",
        "or-pro",
        "or-ultra",
        "deepseek-pro",
        "deepseek-reasoner",
        "ds-v4-pro",
    ):
        return False
    if m in (
        "flash",
        "auto",
        "free",
        "shared",
        "free-shared",
        "free_shared",
        "or-flash",
        "deepseek-flash",
        "deepseek-chat",
        "ds-v4-flash",
        "",
    ):
        return True
    # 其它未知型号：不开放日赠，避免贵模漏扣
    return False


def _is_vip_daily_lot(db: Session, lot: TokenCreditLot) -> bool:
    src = (lot.source or "").strip().lower()
    if src == "vip_daily":
        return True
    if src != "bonus":
        return False
    # 兼容旧批次：source=bonus + 流水备注「VIP 日额度」
    if not lot.ledger_id:
        return False
    led = (
        db.query(BillingLedger.note)
        .filter(BillingLedger.id == int(lot.ledger_id))
        .first()
    )
    note = (led[0] if led else "") or ""
    return "VIP 日额度" in note or "VIP日额度" in note


def spendable_tokens(
    db: Session,
    auth_user_id: int,
    *,
    allow_vip_daily: bool = True,
    now: Optional[datetime] = None,
) -> int:
    now = now or _utcnow()
    total = 0
    for lot in _active_lots_q(db, int(auth_user_id), now).all():
        if not allow_vip_daily and _is_vip_daily_lot(db, lot):
            continue
        total += int(lot.amount_remaining or 0)
    return int(total)


def get_or_create_wallet(db: Session, auth_user_id: int) -> TokenWallet:
    w = db.query(TokenWallet).filter(TokenWallet.auth_user_id == int(auth_user_id)).first()
    if w:
        return w
    w = TokenWallet(
        auth_user_id=int(auth_user_id),
        plan=BillingPlan.FREE,
        balance_tokens=0,
        balance_usd=0,
        bonus_period=None,
    )
    db.add(w)
    db.commit()
    db.refresh(w)
    return w


def _active_lots_q(db: Session, auth_user_id: int, now: Optional[datetime] = None):
    now = now or _utcnow()
    return (
        db.query(TokenCreditLot)
        .filter(
            TokenCreditLot.auth_user_id == int(auth_user_id),
            TokenCreditLot.amount_remaining > 0,
            TokenCreditLot.expires_at > now,
        )
        .order_by(TokenCreditLot.expires_at.asc(), TokenCreditLot.id.asc())
    )


def _sum_active_lots(db: Session, auth_user_id: int, now: Optional[datetime] = None) -> int:
    now = now or _utcnow()
    v = (
        db.query(func.coalesce(func.sum(TokenCreditLot.amount_remaining), 0))
        .filter(
            TokenCreditLot.auth_user_id == int(auth_user_id),
            TokenCreditLot.amount_remaining > 0,
            TokenCreditLot.expires_at > now,
        )
        .scalar()
    )
    return int(v or 0)


def _expire_overdue_lots(db: Session, auth_user_id: int, *, commit: bool = False) -> int:
    """核销已到期批次；返回核销 token 数。"""
    now = _utcnow()
    rows = (
        db.query(TokenCreditLot)
        .filter(
            TokenCreditLot.auth_user_id == int(auth_user_id),
            TokenCreditLot.amount_remaining > 0,
            TokenCreditLot.expires_at <= now,
        )
        .all()
    )
    expired = 0
    for lot in rows:
        amt = int(lot.amount_remaining or 0)
        if amt <= 0:
            continue
        lot.amount_remaining = 0
        expired += amt
        db.add(
            BillingLedger(
                auth_user_id=int(auth_user_id),
                entry_type="expire",
                amount=-amt,
                tokens=amt,
                note=f"lot_expire id={lot.id}",
            )
        )
    if expired:
        w = get_or_create_wallet(db, auth_user_id)
        w.balance_tokens = max(0, int(w.balance_tokens or 0) - expired)
        w.updated_at = now
    if commit:
        db.commit()
    return expired


def _grandfather_legacy_balance(db: Session, wallet: TokenWallet) -> None:
    """上线前已有余额且无批次时，整包迁入 12 个月 legacy 批次。"""
    now = _utcnow()
    bal = int(wallet.balance_tokens or 0)
    if bal <= 0:
        return
    active = _sum_active_lots(db, int(wallet.auth_user_id), now)
    gap = bal - active
    if gap <= 0:
        return
    db.add(
        TokenCreditLot(
            auth_user_id=int(wallet.auth_user_id),
            source="legacy",
            plan=None,
            amount_initial=gap,
            amount_remaining=gap,
            expires_at=now + timedelta(days=LEGACY_VALIDITY_DAYS),
            ledger_id=None,
        )
    )


def sync_credit_lots(db: Session, wallet: TokenWallet, *, commit: bool = True) -> TokenWallet:
    """过期核销 + 存量迁批次；钱包余额对齐有效批次合计。"""
    uid = int(wallet.auth_user_id)
    _expire_overdue_lots(db, uid, commit=False)
    wallet = get_or_create_wallet(db, uid)
    _grandfather_legacy_balance(db, wallet)
    db.flush()
    now = _utcnow()
    active = _sum_active_lots(db, uid, now)
    wallet.balance_tokens = active
    wallet.updated_at = now
    if commit:
        db.commit()
        db.refresh(wallet)
    return wallet


def _credit_lot(
    db: Session,
    *,
    auth_user_id: int,
    amount: int,
    entry_type: str,
    source: str,
    validity_days: int,
    note: Optional[str] = None,
    plan: Optional[str] = None,
    commit: bool = True,
) -> BillingLedger:
    amount = int(amount)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="入账数量必须为正整数")
    days = max(1, int(validity_days or DEFAULT_PACK_VALIDITY_DAYS))
    now = _utcnow()
    w = get_or_create_wallet(db, auth_user_id)
    sync_credit_lots(db, w, commit=False)
    w = get_or_create_wallet(db, auth_user_id)
    ledger = BillingLedger(
        auth_user_id=int(auth_user_id),
        entry_type=str(entry_type)[:16],
        amount=amount,
        tokens=amount,
        note=(note or source)[:255],
    )
    db.add(ledger)
    db.flush()
    db.add(
        TokenCreditLot(
            auth_user_id=int(auth_user_id),
            source=str(source)[:16],
            plan=(plan or None),
            amount_initial=amount,
            amount_remaining=amount,
            expires_at=now + timedelta(days=days),
            ledger_id=int(ledger.id),
        )
    )
    w.balance_tokens = int(w.balance_tokens or 0) + amount
    w.updated_at = now
    if commit:
        db.commit()
        db.refresh(ledger)
    return ledger


def _nearest_lot_expiry(db: Session, auth_user_id: int) -> Optional[datetime]:
    lot = _active_lots_q(db, auth_user_id).first()
    return _as_naive(lot.expires_at) if lot else None


def ensure_vip_status(db: Session, wallet: TokenWallet) -> TokenWallet:
    """VIP 过期则降级为 FREE（不删余额）。无到期时间的 VIP 视为异常数据，同样降级，避免无限日赠。"""
    if wallet.plan != BillingPlan.VIP:
        return wallet
    exp = wallet.vip_expires_at
    now = _utcnow()
    if exp is None:
        wallet.plan = BillingPlan.FREE
        wallet.updated_at = now
        db.commit()
        db.refresh(wallet)
        return wallet
    exp_naive = _as_naive(exp)
    if exp_naive and exp_naive > now:
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
        exp_naive = _as_naive(w.vip_expires_at)
        if exp_naive and exp_naive > now:
            base = exp_naive
    w.plan = BillingPlan.VIP
    w.vip_expires_at = base + timedelta(days=days)
    w.updated_at = now
    db.commit()
    db.refresh(w)
    return w


def ensure_period_bonus(db: Session, wallet: TokenWallet) -> TokenWallet:
    """VIP 按日补充额度；FREE 月赠已关闭（amount=0 仅推进 period 标记）。"""
    wallet = ensure_vip_status(db, wallet)
    wallet = sync_credit_lots(db, wallet, commit=True)
    now = _utcnow()
    if wallet.plan == BillingPlan.VIP:
        period = _period_day(now)
        amount = VIP_DAILY_BONUS_TOKENS
        note = "VIP 日额度"
        validity = VIP_BONUS_VALIDITY_DAYS
    else:
        period = _period_month(now)
        amount = FREE_MONTHLY_BONUS_TOKENS
        note = "FREE 月赠额度"
        validity = FREE_BONUS_VALIDITY_DAYS

    if wallet.bonus_period == period:
        return wallet

    if int(amount) <= 0:
        wallet.bonus_period = period
        wallet.updated_at = now
        db.commit()
        db.refresh(wallet)
        return wallet

    from sqlalchemy import or_, update as sa_update

    # 原子抢占当日/当月 period，防并发双发
    claimed = db.execute(
        sa_update(TokenWallet)
        .where(
            TokenWallet.id == int(wallet.id),
            or_(TokenWallet.bonus_period.is_(None), TokenWallet.bonus_period != period),
        )
        .values(bonus_period=period, updated_at=now)
    )
    if int(getattr(claimed, "rowcount", 0) or 0) != 1:
        db.commit()
        return get_or_create_wallet(db, int(wallet.auth_user_id))

    full_note = f"{note} {period}"
    dup = (
        db.query(BillingLedger.id)
        .filter(
            BillingLedger.auth_user_id == int(wallet.auth_user_id),
            BillingLedger.entry_type == "bonus",
            BillingLedger.note == full_note,
        )
        .first()
    )
    if dup:
        db.commit()
        return get_or_create_wallet(db, int(wallet.auth_user_id))

    lot_source = "vip_daily" if wallet.plan == BillingPlan.VIP else "bonus"
    _credit_lot(
        db,
        auth_user_id=int(wallet.auth_user_id),
        amount=int(amount),
        entry_type="bonus",
        source=lot_source,
        validity_days=validity,
        note=full_note,
        commit=False,
    )
    db.commit()
    return get_or_create_wallet(db, int(wallet.auth_user_id))


def grant_signup_bonus(db: Session, auth_user_id: int) -> bool:
    """注册欢迎礼：一次性；已发过则跳过。返回是否新发放。"""
    amount = int(SIGNUP_BONUS_TOKENS)
    if amount <= 0:
        return False
    uid = int(auth_user_id)
    exists = (
        db.query(BillingLedger)
        .filter(
            BillingLedger.auth_user_id == uid,
            BillingLedger.entry_type == "bonus",
            BillingLedger.note == "signup_welcome",
        )
        .first()
    )
    if exists:
        return False
    get_or_create_wallet(db, uid)
    _credit_lot(
        db,
        auth_user_id=uid,
        amount=amount,
        entry_type="bonus",
        source="bonus",
        validity_days=SIGNUP_BONUS_VALIDITY_DAYS,
        note="signup_welcome",
        commit=True,
    )
    return True


def _plan_is_vip(plan: object) -> bool:
    raw = plan.value if hasattr(plan, "value") else str(plan or "")
    return str(raw).strip().lower() == "vip"


def wallet_vip_active(wallet: TokenWallet) -> bool:
    """与控制台 is_vip_active 同一口径（供路由与余额共用）。"""
    if not _plan_is_vip(wallet.plan):
        return False
    exp = wallet.vip_expires_at
    if exp is None:
        return False
    exp_naive = _as_naive(exp)
    if not exp_naive:
        return False
    return exp_naive > _utcnow()


VALUE_PACK_ACCESS_DAYS = 30  # 超值包（Value Pack）白名单点名资格有效期（自购买日起）


def _lot_value_pack_window_active(lot, now) -> bool:
    created = lot.created_at if lot is not None else None
    if created is None:
        return False
    created_naive = _as_naive(created)
    return bool(created_naive) and (created_naive + timedelta(days=VALUE_PACK_ACCESS_DAYS)) > now


def value_pack_allowed_models(db: Session, auth_user_id: int) -> Optional[set[str]]:
    """超值包（Value Pack）白名单点名资格：

    购买 30 天内且仍有未用额度的超值包批次存在时，返回白名单点名模型集合（catalog id）；否则 None。
    不开全量 VIP——白名单外的名模（国际旗舰等）仍会被路由拒绝（vip_required）。
    """
    from model_warehouse import VALUE_PACK_ALLOWED_IDS

    now = _utcnow()
    lots = (
        db.query(TokenCreditLot)
        .filter(
            TokenCreditLot.auth_user_id == int(auth_user_id),
            TokenCreditLot.plan == "token_value_pack",
            TokenCreditLot.amount_remaining > 0,
            TokenCreditLot.expires_at > now,
        )
        .all()
    )
    if not any(_lot_value_pack_window_active(lot, now) for lot in lots):
        return None
    return set(VALUE_PACK_ALLOWED_IDS)


def get_balance_snapshot(db: Session, auth_user_id: int) -> dict:
    w = ensure_period_bonus(db, get_or_create_wallet(db, auth_user_id))
    exp = w.vip_expires_at
    nearest = _nearest_lot_expiry(db, int(auth_user_id))
    total = int(w.balance_tokens or 0)
    usd = int(w.balance_usd or 0)
    prepaid = spendable_tokens(db, int(auth_user_id), allow_vip_daily=False)
    vip_daily_left = max(0, total - prepaid)
    au = db.query(AuthUser).filter(AuthUser.id == int(auth_user_id)).first()
    from model_warehouse import flash_ref_usd_per_m as _flash_ref

    ref = _flash_ref()
    out = {
        "auth_user_id": int(auth_user_id),
        "email": (au.email or None) if au else None,
        "plan": w.plan.value if hasattr(w.plan, "value") else str(w.plan),
        "balance_tokens": total,
        "balance_usd": usd,              # USD 美分
        "balance_usd_display": f"${usd / 100:.2f}",  # 前端直接展示
        "flash_ref_usd_per_m": round(ref, 4),
        "prepaid_tokens": int(prepaid),
        "vip_daily_remaining": int(vip_daily_left),
        "bonus_period": w.bonus_period,
        "free_monthly_bonus": FREE_MONTHLY_BONUS_TOKENS,
        "signup_bonus_tokens": SIGNUP_BONUS_TOKENS,
        "vip_daily_bonus": VIP_DAILY_BONUS_TOKENS,
        "vip_daily_models": "flash,auto,shared",
        "vip_expires_at": exp.isoformat() if exp else None,
        "credits_expire_at": nearest.isoformat() if nearest else None,
        "is_vip_active": wallet_vip_active(w),
        "is_value_pack_active": bool(value_pack_allowed_models(db, int(auth_user_id))),
    }
    try:
        from free_shared import user_shared_quota_snapshot

        out.update(user_shared_quota_snapshot(db, int(auth_user_id)))
    except Exception:
        pass
    return out


def assert_can_spend(
    db: Session,
    auth_user_id: int,
    need_tokens: int = 1,
    model: Optional[str] = None,
) -> TokenWallet:
    from auth_user_service import raise_if_frozen

    u = db.query(AuthUser).filter(AuthUser.id == int(auth_user_id)).first()
    raise_if_frozen(u)
    w = ensure_period_bonus(db, get_or_create_wallet(db, auth_user_id))
    allow_vip = model_allows_vip_daily(model)
    bal = spendable_tokens(db, int(auth_user_id), allow_vip_daily=allow_vip)
    total = int(w.balance_tokens or 0)
    if bal <= 0:
        if total > 0 and not allow_vip:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail={
                    "message_zh": "当前模型需使用充值额度；每日赠送仅可用于 flash/auto/共享档，请先充值。",
                    "message_en": "This model needs prepaid credits. Daily bonus works only for flash/auto/shared — please top up.",
                    "message": "当前模型需使用充值额度；每日赠送仅可用于 flash/auto/共享档，请先充值。",
                    "code": "prepaid_required",
                },
            )
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "message_zh": "余额不足，请充值后再试",
                "message_en": "Insufficient balance. Please top up and try again.",
                "message": "余额不足，请充值后再试",
                "code": "insufficient_balance",
            },
        )
    if bal < int(need_tokens):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "message_zh": f"额度不足（可用 {bal} token，本次预估 {need_tokens}）",
                "message_en": f"Not enough credits (available {bal}, this request needs about {need_tokens}).",
                "message": f"额度不足（可用 {bal} token，本次预估 {need_tokens}）",
                "code": "insufficient_credits",
            },
        )
    return w


def consume_tokens(
    db: Session,
    *,
    auth_user_id: int,
    tokens: int,
    model: Optional[str] = None,
    request_id: Optional[str] = None,
    amount_usd: int = 0,  # 2026-08-03: 并行扣 USD 余额（美分，消耗为正数）
) -> TokenWallet:
    from sqlalchemy import update as sa_update

    from models import TokenCreditLot, TokenWallet as TW

    tokens = max(0, int(tokens))
    amount_usd = max(0, int(amount_usd))
    w = ensure_period_bonus(db, get_or_create_wallet(db, auth_user_id))
    if tokens <= 0 and amount_usd <= 0:
        return w
    allow_vip = model_allows_vip_daily(model)
    now = _utcnow()
    avail = spendable_tokens(
        db, int(auth_user_id), allow_vip_daily=allow_vip, now=now
    )
    if avail <= 0:
        if int(w.balance_tokens or 0) > 0 and not allow_vip:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail={
                    "message_zh": "当前模型需使用充值额度；每日赠送仅可用于 flash/auto/共享档，请先充值。",
                    "message_en": "This model needs prepaid credits. Daily bonus works only for flash/auto/shared — please top up.",
                    "message": "当前模型需使用充值额度；每日赠送仅可用于 flash/auto/共享档，请先充值。",
                    "code": "prepaid_required",
                },
            )
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "message_zh": "余额不足，请充值",
                "message_en": "Insufficient balance. Please top up.",
                "message": "余额不足，请充值",
                "code": "insufficient_balance",
            },
        )
    # 成功响应后尽量扣光可用额度，避免估算偏差导致负账
    if avail < tokens:
        tokens = avail
    left = tokens
    # 原子批次扣：UPDATE ... WHERE amount_remaining >= take，防并发透支
    guard = 0
    while left > 0 and guard < 64:
        guard += 1
        lot = None
        for cand in _active_lots_q(db, int(auth_user_id), now).all():
            if not allow_vip and _is_vip_daily_lot(db, cand):
                continue
            if int(cand.amount_remaining or 0) <= 0:
                continue
            lot = cand
            break
        if lot is None:
            break
        take = min(int(lot.amount_remaining or 0), left)
        if take <= 0:
            break
        res = db.execute(
            sa_update(TokenCreditLot)
            .where(
                TokenCreditLot.id == int(lot.id),
                TokenCreditLot.amount_remaining >= int(take),
            )
            .values(amount_remaining=TokenCreditLot.amount_remaining - int(take))
        )
        if int(getattr(res, "rowcount", 0) or 0) == 1:
            left -= take
        else:
            db.expire(lot)
            continue
    deducted = int(tokens) - int(left)
    tokens = max(0, deducted)
    if amount_usd > 0 and tokens < avail:
        # 若 token 被夹断，按比例缩 USD（避免只扣 USD）
        pass
    db.flush()
    w.balance_tokens = _sum_active_lots(db, int(auth_user_id), now)
    w.updated_at = now
    # USD：尽量原子减；不足则夹到 0
    if amount_usd > 0:
        usd_take = min(amount_usd, max(0, int(w.balance_usd or 0)))
        if usd_take > 0:
            res_u = db.execute(
                sa_update(TW)
                .where(TW.id == int(w.id), TW.balance_usd >= int(usd_take))
                .values(balance_usd=TW.balance_usd - int(usd_take))
            )
            if int(getattr(res_u, "rowcount", 0) or 0) != 1:
                # 竞态下回退内存夹断
                w.balance_usd = max(0, int(w.balance_usd or 0) - usd_take)
            amount_usd = usd_take
        else:
            amount_usd = 0
    db.add(
        BillingLedger(
            auth_user_id=int(auth_user_id),
            entry_type="consume",
            amount=-int(tokens),
            amount_usd=-amount_usd,
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
    validity_days: Optional[int] = None,
    plan: Optional[str] = None,
) -> dict:
    amount = int(amount)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="充值数量必须为正整数")
    u = db.query(AuthUser).filter(AuthUser.id == int(auth_user_id)).first()
    if not u:
        raise HTTPException(status_code=404, detail="用户不存在")
    if set_vip:
        extend_vip(db, auth_user_id, days=int(vip_days) if vip_days else 30)
    days = int(validity_days) if validity_days is not None else DEFAULT_PACK_VALIDITY_DAYS
    if days <= 0:
        days = int(vip_days) if vip_days else DEFAULT_PACK_VALIDITY_DAYS
    ledger = _credit_lot(
        db,
        auth_user_id=int(auth_user_id),
        amount=amount,
        entry_type="topup",
        source="topup",
        validity_days=days,
        note=(note or "topup")[:255],
        plan=plan,
        commit=True,
    )
    # 首次充值触发推荐返利
    try:
        settle_referral_on_topup(
            db, referee_id=int(auth_user_id), topup_amount=amount, topup_ledger_id=int(ledger.id)
        )
    except Exception:
        pass
    return get_balance_snapshot(db, auth_user_id)


def topup_usd(
    db: Session,
    *,
    auth_user_id: int,
    usd_cents: int,
    note: Optional[str] = None,
    set_vip: bool = False,
    vip_days: int = 30,
    plan: Optional[str] = None,
    token_amount: Optional[int] = None,
) -> dict:
    """USD 余额充值（美分）。token 到账优先套餐契约（plan 的 credit_tokens），
    未指定时退回按 flash 锚换算（历史/人工充值兼容）。"""
    usd_cents = max(0, int(usd_cents))
    if usd_cents <= 0:
        raise HTTPException(status_code=400, detail="充值金额无效")
    u = db.query(AuthUser).filter(AuthUser.id == int(auth_user_id)).first()
    if not u:
        raise HTTPException(status_code=404, detail="用户不存在")
    if set_vip:
        extend_vip(db, auth_user_id, days=int(vip_days) if vip_days else 30)

    # 更新 USD 余额
    w = get_or_create_wallet(db, int(auth_user_id))
    w.balance_usd = int(w.balance_usd or 0) + usd_cents
    w.updated_at = _utcnow()

    # token 到账：套餐契约（credit_tokens）优先，未指定退回 flash 锚换算（FIFO lot 兼容）
    if token_amount is not None and int(token_amount) > 0:
        token_amount = int(token_amount)
    elif token_amount is not None and int(token_amount) == 0:
        token_amount = 0  # 明确 0：仅开通资格（如 VIP 资格包），不发额度
    else:
        from model_warehouse import flash_ref_usd_per_m as _flash_ref
        ref = _flash_ref()
        token_amount = max(1, int(round(usd_cents / 100.0 / ref * 1_000_000))) if ref > 0 else usd_cents
    if int(token_amount) > 0:
        ledger = _credit_lot(
            db, auth_user_id=int(auth_user_id), amount=token_amount,
            entry_type="topup", source="topup",
            validity_days=DEFAULT_PACK_VALIDITY_DAYS,
            note=(note or "topup_usd")[:255], plan=plan, commit=False,
        )
        db.add(BillingLedger(
            auth_user_id=int(auth_user_id), entry_type="topup",
            amount=token_amount, amount_usd=usd_cents,
            model=None, tokens=token_amount,
            note=(note or "topup")[:255],
        ))
        db.commit()
        db.refresh(w)

    # 首次充值触发推荐返利（仅发额度的充值）
    if int(token_amount) > 0:
        try:
            settle_referral_on_topup(
                db, referee_id=int(auth_user_id), topup_amount=token_amount, topup_ledger_id=int(ledger.id)
            )
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


def rename_api_key(db: Session, auth_user_id: int, key_id: int, name: str) -> dict:
    row = (
        db.query(ApiKey)
        .filter(
            ApiKey.id == int(key_id),
            ApiKey.auth_user_id == int(auth_user_id),
            ApiKey.is_active.is_(True),
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="API Key 不存在或已停用")
    new_name = (name or "").strip()[:64]
    if not new_name:
        raise HTTPException(status_code=400, detail="名称不能为空")
    row.name = new_name
    db.commit()
    db.refresh(row)
    return {
        "id": row.id,
        "name": row.name,
        "key_prefix": row.key_prefix,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "last_used_at": row.last_used_at.isoformat() if row.last_used_at else None,
        "is_active": bool(row.is_active),
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


def _find_api_key_any_status(db: Session, api_key: str) -> Optional[ApiKey]:
    """含已吊销；仅用于区分 invalid vs disabled。"""
    from security_util import hash_api_key

    k = (api_key or "").strip()
    if not k:
        return None
    hashed = hash_api_key(k)
    row = db.query(ApiKey).filter(ApiKey.api_key == hashed).first()
    if row:
        return row
    return db.query(ApiKey).filter(ApiKey.api_key == k).first()


def resolve_chat_user_from_api_key(db: Session, api_key: str) -> tuple[User, int]:
    """返回 (gateway User, auth_user_id)。"""
    row = get_api_key_row(db, api_key)
    if not row:
        any_row = _find_api_key_any_status(db, api_key)
        if any_row is not None and not bool(any_row.is_active):
            raise HTTPException(
                status_code=401,
                detail={
                    "message_zh": "该 API Key 已停用，请到控制台创建新 Key。",
                    "message_en": "This API key has been revoked. Create a new key in the console.",
                    "message": "该 API Key 已停用，请到控制台创建新 Key。",
                    "code": "key_disabled",
                },
            )
        raise HTTPException(
            status_code=401,
            detail={
                "message_zh": "无效的 API Key",
                "message_en": "Invalid API key",
                "message": "无效的 API Key",
                "code": "invalid_api_key",
            },
        )
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
        _credit_lot(
            db,
            auth_user_id=uid,
            amount=amount,
            entry_type="referral",
            source="referral",
            validity_days=REFERRAL_VALIDITY_DAYS,
            note=note,
            commit=False,
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
        from sqlalchemy import update as sa_update

        claimed = db.execute(
            sa_update(Referral)
            .where(Referral.id == int(r.id), Referral.status == "pending")
            .values(
                reward_tokens=int(reward),
                status="paid",
                topup_ledger_id=int(topup_ledger_id),
            )
        )
        if int(getattr(claimed, "rowcount", 0) or 0) != 1:
            continue
        if reward > 0:
            _credit_lot(
                db,
                auth_user_id=int(r.referrer_id),
                amount=reward,
                entry_type="referral",
                source="referral",
                validity_days=REFERRAL_VALIDITY_DAYS,
                note=f"L{r.level} 返利 from user {referee_id}",
                commit=False,
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


def admin_referral_overview(
    db: Session, *, q: Optional[str] = None, limit: int = 50, offset: int = 0
) -> dict:
    """邀请人列表：邀请码、一级/二级人数、已获赠 token。"""
    from models import AuthUser

    qq = (q or "").strip()
    base = db.query(InviteCode, AuthUser).join(AuthUser, AuthUser.id == InviteCode.auth_user_id)
    if qq:
        if qq.isdigit():
            base = base.filter(
                (InviteCode.auth_user_id == int(qq)) | (InviteCode.code.ilike(f"%{qq.upper()}%"))
            )
        else:
            like = f"%{qq}%"
            base = base.filter(
                (InviteCode.code.ilike(f"%{qq.upper()}%"))
                | (AuthUser.email.ilike(like))
                | (AuthUser.phone.ilike(like))
            )
    total = base.count()
    pairs = (
        base.order_by(InviteCode.id.desc())
        .offset(max(0, int(offset)))
        .limit(min(200, max(1, int(limit))))
        .all()
    )
    out = []
    for inv, u in pairs:
        uid = int(inv.auth_user_id)
        refs = db.query(Referral).filter(Referral.referrer_id == uid).all()
        l1 = [r for r in refs if int(r.level) == 1]
        l2 = [r for r in refs if int(r.level) == 2]
        earned = sum(int(r.reward_tokens or 0) for r in refs if r.status == "paid")
        pending = sum(1 for r in refs if r.status == "pending")
        out.append(
            {
                "auth_user_id": uid,
                "code": inv.code,
                "email": u.email or "",
                "phone": u.phone or "",
                "invitees_l1": len(l1),
                "invitees_l2": len(l2),
                "earned_tokens": earned,
                "pending_count": pending,
                "created_at": inv.created_at.isoformat() if inv.created_at else None,
            }
        )
    return {"total": total, "rows": out, "limit": limit, "offset": offset}


def admin_referral_detail(db: Session, auth_user_id: int, *, limit: int = 100) -> dict:
    from models import AuthUser

    uid = int(auth_user_id)
    inv = db.query(InviteCode).filter(InviteCode.auth_user_id == uid).first()
    u = db.query(AuthUser).filter(AuthUser.id == uid).first()
    refs = (
        db.query(Referral)
        .filter(Referral.referrer_id == uid)
        .order_by(Referral.id.desc())
        .limit(min(500, max(1, int(limit))))
        .all()
    )
    referee_ids = list({int(r.referee_id) for r in refs})
    users = {}
    if referee_ids:
        for ru in db.query(AuthUser).filter(AuthUser.id.in_(referee_ids)).all():
            users[int(ru.id)] = ru
    rows = []
    for r in refs:
        ru = users.get(int(r.referee_id))
        rows.append(
            {
                "id": r.id,
                "referee_id": int(r.referee_id),
                "referee_email": (ru.email if ru else "") or "",
                "referee_phone": (ru.phone if ru else "") or "",
                "level": int(r.level),
                "reward_tokens": int(r.reward_tokens or 0),
                "status": r.status,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
        )
    stats = referral_stats(db, uid)
    return {
        "auth_user_id": uid,
        "code": inv.code if inv else None,
        "user": {
            "id": uid,
            "email": (u.email if u else "") or "",
            "phone": (u.phone if u else "") or "",
        },
        **stats,
        "rows": rows,
    }
