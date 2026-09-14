# -*- coding: utf-8 -*-
"""临时专项测试：T1/T2/T3/T4/T8/T10/T11（写本地测试数据，可清理）"""
import sys, json, threading, time, uuid
sys.path.insert(0, ".")
from fastapi.testclient import TestClient
from main import app
from database import SessionLocal
from models import AuthUser
from auth_user_service import hash_password

PASSWORD = "Test1234!"
results = []

def record(name, ok, detail=""):
    results.append({"name": name, "ok": bool(ok), "detail": str(detail)[:300]})
    print(("PASS " if ok else "FAIL ") + name + ("  " + str(detail)[:200] if detail else ""))

def fresh_user(db, tag):
    em = f"batch-{tag}-{uuid.uuid4().hex[:8]}@ai24x.local"
    u = AuthUser(email=em, password_hash=hash_password(PASSWORD))
    db.add(u); db.commit(); db.refresh(u)
    return u, em

c = TestClient(app)
db = SessionLocal()

# ---------- T11 登录频控 ----------
try:
    u, em = fresh_user(db, "t11")
    codes = []
    for i in range(8):
        r = c.post("/v1/auth/login", json={"email": em, "password": "wrong-pass"})
        codes.append(r.status_code)
    r9 = c.post("/v1/auth/login", json={"email": em, "password": PASSWORD})
    record("T11_login_throttle_9th_429", all(x == 401 for x in codes) and r9.status_code == 429, f"first8={codes} 9th={r9.status_code}")
except Exception as e:
    record("T11_login_throttle_9th_429", False, repr(e))

# ---------- T10 OTP 锁 ----------
try:
    from email_otp_memory import store_otp, verify_and_consume_otp
    em = f"otp-{uuid.uuid4().hex[:8]}@ai24x.local"
    store_otp(em, "register", "123456", ttl_s=300)
    res = [verify_and_consume_otp(em, "register", "000000") for _ in range(5)]
    locked = verify_and_consume_otp(em, "register", "123456")
    record("T10_otp_5_fail_lock", res == [False]*5 and locked is False, f"5xFalse locked={locked}")
    # P2 确认：重新发码是否清锁
    store_otp(em, "register", "654321", ttl_s=300)
    after_resend = verify_and_consume_otp(em, "register", "654321")
    record("P2_otp_resend_clears_lock", after_resend is True, f"after_resend_correct_code={after_resend} (lock cleared by resend = known P2)")
except Exception as e:
    record("T10_otp_5_fail_lock", False, repr(e))

# ---------- T8 client_ip ----------
try:
    from security_util import client_ip
    class FakeReq:
        def __init__(self, headers): self.headers = headers; self.client = type("C", (), {"host": "203.0.113.9"})()
    r1 = client_ip(FakeReq({"x-real-ip": "198.51.100.7", "x-forwarded-for": "8.8.8.8, 9.9.9.9"}))
    r2 = client_ip(FakeReq({"x-forwarded-for": "8.8.8.8, 9.9.9.9"}))
    r3 = client_ip(FakeReq({}))
    record("T8_client_ip", r1 == "198.51.100.7" and r2 == "9.9.9.9" and r3 == "203.0.113.9", f"xri={r1} xff_right={r2} fallback={r3}")
except Exception as e:
    record("T8_client_ip", False, repr(e))

# ---------- T4 mock 生产硬禁 ----------
try:
    from token_pay_service import token_pay_mock_allowed
    from config import settings
    dev_val = token_pay_mock_allowed()
    old = settings.app_env
    settings.app_env = "production"
    prod_val = token_pay_mock_allowed()
    settings.app_env = old
    record("T4_mock_prod_disable", dev_val is True and prod_val is False, f"dev={dev_val} prod={prod_val}")
except Exception as e:
    record("T4_mock_prod_disable", False, repr(e))

