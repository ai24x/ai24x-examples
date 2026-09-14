"""
Creem Checkout API (international USD via Merchant-of-Record).

- test / live switched by CREEM_MODE (test-api.creem.io / api.creem.io)
- amount: token_pay_orders.amount_fen stores USD cents (same as PayPal)
- fulfill: checkout.completed webhook (HMAC-SHA256 verify) -> try_fulfill
"""
from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

_CREEM_TEST = "https://test-api.creem.io/v1"
_CREEM_LIVE = "https://api.creem.io/v1"


def creem_api_base(s: Any) -> str:
    mode = str(getattr(s, "creem_mode", "test") or "test").strip().lower()
    return _CREEM_LIVE if mode in ("live", "production", "prod") else _CREEM_TEST


def creem_configured(s: Any) -> bool:
    return bool(
        (getattr(s, "creem_api_key", "") or "").strip()
        and (getattr(s, "creem_webhook_secret", "") or "").strip()
    )


async def create_checkout_session(
    s: Any,
    *,
    product_id: str,
    request_id: str,
    success_url: str,
    customer_email: str = "",
    metadata: Optional[dict] = None,
) -> dict[str, Any]:
    """Create a Creem checkout; returns response JSON (incl. checkout_url)."""
    if not creem_configured(s):
        raise RuntimeError("creem_not_configured")
    pid = str(product_id or "").strip()
    if not pid:
        raise RuntimeError("missing_creem_product_id")
    rid = str(request_id or "").strip()
    if not rid:
        raise RuntimeError("missing_creem_request_id")
    body: dict[str, Any] = {
        "product_id": pid,
        "request_id": rid[:64],
        "success_url": (success_url or "https://www.ai24x.com/console.html").strip(),
        "metadata": metadata or {},
    }
    if customer_email:
        body["customer"] = {"email": str(customer_email)[:255]}
    url = f"{creem_api_base(s)}/checkouts"
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            url,
            json=body,
            headers={
                "x-api-key": str(getattr(s, "creem_api_key", "") or "").strip(),
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
    try:
        payload = r.json()
    except Exception:
        payload = {"raw": r.text}
    if r.status_code >= 400:
        raise RuntimeError(f"creem_create_checkout {r.status_code}: {payload}")
    return payload if isinstance(payload, dict) else {}


def verify_webhook_signature(
    s: Any,
    *,
    headers: dict[str, str],
    body: str,
) -> bool:
    """HMAC-SHA256(webhook_secret, raw body) hex vs creem-signature header."""
    secret = str(getattr(s, "creem_webhook_secret", "") or "").strip()
    if not secret:
        return False
    h = {k.lower(): v for k, v in headers.items()}
    expect = str(h.get("creem-signature") or "").strip()
    if not expect:
        return False
    raw = (body or "").encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest.lower(), expect.lower())


def extract_checkout_data(event: dict[str, Any]) -> dict[str, Any]:
    """Extract fulfillment fields from checkout.completed event."""
    obj = event.get("object") or {}
    if not isinstance(obj, dict):
        obj = {}
    order = obj.get("order") or {}
    if not isinstance(order, dict):
        order = {}
    product = obj.get("product") or {}
    if not isinstance(product, dict):
        product = {}
    customer = obj.get("customer") or {}
    if not isinstance(customer, dict):
        customer = {}

    def _int(v: Any) -> int:
        try:
            return int(float(str(v or 0)))
        except (TypeError, ValueError):
            return 0

    return {
        "request_id": str(obj.get("request_id") or "").strip(),
        "checkout_id": str(obj.get("id") or "").strip(),
        "status": str(obj.get("status") or "").strip().lower(),
        "order_id": str(order.get("id") or "").strip(),
        "amount": _int(order.get("amount") or 0),
        "amount_paid": _int(obj.get("amount_paid") or 0),
        "currency": str(order.get("currency") or "").strip().upper(),
        "product_id": str(product.get("id") or "").strip(),
        "customer_email": str(customer.get("email") or "").strip(),
    }