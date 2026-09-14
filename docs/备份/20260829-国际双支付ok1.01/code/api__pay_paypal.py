"""
PayPal Orders API v2（Token 充值）。

- Sandbox / Live 由 PAYPAL_MODE 切换
- 金额：下单用套餐 price_usd；token_pay_orders.amount_fen 存 **USD 分**（美分）
- 履约：Capture 成功或 Webhook → try_fulfill（T 前缀单）
"""
from __future__ import annotations

import base64
import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

_SANDBOX = "https://api-m.sandbox.paypal.com"
_LIVE = "https://api-m.paypal.com"


def paypal_api_base(s: Any) -> str:
    mode = str(getattr(s, "paypal_mode", "sandbox") or "sandbox").strip().lower()
    return _LIVE if mode in ("live", "production", "prod") else _SANDBOX


def paypal_configured(s: Any) -> bool:
    return bool(
        (getattr(s, "paypal_client_id", "") or "").strip()
        and (getattr(s, "paypal_client_secret", "") or "").strip()
    )


async def _access_token(s: Any) -> str:
    cid = str(getattr(s, "paypal_client_id", "") or "").strip()
    secret = str(getattr(s, "paypal_client_secret", "") or "").strip()
    if not cid or not secret:
        raise RuntimeError("paypal_not_configured")
    basic = base64.b64encode(f"{cid}:{secret}".encode("utf-8")).decode("ascii")
    url = f"{paypal_api_base(s)}/v1/oauth2/token"
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            url,
            data={"grant_type": "client_credentials"},
            headers={
                "Authorization": f"Basic {basic}",
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
    if r.status_code >= 400:
        raise RuntimeError(f"paypal_oauth_error {r.status_code}: {r.text[:400]}")
    tok = (r.json() or {}).get("access_token")
    if not tok:
        raise RuntimeError("paypal_oauth_missing_token")
    return str(tok)


def _approve_link(order: dict[str, Any]) -> str:
    for link in order.get("links") or []:
        if str(link.get("rel") or "") == "approve":
            return str(link.get("href") or "")
    return ""


async def create_checkout_order(
    s: Any,
    *,
    out_trade_no: str,
    amount_usd: float,
    description: str,
    return_url: str,
    cancel_url: str,
) -> dict[str, Any]:
    """创建 Checkout Order；返回 PayPal 原始 JSON（含 id / links）。"""
    if not paypal_configured(s):
        raise RuntimeError("paypal_not_configured")
    value = f"{float(amount_usd):.2f}"
    locale = str(getattr(s, "paypal_locale", "") or "en-US").strip() or "en-US"
    landing = str(getattr(s, "paypal_landing_page", "") or "BILLING").strip().upper() or "BILLING"
    if landing not in ("LOGIN", "BILLING", "NO_PREFERENCE"):
        landing = "BILLING"
    body = {
        "intent": "CAPTURE",
        "purchase_units": [
            {
                "reference_id": out_trade_no[:127],
                "custom_id": out_trade_no[:127],
                "description": (description or "AI24X Token")[:127],
                "amount": {"currency_code": "USD", "value": value},
            }
        ],
        "application_context": {
            "brand_name": "AI24X",
            "locale": locale,
            "landing_page": landing,
            "user_action": "PAY_NOW",
            "shipping_preference": "NO_SHIPPING",
            "return_url": return_url,
            "cancel_url": cancel_url,
        },
    }
    token = await _access_token(s)
    url = f"{paypal_api_base(s)}/v2/checkout/orders"
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            url,
            json=body,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Prefer": "return=representation",
            },
        )
    try:
        payload = r.json()
    except Exception:
        payload = {"raw": r.text}
    if r.status_code >= 400:
        raise RuntimeError(f"paypal_create_order {r.status_code}: {payload}")
    return payload


