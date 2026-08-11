"""
Token 在线支付：独立表 token_pay_orders，不读写 a1 的 pay_orders。

安全约定：
- 商户单号前缀 T（a1 为 M…），避免同商户号下混淆
- 回调只查 token_pay_orders；找不到则拒绝履约（绝不写 a1 配额）
- 真实支付默认关闭（TOKEN_PAY_ENABLED）；可用 mock 测钱包履约
"""
from __future__ import annotations

import logging
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from config import settings
from models import AuthUser, TokenPayOrder
from token_mvp_service import get_balance_snapshot, topup_tokens
from token_plans import get_plan, list_public_plans, normalize_plan

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def pay_settings_ns() -> SimpleNamespace:
    """构造给 pay_wechat_v3 / pay_alipay_wap 用的配置对象（notify 走 Token 专用 URL）。"""

    def _pem(s: str) -> str:
        raw = (s or "").strip()
        if raw == "***" or raw.startswith("***"):
            return ""
        return raw.replace("\\n", "\n").strip()

    def _s(v: str) -> str:
        t = (v or "").strip()
        if t == "***" or t.startswith("***"):
            return ""
        return t

    kwargs: dict[str, Any] = {
        "wechat_mch_id": _s(settings.wechat_mch_id or ""),
        "wechat_app_id": _s(settings.wechat_app_id or ""),
        "wechat_mch_serial_no": _s(settings.wechat_mch_serial_no or ""),
        "wechat_mch_private_key_path": _s(settings.wechat_mch_private_key_path or ""),
        "wechat_mch_private_key_pem": _pem(settings.wechat_mch_private_key_pem or ""),
        "wechat_api_v3_key": _s(settings.wechat_api_v3_key or ""),
        "wechat_pay_host": _s(settings.wechat_pay_host or "https://api.mch.weixin.qq.com")
        or "https://api.mch.weixin.qq.com",
        "wechat_notify_skip_verify": bool(settings.wechat_notify_skip_verify)
        if (settings.app_env or "").strip().lower() not in ("prod", "production")
        else False,
        "alipay_app_id": _s(settings.alipay_app_id or ""),
        "alipay_gateway": _s(settings.alipay_gateway or "https://openapi.alipay.com/gateway.do")
        or "https://openapi.alipay.com/gateway.do",
        "alipay_merchant_private_key_path": _s(settings.alipay_merchant_private_key_path or ""),
        "alipay_merchant_private_key_pem": _pem(settings.alipay_merchant_private_key_pem or ""),
        "alipay_public_key": _pem(settings.alipay_public_key or ""),
        "paypal_client_id": _s(getattr(settings, "paypal_client_id", "") or ""),
        "paypal_client_secret": _s(getattr(settings, "paypal_client_secret", "") or ""),
        "paypal_mode": _s(getattr(settings, "paypal_mode", "sandbox") or "sandbox") or "sandbox",
        "paypal_webhook_id": _s(getattr(settings, "paypal_webhook_id", "") or ""),
        "paypal_return_url": _s(getattr(settings, "token_paypal_return_url", "") or ""),
        "paypal_cancel_url": _s(getattr(settings, "token_paypal_cancel_url", "") or ""),
        "paypal_locale": _s(getattr(settings, "paypal_locale", "") or "") or "en-US",
        "paypal_landing_page": _s(getattr(settings, "paypal_landing_page", "") or "") or "BILLING",
        "creem_api_key": _s(getattr(settings, "creem_api_key", "") or ""),
        "creem_webhook_secret": _s(getattr(settings, "creem_webhook_secret", "") or ""),
        "creem_mode": _s(getattr(settings, "creem_mode", "test") or "test") or "test",
        "creem_return_url": _s(getattr(settings, "creem_return_url", "") or ""),
    }

    if bool(getattr(settings, "token_pay_reuse_a1", True)):
        try:
            from a1_pay_credentials import merge_a1_into_pay_kwargs

            kwargs = merge_a1_into_pay_kwargs(kwargs)
        except Exception as e:
            logger.warning("TOKEN_PAY_REUSE_A1 merge failed: %s", e)

    return SimpleNamespace(
        **kwargs,
        # 回调永远用 Token 独立 URL（绝不复用 a1）
        wechat_notify_url=(settings.token_wechat_notify_url or "").strip(),
        alipay_notify_url=(settings.token_alipay_notify_url or "").strip(),
        alipay_return_url=(settings.token_alipay_return_url or "").strip(),
    )


def token_pay_enabled() -> bool:
    try:
        from system_flags import effective_token_pay_enabled

        return effective_token_pay_enabled()
    except Exception:
        return bool(settings.token_pay_enabled)


def token_pay_mock_allowed() -> bool:
    """模拟到账开关。
    - 生产（APP_ENV=prod/production）：一律禁止，防覆盖文件误开
    - 真支付已开：仅当 MOCK 配置为 true 才允许（管理台覆盖优先于 env）
    - 真支付未开：MOCK=true，或本机/dev/test；若管理台显式关 MOCK 则禁止
    """
    from security_util import is_prod

    if is_prod():
        return False
    try:
        from system_flags import effective_token_pay_mock_flag, get_override

        mock_flag = effective_token_pay_mock_flag()
        has_ov = get_override("token_pay_mock_enabled") is not None
    except Exception:
        mock_flag = bool(settings.token_pay_mock_enabled)
        has_ov = False

    if token_pay_enabled():
        return bool(mock_flag)
    if has_ov:
        return bool(mock_flag)
    if bool(mock_flag):
        return True
    env = (settings.app_env or "").strip().lower()
    return env in ("dev", "local", "test")


def mk_out_trade_no(auth_user_id: int) -> str:
    # 前缀 T 与 a1 的 M 区分；总长 <= 32（微信限制）
    now = int(time.time())
    tail = secrets.token_hex(3)
    return f"T{int(auth_user_id)}{now}{tail}"[:32]


def public_plans() -> dict:
    cfg = pay_settings_ns()
    from pay_alipay_wap import alipay_configured
    from pay_creem import creem_configured
    from pay_paypal import paypal_configured
    from pay_wechat_v3 import wechat_pay_configured

    wx_cfg = wechat_pay_configured(cfg)
    ali_cfg = alipay_configured(cfg)
    pp_cfg = paypal_configured(cfg)
    creem_cfg = creem_configured(cfg)
    enabled = token_pay_enabled()
    return {
        "plans": list_public_plans(),
        "pay": {
            "enabled": enabled,
            "mock_allowed": token_pay_mock_allowed(),
            "wechat_configured": wx_cfg,
            "alipay_configured": ali_cfg,
            "paypal_configured": pp_cfg,
            "paypal_mode": str(getattr(cfg, "paypal_mode", "sandbox") or "sandbox"),
            "creem_configured": creem_cfg,
            "creem_mode": str(getattr(cfg, "creem_mode", "test") or "test"),
            # ready = 可拉真单（开关开 + 商户齐）
            "wechat_ready": bool(enabled and wx_cfg),
            "alipay_ready": bool(enabled and ali_cfg),
            "paypal_ready": bool(enabled and pp_cfg),
            "creem_ready": bool(enabled and creem_cfg),
            "crypto_configured": crypto_configured(),
            "crypto_ready": crypto_ready(),
        },
    }


