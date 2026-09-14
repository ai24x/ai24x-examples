$ErrorActionPreference = "Stop"
Set-Location C:\ai24x01\api
& .\venv\Scripts\python.exe -c @"
import sys
sys.path.insert(0, r'C:\ai24x01\api')
from database import SessionLocal
from models import AuthUser, TokenWallet, BillingLedger, TokenPayOrder

db = SessionLocal()
for em in ['ityizu@foxmail.com', 'lei@itxin.com']:
    u = db.query(AuthUser).filter(AuthUser.email == em).first()
    print('====', em, 'uid=', u.id if u else None)
    if not u:
        continue
    w = db.query(TokenWallet).filter(TokenWallet.auth_user_id == u.id).first()
    print(' wallet plan=', getattr(w,'plan',None), 'tok=', w.balance_tokens, 'usd_cents=', w.balance_usd, 'vip=', w.vip_expires_at)
    tops = (
        db.query(BillingLedger)
        .filter(BillingLedger.auth_user_id == u.id, BillingLedger.entry_type == 'topup')
        .order_by(BillingLedger.id.asc())
        .all()
    )
    print(' topups n=', len(tops))
    for t in tops[:20]:
        print('  topup id=', t.id, 'tok=', t.amount, 'usd=', t.amount_usd, 'note=', (t.note or '')[:100], 'at=', t.created_at)
    ords = (
        db.query(TokenPayOrder)
        .filter(TokenPayOrder.auth_user_id == u.id)
        .order_by(TokenPayOrder.id.asc())
        .all()
    )
    print(' orders n=', len(ords))
    for o in ords[:25]:
        print('  order', o.id, 'st=', o.status, 'ch=', o.channel, 'plan=', o.plan, 'product=', o.product,
              'fen=', o.amount_fen, 'usd=', o.amount_usd, 'otn=', (o.out_trade_no or '')[:40])
    # consume sample: how many have usd vs tokens
    from sqlalchemy import func
    cons = db.query(
        func.count(BillingLedger.id),
        func.coalesce(func.sum(BillingLedger.amount), 0),
        func.coalesce(func.sum(BillingLedger.amount_usd), 0),
    ).filter(BillingLedger.auth_user_id == u.id, BillingLedger.entry_type == 'consume').one()
    print(' consume: n=', cons[0], 'sum_tok=', cons[1], 'sum_usd_cents=', cons[2])
db.close()
"@
