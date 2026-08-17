# -*- coding: utf-8 -*-
"""临时专项测试：定价履约(credit_tokens) + T13 共享池熔断（写本地测试数据，可清理）"""
import sys, os, uuid, pathlib
sys.path.insert(0, ".")
from database import SessionLocal
from models import AuthUser, TokenPayOrder, BillingLedger
from auth_user_service import hash_password

PASSWORD = "Test1234!"
results = []

def record(name, ok, detail=""):
    results.append({"name": name, "ok": bool(ok), "detail": str(detail)[:400]})
    print(("PASS " if ok else "FAIL ") + name + ("  " + str(detail)[:250] if detail else ""))

db = SessionLocal()

def fresh_user(tag):
    em = f"pr-{tag}-{uuid.uuid4().hex[:8]}@ai24x.local"
    u = AuthUser(email=em, password_hash=hash_password(PASSWORD))
    db.add(u); db.commit(); db.refresh(u)
    return u, em

def topup_ledger_amount(uid, plan):
    row = (db.query(BillingLedger)
           .filter(BillingLedger.auth_user_id == int(uid), BillingLedger.entry_type == "topup",
                   BillingLedger.note.like(f"%:{plan}"))
           .order_by(BillingLedger.id.desc()).first())
    return int(row.amount) if row else None

# ---------- 定价履约 ----------
try:
    from token_pay_service import create_pending_order, try_fulfill
    from token_mvp_service import get_balance_snapshot

    for tag, plan, exp_tokens, exp_usd in [
        ("starter", "token_pack_10k", 1_000_000, 200),
        ("builder", "token_pack_100k", 50_000_000, 2000),
        ("scale", "token_vip_month_50w", 200_000_000, 9900),
    ]:
        u, em = fresh_user(tag)
        row = create_pending_order(db, auth_user_id=int(u.id), plan=plan, channel="paypal")
        r = try_fulfill(db, out_trade_no=str(row.out_trade_no), transaction_id=f"tx-{uuid.uuid4().hex[:12]}", amount_fen=int(row.amount_fen), channel_tag="paypal")
        snap = get_balance_snapshot(db, int(u.id))
        ledger_tok = topup_ledger_amount(int(u.id), plan)
        ok = bool(r.get("ok")) and ledger_tok == exp_tokens and int(snap.get("balance_usd") or 0) == exp_usd
        ok = ok and int(snap.get("balance_tokens") or 0) >= exp_tokens
        record(f"PACK_{tag}_credit_tokens_fulfilled", ok, f"plan={plan} ledger_tok={ledger_tok} expect={exp_tokens} bal_tok={snap.get('balance_tokens')} usd={snap.get('balance_usd')} expect={exp_usd}")
except Exception as e:
    record("PACK_*_credit_tokens_fulfilled", False, repr(e))

# vip 资格包：credit_tokens=0 应只开通 VIP、不发额度（2026-08-05 起不再回退 flash 锚换算）
try:
    from token_pay_service import create_pending_order, try_fulfill
    from token_mvp_service import get_balance_snapshot
    u, em = fresh_user("vip-pass")
    row = create_pending_order(db, auth_user_id=int(u.id), plan="token_vip_month", channel="paypal")
    r = try_fulfill(db, out_trade_no=str(row.out_trade_no), transaction_id=f"tx-{uuid.uuid4().hex[:12]}", amount_fen=int(row.amount_fen), channel_tag="paypal")
    snap = get_balance_snapshot(db, int(u.id))
    got_tok = topup_ledger_amount(int(u.id), "token_vip_month")
    ok = bool(r.get("ok")) and got_tok is None and int(snap.get("balance_tokens") or 0) == 0 and bool(snap.get("is_vip_active"))
    record("PACK_vip_pass_no_credits", ok, f"ledger={got_tok} bal={snap.get('balance_tokens')} vip={snap.get('is_vip_active')}")
except Exception as e:
    record("PACK_vip_pass_no_credits", False, repr(e))

# ---------- T13 熔断 ----------
try:
    import free_shared
    tpath = pathlib.Path("data") / f"_t13_test_{uuid.uuid4().hex[:6]}.json"
    free_shared._USAGE_PATH = tpath
    free_shared._usage_cache = {}
    free_shared._usage_cache_ts = 0.0
    old_def = dict(free_shared._DEFAULTS)
    free_shared._DEFAULTS["pool_alert_tokens"] = 1000
    free_shared._DEFAULTS["pool_break_tokens"] = 3000
    free_shared._DEFAULTS["pool_break_reqs"] = 0
    free_shared._DEFAULTS["pool_break_action"] = "disable"
    free_shared.record_pool_upstream_usage(catalog_id="or-mimo", tokens=1200)
    free_shared.record_pool_upstream_usage(catalog_id="silicon-qwen", tokens=2000)
    st = free_shared.pool_breaker_state()
    cfg = free_shared.effective_config()
    ok = bool(st.get("active")) and st.get("action") == "disable" and cfg.get("enabled") is False
    record("T13_breaker_disable", ok, f"active={st.get('active')} enabled={cfg.get('enabled')}")
    free_shared._DEFAULTS.clear(); free_shared._DEFAULTS.update(old_def)
    free_shared._DEFAULTS["pool_alert_tokens"] = 1000
    free_shared._DEFAULTS["pool_break_tokens"] = 3000
    free_shared._DEFAULTS["pool_break_reqs"] = 0
    free_shared._DEFAULTS["pool_break_action"] = "free-router"
    data = free_shared._load_usage()
    data["date"] = "2099-01-01"
    free_shared._save_usage(data)
    free_shared.record_pool_upstream_usage(catalog_id="or-mimo", tokens=1200)
    free_shared.record_pool_upstream_usage(catalog_id="or-mimo", tokens=2000)
    st2 = free_shared.pool_breaker_state()
    cfg2 = free_shared.effective_config()
    ok2 = bool(st2.get("active")) and cfg2.get("prefer") == "or-free-router" and cfg2.get("pool_enabled") == ["or-free-router"]
    record("T13_breaker_free_router", ok2, f"prefer={cfg2.get('prefer')} pool={cfg2.get('pool_enabled')}")
    free_shared._DEFAULTS.clear(); free_shared._DEFAULTS.update(old_def)
    try:
        os.remove(str(tpath))
    except OSError:
        pass
except Exception as e:
    record("T13_*", False, repr(e))

failed = [r for r in results if not r["ok"]]
print(f"\n=== {len(results)-len(failed)}/{len(results)} passed ===")
if failed:
    print("FAILED:", [r["name"] for r in failed])
    sys.exit(1)