def _assert_promo_purchase_ok(db: Session, *, auth_user_id: int, plan_id: str) -> None:
    """优惠体验套餐限购（按已支付成功次数）。"""
    meta = get_plan(plan_id) or {}
    if not meta.get("promo"):
        return
    try:
        max_n = int(meta.get("promo_max_purchases") or 0)
    except (TypeError, ValueError):
        max_n = 0
    if max_n <= 0:
        return
    n = (
        db.query(TokenPayOrder)
        .filter(
            TokenPayOrder.auth_user_id == int(auth_user_id),
            TokenPayOrder.plan == str(plan_id),
            TokenPayOrder.status == "paid",
        )
        .count()
    )
    if n >= max_n:
        from user_i18n import raise_user

        raise_user(
            400,
            "该优惠套餐每位用户限购一次，请选择其它套餐。",
            "This promo plan is limited to one purchase per account. Please choose another plan.",
            code="promo_limit",
        )


def create_pending_order(
    db: Session,
    *,
    auth_user_id: int,
    plan: str,
    channel: str,
) -> TokenPayOrder:
    from auth_user_service import raise_if_frozen

    u = db.query(AuthUser).filter(AuthUser.id == int(auth_user_id)).first()
    if not u:
        raise HTTPException(status_code=404, detail="用户不存在")
    raise_if_frozen(u)
    try:
        plan_id, price_fen = normalize_plan(plan)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    _assert_promo_purchase_ok(db, auth_user_id=int(auth_user_id), plan_id=plan_id)
    ch = (channel or "wechat")[:16]
    # PayPal/Creem/Crypto：amount_fen 存 USD 美分；微信/支付宝仍为 CNY 分
    if ch in ("paypal", "creem", "crypto"):
        meta = get_plan(plan_id) or {}
        try:
            usd = float(meta.get("price_usd") or 0)
        except Exception:
            usd = 0.0
        if usd <= 0:
            raise HTTPException(status_code=400, detail="plan_missing_usd_price")
        price_fen = max(1, int(round(usd * 100)))
    otn = mk_out_trade_no(int(auth_user_id))
    row = TokenPayOrder(
        out_trade_no=otn,
        auth_user_id=int(auth_user_id),
        plan=plan_id,
        amount_fen=int(price_fen),
        channel=ch,
        status="pending",
        product="token",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _fulfill_order_row(
    db: Session,
    row: TokenPayOrder,
    *,
    transaction_id: str,
    amount_fen: int,
    channel_tag: str,
) -> dict[str, Any]:
    from sqlalchemy import update as sa_update

    from token_plans import _resolve_plan, _usd_cny

    otn = str(row.out_trade_no)
    txid = str(transaction_id or "").strip()
    if not txid:
        return {"ok": False, "error": "missing_trade_refs"}

    if str(row.status) == "paid":
        if row.transaction_id and str(row.transaction_id) == txid:
            return {"ok": True, "duplicate": True, "out_trade_no": otn}
        return {"ok": False, "error": "order_already_paid"}

    if int(row.amount_fen) != int(amount_fen):
        return {"ok": False, "error": "amount_mismatch"}

    # 履约可用已下架套餐定义（前台 enabled=false 仍需给已下单用户到账）
    plan = _resolve_plan(str(row.plan))
    if not plan:
        return {"ok": False, "error": "plan_missing"}

    plan_credit = int(plan.get("credit_tokens") or 0)
    credit = plan_credit
    set_vip = bool(plan.get("set_vip"))
    note = f"{channel_tag}:{otn}:{row.plan}"

    fx = _usd_cny()
    plan_usd = float(plan.get("price_usd") or 0)
    if plan_usd > 0:
        usd_cents = int(round(plan_usd * 100))
    else:
        usd_cents = max(1, int(round(int(amount_fen) / fx)))

    if credit <= 0 and set_vip:
        credit = 1
    if credit <= 0 and usd_cents <= 0:
        return {"ok": False, "error": "nothing_to_fulfill"}

    now = _utcnow()
    # 原子抢占：仅 pending→paid 成功的一方可入账，防 webhook+手动确认双到账
    claimed = db.execute(
        sa_update(TokenPayOrder)
        .where(
            TokenPayOrder.out_trade_no == otn,
            TokenPayOrder.status.in_(["pending", "awaiting_verify"]),
        )
        .values(
            status="paid",
            transaction_id=txid[:128],
            amount_usd=int(usd_cents),
            paid_at=now,
            updated_at=now,
        )
    )
    if int(getattr(claimed, "rowcount", 0) or 0) != 1:
        db.rollback()
        again = db.query(TokenPayOrder).filter(TokenPayOrder.out_trade_no == otn).first()
        if again and str(again.status) == "paid":
            if again.transaction_id and str(again.transaction_id) == txid:
                return {"ok": True, "duplicate": True, "out_trade_no": otn}
            return {"ok": False, "error": "order_already_paid"}
        return {"ok": False, "error": "claim_failed"}
    db.commit()

    from models import BillingLedger
    from token_mvp_service import topup_usd

    # 入账幂等：同 note 已有 topup 则跳过（抢占已成功但入账中断时可重试）
    existed = (
        db.query(BillingLedger.id)
        .filter(
            BillingLedger.auth_user_id == int(row.auth_user_id),
            BillingLedger.entry_type == "topup",
            BillingLedger.note == note[:255],
        )
        .first()
    )
    if not existed:
        topup_usd(
            db,
            auth_user_id=int(row.auth_user_id),
            usd_cents=usd_cents,
            note=note,
            set_vip=set_vip,
            vip_days=int(plan.get("vip_days") or 30),
            plan=str(row.plan),
            token_amount=plan_credit if plan_credit > 0 else (0 if set_vip else None),
        )

    snap = get_balance_snapshot(db, int(row.auth_user_id))
    return {"ok": True, "out_trade_no": otn, "balance": snap}


def try_fulfill(
    db: Session,
    *,
    out_trade_no: str,
    transaction_id: str,
    amount_fen: int,
    channel_tag: str,
) -> dict[str, Any]:
    otn = str(out_trade_no or "").strip()
    if not otn:
        return {"ok": False, "error": "missing_out_trade_no"}
    # 只处理 Token 单；非 T 前缀直接忽略，避免误履约
    if not otn.startswith("T"):
        return {"ok": False, "error": "not_token_order"}
    row = db.query(TokenPayOrder).filter(TokenPayOrder.out_trade_no == otn).first()
    if not row:
        return {"ok": False, "error": "order_not_found"}
    return _fulfill_order_row(
        db,
        row,
        transaction_id=transaction_id,
        amount_fen=int(amount_fen),
        channel_tag=channel_tag,
    )


def mock_fulfill(db: Session, *, out_trade_no: str, auth_user_id: Optional[int] = None) -> dict:
    if not token_pay_mock_allowed():
        raise HTTPException(status_code=403, detail="mock 支付未开启")
    otn = str(out_trade_no or "").strip()
    row = db.query(TokenPayOrder).filter(TokenPayOrder.out_trade_no == otn).first()
    if not row:
        raise HTTPException(status_code=404, detail="订单不存在")
    if auth_user_id is not None and int(row.auth_user_id) != int(auth_user_id):
        raise HTTPException(status_code=403, detail="订单不属于当前用户")
    r = _fulfill_order_row(
        db,
        row,
        transaction_id=f"MOCK{int(time.time())}",
        amount_fen=int(row.amount_fen),
        channel_tag="mock",
    )
    if not r.get("ok"):
        raise HTTPException(status_code=409, detail=str(r.get("error") or "fulfill_failed"))
    return r


def list_orders_for_user(db: Session, auth_user_id: int, *, limit: int = 20) -> dict:
    q = (
        db.query(TokenPayOrder)
        .filter(TokenPayOrder.auth_user_id == int(auth_user_id))
        .order_by(TokenPayOrder.id.desc())
        .limit(min(100, max(1, int(limit))))
    )
    rows = q.all()
    return {
        "rows": [
            {
                "out_trade_no": r.out_trade_no,
                "plan": r.plan,
                "amount_fen": r.amount_fen,
                "channel": r.channel,
                "status": r.status,
                "code_url": r.code_url,
                "transaction_id": r.transaction_id,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "paid_at": r.paid_at.isoformat() if r.paid_at else None,
            }
            for r in rows
        ]
    }


def pending_order_expired(r, now=None) -> bool:
    """pending 未付订单是否已超时（无 expires_at 字段，按 created_at + 渠道窗口判定）。

    微信/支付宝扫码未付默认 24h 过期；PayPal 订单默认 72h（PayPal 授权有效期）。
    窗口可用环境变量覆盖：TOKEN_PENDING_EXPIRE_HOURS_CN / TOKEN_PENDING_EXPIRE_HOURS_PP。
    """
    if r is None or getattr(r, "status", "") != "pending" or not getattr(r, "created_at", None):
        return False
    channel = str(getattr(r, "channel", "") or "").strip().lower()
    try:
        hours = int(os.getenv("TOKEN_PENDING_EXPIRE_HOURS_PP", "72"))
        if channel in ("wechat", "alipay", "mock"):
            hours = int(os.getenv("TOKEN_PENDING_EXPIRE_HOURS_CN", "24"))
    except ValueError:
        hours = 24 if channel in ("wechat", "alipay", "mock") else 72
    now = now or datetime.now(timezone.utc)
    created = getattr(r, "created_at", None)
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    else:
        created = created.astimezone(timezone.utc)
    return (now - created) > timedelta(hours=hours)


def _pending_expire_hours(channel: str) -> int:
    ch = str(channel or "").strip().lower()
    if ch in ("wechat", "alipay", "mock"):
        try:
            return max(1, int(os.getenv("TOKEN_PENDING_EXPIRE_HOURS_CN", "24")))
        except ValueError:
            return 24
    try:
        return max(1, int(os.getenv("TOKEN_PENDING_EXPIRE_HOURS_PP", "72")))
    except ValueError:
        return 72


def admin_list_orders(
    db: Session,
    *,
    auth_user_id: Optional[int] = None,
    status: Optional[str] = None,
    channel: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    include_expired: bool = False,
) -> dict:
    query = db.query(TokenPayOrder)
    if auth_user_id is not None:
        query = query.filter(TokenPayOrder.auth_user_id == int(auth_user_id))
    if status:
        query = query.filter(TokenPayOrder.status == str(status).strip())
    ch = (channel or "").strip().lower()
    if ch:
        query = query.filter(TokenPayOrder.channel == ch)
    qq = (q or "").strip()
    if qq:
        like = f"%{qq}%"
        query = query.filter(
            (TokenPayOrder.out_trade_no.ilike(like))
            | (TokenPayOrder.transaction_id.ilike(like))
        )
    total = query.count()
    total_expired = 0
    if not include_expired and (not status or str(status).strip() == "pending"):
        all_rows = query.all()
        valid = [x for x in all_rows if not pending_order_expired(x) and not getattr(x, "confirmed_unpaid_at", None)]
        total_expired = len(all_rows) - len(valid)
        if valid:
            query = query.filter(TokenPayOrder.id.in_([x.id for x in valid]))
        else:
            query = query.filter(TokenPayOrder.id < 0)
        total = len(valid)
    rows = (
        query.order_by(TokenPayOrder.id.desc())
        .offset(max(0, int(offset)))
        .limit(min(200, max(1, int(limit))))
        .all()
    )
    from models import AuthUser

    out_rows = []
    for r in rows:
        u = db.query(AuthUser).filter(AuthUser.id == int(r.auth_user_id)).first()
        out_rows.append(
            {
                "id": r.id,
                "out_trade_no": r.out_trade_no,
                "auth_user_id": r.auth_user_id,
                "plan": r.plan,
                "amount_fen": r.amount_fen,
                "channel": r.channel,
                "status": r.status,
                "transaction_id": r.transaction_id,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "paid_at": r.paid_at.isoformat() if r.paid_at else None,
                "expired": pending_order_expired(r),
                "confirmed_unpaid_at": r.confirmed_unpaid_at.isoformat() if r.confirmed_unpaid_at else None,
                "utm_source": (getattr(u, "utm_source", None) if u else None) or None,
                "utm_medium": (getattr(u, "utm_medium", None) if u else None) or None,
                "utm_campaign": (getattr(u, "utm_campaign", None) if u else None) or None,
                "gclid": (getattr(u, "gclid", None) if u else None) or None,
            }
        )
    return {"total": total, "total_expired": total_expired, "rows": out_rows}


def admin_orders_csv_text(
    db: Session,
    *,
    auth_user_id: Optional[int] = None,
    status: Optional[str] = None,
    channel: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = 2000,
) -> str:
    """导出订单 CSV（UTF-8 BOM，Excel 可直接打开）。"""
    import csv
    import io

    data = admin_list_orders(
        db,
        auth_user_id=auth_user_id,
        status=status,
        channel=channel,
        q=q,
        limit=min(5000, max(1, int(limit))),
        offset=0,
    )
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(
        [
            "id",
            "out_trade_no",
            "auth_user_id",
            "plan",
            "amount_fen",
            "channel",
            "status",
            "transaction_id",
            "created_at",
            "paid_at",
        ]
    )
    for r in data.get("rows") or []:
        w.writerow(
            [
                r.get("id"),
                r.get("out_trade_no"),
                r.get("auth_user_id"),
                r.get("plan"),
                r.get("amount_fen"),
                r.get("channel"),
                r.get("status"),
                r.get("transaction_id") or "",
                r.get("created_at") or "",
                r.get("paid_at") or "",
            ]
        )
    return "\ufeff" + buf.getvalue()


def admin_token_summary(db: Session) -> dict:
    """管理端看板：订单计数 + 支付通道就绪（不含密钥）。"""
    from sqlalchemy import func

    from models import AuthUser, TokenCreditLot, TokenWallet

    def _cnt(status: str | None = None, channel: str | None = None) -> int:
        q = db.query(func.count(TokenPayOrder.id))
        if status:
            q = q.filter(TokenPayOrder.status == status)
        if channel:
            q = q.filter(TokenPayOrder.channel == channel)
        return int(q.scalar() or 0)

    paid_fen = (
        db.query(func.coalesce(func.sum(TokenPayOrder.amount_fen), 0))
        .filter(TokenPayOrder.status == "paid", TokenPayOrder.channel.in_(("wechat", "alipay")))
        .scalar()
    )
    paid_usd_cents = (
        db.query(func.coalesce(func.sum(TokenPayOrder.amount_fen), 0))
        .filter(TokenPayOrder.status == "paid", TokenPayOrder.channel == "paypal")
        .scalar()
    )
    users = int(db.query(func.count(AuthUser.id)).scalar() or 0)
    wallets = int(db.query(func.count(TokenWallet.id)).scalar() or 0)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    active_lots = int(
        db.query(func.count(TokenCreditLot.id))
        .filter(TokenCreditLot.amount_remaining > 0, TokenCreditLot.expires_at > now)
        .scalar()
        or 0
    )
    active_tokens = int(
        db.query(func.coalesce(func.sum(TokenCreditLot.amount_remaining), 0))
        .filter(TokenCreditLot.amount_remaining > 0, TokenCreditLot.expires_at > now)
        .scalar()
        or 0
    )
    pay = public_plans().get("pay") or {}
    return {
        "ok": True,
        "users": users,
        "wallets": wallets,
        "credits": {
            "active_lots": active_lots,
            "active_tokens": active_tokens,
        },
        "orders": {
            "pending": _cnt("pending"),
            "paid": _cnt("paid"),
            "failed": _cnt("failed"),
            "by_channel_paid": {
                "wechat": _cnt("paid", "wechat"),
                "alipay": _cnt("paid", "alipay"),
                "paypal": _cnt("paid", "paypal"),
                "creem": _cnt("paid", "creem"),
            },
            "paid_amount_cny_fen": int(paid_fen or 0),
            "paid_amount_usd_cents": int(paid_usd_cents or 0),
        },
        "pay": pay,
    }


async def admin_query_fulfill_order(db: Session, *, out_trade_no: str) -> dict:
    """管理端代用户查单履约（pending → 向通道确认后加 Token）。"""
    otn = str(out_trade_no or "").strip()
    row = db.query(TokenPayOrder).filter(TokenPayOrder.out_trade_no == otn).first()
    if not row:
        raise HTTPException(status_code=404, detail="订单不存在")
    uid = int(row.auth_user_id)
    ch = str(row.channel or "")
    if ch == "wechat":
        return await query_and_fulfill_wechat(db, out_trade_no=otn, auth_user_id=uid)
    if ch == "alipay":
        return query_and_fulfill_alipay(db, out_trade_no=otn, auth_user_id=uid)
    if ch == "paypal":
        return await query_and_fulfill_paypal(db, out_trade_no=otn, auth_user_id=uid)
    if ch == "creem":
        return await query_creem_order(db, out_trade_no=otn, auth_user_id=uid)
    raise HTTPException(status_code=400, detail=f"unsupported_channel:{ch}")


async def create_wechat_native(db: Session, *, auth_user_id: int, plan: str) -> dict:
    row = create_pending_order(db, auth_user_id=auth_user_id, plan=plan, channel="wechat")
    plan_meta = get_plan(row.plan) or {}
    title = str(plan_meta.get("title") or row.plan)

    if token_pay_mock_allowed() and not token_pay_enabled():
        row.code_url = f"mock://token-pay/{row.out_trade_no}"
        db.commit()
        return {
            "out_trade_no": row.out_trade_no,
            "plan": row.plan,
            "amount_fen": row.amount_fen,
            "channel": "wechat",
            "code_url": row.code_url,
            "mock": True,
            "hint": "TOKEN_PAY_ENABLED 未开：请用 POST /v1/billing/orders/mock_fulfill 模拟到账",
        }

    if not token_pay_enabled():
        raise HTTPException(status_code=503, detail="Token 在线支付未开启（TOKEN_PAY_ENABLED）")

    cfg = pay_settings_ns()
    from pay_wechat_v3 import native_create_order, wechat_pay_configured

    if not wechat_pay_configured(cfg):
        raise HTTPException(
            status_code=503,
            detail="微信未配置完整，或 TOKEN_WECHAT_NOTIFY_URL 为空（须指向主站 Token 回调，勿复用 a1 回调）",
        )
    try:
        wx = await native_create_order(
            cfg,
            out_trade_no=row.out_trade_no,
            description=title,
            amount_fen=int(row.amount_fen),
        )
    except Exception as e:
        logger.exception("wechat native create failed")
        row.status = "failed"
        db.commit()
        raise HTTPException(status_code=502, detail=f"微信下单失败: {e}") from e

    code_url = str((wx or {}).get("code_url") or "")
    row.code_url = code_url or None
    db.commit()
    return {
        "out_trade_no": row.out_trade_no,
        "plan": row.plan,
        "amount_fen": row.amount_fen,
        "channel": "wechat",
        "code_url": code_url,
        "mock": False,
    }


async def create_alipay_wap(db: Session, *, auth_user_id: int, plan: str) -> dict:
    row = create_pending_order(db, auth_user_id=auth_user_id, plan=plan, channel="alipay")
    plan_meta = get_plan(row.plan) or {}
    title = str(plan_meta.get("title") or row.plan)
    yuan = f"{int(row.amount_fen) / 100:.2f}"

    if token_pay_mock_allowed() and not token_pay_enabled():
        pay_url = f"mock://token-pay/{row.out_trade_no}"
        row.code_url = pay_url
        db.commit()
        return {
            "out_trade_no": row.out_trade_no,
            "plan": row.plan,
            "amount_fen": row.amount_fen,
            "channel": "alipay",
            "pay_url": pay_url,
            "mock": True,
            "hint": "TOKEN_PAY_ENABLED 未开：请用 POST /v1/billing/orders/mock_fulfill 模拟到账",
        }

    if not token_pay_enabled():
        raise HTTPException(status_code=503, detail="Token 在线支付未开启（TOKEN_PAY_ENABLED）")

    cfg = pay_settings_ns()
    from pay_alipay_wap import alipay_configured, build_wap_pay_url

    if not alipay_configured(cfg):
        raise HTTPException(
            status_code=503,
            detail="支付宝未配置完整，或 TOKEN_ALIPAY_NOTIFY_URL 为空（须指向主站 Token 回调）",
        )
    try:
        pay_url = build_wap_pay_url(
            cfg,
            out_trade_no=row.out_trade_no,
            subject=title,
            total_amount_yuan=yuan,
            return_url=(cfg.alipay_return_url or None),
        )
    except Exception as e:
        logger.exception("alipay wap create failed")
        row.status = "failed"
        db.commit()
        raise HTTPException(status_code=502, detail=f"支付宝下单失败: {e}") from e

    row.code_url = pay_url[:2000] if pay_url else None
    db.commit()
    return {
        "out_trade_no": row.out_trade_no,
        "plan": row.plan,
        "amount_fen": row.amount_fen,
        "channel": "alipay",
        "pay_url": pay_url,
        "mock": False,
    }


async def create_paypal_order(db: Session, *, auth_user_id: int, plan: str) -> dict:
    row = create_pending_order(db, auth_user_id=auth_user_id, plan=plan, channel="paypal")
    plan_meta = get_plan(row.plan) or {}
    title = str(plan_meta.get("title_en") or plan_meta.get("title_zh") or row.plan)
    usd = float(plan_meta.get("price_usd") or 0) or (int(row.amount_fen) / 100.0)

    if token_pay_mock_allowed() and not token_pay_enabled():
        pay_url = f"mock://token-pay/{row.out_trade_no}"
        row.code_url = pay_url
        db.commit()
        return {
            "out_trade_no": row.out_trade_no,
            "plan": row.plan,
            "amount_fen": row.amount_fen,
            "amount_usd": f"{usd:.2f}",
            "currency": "USD",
            "channel": "paypal",
            "pay_url": pay_url,
            "mock": True,
            "hint": "TOKEN_PAY_ENABLED 未开：请用 mock_fulfill 模拟到账",
        }

    if not token_pay_enabled():
        raise HTTPException(status_code=503, detail="Token 在线支付未开启（TOKEN_PAY_ENABLED）")

    cfg = pay_settings_ns()
    from pay_paypal import approve_url_from_order, create_checkout_order, paypal_configured

    if not paypal_configured(cfg):
        raise HTTPException(status_code=503, detail="PayPal 未配置（PAYPAL_CLIENT_ID / SECRET）")

    ret = (getattr(cfg, "paypal_return_url", "") or "https://www.ai24x.com/console.html").strip()
    can = (getattr(cfg, "paypal_cancel_url", "") or ret).strip()
    # 带回本站单号，便于 return 页触发 capture
    sep = "&" if "?" in ret else "?"
    ret_q = f"{ret}{sep}paypal=1&out_trade_no={row.out_trade_no}"
    can_q = f"{can}{sep}paypal_cancel=1&out_trade_no={row.out_trade_no}" if "out_trade_no=" not in can else can

    try:
        pp = await create_checkout_order(
            cfg,
            out_trade_no=row.out_trade_no,
            amount_usd=usd,
            description=title,
            return_url=ret_q,
            cancel_url=can_q,
        )
    except Exception as e:
        logger.exception("paypal create failed")
        row.status = "failed"
        db.commit()
        err = str(e)
        if "invalid_client" in err or "paypal_oauth_error" in err:
            detail = "PayPal 商户凭证无效，请稍后重试或联系客服。"
        else:
            detail = "PayPal 下单暂时失败，请稍后重试。"
        raise HTTPException(status_code=502, detail=detail) from e

    pay_url = approve_url_from_order(pp or {})
    pp_id = str((pp or {}).get("id") or "")
    # code_url 存 approve 链接；transaction_id 暂存 PayPal order id（paid 后改为 capture id）
    row.code_url = (pay_url or "")[:2000] or None
    if pp_id:
        row.transaction_id = pp_id[:128]
    db.commit()
    return {
        "out_trade_no": row.out_trade_no,
        "plan": row.plan,
        "amount_fen": row.amount_fen,
        "amount_usd": f"{usd:.2f}",
        "currency": "USD",
        "channel": "paypal",
        "pay_url": pay_url,
        "paypal_order_id": pp_id,
        "mock": False,
    }


async def create_creem_order(db: Session, *, auth_user_id: int, plan: str) -> dict:
    """Creem Checkout: create order + checkout session (USD cents, same as PayPal)."""
    row = create_pending_order(db, auth_user_id=int(auth_user_id), plan=plan, channel="creem")
    meta = get_plan(row.plan) or {}
    try:
        usd = float(meta.get("price_usd") or 0)
    except Exception:
        usd = 0.0
    title = str(meta.get("title_en") or meta.get("title_zh") or row.plan)

    cfg = pay_settings_ns()
    from pay_creem import create_checkout_session, creem_configured

    if not creem_configured(cfg):
        raise HTTPException(
            status_code=503,
            detail="Creem not configured (CREEM_API_KEY / CREEM_WEBHOOK_SECRET)",
        )

    product_id = str(meta.get("creem_product_id") or "").strip()
    if not product_id:
        raise HTTPException(status_code=503, detail="plan_missing_creem_product_id")

    ret = (getattr(cfg, "creem_return_url", "") or "https://www.ai24x.com/console.html").strip()
    sep = "&" if "?" in ret else "?"
    ret_q = f"{ret}{sep}creem=1&out_trade_no={row.out_trade_no}"

    u = db.query(AuthUser).filter(AuthUser.id == int(auth_user_id)).first()
    customer_email = (u.email if u else "") or ""

    try:
        session = await create_checkout_session(
            cfg,
            product_id=product_id,
            request_id=row.out_trade_no,
            success_url=ret_q,
            customer_email=customer_email,
            metadata={"plan": row.plan, "out_trade_no": row.out_trade_no},
        )
    except Exception as e:
        logger.exception("creem create failed")
        row.status = "failed"
        db.commit()
        raise HTTPException(status_code=502, detail="Creem checkout failed, try again later.") from e

    pay_url = str((session or {}).get("checkout_url") or "")
    chk_id = str((session or {}).get("id") or "")
    row.code_url = (pay_url or "")[:2000] or None
    if chk_id:
        row.transaction_id = chk_id[:128]
    db.commit()
    return {
        "out_trade_no": row.out_trade_no,
        "plan": row.plan,
        "amount_fen": row.amount_fen,
        "amount_usd": f"{usd:.2f}",
        "currency": "USD",
        "channel": "creem",
        "pay_url": pay_url,
        "checkout_id": chk_id,
        "mock": False,
    }


async def query_creem_order(db: Session, *, out_trade_no: str, auth_user_id: int) -> dict:
    """Creem local order status (webhook is authoritative). No upstream query needed."""
    otn = str(out_trade_no or "").strip()
    row = db.query(TokenPayOrder).filter(TokenPayOrder.out_trade_no == otn).first()
    if not row or int(row.auth_user_id) != int(auth_user_id):
        raise HTTPException(status_code=404, detail="order_not_found")
    if str(row.status) == "paid":
        return {
            "ok": True,
            "duplicate": True,
            "out_trade_no": otn,
            "balance": get_balance_snapshot(db, int(auth_user_id)),
        }
    return {"ok": False, "status": str(row.status), "out_trade_no": otn}

async def capture_and_fulfill_paypal(
    db: Session, *, out_trade_no: str, auth_user_id: int, paypal_order_id: str | None = None
) -> dict:
    """Return URL / 手动确认：Capture 后履约。"""
    otn = str(out_trade_no or "").strip()
    row = db.query(TokenPayOrder).filter(TokenPayOrder.out_trade_no == otn).first()
    if not row or int(row.auth_user_id) != int(auth_user_id):
        raise HTTPException(status_code=404, detail="订单不存在")
    if str(row.channel) != "paypal":
        raise HTTPException(status_code=400, detail="not_paypal_order")
    if str(row.status) == "paid":
        return {
            "ok": True,
            "duplicate": True,
            "out_trade_no": otn,
            "balance": get_balance_snapshot(db, int(auth_user_id)),
        }

    if token_pay_mock_allowed() and not token_pay_enabled():
        return mock_fulfill(db, out_trade_no=otn, auth_user_id=auth_user_id)
    if not token_pay_enabled():
        raise HTTPException(status_code=503, detail="Token 在线支付未开启")

    cfg = pay_settings_ns()
    from pay_paypal import (
        capture_order,
        extract_capture_id,
        extract_captured_usd_cents,
        extract_custom_id,
        get_order,
        is_order_completed,
        paypal_configured,
    )

    if not paypal_configured(cfg):
        raise HTTPException(status_code=503, detail="PayPal 未配置")

    pid = (paypal_order_id or str(row.transaction_id or "")).strip()
    if not pid:
        raise HTTPException(status_code=400, detail="missing_paypal_order_id")

    try:
        # 已完成则直接读；否则 capture。并发回跳/轮询可能二次 capture → ORDER_ALREADY_CAPTURED，改查单履约。
        cur = await get_order(cfg, paypal_order_id=pid)
        if is_order_completed(cur):
            captured = cur
        else:
            try:
                captured = await capture_order(cfg, paypal_order_id=pid)
            except RuntimeError as e:
                err = str(e)
                if "ORDER_ALREADY_CAPTURED" in err:
                    logger.info("paypal already captured otn=%s pid=%s; refetch", otn, pid)
                    captured = await get_order(cfg, paypal_order_id=pid)
                else:
                    raise
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("paypal capture failed otn=%s", otn)
        raise HTTPException(
            status_code=502,
            detail="PayPal 确认失败，请稍后在「我的订单」点确认到账。",
        ) from e

    # 并发：另一请求可能已履约
    db.refresh(row)
    if str(row.status) == "paid":
        return {
            "ok": True,
            "duplicate": True,
            "out_trade_no": otn,
            "balance": get_balance_snapshot(db, int(auth_user_id)),
        }

    if not is_order_completed(captured):
        raise HTTPException(status_code=409, detail="支付尚未完成，请稍后再试。")

    custom = extract_custom_id(captured) or otn
    if custom and custom != otn:
        logger.warning("paypal custom_id mismatch otn=%s custom=%s", otn, custom)
    cents = extract_captured_usd_cents(captured)
    if cents <= 0:
        cents = int(row.amount_fen)
    txid = extract_capture_id(captured) or pid
    r = try_fulfill(
        db,
        out_trade_no=otn,
        transaction_id=txid,
        amount_fen=cents,
        channel_tag="paypal_capture",
    )
    if not r.get("ok"):
        raise HTTPException(status_code=409, detail=str(r.get("error") or "fulfill_failed"))
    return r


async def query_and_fulfill_paypal(db: Session, *, out_trade_no: str, auth_user_id: int) -> dict:
    """与微信「确认到账」同义：查单/Capture 后履约。"""
    return await capture_and_fulfill_paypal(db, out_trade_no=out_trade_no, auth_user_id=auth_user_id)


async def query_and_fulfill_wechat(db: Session, *, out_trade_no: str, auth_user_id: int) -> dict:
    """主动查单补履约（notify 未达时）。"""
    otn = str(out_trade_no or "").strip()
    row = db.query(TokenPayOrder).filter(TokenPayOrder.out_trade_no == otn).first()
    if not row or int(row.auth_user_id) != int(auth_user_id):
        raise HTTPException(status_code=404, detail="订单不存在")
    if str(row.status) == "paid":
        return {"ok": True, "duplicate": True, "out_trade_no": otn, "balance": get_balance_snapshot(db, int(auth_user_id))}

    if token_pay_mock_allowed() and not token_pay_enabled():
        return mock_fulfill(db, out_trade_no=otn, auth_user_id=auth_user_id)

    if not token_pay_enabled():
        raise HTTPException(status_code=503, detail="Token 在线支付未开启")

    cfg = pay_settings_ns()
    from pay_wechat_v3 import query_transaction_by_out_trade_no, wechat_pay_configured

    if not wechat_pay_configured(cfg):
        raise HTTPException(status_code=503, detail="微信未配置")
    txn = await query_transaction_by_out_trade_no(cfg, out_trade_no=otn)
    if str(txn.get("trade_state") or "") != "SUCCESS":
        return {"ok": False, "trade_state": txn.get("trade_state"), "out_trade_no": otn}
    txid = str(txn.get("transaction_id") or "")
    total = int(((txn.get("amount") or {}) if isinstance(txn.get("amount"), dict) else {}).get("total") or 0)
    r = try_fulfill(db, out_trade_no=otn, transaction_id=txid, amount_fen=total, channel_tag="wechat_query")
    if not r.get("ok"):
        raise HTTPException(status_code=409, detail=str(r.get("error") or "fulfill_failed"))
    return r


def query_and_fulfill_alipay(db: Session, *, out_trade_no: str, auth_user_id: int) -> dict:
    otn = str(out_trade_no or "").strip()
    row = db.query(TokenPayOrder).filter(TokenPayOrder.out_trade_no == otn).first()
    if not row or int(row.auth_user_id) != int(auth_user_id):
        raise HTTPException(status_code=404, detail="订单不存在")
    if str(row.status) == "paid":
        return {"ok": True, "duplicate": True, "out_trade_no": otn, "balance": get_balance_snapshot(db, int(auth_user_id))}

    if token_pay_mock_allowed() and not token_pay_enabled():
        return mock_fulfill(db, out_trade_no=otn, auth_user_id=auth_user_id)

    if not token_pay_enabled():
        raise HTTPException(status_code=503, detail="Token 在线支付未开启")

    cfg = pay_settings_ns()
    from pay_alipay_wap import alipay_configured, query_trade

    if not alipay_configured(cfg):
        raise HTTPException(status_code=503, detail="支付宝未配置")
    txn = query_trade(cfg, out_trade_no=otn)
    status_s = str(txn.get("trade_status") or "")
    if status_s not in ("TRADE_SUCCESS", "TRADE_FINISHED"):
        return {"ok": False, "trade_status": status_s, "out_trade_no": otn}
    trade_no = str(txn.get("trade_no") or "")
    try:
        yuan = float(txn.get("total_amount") or "0")
        fen = int(round(yuan * 100))
    except Exception:
        fen = int(row.amount_fen)
    r = try_fulfill(db, out_trade_no=otn, transaction_id=trade_no, amount_fen=fen, channel_tag="alipay_query")
    if not r.get("ok"):
        raise HTTPException(status_code=409, detail=str(r.get("error") or "fulfill_failed"))
    return r


def cleanup_expired_pending_orders(db, *, dry_run: bool = True, now=None, max_void: int = 200) -> dict:
    """清理超时未付订单（防积压，作废前先确认无渠道交易号）。

    规则（保守，避免丢钱）：
      1) 仅处理 status=pending 且已超时（pending_order_expired，微信/支付宝 24h、PayPal 72h）。
      2) 有 transaction_id 且【未】确认未收款的超时单【不】作废——可能已收款未发放（真问题），保留待渠道对账。
      3) 无 transaction_id 或已确认未收款（confirmed_unpaid_at 非空）的超时单 = 用户未完成支付，status 置 failed（作废）。
      4) dry_run=True 只统计不落库；单次作废 > max_void 时中止，防误伤。
    返回统计供预警/管理台展示。
    """
    def _confirmed(r):
        return bool(getattr(r, "confirmed_unpaid_at", None))

    rows = db.query(TokenPayOrder).filter(TokenPayOrder.status == "pending").all()
    valid = [r for r in rows if not pending_order_expired(r, now=now) and not _confirmed(r)]
    expired = [r for r in rows if pending_order_expired(r, now=now)]
    voidable = [r for r in expired if not getattr(r, "transaction_id", None) or _confirmed(r)]
    keep_reconcile = [r for r in expired if getattr(r, "transaction_id", None) and not _confirmed(r)]
    confirmed_unpaid = [r for r in rows if _confirmed(r)]

    voided = []
    if not dry_run and voidable:
        if len(voidable) > max(1, int(max_void)):
            return {
                "ok": False,
                "dry_run": dry_run,
                "error": "本次可作废 {n} 笔，超过保护上限 {m}，已中止，请人工确认后重试".format(n=len(voidable), m=int(max_void)),
                "scanned": len(rows),
                "valid": len(valid),
                "voidable": len(voidable),
                "kept_for_reconcile": len(keep_reconcile),
                "voided": 0,
            }
        for r in voidable:
            r.status = "failed"
            voided.append(r.id)
        db.commit()

    return {
        "ok": True,
        "dry_run": dry_run,
        "scanned": len(rows),
        "valid": len(valid),
        "expired": len(expired),
        "voidable_no_txn": len(voidable),
        "voidable_breakdown": {
            "no_txn": len([r for r in voidable if not getattr(r, "transaction_id", None)]),
            "confirmed_unpaid": len([r for r in voidable if getattr(r, "confirmed_unpaid_at", None)]),
        },
        "voided": len(voided),
        "voided_ids": voided,
        "kept_for_reconcile": len(keep_reconcile),
        "kept_reconcile_ids": [r.id for r in keep_reconcile],
        "confirmed_unpaid": len(confirmed_unpaid),
        "confirmed_unpaid_ids": [r.id for r in confirmed_unpaid],
        "note": (
            "有交易号且未确认未收款的超时单保留 pending 待渠道对账（可能已收款未发放，勿作废）；"
            "无交易号或已确认未收款的超时单作废（用户未完成支付）。"
        ),
    }


def confirm_order_unpaid(db, order_id: int) -> dict:
    """对账确认某笔 pending 订单未收款（有交易号但渠道确认无捕获/未完成支付）。幂等。

    标记后：有效待履约统计不再计入；超时后 cleanup 会将其作废为 failed。
    """
    r = db.query(TokenPayOrder).filter(TokenPayOrder.id == int(order_id)).first()
    if r is None:
        return {"ok": False, "error": "订单不存在"}
    if r.status != "pending":
        return {"ok": False, "error": "仅 pending 订单可确认未收款（当前 " + str(r.status) + "）"}
    if r.confirmed_unpaid_at:
        return {
            "ok": True,
            "id": r.id,
            "out_trade_no": r.out_trade_no,
            "status": r.status,
            "transaction_id": r.transaction_id,
            "confirmed_unpaid_at": r.confirmed_unpaid_at.isoformat() if r.confirmed_unpaid_at else None,
            "note": "已确认未收款（重复确认，时间戳未改动）",
        }
    r.confirmed_unpaid_at = datetime.now(timezone.utc)
    db.commit()
    return {
        "ok": True,
        "id": r.id,
        "out_trade_no": r.out_trade_no,
        "status": r.status,
        "transaction_id": r.transaction_id,
        "confirmed_unpaid_at": r.confirmed_unpaid_at.isoformat() if r.confirmed_unpaid_at else None,
        "note": "已标记：对账确认未收款；超时后清理任务将作废为 failed",
    }

# ================= Crypto (USDT-TRC20) =================
def crypto_settings_ns() -> SimpleNamespace:
    """CRYPTO_* 配置。地址为空 = 未配置。"""
    return SimpleNamespace(
        address=str(getattr(settings, "crypto_trc20_address", "") or "").strip(),
        enabled=bool(getattr(settings, "crypto_enabled", False)),
        min_confirm=int(getattr(settings, "crypto_min_confirm", 6) or 6),
        daily_limit_usd=float(getattr(settings, "crypto_daily_limit_usd", 1000) or 1000),
        order_limit_usd=float(getattr(settings, "crypto_order_limit_usd", 500) or 500),
    )


def crypto_configured() -> bool:
    return bool(crypto_settings_ns().address)


def crypto_ready() -> bool:
    cfg = crypto_settings_ns()
    return bool(cfg.enabled and cfg.address)


def create_crypto_order(db: Session, *, auth_user_id: int, plan: str) -> dict:
    """USDT-TRC20 下单：创建 pending 订单，返回收款地址/金额。USDT 1:1 USD。"""
    row = create_pending_order(db, auth_user_id=auth_user_id, plan=plan, channel="crypto")
    meta = get_plan(row.plan) or {}
    try:
        usd = float(meta.get("price_usd") or 0)
    except Exception:
        usd = 0.0
    if usd <= 0:
        usd = int(row.amount_fen) / 100.0
    cfg = crypto_settings_ns()
    if not cfg.address:
        row.status = "failed"
        db.commit()
        raise HTTPException(status_code=503, detail="Crypto 未配置（CRYPTO_TRC20_ADDRESS）")
    if usd > cfg.order_limit_usd:
        row.status = "failed"
        db.commit()
        raise HTTPException(status_code=400, detail=f"单笔限额 ${cfg.order_limit_usd:.0f}，请分拆或联系客服")
    row.code_url = cfg.address
    db.commit()
    return {
        "out_trade_no": row.out_trade_no,
        "plan": row.plan,
        "amount_fen": row.amount_fen,
        "amount_usd": f"{usd:.2f}",
        "amount_usdt": f"{usd:.2f}",
        "currency": "USDT",
        "network": "TRC20",
        "channel": "crypto",
        "address": cfg.address,
        "min_confirm": cfg.min_confirm,
        "expire_minutes": 60,
        "hint": "请向上述 TRC20 地址转入等额 USDT，转账后提交 txid 核验。",
    }


def submit_crypto_txid(
    db: Session, *, out_trade_no: str, txid: str, auth_user_id: Optional[int] = None
) -> dict:
    """用户提交链上 txid，订单进入 awaiting_verify。"""
    otn = str(out_trade_no or "").strip()
    txid = str(txid or "").strip()
    if not otn or not txid:
        raise HTTPException(status_code=400, detail="missing out_trade_no/txid")
    row = db.query(TokenPayOrder).filter(TokenPayOrder.out_trade_no == otn).first()
    if not row:
        raise HTTPException(status_code=404, detail="订单不存在")
    if auth_user_id is not None and int(row.auth_user_id) != int(auth_user_id):
        raise HTTPException(status_code=403, detail="订单不属于当前用户")
    if row.status == "paid":
        return {"ok": True, "duplicate": True, "out_trade_no": otn, "status": "paid"}
    row.transaction_id = txid[:128]
    if row.status in ("pending", "verify_failed"):
        row.status = "awaiting_verify"
    db.commit()
    return {"ok": True, "out_trade_no": otn, "txid": txid, "status": row.status}


def tronscan_tx_info(txid: str, timeout: int = 15) -> dict:
    """TronScan 单笔查询（v1 人工核验用）：返回链上原始 JSON。"""
    try:
        import httpx
    except Exception:
        return {"error": "httpx not available"}
    url = f"https://apilist.tronscanapi.com/api/transaction-info?hash={txid}"
    try:
        r = httpx.get(url, timeout=timeout, headers={"User-Agent": "ai24x-crypto-verify/1.0"})
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.warning("tronscan query failed txid=%s err=%s", txid, e)
        return {"error": str(e)}


def verify_crypto_order(
    db: Session, *, out_trade_no: str, auth_user_id: Optional[int] = None, mock: bool = True
) -> dict:
    """v1 人工核验。mock=True 本地模拟直接入账（测试用）；mock=False 走 TronScan 链上核验。"""
    otn = str(out_trade_no or "").strip()
    row = db.query(TokenPayOrder).filter(TokenPayOrder.out_trade_no == otn).first()
    if not row:
        raise HTTPException(status_code=404, detail="订单不存在")
    if auth_user_id is not None and int(row.auth_user_id) != int(auth_user_id):
        raise HTTPException(status_code=403, detail="订单不属于当前用户")
    if row.status == "paid":
        return {
            "ok": True,
            "duplicate": True,
            "out_trade_no": otn,
            "status": "paid",
            "balance": get_balance_snapshot(db, int(row.auth_user_id)),
        }
    txid = str(row.transaction_id or "").strip()
    if not mock:
        if not txid:
            raise HTTPException(status_code=409, detail="订单未提交 txid")
        info = tronscan_tx_info(txid)
        if info.get("error") or not info:
            row.status = "verify_failed"
            db.commit()
            raise HTTPException(status_code=409, detail="链上查询失败，请稍后重试或联系客服")
        # v1 人工核验：链上数据由管理员人工对照收款地址/金额/确认数
        # （自动匹配逻辑在 v2 监听脚本 crypto_listener.py 实现）
    tx_id = txid or f"MOCKCRYPTO{int(time.time())}"
    r = try_fulfill(
        db,
        out_trade_no=otn,
        transaction_id=tx_id,
        amount_fen=int(row.amount_fen),
        channel_tag="crypto",
    )
    if not r.get("ok"):
        row.status = "verify_failed"
        db.commit()
        raise HTTPException(status_code=409, detail=str(r.get("error") or "fulfill_failed"))
    return r
