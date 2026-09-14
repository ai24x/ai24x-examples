$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "689c6bb5a34f"
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
if ($pm -notlike "*def apply_hero_pick*") { throw "missing apply_hero_pick" }
$html = Get-Content "web\token-admin.html" -Raw -Encoding UTF8
if ($html -notlike "*btn-hero-apply*") { throw "token-admin missing btn-hero-apply" }
if ($html -notlike "*apply-hero*") { throw "token-admin missing apply-hero path" }
$main = Get-Content "api\main.py" -Raw -Encoding UTF8
if ($main -notlike "*/v1/admin/price/apply-hero*") { throw "main missing apply-hero route" }
Write-Host "markers OK" -ForegroundColor Green

Write-Host "== 3. restart core ==" -ForegroundColor Cyan
Restart-Service AI24X-core -Force -ErrorAction Stop
Start-Sleep -Seconds 14

Write-Host "== 4. verify ==" -ForegroundColor Cyan
$ph = Invoke-RestMethod -UseBasicParsing -Uri "http://127.0.0.1:8002/health" -TimeoutSec 15
git merge-base --is-ancestor $EXP $ph.commit
if ($LASTEXITCODE -ne 0) { throw ("health commit mismatch " + $ph.commit) }

Set-Location "$work\api"
& .\venv\Scripts\python.exe -c "from price_monitor import snapshot; s=snapshot(); assert any((t.get('apply') or {}).get('applyable') is not None for t in s['hero_picks']['tiers']); print('apply_meta_ok')"
Set-Location $work

$ta = Invoke-WebRequest -UseBasicParsing -Uri "https://www.ai24x.com/token-admin.html" -TimeoutSec 20
if ($ta.Content -notlike "*btn-hero-apply*") { throw "public token-admin missing apply button markup" }

Write-Host ("DONE EXP=$EXP HEAD=$HEAD health=$($ph.commit)") -ForegroundColor Green
# ✅ 04更新完成｜一键切主通道｜EXP=689c6bb5a34f HEAD=<HEAD> health=<commit>｜apply-hero+token-admin
