$ErrorActionPreference = "Stop"
Set-Location C:\ai24x01\api
$env:PYTHONIOENCODING = "utf-8"
& .\venv\Scripts\python.exe -c @"
import os, sys, json, re, glob
os.chdir(r'C:\ai24x01\api')
sys.path.insert(0, r'C:\ai24x01\api')
from database import SessionLocal
from models import ApiKey
from security_util import hash_api_key
from token_mvp_service import get_api_key_row, _find_api_key_any_status

# load openclaw.json keys
paths = glob.glob(r'C:\Users\Administrator\.openclaw\**\openclaw.json', recursive=True)
paths += glob.glob(r'C:\Users\Administrator\**\openclaw.json', recursive=True)
print('openclaw_paths', paths[:10])
keys=[]
for p in paths[:5]:
    try:
        t=open(p,encoding='utf-8',errors='ignore').read()
    except Exception as e:
        print('read_err', p, e); continue
    found=re.findall(r'sk-[A-Za-z0-9]{20,80}', t)
    print('file', p, 'nkeys', len(found))
    for k in found:
        keys.append((k,p))

db=SessionLocal()
for k,p in keys:
    h=hash_api_key(k)
    active=get_api_key_row(db,k)
    anyrow=_find_api_key_any_status(db,k)
    # also raw equality search by hash string
    byhash=db.query(ApiKey).filter(ApiKey.api_key==h).first()
    print('pref', k[:14], 'active', getattr(active,'id',None), 'any', getattr(anyrow,'id',None), 'active_flag', getattr(anyrow,'is_active',None), 'byhash', getattr(byhash,'id',None), 'byhash_active', getattr(byhash,'is_active',None), 'uid', getattr(anyrow or byhash,'auth_user_id',None), 'name', getattr(anyrow or byhash,'name',None))

# timeline: count 401 vs 200 on chat since 20:00 from log if easy
print('done')
db.close()
"@

Write-Host "=== 401 vs 200 since 20:00 (approx from log) ==="
Select-String -Path C:\ai24x01\logs\ai24x-core.err.log -Pattern "POST /v1/chat/(completions|run)|POST /v1/responses" |
  Where-Object { $_.Line -match '2026-09-03 2[0-1]:' } |
  ForEach-Object {
    if ($_.Line -match 'Status: (\d+)') { $matches[1] }
  } | Group-Object | Sort-Object Name | Format-Table Count, Name -AutoSize
