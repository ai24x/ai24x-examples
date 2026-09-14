$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "caf5ff948601"
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
if ($pm -notlike "*def build_hero_picks*") { throw "missing build_hero_picks" }
if ($pm -notlike '*"hero_picks"*') { throw "snapshot missing hero_picks key" }
$html = Get-Content "web\token-admin.html" -Raw -Encoding UTF8
if ($html -notlike "*pmHeroTiers*") { throw "token-admin missing pmHeroTiers" }
if ($html -notlike "*renderHeroPicks*") { throw "token-admin missing renderHeroPicks" }
Write-Host "markers OK" -ForegroundColor Green

Write-Host "== 3. restart core ==" -ForegroundColor Cyan
Restart-Service AI24X-core -Force -ErrorAction Stop
Start-Sleep -Seconds 14

Write-Host "== 4. verify ==" -ForegroundColor Cyan
$ph = Invoke-RestMethod -UseBasicParsing -Uri "http://127.0.0.1:8002/health" -TimeoutSec 15
git merge-base --is-ancestor $EXP $ph.commit
if ($LASTEXITCODE -ne 0) { throw ("health commit mismatch " + $ph.commit) }

# admin API needs key — smoke via python import on disk (same code process loads)
Set-Location "$work\api"
& .\venv\Scripts\python.exe -c "from price_monitor import snapshot; s=snapshot(); assert s.get('hero_picks',{}).get('tiers'); print('hero_ok', len(s['hero_picks']['tiers']))"
Set-Location $work

$ta = Invoke-WebRequest -UseBasicParsing -Uri "https://www.ai24x.com/token-admin.html" -TimeoutSec 20
if ($ta.Content -notlike "*pmHeroTiers*") { throw "public token-admin missing pmHeroTiers" }

Write-Host ("DONE EXP=$EXP HEAD=$HEAD health=$($ph.commit)") -ForegroundColor Green
# ✅ 04更新完成｜管理台主打建议作战台｜EXP=caf5ff948601 HEAD=<HEAD> health=<commit>｜hero_picks+token-admin
