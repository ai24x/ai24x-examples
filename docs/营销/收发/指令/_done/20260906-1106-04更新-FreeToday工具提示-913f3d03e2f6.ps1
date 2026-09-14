$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "913f3d03e2f6"
Set-Location $work

Write-Host "== 1. fetch + pull ==" -ForegroundColor Cyan
git fetch origin
git pull --ff-only origin master
$HEAD = (git rev-parse --short=12 HEAD).Trim()
Write-Host "HEAD=$HEAD"
git merge-base --is-ancestor $EXP HEAD
if ($LASTEXITCODE -ne 0) { throw "HEAD missing $EXP" }

Write-Host "== 2. markers ==" -ForegroundColor Cyan
$www = Get-Content "web\console.html" -Raw -Encoding UTF8
if ($www -notlike "*locales.js?v=20260906b*") { throw "www console missing locales v20260906b" }
if ($www -notlike "*console.js?v=20260906b*") { throw "www console missing console.js v20260906b" }
if ($www -notlike "*no tool calling*") { throw "www console missing free-today hint" }
$wjs = Get-Content "web\js\console.js" -Raw -Encoding UTF8
if ($wjs -notlike "*text only, no tools*") { throw "www console.js missing free-today dynamic hint" }
$wl = Get-Content "web\config\locales.js" -Raw -Encoding UTF8
if ($wl -notlike "*Daily free text · no tool calling*") { throw "www locales missing free-today en" }
$open = Get-Content "p\open\web\console.html" -Raw -Encoding UTF8
if ($open -notlike "*locales.js?v=20260906b*") { throw "open console missing locales v20260906b" }
if ($open -notlike "*console.js?v=20260906b*") { throw "open console missing console.js v20260906b" }
$ojs = Get-Content "p\open\web\js\console.js" -Raw -Encoding UTF8
if ($ojs -notlike "*text only, no tools*") { throw "open console.js missing free-today dynamic hint" }
Write-Host "markers OK" -ForegroundColor Green

Write-Host "== 3. public verify ==" -ForegroundColor Cyan
$wwwP = Invoke-WebRequest -UseBasicParsing -Uri "https://www.ai24x.com/console.html" -TimeoutSec 25
if ($wwwP.Content -notlike "*locales.js?v=20260906b*") { throw "public www console missing locales v20260906b" }
if ($wwwP.Content -notlike "*console.js?v=20260906b*") { throw "public www console missing console.js v20260906b" }
if ($wwwP.Content -notlike "*no tool calling*") { throw "public www missing free-today hint" }
$openP = Invoke-WebRequest -UseBasicParsing -Uri "https://open.ai24x.com/console.html" -TimeoutSec 25
if ($openP.Content -notlike "*locales.js?v=20260906b*") { throw "public open console missing locales v20260906b" }
if ($openP.Content -notlike "*console.js?v=20260906b*") { throw "public open console missing console.js v20260906b" }

$ph = Invoke-RestMethod -UseBasicParsing -Uri "http://127.0.0.1:8002/health" -TimeoutSec 15
# static-only: health commit may lag code until next core restart; still require EXP in git HEAD
Write-Host ("health.commit=" + $ph.commit)

Write-Host ("DONE EXP=$EXP HEAD=$HEAD health=$($ph.commit)") -ForegroundColor Green
# ✅ 04更新完成｜Free today工具提示｜EXP=913f3d03e2f6 HEAD=<HEAD> health=<commit>｜公网验收通过
