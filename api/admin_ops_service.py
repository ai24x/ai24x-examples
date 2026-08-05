"""管理端：用户列表、成本毛利简报、告警摘要（无密钥）。"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from models import AuthUser, BillingLedger, TokenPayOrder, TokenWallet


def admin_list_users(
    db: Session,
    *,
    q: str = "",
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    limit = max(1, min(200, int(limit or 50)))
    offset = max(0, int(offset or 0))
    query = db.query(AuthUser)
    term = (q or "").strip()
    if term:
        if term.isdigit():
            query = query.filter(
                or_(AuthUser.id == int(term), AuthUser.phone.contains(term), AuthUser.email.contains(term))
            )
        else:
            like = f"%{term}%"
            query = query.filter(or_(AuthUser.email.ilike(like), AuthUser.phone.ilike(like)))
    total = int(query.count() or 0)
    rows = query.order_by(AuthUser.id.desc()).offset(offset).limit(limit).all()
    out = []
    for u in rows:
        w = db.query(TokenWallet).filter(TokenWallet.auth_user_id == int(u.id)).first()
        bal = int(w.balance_tokens or 0) if w else 0
        usd = int(w.balance_usd or 0) if w else 0
        plan = ""
        if w is not None:
            plan = w.plan.value if hasattr(w.plan, "value") else str(w.plan or "")
        frozen = bool(getattr(u, "frozen_at", None))
        out.append(
            {
                "id": int(u.id),
                "email": u.email or "",
                "phone": u.phone or "",
                "frozen": frozen,
                "freeze_reason": (getattr(u, "freeze_reason", None) or "") or None,
                "balance_tokens": bal,
                "balance_usd": usd,
                "balance_usd_display": f"${usd / 100:.2f}",
                "plan": plan or "free",
                "created_at": u.created_at.isoformat() if u.created_at else None,
                "utm_source": (getattr(u, "utm_source", None) or "") or None,
                "utm_medium": (getattr(u, "utm_medium", None) or "") or None,
                "utm_campaign": (getattr(u, "utm_campaign", None) or "") or None,
                "utm_content": (getattr(u, "utm_content", None) or "") or None,
                "gclid": (getattr(u, "gclid", None) or "") or None,
                "acquired_at": u.acquired_at.isoformat()
                if getattr(u, "acquired_at", None)
                else None,
            }
        )
    return {"ok": True, "total": total, "limit": limit, "offset": offset, "rows": out}


def admin_acquisition_funnel(db: Session, *, days: int = 14) -> dict[str, Any]:
    """
    渠道→注册→已支付订单（join auth_users，不在订单表冗余 UTM）。
    供投流日报 / A/B/C 组对照。
    """
    days = max(1, min(90, int(days or 14)))
    since = datetime.now(timezone.utc) - timedelta(days=days)

    regs = (
        db.query(AuthUser)
        .filter(AuthUser.created_at >= since)
        .order_by(AuthUser.id.desc())
        .limit(2000)
        .all()
    )
    by_campaign: dict[str, dict[str, Any]] = {}
    for u in regs:
        key = (getattr(u, "utm_campaign", None) or getattr(u, "utm_source", None) or "(none)").strip()
        bucket = by_campaign.setdefault(
            key,
            {
                "utm_campaign": getattr(u, "utm_campaign", None),
                "utm_source": getattr(u, "utm_source", None),
                "utm_medium": getattr(u, "utm_medium", None),
                "registers": 0,
                "paid_users": 0,
                "paid_orders": 0,
                "paid_amount_fen": 0,
            },
        )
        bucket["registers"] += 1

    paid = (
        db.query(TokenPayOrder)
        .filter(TokenPayOrder.status == "paid", TokenPayOrder.paid_at >= since)
        .order_by(TokenPayOrder.id.desc())
        .limit(5000)
        .all()
    )
    paid_users_seen: set[int] = set()
    order_rows = []
    for o in paid:
        u = db.query(AuthUser).filter(AuthUser.id == int(o.auth_user_id)).first()
        src = (getattr(u, "utm_source", None) if u else None) or None
        camp = (getattr(u, "utm_campaign", None) if u else None) or None
        med = (getattr(u, "utm_medium", None) if u else None) or None
        key = (camp or src or "(none)").strip()
        bucket = by_campaign.setdefault(
            key,
            {
                "utm_campaign": camp,
                "utm_source": src,
                "utm_medium": med,
                "registers": 0,
                "paid_users": 0,
                "paid_orders": 0,
                "paid_amount_fen": 0,
            },
        )
        bucket["paid_orders"] += 1
        bucket["paid_amount_fen"] += int(o.amount_fen or 0)
        uid = int(o.auth_user_id)
        if uid not in paid_users_seen:
            bucket["paid_users"] += 1
            paid_users_seen.add(uid)

        order_rows.append(
            {
                "out_trade_no": o.out_trade_no,
                "auth_user_id": uid,
                "plan": o.plan,
                "amount_fen": int(o.amount_fen or 0),
                "channel": o.channel,
                "paid_at": o.paid_at.isoformat() if o.paid_at else None,
                "utm_source": src,
                "utm_medium": med,
                "utm_campaign": camp,
                "utm_content": (getattr(u, "utm_content", None) if u else None) or None,
                "gclid": (getattr(u, "gclid", None) if u else None) or None,
            }
        )

    campaigns = sorted(
        by_campaign.values(),
        key=lambda x: (-int(x.get("paid_amount_fen") or 0), -int(x.get("registers") or 0)),
    )
    return {
        "ok": True,
        "days": days,
        "since": since.isoformat(),
        "campaigns": campaigns,
        "paid_orders": order_rows[:200],
        "note": "UTM on user (first-touch at register); orders joined by auth_user_id",
    }


def admin_economics(db: Session, *, days: int = 7) -> dict[str, Any]:
    """
    粗算毛利：收入=已支付订单；成本=消耗 token × 估算上游单价（Flash 均价）。
    非精确对账，供运营看方向。
    """
    days = max(1, min(90, int(days or 7)))
    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)

    consume_tokens = int(
        db.query(func.coalesce(func.sum(func.abs(BillingLedger.amount)), 0))
        .filter(BillingLedger.entry_type == "consume", BillingLedger.created_at >= since)
        .scalar()
        or 0
    )
    # 上游成本粗算（非售价）：Flash 地板约 $0.24/M；售价锚见 TOKEN_FLASH_REF_USD_PER_M≈0.35
    try:
        cost_per_m = float(os.getenv("TOKEN_ECON_COST_USD_PER_M") or "0.24")
    except ValueError:
        cost_per_m = 0.24
    if cost_per_m <= 0:
        cost_per_m = 0.24
    est_cost_usd = round((consume_tokens / 1_000_000.0) * cost_per_m, 4)

    paid_cny_fen = int(
        db.query(func.coalesce(func.sum(TokenPayOrder.amount_fen), 0))
        .filter(
            TokenPayOrder.status == "paid",
            TokenPayOrder.channel.in_(("wechat", "alipay")),
            TokenPayOrder.paid_at >= since,
        )
        .scalar()
        or 0
    )
    paid_usd_cents = int(
        db.query(func.coalesce(func.sum(TokenPayOrder.amount_fen), 0))
        .filter(
            TokenPayOrder.status == "paid",
            TokenPayOrder.channel == "paypal",
            TokenPayOrder.paid_at >= since,
        )
        .scalar()
        or 0
    )
    # CNY→USD 粗算 7.2
    rev_usd = round(paid_cny_fen / 100.0 / 7.2 + paid_usd_cents / 100.0, 4)
    margin = round(rev_usd - est_cost_usd, 4)

    new_users = int(
        db.query(func.count(AuthUser.id)).filter(AuthUser.created_at >= since).scalar() or 0
    )
    from token_pay_service import pending_order_expired

    _pend_rows = db.query(TokenPayOrder).filter(TokenPayOrder.status == "pending").all()
    pending = len(
        [x for x in _pend_rows if not pending_order_expired(x) and not getattr(x, "confirmed_unpaid_at", None)]
    )
    pending_expired = len([x for x in _pend_rows if pending_order_expired(x)])
    confirmed_unpaid = len([x for x in _pend_rows if getattr(x, "confirmed_unpaid_at", None)])

    return {
        "ok": True,
        "days": days,
        "since": since.isoformat(),
        "consume_tokens": consume_tokens,
        "est_upstream_cost_usd": est_cost_usd,
        "revenue_usd_est": rev_usd,
        "paid_cny_yuan": round(paid_cny_fen / 100.0, 2),
        "paid_usd": round(paid_usd_cents / 100.0, 2),
        "gross_margin_usd_est": margin,
        "new_users": new_users,
        "pending_orders": pending,
        "pending_expired": pending_expired,
        "pending_confirmed_unpaid": confirmed_unpaid,
        "note": (
            "成本按上游 Flash 地板粗算（默认 $0.24/M，可用 TOKEN_ECON_COST_USD_PER_M 覆盖）；"
            "售价锚见 TOKEN_FLASH_REF_USD_PER_M。"
            "会低估 Claude/GPT 等高倍率名模真实上游成本——"
            "请到「模型仓库」维护各 VIP 的 cost_in/out，并看「用量监控」按模型拆分；精确对账对照上游账单。"
        ),
        "usage_hint": "GET /v1/admin/token/usage_monitor",
        "pricing_hint": "POST /v1/admin/token/model_warehouse vip_rates",
    }


def admin_usage_monitor(db: Session, *, days: int = 1, top_n: int = 20) -> dict[str, Any]:
    """
    高消耗监测：按用户 / 按模型拆分平台额度消耗，标出异常阈值。
    用于发现刷接口、倍率漏乘、异常大户。
    """
    days = max(1, min(30, int(days or 1)))
    top_n = max(5, min(50, int(top_n or 20)))
    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)

    # 按用户消耗
    user_rows = (
        db.query(
            BillingLedger.auth_user_id,
            func.coalesce(func.sum(func.abs(BillingLedger.amount)), 0).label("tokens"),
            func.count(BillingLedger.id).label("n"),
        )
        .filter(BillingLedger.entry_type == "consume", BillingLedger.created_at >= since)
        .group_by(BillingLedger.auth_user_id)
        .order_by(func.sum(func.abs(BillingLedger.amount)).desc())
        .limit(top_n)
        .all()
    )
    top_users = []
    for uid, tokens, n in user_rows:
        u = db.query(AuthUser).filter(AuthUser.id == int(uid)).first()
        tok = int(tokens or 0)
        # 日均 > 50 万平台 token 或单用户占比较高 → 标红关注
        flag = "high" if tok >= 500_000 * days else ("watch" if tok >= 100_000 * days else "ok")
        top_users.append(
            {
                "auth_user_id": int(uid),
                "email": (u.email if u else "") or "",
                "phone": (u.phone if u else "") or "",
                "frozen": bool(getattr(u, "frozen_at", None)) if u else False,
                "consume_tokens": tok,
                "ledger_rows": int(n or 0),
                "flag": flag,
            }
        )

    # 按模型消耗（ledger.model）
    model_rows = (
        db.query(
            func.coalesce(BillingLedger.model, "(empty)"),
            func.coalesce(func.sum(func.abs(BillingLedger.amount)), 0).label("tokens"),
            func.count(BillingLedger.id).label("n"),
        )
        .filter(BillingLedger.entry_type == "consume", BillingLedger.created_at >= since)
        .group_by(func.coalesce(BillingLedger.model, "(empty)"))
        .order_by(func.sum(func.abs(BillingLedger.amount)).desc())
        .limit(top_n)
        .all()
    )
    top_models = []
    for mid, tokens, n in model_rows:
        mid_s = str(mid or "")
        tok = int(tokens or 0)
        # 国际高倍率名模标通道风险
        is_intl = mid_s.startswith("vip-gpt") or "claude" in mid_s or "gemini" in mid_s
        flag = "intl_vip" if is_intl and tok > 0 else ("high" if tok >= 1_000_000 * days else "ok")
        top_models.append(
            {
                "model": mid_s,
                "consume_tokens": tok,
                "ledger_rows": int(n or 0),
                "flag": flag,
            }
        )

    total_consume = int(
        db.query(func.coalesce(func.sum(func.abs(BillingLedger.amount)), 0))
        .filter(BillingLedger.entry_type == "consume", BillingLedger.created_at >= since)
        .scalar()
        or 0
    )

    # 通道 ready 摘要（不暴露密钥）
    providers = {}
    try:
        from upstream_providers import list_providers_admin

        providers = list_providers_admin()
    except Exception as e:
        providers = {"ok": False, "error": str(e)[:120]}

    alerts: list[dict[str, Any]] = []
    for row in top_users:
        if row["flag"] == "high":
            alerts.append(
                {
                    "level": "warn",
                    "code": "user_high_burn",
                    "msg": f"用户 {row['auth_user_id']} 近{days}日消耗 {row['consume_tokens']} 平台 token",
                }
            )
    intl_burn = sum(int(m["consume_tokens"]) for m in top_models if m.get("flag") == "intl_vip")
    if intl_burn >= 200_000 * days:
        alerts.append(
            {
                "level": "warn",
                "code": "intl_vip_burn",
                "msg": f"国际名模近{days}日合计消耗约 {intl_burn} 平台 token，请对账 OR/厂账单",
            }
        )

    return {
        "ok": True,
        "days": days,
        "since": since.isoformat(),
        "total_consume_tokens": total_consume,
        "top_users": top_users,
        "top_models": top_models,
        "providers": providers,
        "alerts": alerts,
        "thresholds": {
            "user_high_per_day": 500_000,
            "user_watch_per_day": 100_000,
            "intl_burn_warn_per_day": 200_000,
        },
        "ops_note": (
            "消耗为平台额度（已含 VIP billing_mult）。"
            "发现 high 用户：先查流水与请求，必要时冻结；"
            "通道仓库见 providers；填 Key 后即可启用备用。"
        ),
    }


def admin_ops_alerts(db: Session) -> dict[str, Any]:
    """轻量告警：不发飞书，只返回列表供管理台展示。"""
    from model_router import _layer_upstream, _upstream_mode

    alerts: list[dict[str, Any]] = []
    mode = _upstream_mode()
    l1 = _layer_upstream("L1")
    l0 = _layer_upstream("L0")
    if not l1.get("key"):
        alerts.append({"level": "error", "code": "llm_l1_no_key", "msg": "主档 L1 未配置密钥"})
    if not l0.get("key"):
        alerts.append(
            {
                "level": "warn",
                "code": "llm_l0_no_key",
                "msg": "兜底 L0 未配置（建议硅基或 OR L0），主档故障时无法降级",
            }
        )
    from token_pay_service import pending_order_expired

    _pend_rows = db.query(TokenPayOrder).filter(TokenPayOrder.status == "pending").all()
    pending = len(
        [x for x in _pend_rows if not pending_order_expired(x) and not getattr(x, "confirmed_unpaid_at", None)]
    )
    expired = len([x for x in _pend_rows if pending_order_expired(x)])
    kept = len(
        [
            x
            for x in _pend_rows
            if pending_order_expired(x) and getattr(x, "transaction_id", None) and not getattr(x, "confirmed_unpaid_at", None)
        ]
    )
    confirmed = len([x for x in _pend_rows if getattr(x, "confirmed_unpaid_at", None)])
    tail = []
    if kept:
        tail.append(f"有交易号待对账 {kept} 笔")
    if expired:
        tail.append(f"过期未付 {expired} 笔已过滤")
    if confirmed:
        tail.append(f"已确认未收款 {confirmed} 笔")
    extra = ("（" + "；".join(tail) + "）") if tail else ""
    if pending >= 5:
        alerts.append(
            {
                "level": "warn",
                "code": "pay_pending_backlog",
                "msg": f"有效待履约订单 {pending} 笔，请及时查单" + extra,
            }
        )
    elif pending > 0:
        alerts.append(
            {
                "level": "info",
                "code": "pay_pending",
                "msg": f"有效待履约订单 {pending} 笔" + extra,
            }
        )
    try:
        from llm_keys import get_key, recent_vip_degrades

        if not get_key("OPENROUTER_API_KEY_FREE") and get_key("OPENROUTER_API_KEY"):
            alerts.append(
                {
                    "level": "warn",
                    "code": "or_free_key_missing",
                    "msg": "未配 OR 免费 Key，共享通道可能占用主收银 Key",
                }
            )
        if not get_key("SILICONFLOW_API_KEY_FREE") and get_key("SILICONFLOW_API_KEY"):
            alerts.append(
                {
                    "level": "warn",
                    "code": "sf_free_key_missing",
                    "msg": "未配硅基免费 Key，L0/共享可能占用主硅基 Key",
                }
            )
        deg = recent_vip_degrades(5)
        if deg:
            last = deg[-1]
            alerts.append(
                {
                    "level": "warn",
                    "code": "vip_degraded",
                    "msg": (
                        f"VIP 点名曾降级：{last.get('public_id')} → "
                        f"{last.get('to_provider')}/{last.get('to_model')}（请补同名映射或查 OR）"
                    ),
                }
            )
    except Exception:
        pass
    try:
        um = admin_usage_monitor(db, days=1, top_n=5)
        for a in um.get("alerts") or []:
            alerts.append(a)
    except Exception:
        pass
    return {
        "ok": True,
        "upstream_mode": mode,
        "alerts": alerts,
        "count": len(alerts),
    }
