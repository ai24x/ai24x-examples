"""
Dodo Payments Checkout (international USD via Merchant-of-Record).

- test / live switched by DODO_MODE (test.dodopayments.com / live.dodopayments.com)
- amount: token_pay_orders.amount_fen stores USD cents (same as PayPal/Creem)
- fulfill: payment.succeeded webhook (Standard Webhooks HMAC-SHA256 verify) -> try_fulfill
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import time
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

_DODO_TEST = "https://test.dodopayments.com"
_DODO_LIVE = "https://live.dodopayments.com"


def dodo_api_base(s: Any) -> str:
    mode = str(getattr(s, "dodo_mode", "test") or "test").strip().lower()
    return _DODO_LIVE if mode in ("live", "production", "prod") else _DODO_TEST


def dodo_configured(s: Any) -> bool:
    """API key + webhook secret both set => merchant ready."""
    return bool(
        (getattr(s, "dodo_api_key", "") or "").strip()
        and (getattr(s, "dodo_webhook_secret", "") or "").strip()
    )


def dodo_api_key_ready(s: Any) -> bool:
    return bool((getattr(s, "dodo_api_key", "") or "").strip())


async def create_checkout_session(
    s: Any,
    *,
    product_id: str,
    request_id: str,
    success_url: str,
    cancel_url: str = "",
    customer_email: str = "",
    metadata: Optional[dict] = None,
) -> dict[str, Any]:
    """Create a Dodo checkout session; returns response JSON (incl. checkout_url)."""
    if not dodo_api_key_ready(s):
        raise RuntimeError("dodo_not_configured")
    pid = str(product_id or "").strip()
    if not pid:
        raise RuntimeError("missing_dodo_product_id")
    rid = str(request_id or "").strip()
    if not rid:
        raise RuntimeError("missing_dodo_request_id")
    fallback = "https://www.ai24x.com/console.html"
    body: dict[str, Any] = {
        "product_cart": [{"product_id": pid, "quantity": 1}],
        "metadata": dict(metadata or {}),
        "return_url": (success_url or fallback).strip(),
        "cancel_url": (cancel_url or fallback).strip(),
        "feature_flags": {
            "redirect_immediately": True,
            # Hosted checkout: only collect country (+ ZIP where tax requires it).
            "enable_minimal_address_collection": True,
        },
        "customization": {"theme": "dark"},
    }
    email = str(customer_email or "").strip()[:255]
    if email:
        # Prefill customer info; Dodo's hosted page lets the buyer verify/edit it.
        name = email.split("@", 1)[0].strip() or "AI24X User"
        body["customer"] = {"name": name[:120], "email": email}
    url = f"{dodo_api_base(s)}/checkouts"
    key = str(getattr(s, "dodo_api_key", "") or "").strip()
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            url,
            json=body,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
    try:
        payload = r.json()
    except Exception:
        payload = {"raw": r.text}
    if r.status_code >= 400:
        raise RuntimeError(f"dodo_create_checkout {r.status_code}: {payload}")
    return payload if isinstance(payload, dict) else {}


async def get_checkout_session(s: Any, session_id: str) -> dict[str, Any]:
    """GET /checkouts/{id} — payment_status / payment_id for manual fulfill."""
    if not dodo_api_key_ready(s):
        raise RuntimeError("dodo_not_configured")
    sid = str(session_id or "").strip()
    if not sid:
        raise RuntimeError("missing_checkout_session_id")
    url = f"{dodo_api_base(s)}/checkouts/{sid}"
    key = str(getattr(s, "dodo_api_key", "") or "").strip()
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(
            url,
            headers={
                "Authorization": f"Bearer {key}",
                "Accept": "application/json",
            },
        )
    try:
        payload = r.json()
    except Exception:
        payload = {"raw": r.text}
    if r.status_code >= 400:
        raise RuntimeError(f"dodo_get_checkout {r.status_code}: {payload}")
    return payload if isinstance(payload, dict) else {}


def _webhook_key_bytes(secret: str) -> bytes:
    """Standard Webhooks signing key = whsec_ stripped, then base64-decoded."""
    stripped = secret
    if stripped.startswith("whsec_"):
        stripped = stripped[len("whsec_"):]
    try:
        return base64.b64decode(stripped, validate=True)
    except Exception:
        return stripped.encode("utf-8")


def verify_webhook_signature(
    s: Any,
    *,
    headers: dict[str, str],
    body: str,
    max_age_sec: int = 300,
) -> bool:
    """Standard Webhooks HMAC-SHA256(webhook_id.timestamp.body) vs webhook-signature."""
    secret = str(getattr(s, "dodo_webhook_secret", "") or "").strip()
    if not secret:
        return False
    h = {k.lower(): v for k, v in headers.items()}
    wh_id = str(h.get("webhook-id") or "").strip()
    wh_ts = str(h.get("webhook-timestamp") or "").strip()
    sig = str(h.get("webhook-signature") or "").strip()
    if not (wh_id and wh_ts and sig):
        return False
    try:
        ts = int(wh_ts)
        if max_age_sec > 0 and abs(int(time.time()) - ts) > max_age_sec:
            logger.warning("dodo webhook timestamp too old ts=%s", wh_ts)
            return False
    except (TypeError, ValueError):
        return False
    msg = f"{wh_id}.{wh_ts}.{body}".encode("utf-8")
    digest = hmac.new(_webhook_key_bytes(secret), msg, hashlib.sha256).digest()
    expect = base64.b64encode(digest).decode("ascii")
    # header format: v1,<sig> (multiple values possible, comma separated)
    for part in sig.split(","):
        part = part.strip()
        if not part:
            continue
        if part.startswith("v1,"):
            part = part[len("v1,"):]
        if hmac.compare_digest(part, expect):
            return True
    return False


def extract_payment_data(event: dict[str, Any]) -> dict[str, Any]:
    """Extract fulfillment fields from payment.succeeded / payment.failed event."""
    data = event.get("data") or {}
    if not isinstance(data, dict):
        data = {}
    cart = data.get("product_cart") or []
    first = cart[0] if isinstance(cart, list) and cart else {}
    if not isinstance(first, dict):
        first = {}
    customer = data.get("customer") or {}
    if not isinstance(customer, dict):
        customer = {}
    meta = data.get("metadata") or {}
    if not isinstance(meta, dict):
        meta = {}

    def _int(v: Any) -> int:
        try:
            return int(float(str(v or 0)))
        except (TypeError, ValueError):
            return 0

    return {
        "event_type": str(event.get("type") or "").strip(),
        "payment_id": str(data.get("payment_id") or "").strip(),
        "checkout_id": str(data.get("checkout_session_id") or "").strip(),
        "out_trade_no": str(meta.get("out_trade_no") or "").strip(),
        "plan": str(meta.get("plan") or "").strip(),
        "status": str(data.get("status") or "").strip().lower(),
        "amount": _int(data.get("total_amount") or 0),
        "currency": str(data.get("currency") or "").strip().upper(),
        "product_id": str(first.get("product_id") or "").strip(),
        "customer_email": str(customer.get("email") or "").strip(),
    }
