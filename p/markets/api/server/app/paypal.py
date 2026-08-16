"""AI24X Markets · PayPal 适配层（复用核心层 pay_paypal.py，共享不复制）。

身份复用核心层账号；订阅订单 custom_id 格式：markets:{user_id}:{plan}。
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

_CORE_API_DIR = Path(__file__).resolve().parents[5] / "api"  # ai24x01\api
if str(_CORE_API_DIR) not in sys.path:
    sys.path.append(str(_CORE_API_DIR))

import pay_paypal  # noqa: E402

from . import billing  # noqa: E402


class _Settings:
    """minimal settings object 供 pay_paypal 各函数读取。"""

    paypal_client_id = os.environ.get("PAYPAL_CLIENT_ID", "")
    paypal_client_secret = os.environ.get("PAYPAL_CLIENT_SECRET", "")
    paypal_mode = os.environ.get("PAYPAL_MODE", "sandbox")
    paypal_webhook_id = os.environ.get("PAYPAL_WEBHOOK_ID", "")
    paypal_locale = "en-US"
    paypal_landing_page = "BILLING"


_S = _Settings()


def configured() -> bool:
    return pay_paypal.paypal_configured(_S)


def make_custom_id(user_id: str, plan: str) -> str:
    return f"markets:{user_id}:{plan}"


def parse_custom_id(custom_id: str) -> Optional[Tuple[str, str]]:
    parts = (custom_id or "").split(":")
    if len(parts) >= 3 and parts[0] == "markets":
        return parts[1], parts[2]
    return None


async def create_checkout(user_id: str, plan: str) -> Dict[str, Any]:
    """创建 PayPal Checkout 订单，落库并返回支付跳转链接。"""
    if plan not in billing.PLANS:
        raise ValueError(f"unknown_plan:{plan}")
    if not configured():
        raise RuntimeError("paypal_not_configured")
    plan_info = billing.PLANS[plan]
    cid = make_custom_id(user_id, plan)
    return_url = os.environ.get(
        "MARKETS_PAYPAL_RETURN_URL", "https://markets.ai24x.com/app.html?pay=done"
    )
    # PayPal 批准后会自动向 return_url 追加 &token=<orderId>，前端 handlePayReturn 据此立即确认。
    cancel_url = os.environ.get(
        "MARKETS_PAYPAL_CANCEL_URL", "https://markets.ai24x.com/app.html#sub"
    )
    order = await pay_paypal.create_checkout_order(
        _S,
        out_trade_no=f"mk{user_id}{int(time.time())}",
        amount_usd=float(plan_info["usd"]),
        description=str(plan_info["description"]),
        return_url=return_url,
        cancel_url=cancel_url,
    )
    order_id = str(order.get("id") or "")
    if not order_id:
        raise RuntimeError("paypal_missing_order_id")
    billing.create_order(order_id, cid, float(plan_info["usd"]), plan)
    return {
        "order_id": order_id,
        "pay_url": pay_paypal.approve_url_from_order(order),
        "plan": plan,
        "amount_usd": f"{float(plan_info['usd']):.2f}",
        "currency": "USD",
        "channel": "paypal",
    }


async def fulfill_order(paypal_order_id: str) -> Dict[str, Any]:
    """查单 → 完成则解析 custom_id → 激活订阅（幂等）。"""
    if not configured():
        raise RuntimeError("paypal_not_configured")
    order = await pay_paypal.get_order(_S, paypal_order_id=paypal_order_id)
    if not pay_paypal.is_order_completed(order):
        return {"status": "not_completed", "order_id": paypal_order_id}
    cid = pay_paypal.extract_custom_id(order)
    parsed = parse_custom_id(cid)
    if not parsed:
        return {"status": "bad_custom_id", "custom_id": cid}
    user_id, plan = parsed
    billing.mark_order_paid(paypal_order_id)
    sub = billing.activate_subscription(user_id, plan, source="paypal")
    return {"status": "activated", "subscription": sub}


async def capture_and_fulfill(paypal_order_id: str) -> Dict[str, Any]:
    """回跳后 Capture + 履约（核心层同款模式，可当「确认到账」）。"""
    if not configured():
        raise RuntimeError("paypal_not_configured")
    captured = await pay_paypal.capture_order(_S, paypal_order_id=paypal_order_id)
    if not pay_paypal.is_order_completed(captured):
        return {"status": "not_completed", "order_id": paypal_order_id}
    return await fulfill_order(paypal_order_id)


async def handle_webhook(headers: Dict[str, str], body: str) -> Dict[str, Any]:
    """PayPal webhook 入口：验签 → 履约（幂等）。未配 webhook id 时降级为拒绝（走 capture 查单）。"""
    ok = await pay_paypal.verify_webhook_signature(_S, headers=headers, body=body)
    if not ok:
        raise PermissionError("paypal_webhook_bad_signature")
    try:
        event = json.loads(body)
    except Exception:
        raise ValueError("paypal_webhook_bad_json")
    etype = str(event.get("event_type") or "")
    if etype in ("CHECKOUT.ORDER.APPROVED", "PAYMENT.CAPTURE.COMPLETED"):
        resource = event.get("resource") or {}
        related = (resource.get("supplementary_data") or {}).get("related_ids") or {}
        order_id = (
            str(related.get("order_id") or "")
            or str(resource.get("id") or "")
            or str(resource.get("supplementary_data", {}).get("order_id") or "")
        )
        if order_id:
            return await fulfill_order(order_id)
    return {"status": "ignored", "event": etype}
