$ErrorActionPreference = "Stop"
$cfg = "C:\Users\Administrator\.openclaw\openclaw.json"
$keyFile = "C:\Users\Administrator\ops\subbrain-02-hub-key-20260904.txt"
if (-not (Test-Path $cfg)) { throw "missing $cfg" }
if (-not (Test-Path $keyFile)) { throw "missing $keyFile" }

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$bak = "C:\Users\Administrator\.openclaw\openclaw.json.bak-byok-api-hub-$stamp"
Copy-Item -LiteralPath $cfg -Destination $bak -Force
Write-Host "backup=$bak"

# Prefer py launcher / python
$py = $null
foreach ($c in @("py","python","python3")) {
  $cmd = Get-Command $c -ErrorAction SilentlyContinue
  if ($cmd) { $py = $cmd.Source; break }
}
if (-not $py) { throw "python not found on 02" }

& $py -c @"
import json, urllib.request, urllib.error, shutil, os, subprocess, sys
cfg = r'$cfg'
key_file = r'$keyFile'
raw = open(key_file, encoding='utf-8').read().splitlines()[0].strip()
assert raw.startswith('sk-') and len(raw) >= 40
print('key_prefix=', raw[:10], 'len=', len(raw))

with open(cfg, encoding='utf-8') as f:
    data = json.load(f)

hits = []

def walk(obj, path):
    if isinstance(obj, dict):
        bu = obj.get('baseUrl') or obj.get('base_url')
        if isinstance(bu, str) and ('ai24x.com' in bu) and (('apiKey' in obj) or ('api_key' in obj)):
            hits.append((path, obj, bu))
        for k, v in obj.items():
            walk(v, path + '.' + str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            walk(v, path + f'[{i}]')

# prefer named provider
prov = None
path = None
try:
    prov = data['models']['providers']['ai24x-byok']
    path = 'models.providers.ai24x-byok'
except Exception:
    pass
if prov is None:
    try:
        prov = data['providers']['ai24x-byok']
        path = 'providers.ai24x-byok'
    except Exception:
        pass
if prov is not None:
    hits = [(path, prov, str(prov.get('baseUrl') or ''))] + hits

# unique by id(obj)
seen = set(); uniq = []
for p, o, bu in hits:
    i = id(o)
    if i in seen: continue
    seen.add(i); uniq.append((p, o, bu))

if not uniq:
    # show provider names
    names = []
    try: names = list(data.get('models',{}).get('providers',{}).keys())
    except Exception: pass
    print('NO_HIT providers=', names)
    raise SystemExit(2)

for p, o, bu in uniq:
    print('patch', p, 'oldBase=', bu)
    o['baseUrl'] = 'https://api.ai24x.com/v1'
    if 'apiKey' in o: o['apiKey'] = raw
    if 'api_key' in o: o['api_key'] = raw
    env = o.get('env')
    if isinstance(env, dict):
        if 'OPENAI_BASE_URL' in env: env['OPENAI_BASE_URL'] = 'https://api.ai24x.com/v1'
        if 'OPENAI_API_KEY' in env: env['OPENAI_API_KEY'] = raw

with open(cfg, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
    f.write('\n')
print('updated', cfg)

# verify
with open(cfg, encoding='utf-8') as f:
    data2 = json.load(f)
hits2=[]
walk(data2,'root')
for p,o,bu in hits2:
    if 'api.ai24x.com' in str(bu):
        k = o.get('apiKey') or o.get('api_key') or ''
        print('verify', p, 'base=', bu, 'key_pref=', k[:10])

body = json.dumps({'model':'deepseek-chat','messages':[{'role':'user','content':'ping'}],'max_tokens':8}).encode()
req = urllib.request.Request('https://api.ai24x.com/v1/chat/completions', data=body, headers={'Content-Type':'application/json','Authorization':'Bearer '+raw}, method='POST')
try:
    with urllib.request.urlopen(req, timeout=60) as resp:
        d = json.loads(resp.read().decode())
        print('probe_status', resp.status)
        print('billing_mode', (d.get('ai24x') or {}).get('billing_mode'))
        print('model', d.get('model'))
except urllib.error.HTTPError as e:
    print('probe_status', e.code, e.read().decode()[:400])
    raise

# restart gateway
def try_restart():
    for cmd in [
        ['openclaw', 'gateway', 'restart'],
        ['npx', 'openclaw', 'gateway', 'restart'],
    ]:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            print('restart_cmd', cmd, 'code', r.returncode)
            if r.stdout: print(r.stdout[:500])
            if r.stderr: print(r.stderr[:500])
            if r.returncode == 0: return True
        except Exception as e:
            print('restart_skip', cmd, type(e).__name__, e)
    return False
ok = try_restart()
print('restart_ok', ok)
print('DONE')
"@
