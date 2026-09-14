$ErrorActionPreference = "Stop"
Set-Location C:\ai24x01\api

Write-Host "=== NSSM AppEnvironmentExtra keys (names only) ==="
$nssm = if (Test-Path "C:\Program Files\nssm\nssm.exe") { "C:\Program Files\nssm\nssm.exe" } else { "C:\nssm\nssm.exe" }
$extra = & $nssm get AI24X-core AppEnvironmentExtra 2>$null
$extraText = ($extra | Out-String).Replace("`0","")
$extraText -split "`r?`n" | ForEach-Object {
  $line = $_.Trim()
  if (-not $line) { return }
  $name = ($line -split "=",2)[0]
  Write-Host "ENV_NAME=$name"
}

Write-Host "=== import settings like run_prod (cwd=api) ==="
& .\venv\Scripts\python.exe -c @"
import os, hashlib
os.chdir(r'C:\ai24x01\api')
from config import settings
sk = settings.secret_key or ''
print('secret_fp=', hashlib.sha256(sk.encode()).hexdigest()[:16], 'len=', len(sk))
print('db_url_host=', settings.database_url.split('@')[-1][:80] if '@' in settings.database_url else settings.database_url[:60])
print('strict_auth=', settings.strict_auth)
print('admin_require_sms=', settings.admin_require_sms)
print('app_env=', settings.app_env)
"@

Write-Host "=== create temp key, probe chat, cleanup ==="
& .\venv\Scripts\python.exe -c @"
import os, sys, json, urllib.request, hashlib, secrets
os.chdir(r'C:\ai24x01\api')
sys.path.insert(0, r'C:\ai24x01\api')
from database import SessionLocal
from models import AuthUser, ApiKey, TokenWallet
from security_util import hash_api_key
from config import settings
from token_mvp_service import get_api_key_row

db = SessionLocal()
# pick a non-frozen user with wallet balance if possible
u = db.query(AuthUser).filter(AuthUser.frozen_at.is_(None)).order_by(AuthUser.id.asc()).first()
print('probe_user_id=', u.id if u else None, 'email=', (u.email or '')[:40] if u else None)
raw = 'sk-diag' + secrets.token_hex(24)
h = hash_api_key(raw)
print('hash_prefix=', h[:16])
print('secret_fp=', hashlib.sha256((settings.secret_key or '').encode()).hexdigest()[:16])
row = ApiKey(auth_user_id=int(u.id), name='diag-401', api_key=h, is_active=True)
db.add(row)
db.commit()
db.refresh(row)
print('row_id=', row.id)
found = get_api_key_row(db, raw)
print('get_api_key_row=', 'FOUND' if found else 'MISS', 'id=', getattr(found,'id',None))

def hit(url, headers, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode('utf-8'), headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, resp.read().decode('utf-8', errors='replace')[:500]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', errors='replace')[:800]

body = {'model':'flash','messages':[{'role':'user','content':'ping'}],'max_tokens':8}
# 1) X-API-Key
code, text = hit('http://127.0.0.1:8002/v1/chat/completions', {
    'Content-Type':'application/json',
    'X-API-Key': raw,
}, body)
print('X-API-Key status=', code, 'body=', text)
# 2) Bearer sk-
code2, text2 = hit('http://127.0.0.1:8002/v1/chat/completions', {
    'Content-Type':'application/json',
    'Authorization': 'Bearer ' + raw,
}, body)
print('Bearer status=', code2, 'body=', text2)
# 3) balance endpoint with same key (if exists)
try:
    req = urllib.request.Request('http://127.0.0.1:8002/v1/billing/balance', headers={'X-API-Key': raw}, method='GET')
    with urllib.request.urlopen(req, timeout=10) as resp:
        print('balance status=', resp.status, 'body=', resp.read().decode()[:300])
except urllib.error.HTTPError as e:
    print('balance status=', e.code, 'body=', e.read().decode('utf-8', errors='replace')[:500])

# cleanup
row.is_active = False
db.commit()
db.close()
print('cleaned')
"@

Write-Host "=== recent 401 lines ==="
Get-Content C:\ai24x01\logs\ai24x-core.err.log -Tail 80 -Encoding UTF8 | Select-String -Pattern "chat/completions|401|invalid"
