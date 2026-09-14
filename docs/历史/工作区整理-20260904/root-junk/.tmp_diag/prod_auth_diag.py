import hashlib
import json
import os
import sys
os.chdir(r"C:\ai24x01\api")
sys.path.insert(0, os.getcwd())
from sqlalchemy.engine import make_url
from config import settings
from database import SessionLocal
from models import ApiKey, AuthUser, TokenWallet
u = make_url(settings.database_url)
print(json.dumps({"cwd":os.getcwd(),"python":sys.executable,"config":__import__("config").__file__,"db":{"driver":u.drivername,"host":u.host,"port":u.port,"database":u.database},"secret_len":len(settings.secret_key or ""),"secret_hash16":hashlib.sha256((settings.secret_key or "").encode()).hexdigest()[:16]}, ensure_ascii=True))
db = SessionLocal()
try:
    out=[]
    for kid in (92,101,42,94,103):
        k=db.query(ApiKey).filter(ApiKey.id==kid).first()
        if not k:
            out.append({"id":kid,"found":False}); continue
        au=db.query(AuthUser).filter(AuthUser.id==k.auth_user_id).first()
        w=db.query(TokenWallet).filter(TokenWallet.auth_user_id==k.auth_user_id).first()
        out.append({"id":kid,"found":True,"active":bool(k.is_active),"auth_user_id":k.auth_user_id,"email":au.email if au else None,"stored_prefix":str(k.api_key or "")[:12],"stored_len":len(str(k.api_key or "")),"plan":(w.plan.value if w and hasattr(w.plan,"value") else str(w.plan) if w else None),"balance_usd":w.balance_usd if w else None,"balance_tokens":w.balance_tokens if w else None,"vip_expires":str(w.vip_expires_at) if w else None})
    print(json.dumps(out, ensure_ascii=True))
finally:
    db.close()