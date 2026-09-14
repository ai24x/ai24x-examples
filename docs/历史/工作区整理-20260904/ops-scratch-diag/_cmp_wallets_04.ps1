$ErrorActionPreference = "Stop"
Set-Location C:\ai24x01\api
& .\venv\Scripts\python.exe -c @"
import sys
sys.path.insert(0, r'C:\ai24x01\api')
from database import SessionLocal
from models import AuthUser, TokenWallet
db=SessionLocal()
for em in ['ityizu@foxmail.com','lei@itxin.com']:
  u=db.query(AuthUser).filter(AuthUser.email==em).first()
  w=db.query(TokenWallet).filter(TokenWallet.auth_user_id==u.id).first() if u else None
  print(em, 'uid', u.id if u else None)
  if w:
    print('  balance_tokens', w.balance_tokens, 'balance_usd', getattr(w,'balance_usd',None), 'vip', getattr(w,'is_vip_active',None) or getattr(w,'vip_until',None))
    for a in dir(w):
      pass
    cols=[c.name for c in w.__table__.columns]
    print('  cols', cols)
    d={c: getattr(w,c) for c in cols}
    print(' ', {k:d[k] for k in d if 'bal' in k or 'vip' in k or 'usd' in k or 'token' in k})
db.close()
"@