async def capture_order(s: Any, *, paypal_order_id: str) -> dict[str, Any]:
    if not paypal_configured(s):
        raise RuntimeError("paypal_not_configured")
    pid = str(paypal_order_id or "").strip()
    if not pid:
        raise RuntimeError("missing_paypal_order_id")
    token = await _access_token(s)
    url = f"{paypal_api_base(s)}/v2/checkout/orders/{pid}/capture"
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Prefer": "return=representation",
            },
        )
    try:
        payload = r.json()
    except Exception:
        payload = {"raw": r.text}
    if r.status_code >= 400:
        raise RuntimeError(f"paypal_capture {r.status_code}: {payload}")
    return payload


async def get_order(s: Any, *, paypal_order_id: str) -> dict[str, Any]:
    if not paypal_configured(s):
        raise RuntimeError("paypal_not_configured")
    pid = str(paypal_order_id or "").strip()
    token = await _access_token(s)
    url = f"{paypal_api_base(s)}/v2/checkout/orders/{pid}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(
            url,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        )
    try:
        payload = r.json()
    except Exception:
        payload = {"raw": r.text}
    if r.status_code >= 400:
        raise RuntimeError(f"paypal_get_order {r.status_code}: {payload}")
    return payload


def extract_custom_id(order: dict[str, Any]) -> str:
    for pu in order.get("purchase_units") or []:
        cid = str(pu.get("custom_id") or pu.get("reference_id") or "").strip()
        if cid:
            return cid
    return ""


def extract_capture_id(order: dict[str, Any]) -> str:
    for pu in order.get("purchase_units") or []:
        payments = pu.get("payments") or {}
        for cap in payments.get("captures") or []:
            cid = str(cap.get("id") or "").strip()
            if cid:
                return cid
    return str(order.get("id") or "")


def extract_captured_usd_cents(order: dict[str, Any]) -> int:
    for pu in order.get("purchase_units") or []:
        payments = pu.get("payments") or {}
        for cap in payments.get("captures") or []:
            amt = cap.get("amount") or {}
            try:
                return int(round(float(amt.get("value") or 0) * 100))
            except Exception:
                continue
        amt = pu.get("amount") or {}
        try:
            return int(round(float(amt.get("value") or 0) * 100))
        except Exception:
            pass
    return 0


def is_order_completed(order: dict[str, Any]) -> bool:
    st = str(order.get("status") or "").upper()
    if st == "COMPLETED":
        return True
    for pu in order.get("purchase_units") or []:
        payments = pu.get("payments") or {}
        for cap in payments.get("captures") or []:
            if str(cap.get("status") or "").upper() == "COMPLETED":
                return True
    return False


async def verify_webhook_signature(
    s: Any,
    *,
    headers: dict[str, str],
    body: str,
) -> bool:
    """
    使用 PayPal verify-webhook-signature。
    未配置 PAYPAL_WEBHOOK_ID 时返回 False（调用方应拒绝或改走 capture 查单）。
    """
    wh_id = str(getattr(s, "paypal_webhook_id", "") or "").strip()
    if not wh_id or not paypal_configured(s):
        return False
    h = {k.lower(): v for k, v in headers.items()}
    transmission_id = h.get("paypal-transmission-id") or ""
    timestamp = h.get("paypal-transmission-time") or ""
    cert_url = h.get("paypal-cert-url") or ""
    auth_algo = h.get("paypal-auth-algo") or ""
    transmission_sig = h.get("paypal-transmission-sig") or ""
    if not (transmission_id and timestamp and cert_url and auth_algo and transmission_sig):
        return False
    import json

    try:
        event = json.loads(body)
    except Exception:
        return False
    token = await _access_token(s)
    url = f"{paypal_api_base(s)}/v1/notifications/verify-webhook-signature"
    payload = {
        "transmission_id": transmission_id,
        "transmission_time": timestamp,
        "cert_url": cert_url,
        "auth_algo": auth_algo,
        "transmission_sig": transmission_sig,
        "webhook_id": wh_id,
        "webhook_event": event,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
    if r.status_code >= 400:
        logger.warning("paypal webhook verify http %s %s", r.status_code, r.text[:200])
        return False
    return str((r.json() or {}).get("verification_status") or "").upper() == "SUCCESS"


def approve_url_from_order(order: dict[str, Any]) -> str:
    return _approve_link(order)
