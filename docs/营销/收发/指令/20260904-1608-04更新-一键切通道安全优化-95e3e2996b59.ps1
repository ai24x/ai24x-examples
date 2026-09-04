$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "95e3e2996b59"
Set-Location $work

Write-Host "== 1. fetch + pull ==" -ForegroundColor Cyan
git fetch origin
git pull --ff-only origin master
$HEAD = (git rev-parse --short=12 HEAD).Trim()
Write-Host "HEAD=$HEAD"
git merge-base --is-ancestor $EXP HEAD
if ($LASTEXITCODE -ne 0) { throw "HEAD missing $EXP" }

Write-Host "== 2. markers ==" -ForegroundColor Cyan
$pm = Get-Content "api\price_monitor.py" -Raw -Encoding UTF8
if ($pm -notlike "*def list_hero_ops_alerts*") { throw "missing list_hero_ops_alerts" }
if ($pm -notlike "*def tick_hero_pending*") { throw "missing tick_hero_pending" }
if ($pm -notlike "*risk_warning*") { throw "missing risk_warning" }
$html = Get-Content "web\token-admin.html" -Raw -Encoding UTF8
if ($html -notlike "*pmHeroPending*") { throw "token-admin missing pmHeroPending" }
if ($html -notlike "*hero_gm_risk*") { throw "token-admin missing hero_gm_risk label" }
$oa = Get-Content "api\ops_alert.py" -Raw -Encoding UTF8
if ($oa -notlike "*list_hero_ops_alerts*") { throw "ops_alert missing hero alerts" }
Write-Host "markers OK" -ForegroundColor Green

Write-Host "== 3. restart core ==" -ForegroundColor Cyan
Restart-Service AI24X-core -Force -ErrorAction Stop
Start-Sleep -Seconds 14

Write-Host "== 4. verify ==" -ForegroundColor Cyan
$ph = Invoke-RestMethod -UseBasicParsing -Uri "http://127.0.0.1:8002/health" -TimeoutSec 15
git merge-base --is-ancestor $EXP $ph.commit
if ($LASTEXITCODE -ne 0) { throw ("health commit mismatch " + $ph.commit) }

Set-Location "$work\api"
& .\venv\Scripts\python.exe -c "from price_monitor import snapshot, list_hero_ops_alerts; s=snapshot(); assert 'pending_alerts' in s['hero_picks']; list_hero_ops_alerts(); print('hero_safe_ok')"
Set-Location $work

$ta = Invoke-WebRequest -UseBasicParsing -Uri "https://www.ai24x.com/token-admin.html" -TimeoutSec 20
if ($ta.Content -notlike "*pmHeroPending*") { throw "public token-admin missing pmHeroPending" }

Write-Host ("DONE EXP=$EXP HEAD=$HEAD health=$($ph.commit)") -ForegroundColor Green
# ✅ 04更新完成｜一键切通道安全优化｜EXP=95e3e2996b59 HEAD=<HEAD> health=<commit>｜pending+gm_risk+audit
