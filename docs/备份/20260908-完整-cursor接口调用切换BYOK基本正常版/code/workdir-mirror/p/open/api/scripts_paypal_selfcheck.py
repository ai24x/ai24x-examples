#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PayPal 模块自检（无真实密钥时只测导入与未配置行为）。"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

API = Path(__file__).resolve().parent
sys.path.insert(0, str(API))


def main() -> int:
    from pay_paypal import (
        approve_url_from_order,
        extract_capture_id,
        extract_captured_usd_cents,
        extract_custom_id,
        is_order_completed,
        paypal_api_base,
        paypal_configured,
    )

    empty = SimpleNamespace(paypal_client_id="", paypal_client_secret="", paypal_mode="sandbox")
    assert paypal_configured(empty) is False
    assert "sandbox" in paypal_api_base(empty)

    sample = {
        "id": "ORDER123",
        "status": "COMPLETED",
        "purchase_units": [
            {
                "custom_id": "T1demo",
                "reference_id": "T1demo",
                "amount": {"currency_code": "USD", "value": "1.00"},
                "payments": {
                    "captures": [
                        {
                            "id": "CAP999",
                            "status": "COMPLETED",
                            "amount": {"currency_code": "USD", "value": "1.00"},
                        }
                    ]
                },
            }
        ],
        "links": [{"rel": "approve", "href": "https://www.sandbox.paypal.com/checkoutnow?token=ORDER123"}],
    }
    assert extract_custom_id(sample) == "T1demo"
    assert extract_capture_id(sample) == "CAP999"
    assert extract_captured_usd_cents(sample) == 100
    assert is_order_completed(sample) is True
    assert "checkoutnow" in approve_url_from_order(sample)

    from token_pay_service import public_plans

    plans = public_plans()
    assert "paypal_ready" in plans["pay"]
    assert "paypal_configured" in plans["pay"]
    print("OK paypal self-check", {"paypal_ready": plans["pay"]["paypal_ready"], "mode": plans["pay"].get("paypal_mode")})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
