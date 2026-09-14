$ErrorActionPreference = "Stop"
Set-Location C:\ai24x01\api

Write-Host "=== deactivate leftover diag keys ==="
& .\venv\Scripts\python.exe -c @"
import os, sys, json, urllib.request, secrets, hashlib, time
os.chdir(r'C:\ai24x01\api')
sys.path.insert(0, r'C:\ai24x01\api')
from database import SessionLocal
from models import AuthUser, ApiKey
from security_util import hash_api_key
from config import settings
from token_mvp_service import get_api_key_row

db = SessionLocal()
n = db.query(ApiKey).filter(ApiKey.name == 'diag-401').update({ApiKey.is_active: False})
db.commit()
print('deactivated_diag=', n)

u = db.query(AuthUser).filter(AuthUser.frozen_at.is_(None)).order_by(AuthUser.id.asc()).first()
raw = 'sk-diag' + secrets.token_hex(24)
h = hash_api_key(raw)
row = ApiKey(auth_user_id=int(u.id), name='diag-401b', api_key=h, is_active=True)
db.add(row); db.commit(); db.refresh(row)
print('created id=', row.id, 'found=', bool(get_api_key_row(db, raw)))

def get(url, headers):
    req = urllib.request.Request(url, headers=headers, method='GET')
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return resp.status, resp.read().decode('utf-8','replace')[:400]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8','replace')[:600]
    except Exception as e:
        return 'ERR', str(e)

def post(url, headers, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return resp.status, resp.read().decode('utf-8','replace')[:400]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8','replace')[:600]
    except Exception as e:
        return 'ERR', str(e)

print('balance', get('http://127.0.0.1:8002/v1/billing/balance', {'X-API-Key': raw}))
print('keys_list', get('http://127.0.0.1:8002/v1/keys', {'X-API-Key': raw}))
t0 = time.time()
print('completions', post('http://127.0.0.1:8002/v1/chat/completions', {'Content-Type':'application/json','X-API-Key': raw}, {'model':'flash','messages':[{'role':'user','content':'hi'}],'max_tokens':5}))
print('elapsed', round(time.time()-t0,3))
print('chat_run', post('http://127.0.0.1:8002/v1/chat/run', {'Content-Type':'application/json','X-API-Key': raw}, {'model':'flash','messages':[{'role':'user','content':'hi'}],'max_tokens':5}))

# also try an EXISTING active key hash-only path: pick latest non-diag active key and verify we cannot recover raw;
# instead ask: do ANY recent 401 have body via forging Authorization with wrong key
print('badkey', post('http://127.0.0.1:8002/v1/chat/completions', {'Content-Type':'application/json','X-API-Key': 'sk-not-real-'+secrets.token_hex(8)}, {'model':'flash','messages':[{'role':'user','content':'hi'}],'max_tokens':5}))

row.is_active=False; db.commit(); db.close()
print('cleaned')
"@

Write-Host "=== log tail ==="
Get-Content C:\ai24x01\logs\ai24x-core.err.log -Tail 40 -Encoding UTF8

Write-Host "=== worker count listening 8002 ==="
netstat -ano | findstr ":8002"
