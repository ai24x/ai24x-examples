$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "df148e7dc613"
Set-Location $work

Write-Host "== 1. fetch + pull ==" -ForegroundColor Cyan
git fetch origin
git pull --ff-only origin master
$HEAD = (git rev-parse --short=12 HEAD).Trim()
Write-Host "HEAD=$HEAD"
git merge-base --is-ancestor $EXP HEAD
if ($LASTEXITCODE -ne 0) { throw "HEAD missing $EXP" }

Write-Host "== 2. markers ==" -ForegroundColor Cyan
if (-not (Test-Path "api\flash_lanes.py")) { throw "missing api/flash_lanes.py" }
$fl = Get-Content "api\flash_lanes.py" -Raw -Encoding UTF8
if ($fl -notlike "*def build_flash_lanes*") { throw "missing build_flash_lanes" }
if ($fl -notlike "*def apply_flash_lane*") { throw "missing apply_flash_lane" }
$sf = Get-Content "api\system_flags.py" -Raw -Encoding UTF8
if ($sf -notlike "*token_llm_l1_lane*") { throw "system_flags missing token_llm_l1_lane" }
$mr = Get-Content "api\model_router.py" -Raw -Encoding UTF8
if ($mr -notlike "*detect_active_flash_lane*") { throw "model_router missing detect_active_flash_lane" }
if ($mr -notlike "*_upstream_from_flash_lane*") { throw "model_router missing _upstream_from_flash_lane" }
$pm = Get-Content "api\price_monitor.py" -Raw -Encoding UTF8
if ($pm -notlike "*flash_lanes*") { throw "price_monitor missing flash_lanes" }
$ta = Get-Content "web\token-admin.html" -Raw -Encoding UTF8
if ($ta -notlike "*pmFlashLanes*") { throw "token-admin missing pmFlashLanes" }
if ($ta -notlike "*apply-flash-lane*") { throw "token-admin missing apply-flash-lane" }
if ($ta -notlike "*btn-flash-lane*") { throw "token-admin missing btn-flash-lane" }
Write-Host "markers OK" -ForegroundColor Green

Write-Host "== 3. restart core + open ==" -ForegroundColor Cyan
Restart-Service AI24X-core -Force -ErrorAction Stop
Restart-Service AI24X-open-api -Force -ErrorAction Stop
Start-Sleep -Seconds 14

Write-Host "== 4. verify ==" -ForegroundColor Cyan
$ph = Invoke-RestMethod -UseBasicParsing -Uri "http://127.0.0.1:8002/health" -TimeoutSec 15
git merge-base --is-ancestor $EXP $ph.commit
if ($LASTEXITCODE -ne 0) { throw ("core health commit mismatch " + $ph.commit) }

Set-Location "$work\api"
& .\venv\Scripts\python.exe -c "from flash_lanes import build_flash_lanes; from price_monitor import snapshot; s=snapshot(); fl=s.get('flash_lanes') or {}; assert fl.get('lanes'), fl; print('flash_lanes_ok', fl.get('active'), len(fl['lanes']))"
Set-Location $work

$taW = Invoke-WebRequest -UseBasicParsing -Uri "https://www.ai24x.com/token-admin.html" -TimeoutSec 20
if ($taW.Content -notlike "*pmFlashLanes*") { throw "public token-admin missing pmFlashLanes" }
if ($taW.Content -notlike "*apply-flash-lane*") { throw "public token-admin missing apply-flash-lane" }

Write-Host ("DONE EXP=$EXP HEAD=$HEAD health=$($ph.commit)") -ForegroundColor Green
# ✅ 04更新完成｜flash通道价表一键切换｜EXP=df148e7dc613 HEAD=<HEAD> health=<commit>｜公网验收通过