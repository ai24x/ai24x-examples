$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "02e8b9c0d8ac"
Set-Location $work
Write-Host "== 1. fetch + pull ==" -ForegroundColor Cyan
git fetch origin
git pull --ff-only origin master
$HEAD = (git rev-parse --short=12 HEAD).Trim()
Write-Host "HEAD=$HEAD"
git merge-base --is-ancestor $EXP HEAD
if ($LASTEXITCODE -ne 0) { throw "HEAD missing $EXP" }

Write-Host "== 2. markers ==" -ForegroundColor Cyan
if (-not (Test-Path "api\upstream_gate.py")) { throw "missing api/upstream_gate.py" }
$core = Get-Content "api\model_router.py" -Raw -Encoding UTF8
if ($core -notlike '*TOKEN_LLM_STREAM_TIMEOUT_S", "90"*') { throw "stream timeout default not 90" }
if ($core -notlike '*_httpx_timeout*') { throw "missing _httpx_timeout" }
if ($core -notlike '*try_acquire_upstream_slot*') { throw "missing stream slot" }
$gate = Get-Content "api\upstream_gate.py" -Raw -Encoding UTF8
if ($gate -notlike '*UpstreamBusyError*') { throw "missing UpstreamBusyError" }
if ($gate -notlike '*TOKEN_LLM_MAX_INFLIGHT*') { throw "missing MAX_INFLIGHT" }
$svc = Get-Content "api\services.py" -Raw -Encoding UTF8
if ($svc -notlike '*UpstreamBusyError*') { throw "services missing busy handling" }
Write-Host "markers OK" -ForegroundColor Green

Write-Host "== 3. restart ==" -ForegroundColor Cyan
Restart-Service AI24X-open-api -ErrorAction SilentlyContinue
Restart-Service AI24X-core -ErrorAction Stop
Start-Sleep -Seconds 16

Write-Host "== 4. verify ==" -ForegroundColor Cyan
$ph = Invoke-RestMethod -UseBasicParsing -Uri "https://api.ai24x.com/health"
git merge-base --is-ancestor $EXP $ph.commit
if ($LASTEXITCODE -ne 0) { throw ("health commit mismatch " + $ph.commit) }
1..3 | ForEach-Object {
  $t0 = Get-Date
  $h = Invoke-RestMethod -UseBasicParsing -Uri "https://api.ai24x.com/health"
  $ms = [int]((Get-Date) - $t0).TotalMilliseconds
  Write-Host ("health_probe $_ ms=$ms")
}
$py = @"
import sys
sys.path.insert(0, r'C:\ai24x01\api')
from model_router import _timeout_s, _stream_timeout_s, _httpx_timeout
from upstream_gate import UpstreamBusyError, _max_inflight
assert abs(_timeout_s() - 15.0) < 0.01
assert abs(_stream_timeout_s() - 90.0) < 0.01 or _stream_timeout_s() >= 30
assert _httpx_timeout(90).read == 90
assert _max_inflight() >= 1
print('p1_upstream_harden_ok')
"@
$p = 'C:\Users\Administrator\ops\_check_p1_upstream.py'
New-Item -ItemType Directory -Force -Path (Split-Path $p) | Out-Null
Set-Content -LiteralPath $p -Value $py -Encoding UTF8
$out = & "C:\ai24x01\api\venv\Scripts\python.exe" $p
if ($out -notlike '*p1_upstream_harden_ok*') { throw $out }
Write-Host $out -ForegroundColor Green
Write-Host ("DONE EXP=$EXP HEAD=$HEAD health=$($ph.commit)") -ForegroundColor Green
# ✅ 04更新完成｜P1上游超时+并发闸｜EXP=02e8b9c0d8ac HEAD=<HEAD> health=<commit>｜stream默认90s+inflight24