# ---------- T2 预检拒绝 + 夹断 ----------
try:
    from token_mvp_service import topup_tokens, get_balance_snapshot, consume_tokens, assert_can_spend
    from services import estimate_need_tokens
    from fastapi import HTTPException
    u2, _ = fresh_user(db, "t2")
    topup_tokens(db, auth_user_id=int(u2.id), amount=100, note="batch_t2", commit_via=None) if False else None
    from token_mvp_service import _credit_lot
    _credit_lot(db, auth_user_id=int(u2.id), amount=100, entry_type="topup", source="topup", validity_days=365, note="batch_t2")
    need = estimate_need_tokens(model="flash", max_tokens=16384, prompt="")
    rejected = False
    try:
        assert_can_spend(db, int(u2.id), need_tokens=need, model="flash")
    except HTTPException as e:
        rejected = e.status_code == 429
    # 夹断：余额 100，请求 5000 -> 扣 100
    consume_tokens(db, auth_user_id=int(u2.id), tokens=5000, model="flash")
    snap = get_balance_snapshot(db, int(u2.id))
    from models import BillingLedger
    last = db.query(BillingLedger).filter(BillingLedger.auth_user_id == int(u2.id), BillingLedger.entry_type == "consume").order_by(BillingLedger.id.desc()).first()
    record("T2_precheck_429_and_clamp", rejected and int(snap.get("balance_tokens") or 0) == 0 and int(last.amount or 0) == -100,
           f"need={need} rejected429={rejected} bal_after={snap.get('balance_tokens')} ledger={last.amount if last else None}")
except Exception as e:
    record("T2_precheck_429_and_clamp", False, repr(e))

# ---------- T3 双账本扣减 ----------
try:
    from token_mvp_service import topup_usd
    u3, _ = fresh_user(db, "t3")
    topup_usd(db, auth_user_id=int(u3.id), usd_cents=10000, note="batch_t3")  # $100 -> tokens
    s0 = get_balance_snapshot(db, int(u3.id))
    consume_tokens(db, auth_user_id=int(u3.id), tokens=1000, amount_usd=45, model="flash")
    s1 = get_balance_snapshot(db, int(u3.id))
    record("T3_dual_ledger_deduct", int(s0.get("balance_tokens")) - int(s1.get("balance_tokens")) == 1000 and int(s0.get("balance_usd")) - int(s1.get("balance_usd")) == 45,
           f"tokens {s0.get('balance_tokens')}->{s1.get('balance_tokens')} usd {s0.get('balance_usd')}->{s1.get('balance_usd')}")
except Exception as e:
    record("T3_dual_ledger_deduct", False, repr(e))

# ---------- T1 并发双 webhook 只入账一次 ----------
try:
    from token_pay_service import create_pending_order, token_pay_enabled
    u4, em4 = fresh_user(db, "t1")
    # 新用户无 paid 记录；用非 promo 套餐 token_pack_100k
    row = create_pending_order(db, auth_user_id=int(u4.id), plan="token_pack_100k", channel="paypal")
    otn = row.out_trade_no
    cents = int(row.amount_fen or 0)
    tx1, tx2 = "SMOKE_T1_A_" + uuid.uuid4().hex[:8], "SMOKE_T1_B_" + uuid.uuid4().hex[:8]
    def fire(txid):
        ev = {"event_type": "PAYMENT.CAPTURE.COMPLETED", "resource": {"id": txid, "custom_id": otn, "amount": {"currency_code": "USD", "value": f"{cents/100:.2f}"}, "status": "COMPLETED"}}
        return c.post("/v1/billing/paypal/webhook", content=json.dumps(ev))
    outs = []
    ths = [threading.Thread(target=lambda: outs.append(fire(tx1).status_code)), threading.Thread(target=lambda: outs.append(fire(tx2).status_code))]
    [t.start() for t in ths]; [t.join() for t in ths]
    db.expire_all()
    from models import TokenPayOrder
    ord2 = db.query(TokenPayOrder).filter(TokenPayOrder.out_trade_no == otn).first()
    snap4 = get_balance_snapshot(db, int(u4.id))
    # 期望：两个 webhook 都返回 200（一个 ok 一个 duplicate），只有一次入账；
    # 到账口径=套餐 credit_tokens（50M），2026-08-05 起履约按契约不再按 flash 锚换算
    expected_once = int(snap4.get("balance_tokens") or 0)
    record("T1_concurrent_webhook_single_credit",
           len(outs) == 2 and str(ord2.status) == "paid" and expected_once == 50_000_000,
           f"http={sorted(outs)} status={ord2.status} txid={ord2.transaction_id[:20]} bal={expected_once}")
except Exception as e:
    record("T1_concurrent_webhook_single_credit", False, repr(e))

db.close()
passed = sum(1 for r in results if r["ok"])
print(f"\nSUMMARY {passed}/{len(results)} passed")
json.dump(results, open("_tmp_batch_test_last.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
sys.exit(0 if passed == len(results) else 1)
