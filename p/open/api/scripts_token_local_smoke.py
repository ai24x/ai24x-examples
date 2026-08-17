"""本地冒烟：冻结 / 价表 / models 脱敏 / webhook 履约（TestClient，不依赖外埠重启）。"""
from __future__ import annotations

import json
import sys
import uuid

from fastapi.testclient import TestClient

from database import SessionLocal, init_db
from main import app
from models import AuthUser, TokenPayOrder
from auth_user_service import hash_password, set_user_frozen, is_user_frozen
from config import settings


def _key() -> str:
    return (settings.sms_internal_key or "").strip()


def main() -> int:
    init_db()
    c = TestClient(app)
    fails: list[str] = []

    # 1) plans admin
    if not _key():
        print("SKIP admin checks: SMS_INTERNAL_KEY empty")
    else:
        r = c.get("/v1/admin/token/plans", headers={"X-SMS-Internal-Key": _key()})
        if r.status_code != 200 or not r.json().get("ok"):
            fails.append(f"plans {r.status_code} {r.text[:120]}")
        else:
            print("OK plans", len(r.json().get("plans") or []))

        r = c.get("/v1/admin/token/routing", headers={"X-SMS-Internal-Key": _key()})
        if r.status_code != 200 or not r.json().get("upstream_mode"):
            fails.append(f"routing {r.status_code}")
        else:
            print("OK routing", r.json().get("upstream_mode"))

    # 2) public models scrub
    r = c.get("/v1/models")
    j = r.json() if r.status_code == 200 else {}
    note = str(j.get("note") or "")
    if "DeepSeek" in note or "deepseek/deepseek" in note:
        fails.append("models note still names DeepSeek")
    else:
        print("OK models note scrub")
    l1m = (j.get("layers") or {}).get("L1", {}).get("models") or []
    if any("deepseek" in str(x).lower() for x in l1m):
        fails.append(f"L1 models leak {l1m}")
    else:
        print("OK L1 models", l1m)

    # 3) freeze roundtrip on first user or create temp
    db = SessionLocal()
    try:
        u = db.query(AuthUser).order_by(AuthUser.id.asc()).first()
        created = False
        if not u:
            u = AuthUser(
                email=f"freeze_smoke_{uuid.uuid4().hex[:8]}@example.com",
                password_hash=hash_password("SmokeTest9"),
            )
            db.add(u)
            db.commit()
            db.refresh(u)
            created = True
        uid = int(u.id)
        set_user_frozen(db, user_id=uid, frozen=True, reason="smoke")
        db.refresh(u)
        if not is_user_frozen(u):
            fails.append("freeze flag not set")
        login = c.post(
            "/v1/auth/login",
            json={"email": u.email, "password": "SmokeTest9"} if created else {"email": u.email or "x", "password": "wrong"},
        )
        # if we don't know password for existing user, only test freeze API
        if _key():
            fr = c.post(
                f"/v1/admin/users/{uid}/freeze",
                headers={"X-SMS-Internal-Key": _key()},
                json={"reason": "smoke2"},
            )
            if fr.status_code != 200 or not fr.json().get("user", {}).get("frozen"):
                fails.append(f"admin freeze {fr.status_code} {fr.text[:120]}")
            else:
                print("OK admin freeze", uid)
            uf = c.post(
                f"/v1/admin/users/{uid}/unfreeze",
                headers={"X-SMS-Internal-Key": _key()},
                json={},
            )
            if uf.status_code != 200 or uf.json().get("user", {}).get("frozen"):
                fails.append(f"admin unfreeze {uf.status_code}")
            else:
                print("OK admin unfreeze", uid)
        else:
            set_user_frozen(db, user_id=uid, frozen=False)
            print("OK freeze helpers (no admin key)")
        if created:
            db.delete(u)
            db.commit()
    finally:
        db.close()

    # 4) webhook fake fulfill (needs pay enabled + user)
    db = SessionLocal()
    try:
        from token_pay_service import create_pending_order, token_pay_enabled

        if not token_pay_enabled():
            print("SKIP webhook: TOKEN_PAY_ENABLED off")
        else:
            u = db.query(AuthUser).order_by(AuthUser.id.asc()).first()
            if not u:
                print("SKIP webhook: no auth user")
            else:
                set_user_frozen(db, user_id=int(u.id), frozen=False)
                row = create_pending_order(
                    db, auth_user_id=int(u.id), plan="token_pack_10k", channel="paypal"
                )
                otn = row.out_trade_no
                cents = int(row.amount_fen or 0)
                cap = "SMOKE_" + uuid.uuid4().hex[:10]
                event = {
                    "event_type": "PAYMENT.CAPTURE.COMPLETED",
                    "resource": {
                        "id": cap,
                        "custom_id": otn,
                        "amount": {"currency_code": "USD", "value": f"{cents / 100:.2f}"},
                        "status": "COMPLETED",
                    },
                }
                wr = c.post("/v1/billing/paypal/webhook", content=json.dumps(event))
                wj = wr.json() if wr.status_code == 200 else {}
                if not wj.get("ok"):
                    fails.append(f"webhook {wr.status_code} {wj}")
                else:
                    print("OK webhook", otn)
                    # cleanup paid row optional
    except Exception as e:
        fails.append(f"webhook exc {e}")
    finally:
        db.close()

    if fails:
        print("FAIL", fails)
        return 1
    print("ALL SMOKE OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
