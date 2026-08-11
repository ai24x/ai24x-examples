"""Local crypto (USDT-TRC20) order flow test. English only output."""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import time
import httpx

BASE = "http://127.0.0.1:8000"
PASSWORD = "TestCrypto#2026x"
EMAIL = f"cryptotest{int(time.time())}@example.com"

def main():
    c = httpx.Client(base_url=BASE, timeout=15)
    # 1) register with dev code
    s = c.post("/v1/auth/email/send", json={"email": EMAIL, "purpose": "register"}).json()
    code = s.get("local_code") or s.get("dev_code")
    if not code:
        print("FAIL register-send:", str(s)[:300]); return 1
    r = c.post("/v1/auth/register", json={"email": EMAIL, "email_code": code, "password": PASSWORD})
    j = r.json()
    tok = j.get("access_token") or j.get("token") or ""
    if not tok:
        print("FAIL register:", r.status_code, str(j)[:300]); return 1
    H = {"Authorization": f"Bearer {tok}"}
    print("PASS register user:", EMAIL)

    # 2) pick cheapest plan
    plans = c.get("/v1/billing/plans").json().get("plans", [])
    p0 = min(plans, key=lambda p: float(p.get("price_usd") or 0))
    plan = p0.get("plan")
    print("plan:", plan, "price_usd:", p0.get("price_usd"))

    # 3) create crypto order
    o = c.post("/v1/billing/crypto/order", json={"plan": plan}, headers=H).json()
    print("create:", str(o)[:400])
    otn = o.get("out_trade_no")
    addr = o.get("address")
    if not otn or not addr:
        print("FAIL create-crypto"); return 1
    print("PASS create-crypto otn:", otn, "addr:", addr)

    # 4) submit txid
    txid = "0x" + "a" * 60
    sub = c.post("/v1/billing/crypto/submit", json={"out_trade_no": otn, "txid": txid}, headers=H).json()
    print("submit:", str(sub)[:300])
    if sub.get("status") != "awaiting_verify":
        print("FAIL submit status"); return 1
    print("PASS submit awaiting_verify")

    # 5) verify (mock) -> fulfill
    v = c.post("/v1/billing/crypto/verify", json={"out_trade_no": otn}, headers=H).json()
    print("verify:", str(v)[:400])
    if not v.get("ok"):
        print("FAIL verify"); return 1
    print("PASS verify fulfilled")

    # 6) orders list
    lst = c.get("/v1/billing/orders", headers=H).json().get("rows", [])
    mine = [x for x in lst if x.get("out_trade_no") == otn]
    print("order status now:", mine[0].get("status") if mine else "NOT FOUND")
    bal = v.get("balance") or {}
    print("balance keys:", list(bal.keys())[:8])
    print("ALL PASS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())