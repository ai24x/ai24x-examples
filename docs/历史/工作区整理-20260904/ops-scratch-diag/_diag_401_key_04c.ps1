$ErrorActionPreference = "Stop"
Set-Location C:\ai24x01\api
$env:PYTHONIOENCODING = "utf-8"
& .\venv\Scripts\python.exe -c @"
import os, sys, json, urllib.request, secrets, hashlib
os.chdir(r'C:\ai24x01\api')
sys.path.insert(0, r'C:\ai24x01\api')
from database import SessionLocal
from models import ApiKey, AuthUser
from security_util import hash_api_key, is_hashed_api_key
from config import settings
from token_mvp_service import get_api_key_row, create_api_key

db = SessionLocal()
rows = db.query(ApiKey).order_by(ApiKey.id.desc()).limit(30).all()
print('recent_keys')
plain = 0
hashed = 0
active = 0
for r in rows:
    stored = str(r.api_key or '')
    h = is_hashed_api_key(stored)
    if h: hashed += 1
    else: plain += 1
    if r.is_active: active += 1
    print('id=', r.id, 'uid=', r.auth_user_id, 'active=', r.is_active, 'hashed=', h, 'name=', (r.name or '')[:30], 'pref=', stored[:18])
print('stats_hashed', hashed, 'plain', plain, 'active_in_sample', active)

# plaintext leftovers?
pl = db.query(ApiKey).filter(~ApiKey.api_key.like('sha256:%')).all()
print('plaintext_total', len(pl))
for r in pl[:10]:
    print(' plain id=', r.id, 'active=', r.is_active, 'len=', len(str(r.api_key or '')), 'pref=', str(r.api_key or '')[:12])

# Create key via official helper for a user who has OLD active keys
old = (
    db.query(ApiKey)
    .filter(ApiKey.is_active.is_(True), ApiKey.api_key.like('sha256:%'), ApiKey.name != 'diag-401b', ApiKey.name != 'diag-401')
    .order_by(ApiKey.id.asc())
    .first()
)
print('oldest_active_hashed id=', getattr(old,'id',None), 'uid=', getattr(old,'auth_user_id',None), 'name=', getattr(old,'name',None))

# mint new key for same user via create_api_key
info = create_api_key(db, int(old.auth_user_id), name='diag-401c')
raw = info.get('api_key') or info.get('key') or info.get('token')
print('create_api_key keys=', list(info.keys()))
print('raw_prefix=', (raw or '')[:10], 'len=', len(raw or ''))
print('row_found', bool(get_api_key_row(db, raw)))

def post(url, headers, body, timeout=12):
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode('utf-8','replace')[:300]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8','replace')[:500]
    except Exception as e:
        return 'ERR', type(e).__name__ + ':' + str(e)

body = {'model':'flash','messages':[{'role':'user','content':'ping'}],'max_tokens':5}
print('new_for_old_user', post('http://127.0.0.1:8002/v1/chat/completions', {'Content-Type':'application/json','X-API-Key': raw}, body, timeout=45))

# deactivate new diag key
db.query(ApiKey).filter(ApiKey.name=='diag-401c').update({ApiKey.is_active: False})
db.commit()

# SECRET fingerprint vs .env file direct parse
import re
from pathlib import Path
text = Path(r'C:\ai24x01\api\.env').read_text(encoding='utf-8')
m = re.search(r'^SECRET_KEY=(.*)$', text, re.M)
env_sk = (m.group(1).strip().strip('\"').strip(\"'\") if m else '')
print('env_secret_fp', hashlib.sha256(env_sk.encode()).hexdigest()[:16], 'len', len(env_sk))
print('settings_secret_fp', hashlib.sha256((settings.secret_key or '').encode()).hexdigest()[:16], 'len', len(settings.secret_key or ''))
print('secret_equal', env_sk == (settings.secret_key or ''))
# check backup
bak = Path(r'C:\ai24x01\api\.env.bak-disable-sms-20260903-200053')
if bak.exists():
    bt = bak.read_text(encoding='utf-8')
    bm = re.search(r'^SECRET_KEY=(.*)$', bt, re.M)
    bsk = (bm.group(1).strip().strip('\"').strip(\"'\") if bm else '')
    print('bak_secret_fp', hashlib.sha256(bsk.encode()).hexdigest()[:16], 'len', len(bsk), 'equal_env', bsk==env_sk)
db.close()
"@
