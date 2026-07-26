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
        # scripts_sync_pay_from_a1 可能把换行存成 \n
        return (s or "").replace("\\n", "\n").strip()

    return SimpleNamespace(
        wechat_mch_id=(settings.wechat_mch_id or "").strip(),
        wechat_app_id=(settings.wechat_app_id or "").strip(),
        wechat_mch_serial_no=(settings.wechat_mch_serial_no or "").strip(),
        wechat_mch_private_key_path=(settings.wechat_mch_private_key_path or "").strip(),
        wechat_mch_private_key_pem=_pem(settings.wechat_mch_private_key_pem or ""),
        wechat_api_v3_key=(settings.wechat_api_v3_key or "").strip(),
        wechat_notify_url=(settings.token_wechat_notify_url or "").strip(),
        wechat_pay_host=(settings.wechat_pay_host or "https://api.mch.weixin.qq.com").strip(),
        # Token 侧默认强制验签（比 a1 测试开关更严）
        wechat_notify_skip_verify=bool(settings.wechat_notify_skip_verify)
        if (settings.app_env or "").strip().lower() not in ("prod", "production")
        else False,
        alipay_app_id=(settings.alipay_app_id or "").strip(),
        alipay_gateway=(settings.alipay_gateway or "https://openapi.alipay.com/gateway.do").strip(),
        alipay_notify_url=(settings.token_alipay_notify_url or "").strip(),
        alipay_return_url=(settings.token_alipay_return_url or "").strip(),
        alipay_merchant_private_key_path=(settings.alipay_merchant_private_key_path or "").strip(),
        alipay_merchant_private_key_pem=_pem(settings.alipay_merchant_private_key_pem or ""),
        alipay_public_key=_pem(settings.alipay_public_key or ""),
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
    from pay_wechat_v3 import wechat_pay_configured

    wx_cfg = wechat_pay_configured(cfg)
    ali_cfg = alipay_configured(cfg)
    enabled = token_pay_enabled()
    return {
        "plans": list_public_plans(),
        "pay": {
            "enabled": enabled,
            "mock_allowed": token_pay_mock_allowed(),
            "wechat_configured": wx_cfg,
            "alipay_configured": ali_cfg,
            # ready = 可拉真单（开关开 + 商户齐）
            "wechat_ready": bool(enabled and wx_cfg),
            "alipay_ready": bool(enabled and ali_cfg),
        },
    }


def create_pending_order(
    db: Session,
    *,
    auth_user_id: int,
    plan: str,
    channel: str,
) -> TokenPayOrder:
    u = db.query(AuthUser).filter(AuthUser.id == int(auth_user_id)).first()
    if not u:
        raise HTTPException(status_code=404, detail="用户不存在")
    try:
        plan_id, price_fen = normalize_plan(plan)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    otn = mk_out_trade_no(int(auth_user_id))
    row = TokenPayOrder(
        out_trade_no=otn,
        auth_user_id=int(auth_user_id),
        plan=plan_id,
        amount_fen=int(price_fen),
        channel=(channel or "wechat")[:16],
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
    q: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    query = db.query(TokenPayOrder)
    if auth_user_id is not None:
        query = query.filter(TokenPayOrder.auth_user_id == int(auth_user_id))
    if status:
        query = query.filter(TokenPayOrder.status == str(status).strip())
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
