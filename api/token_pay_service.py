"""
Token 在线支付：独立表 token_pay_orders，不读写 a1 的 pay_orders。

安全约定：
- 商户单号前缀 T（a1 为 M…），避免同商户号下混淆
- 回调只查 token_pay_orders；找不到则拒绝履约（绝不写 a1 配额）
- 真实支付默认关闭（TOKEN_PAY_ENABLED）；可用 mock 测钱包履约
"""
from __future__ import annotations

import logging
import secrets
import time
from datetime import datetime, timezone
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
    return bool(settings.token_pay_enabled)


def token_pay_mock_allowed() -> bool:
    """模拟到账开关。
    - 真支付已开（TOKEN_PAY_ENABLED）：仅当显式 TOKEN_PAY_MOCK_ENABLED=true 才允许
      （副脑实付联调务必保持 MOCK=false，避免白嫖到账）
    - 真支付未开：MOCK=true，或本机/dev/test 环境，可模拟履约
    """
    if token_pay_enabled():
        return bool(settings.token_pay_mock_enabled)
    if bool(settings.token_pay_mock_enabled):
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
    from pay_paypal import paypal_configured
    from pay_wechat_v3 import wechat_pay_configured

    wx_cfg = wechat_pay_configured(cfg)
    ali_cfg = alipay_configured(cfg)
    pp_cfg = paypal_configured(cfg)
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
            # ready = 可拉真单（开关开 + 商户齐）
            "wechat_ready": bool(enabled and wx_cfg),
            "alipay_ready": bool(enabled and ali_cfg),
            "paypal_ready": bool(enabled and pp_cfg),
        },
    }


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
    ch = (channel or "wechat")[:16]
    # PayPal：amount_fen 存 USD 美分；微信/支付宝仍为 CNY 分
    if ch == "paypal":
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

    plan = get_plan(str(row.plan))
    if not plan:
        return {"ok": False, "error": "plan_missing"}

    credit = int(plan.get("credit_tokens") or 0)
    set_vip = bool(plan.get("set_vip"))
    note = f"{channel_tag}:{otn}:{row.plan}"

    # VIP-only 月卡：到账 0 时写 1 token 作流水锚点（触发推荐结算）
    if credit <= 0 and set_vip:
        credit = 1
    if credit <= 0:
        return {"ok": False, "error": "nothing_to_fulfill"}

    topup_tokens(
        db,
        auth_user_id=int(row.auth_user_id),
        amount=int(credit),
        note=note,
        set_vip=set_vip,
        vip_days=int(plan.get("vip_days") or 30),
        validity_days=int(plan.get("validity_days") or 0) or None,
        plan=str(row.plan),
    )

    row.status = "paid"
    row.transaction_id = txid[:128]
    row.paid_at = _utcnow()
    row.updated_at = _utcnow()
    db.commit()
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


def admin_list_orders(
    db: Session,
    *,
    auth_user_id: Optional[int] = None,
    status: Optional[str] = None,
    channel: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
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
    rows = (
        query.order_by(TokenPayOrder.id.desc())
        .offset(max(0, int(offset)))
        .limit(min(200, max(1, int(limit))))
        .all()
    )
    return {
        "total": total,
        "rows": [
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
            }
            for r in rows
        ],
    }


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
