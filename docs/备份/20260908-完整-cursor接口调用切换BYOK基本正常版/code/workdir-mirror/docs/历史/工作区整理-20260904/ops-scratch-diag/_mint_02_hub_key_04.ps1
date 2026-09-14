$ErrorActionPreference = "Stop"
Set-Location C:\ai24x01\api
$env:PYTHONIOENCODING = "utf-8"
& .\venv\Scripts\python.exe -c @"
import os, sys, json, urllib.request
os.chdir(r'C:\ai24x01\api')
sys.path.insert(0, r'C:\ai24x01\api')
from database import SessionLocal
from models import AuthUser
from token_mvp_service import create_api_key, get_api_key_row

db = SessionLocal()
u = db.query(AuthUser).filter(AuthUser.email == 'ityizu@foxmail.com').first()
print('uid', u.id if u else None)
info = create_api_key(db, int(u.id), name='subbrain-02-hub-20260904')
raw = info['api_key']
print('key_id', info['id'])
print('key_prefix', info['key_prefix'])
print('raw', raw)  # needed once for 02 config; do not commit to git
print('found', bool(get_api_key_row(db, raw)))

# live verify byok on localhost then public
body = json.dumps({
  'model': 'deepseek-chat',
  'messages': [{'role':'user','content':'ping'}],
  'max_tokens': 8,
}).encode()
req = urllib.request.Request(
  'http://127.0.0.1:8002/v1/chat/completions',
  data=body,
  headers={'Content-Type':'application/json','Authorization':'Bearer '+raw},
  method='POST',
)
try:
  with urllib.request.urlopen(req, timeout=60) as resp:
    data = json.loads(resp.read().decode())
    print('local_status', resp.status)
    print('billing_mode', (data.get('ai24x') or {}).get('billing_mode') or data.get('billing_mode'))
    print('model', data.get('model'))
except urllib.error.HTTPError as e:
  print('local_status', e.code, e.read().decode()[:400])

# write key only to ops file on 04 (not in git)
out = r'C:\Users\Administrator\ops\subbrain-02-hub-key-20260904.txt'
os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out, 'w', encoding='utf-8') as f:
  f.write(raw + '\n')
  f.write('key_id=%s\n' % info['id'])
  f.write('email=ityizu@foxmail.com\n')
  f.write('name=subbrain-02-hub-20260904\n')
print('saved', out)
db.close()
"@
