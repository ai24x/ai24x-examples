# -*- coding: utf-8 -*-
"""P2 点名模每日上限 单测（本地 PostgreSQL；测试数据运行后清理）。"""
import sys, uuid
sys.path.insert(0, ".")

from fastapi import HTTPException

from database import init_db, SessionLocal
from models import AuthUser, VipNamedDailyUsage
from auth_user_service import hash_password
import vip_named_guard as g

PASSWORD = "Test1234!"
results = []


def record(name, ok, detail=""):
    results.append({"name": name, "ok": bool(ok), "detail": str(detail)[:300]})
    print(("PASS " if ok else "FAIL ") + name + ("  " + str(detail)[:200] if detail else ""))


init_db()
db = SessionLocal()
uid = None
try:
    em = f"p2-{uuid.uuid4().hex[:8]}@ai24x.local"
    u = AuthUser(email=em, password_hash=hash_password(PASSWORD))
    db.add(u)
    db.commit()
    db.refresh(u)
    uid = int(u.id)
    model = "gpt-5"  # 别名，应归一为 vip-gpt5
    cid = "vip-gpt5"
    day = g.usage_date()

    # 1) 首次检查通过（自动建行）
    g.check_named_daily_limit(db, uid, model)
    row = db.query(VipNamedDailyUsage).filter_by(auth_user_id=uid, model_id=cid, usage_date=day).first()
    record("first_check_ok", row is not None and int(row.call_count) == 0 and int(row.credits_used) == 0)

    # 2) 记录一次后仍通过且计数正确
    g.record_named_usage(db, uid, model, 1200)
    g.check_named_daily_limit(db, uid, model)
    row = db.query(VipNamedDailyUsage).filter_by(auth_user_id=uid, model_id=cid, usage_date=day).first()
    record("after_one_ok", int(row.call_count) == 1 and int(row.credits_used) == 1200)

    # 3) 次数达上限 → 429 named_daily_limit
    row.call_count = 200
    db.commit()
    try:
        g.check_named_daily_limit(db, uid, model)
        record("call_limit_429", False, "expected 429")
    except HTTPException as e:
        record("call_limit_429", e.status_code == 429 and (e.detail or {}).get("code") == "named_daily_limit")

    # 4) credits 达上限 → 429
    row.call_count = 1
    row.credits_used = 50000
    db.commit()
    try:
        g.check_named_daily_limit(db, uid, model)
        record("credit_limit_429", False, "expected 429")
    except HTTPException as e:
        record("credit_limit_429", e.status_code == 429 and (e.detail or {}).get("code") == "named_daily_limit")

    # 5) 不同模型独立计数，互不影响
    g.check_named_daily_limit(db, uid, "claude-opus")  # 别名 → 归一为 vip-claude-opus
    row2 = db.query(VipNamedDailyUsage).filter_by(auth_user_id=uid, model_id="vip-claude-opus", usage_date=day).first()
    record("per_model_independent", row2 is not None and int(row2.call_count) == 0)

except Exception as e:
    record("suite", False, repr(e))
finally:
    try:
        if uid:
            db.query(VipNamedDailyUsage).filter_by(auth_user_id=uid).delete()
            db.query(AuthUser).filter(AuthUser.id == uid).delete()
            db.commit()
    except Exception:
        db.rollback()
    db.close()

failed = [r for r in results if not r["ok"]]
print("RESULT:", "ALL PASS" if not failed else "FAILED %d" % len(failed))
sys.exit(1 if failed else 0)
