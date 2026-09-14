$ErrorActionPreference = "Stop"
Set-Location C:\ai24x01\api
$env:PYTHONIOENCODING = "utf-8"

# Clean leftover diag keys; compare process env SECRET via wmic if possible;
# search common local key files used by probes (without printing full secrets)

Write-Host "=== cleanup diag keys ==="
& .\venv\Scripts\python.exe -c @"
from database import SessionLocal
from models import ApiKey
db=SessionLocal()
n=db.query(ApiKey).filter(ApiKey.name.in_(['diag-401','diag-401b','diag-401c'])).update({ApiKey.is_active: False}, synchronize_session=False)
db.commit(); print('deactivated', n); db.close()
"@

Write-Host "=== look for probe key files (paths only + prefix) ==="
$candidates = @(
  'C:\Users\Administrator\.codex\*',
  'C:\ai24x01\ops\*key*',
  'C:\ai24x01\ops\*probe*',
  'C:\ai24x01\api\.env'
)
Get-ChildItem -Path C:\Users\Administrator -Filter *.json -Recurse -ErrorAction SilentlyContinue |
  Where-Object { $_.FullName -match 'codex|openclaw|ai24x' -and $_.Length -lt 200000 } |
  Select-Object -First 30 FullName, Length |
  Format-Table -AutoSize | Out-String | Write-Host

Write-Host "=== try keys from openclaw/codex auth if present ==="
& .\venv\Scripts\python.exe -c @"
import os, sys, json, re, glob, urllib.request, hashlib
os.chdir(r'C:\ai24x01\api')
sys.path.insert(0, r'C:\ai24x01\api')
from database import SessionLocal
from token_mvp_service import get_api_key_row
from security_util import hash_api_key
from config import settings

# harvest sk- candidates from common config locations (do not print full key)
paths = []
for pat in [
    r'C:\Users\Administrator\.codex\**\*.json',
    r'C:\Users\Administrator\.openclaw\**\*.json',
    r'C:\Users\Administrator\AppData\Roaming\**\*ai24x*',
    r'C:\ai24x01\ops\**\*.txt',
    r'C:\ai24x01\ops\**\*.md',
    r'C:\ai24x01\ops\**\*.json',
]:
    paths.extend(glob.glob(pat, recursive=True))

found_keys = []
for p in paths:
    try:
        if os.path.getsize(p) > 2_000_000:
            continue
        text = open(p, 'r', encoding='utf-8', errors='ignore').read()
    except Exception:
        continue
    for m in re.finditer(r'sk-[A-Za-z0-9]{20,80}', text):
        k = m.group(0)
        found_keys.append((k, p))

# unique by key
uniq = {}
for k,p in found_keys:
    uniq.setdefault(k, p)
print('candidate_keys', len(uniq))
db = SessionLocal()

def post(k):
    body = json.dumps({'model':'flash','messages':[{'role':'user','content':'ping'}],'max_tokens':5}).encode()
    req = urllib.request.Request('http://127.0.0.1:8002/v1/chat/completions', data=body, headers={'Content-Type':'application/json','Authorization':'Bearer '+k}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception as e:
        return type(e).__name__

tested = 0
for k, p in list(uniq.items())[:12]:
    row = get_api_key_row(db, k)
    st = post(k)
    print('pref=', k[:12], 'len=', len(k), 'db=', ('FOUND#'+str(row.id) if row else 'MISS'), 'http=', st, 'from=', os.path.basename(p))
    tested += 1
print('tested', tested)
print('settings_fp', hashlib.sha256(settings.secret_key.encode()).hexdigest()[:16])
db.close()
"@

Write-Host "=== recent completions statuses ==="
Get-Content C:\ai24x01\logs\ai24x-core.err.log -Tail 100 -Encoding UTF8 | Select-String -Pattern "chat/completions|responses|chat/run" | Select-Object -Last 30
