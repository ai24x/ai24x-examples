﻿$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "9c5a5fb"
Set-Location $work

Write-Host "== 1. fetch + pull (origin only) ==" -ForegroundColor Cyan
git fetch origin
git pull --ff-only origin master
$HEAD = (git rev-parse --short=12 HEAD).Trim()
Write-Host "HEAD=$HEAD"
git merge-base --is-ancestor $EXP HEAD
if ($LASTEXITCODE -ne 0) { throw "HEAD missing target $EXP" }

Write-Host "== 2. marker checks ==" -ForegroundColor Cyan
$wwwHtml = Get-Content (Join-Path $work "web\console.html") -Raw -Encoding UTF8
if ($wwwHtml -notlike "*console.js?v=20260828i*") { throw "www console.html cache not 20260828i" }
$openHtml = Get-Content (Join-Path $work "p\open\web\console.html") -Raw -Encoding UTF8
if ($openHtml -notlike "*console.js?v=20260828i*") { throw "open console.html cache not 20260828i" }
if ($openHtml -notlike "*#modal-pay-channels .btn*") { throw "open console.html missing pay modal btn flex CSS" }
$wwwJs = Get-Content (Join-Path $work "web\js\console.js") -Raw -Encoding UTF8
if ($wwwJs -notlike "*pay-btn-title-row*") { throw "www console.js missing pay-btn-title-row" }
if ($wwwJs -notlike '*id === "token"*') { throw "www console.js missing token-first sort" }
$openJs = Get-Content (Join-Path $work "p\open\web\js\console.js") -Raw -Encoding UTF8
if ($openJs -notlike "*pay-btn-title-row*") { throw "open console.js missing pay-btn-title-row" }
if ($openJs -notlike "*var zh = AI24X_API.isZhUi()*") { throw "open renderPlans missing zh" }
Write-Host "markers OK" -ForegroundColor Green

Write-Host "== 3. restart services ==" -ForegroundColor Cyan
Restart-Service AI24X-core -ErrorAction Stop
Restart-Service AI24X-open-api -ErrorAction Stop
Start-Sleep -Seconds 8

Write-Host "== 4. public verify (on 04) ==" -ForegroundColor Cyan
$h = Invoke-RestMethod -UseBasicParsing -Uri "https://api.ai24x.com/health" -Headers @{ Accept = "application/json" }
$okCommit = $false
try { git merge-base --is-ancestor $EXP $h.commit; $okCommit = ($LASTEXITCODE -eq 0) } catch { $okCommit = $false }
if (-not $okCommit) { throw ("core commit mismatch: " + $h.commit) }

$wwwBody = (Invoke-WebRequest -UseBasicParsing -Uri "https://www.ai24x.com/console.html" -Headers @{ Accept = "text/html" }).Content
if ($wwwBody -notlike "*console.js?v=20260828i*") { throw "public www console version not 20260828i" }
$openBody = (Invoke-WebRequest -UseBasicParsing -Uri "https://open.ai24x.com/console.html" -Headers @{ Accept = "text/html" }).Content
if ($openBody -notlike "*console.js?v=20260828i*") { throw "public open console version not 20260828i" }

$wwwJsPub = (Invoke-WebRequest -UseBasicParsing -Uri "https://www.ai24x.com/js/console.js?v=20260828i" -Headers @{ Accept = "application/javascript" }).Content
if ($wwwJsPub -notlike "*pay-btn-title-row*") { throw "public www console.js missing pay layout fix" }
$openJsPub = (Invoke-WebRequest -UseBasicParsing -Uri "https://open.ai24x.com/js/console.js?v=20260828i" -Headers @{ Accept = "application/javascript" }).Content
if ($openJsPub -notlike "*pay-btn-title-row*") { throw "public open console.js missing pay layout fix" }
Write-Host "public verify OK" -ForegroundColor Green

Write-Host ("DONE EXP=" + $EXP + " HEAD=" + $HEAD + " health=" + $h.commit) -ForegroundColor Green

# --- 04 openclaw: 指挥部飞书群发一条 ---
# ✅ 04更新完成｜Console计费UI｜EXP=9c5a5fb HEAD=<HEAD> health=<commit>｜www+open console.js?v=20260828i 公网验收通过
