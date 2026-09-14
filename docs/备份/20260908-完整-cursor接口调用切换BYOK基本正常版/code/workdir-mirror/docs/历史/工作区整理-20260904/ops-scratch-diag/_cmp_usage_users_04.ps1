# Compare usage chart data for two emails (read-only).
$ErrorActionPreference = "Stop"
Set-Location C:\ai24x01\api
$py = @"
import os, sys
sys.path.insert(0, r'C:\ai24x01\api')
os.chdir(r'C:\ai24x01\api')
from database import SessionLocal
from models import AuthUser, BillingLedger
from sqlalchemy import func
from datetime import datetime, timezone, timedelta
from token_mvp_service import usage_daily, usage_models

db = SessionLocal()
emails = ['ityizu@foxmail.com', 'lei@itxin.com']
for em in emails:
    u = db.query(AuthUser).filter(AuthUser.email == em).first()
    print('====', em, '====')
    if not u:
        print('NOT_FOUND')
        continue
    print('id=', u.id, 'created=', getattr(u, 'created_at', None))
    # ledger summary by entry_type
    rows = (
        db.query(
            BillingLedger.entry_type,
            func.count(BillingLedger.id),
            func.coalesce(func.sum(BillingLedger.tokens), 0),
            func.coalesce(func.sum(func.abs(BillingLedger.amount_usd)), 0),
        )
        .filter(BillingLedger.auth_user_id == int(u.id))
        .group_by(BillingLedger.entry_type)
        .all()
    )
    for r in rows:
        print(' type=', r[0], 'n=', int(r[1]), 'tokens=', int(r[2]), 'usd_cents=', int(r[3]))
    # recent consume sample
    cons = (
        db.query(BillingLedger)
        .filter(BillingLedger.auth_user_id == int(u.id), BillingLedger.entry_type == 'consume')
        .order_by(BillingLedger.id.desc())
        .limit(5)
        .all()
    )
    print(' recent_consume=', len(cons))
    for c in cons:
        print('  id=', c.id, 'tok=', c.tokens, 'usd=', c.amount_usd, 'model=', c.model, 'at=', c.created_at)
    # any ledger without consume
    total_n = db.query(func.count(BillingLedger.id)).filter(BillingLedger.auth_user_id == int(u.id)).scalar()
    print(' total_ledger=', int(total_n or 0))
    d = usage_daily(db, int(u.id), days=30)
    tot_tok = sum(int(x.get('tokens') or 0) for x in d['rows'])
    tot_usd = sum(int(x.get('usd_cents') or 0) for x in d['rows'])
    tot_calls = sum(int(x.get('calls') or 0) for x in d['rows'])
    print(' usage_daily_30d tokens=', tot_tok, 'usd_cents=', tot_usd, 'calls=', tot_calls)
    m = usage_models(db, int(u.id), days=30, top_n=5)
    print(' usage_models rows=', len(m.get('rows') or []), 'total_usd=', m.get('total_usd_cents'), 'total_tok=', m.get('total_tokens'))
db.close()
print('DONE')
"@
$p = 'C:\Users\Administrator\ops\_cmp_usage_users.py'
Set-Content -LiteralPath $p -Value $py -Encoding UTF8
& C:\ai24x01\api\venv\Scripts\python.exe $p
