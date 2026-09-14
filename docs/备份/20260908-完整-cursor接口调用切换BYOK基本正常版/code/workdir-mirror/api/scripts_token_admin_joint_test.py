#!/usr/bin/env python3
"""
Token admin + credit-lot joint test (does not print secrets).

Usage (from api/):
  python scripts_token_admin_joint_test.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi.testclient import TestClient

from config import settings
from main import app


def main() -> int:
    # 2026-08-22：管理接口优先独立 ADMIN_API_KEY，未配才回退 SMS 内部密钥
    key = (settings.admin_api_key or settings.sms_internal_key or "").strip()
    if not key:
        print("FAIL: ADMIN_API_KEY / SMS_INTERNAL_KEY missing")
        return 1
    h = {"X-Admin-Key": key, "X-SMS-Internal-Key": key}
    c = TestClient(app)
    out = {}

    r = c.get("/v1/billing/plans")
    assert r.status_code == 200, r.text
    plans = r.json()
    out["paypal_ready"] = bool((plans.get("pay") or {}).get("paypal_ready"))
    out["validity"] = {
        p["plan"]: p.get("validity_days") for p in (plans.get("plans") or [])
    }
    assert out["validity"].get("token_pack_10k") == 365

    r = c.get("/v1/admin/token/summary", headers=h)
    assert r.status_code == 200, r.text
    summary = r.json()
    out["summary_users"] = summary.get("users")
    out["active_lots"] = (summary.get("credits") or {}).get("active_lots")
    out["active_tokens"] = (summary.get("credits") or {}).get("active_tokens")
    out["pay_pills"] = {
        k: (summary.get("pay") or {}).get(k)
        for k in ("enabled", "wechat_ready", "alipay_ready", "paypal_ready", "mock_allowed")
    }

    r = c.get("/v1/admin/token/orders", headers=h, params={"limit": 5})
    assert r.status_code == 200, r.text
    orders = r.json()
    out["orders_total"] = orders.get("total")

    r = c.get("/v1/admin/token/orders/export.csv", headers=h, params={"limit": 20})
    assert r.status_code == 200, r.text
    body = r.content
    assert b"out_trade_no" in body
    out["csv_bytes"] = len(body)
    out["csv_has_header"] = True

    from database import SessionLocal
    from models import AuthUser

    db = SessionLocal()
    try:
        u = db.query(AuthUser).order_by(AuthUser.id.asc()).first()
        uid = int(u.id) if u else None
    finally:
        db.close()
    if uid:
        r = c.get("/v1/admin/token/wallet", headers=h, params={"auth_user_id": uid})
        assert r.status_code == 200, r.text
        before = r.json().get("balance_tokens") or 0
        r = c.post(
            "/v1/admin/token/topup",
            headers=h,
            json={
                "auth_user_id": uid,
                "amount": 17,
                "note": "joint_test_topup",
                "validity_days": 90,
            },
        )
        assert r.status_code == 200, r.text
        after = r.json()
        out["topup_user"] = uid
        out["balance_before"] = before
        out["balance_after"] = after.get("balance_tokens")
        out["credits_expire_at"] = after.get("credits_expire_at")
        assert int(after.get("balance_tokens") or 0) >= int(before) + 17
        assert after.get("credits_expire_at")
    else:
        out["topup_user"] = None

    r = c.get("/token-admin.html")
    out["admin_page"] = r.status_code
    assert r.status_code == 200
    # UI markers (utf-8)
    assert "btnExportCsv".encode("ascii") in r.content
    assert "topDays".encode("ascii") in r.content
    assert "ordChannel".encode("ascii") in r.content

    print(json.dumps({"ok": True, **out}, ensure_ascii=False, indent=2))
    if not out["paypal_ready"]:
        print(
            "NOTE: PayPal not ready — set PAYPAL_CLIENT_ID/SECRET in api/.env then retest Sandbox.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
