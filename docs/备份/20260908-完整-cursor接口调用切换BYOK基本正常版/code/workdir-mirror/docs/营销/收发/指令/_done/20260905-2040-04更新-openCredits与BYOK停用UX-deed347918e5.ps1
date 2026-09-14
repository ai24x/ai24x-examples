﻿$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "deed347918e5"
Set-Location $work

Write-Host "== 1. fetch + pull ==" -ForegroundColor Cyan
git fetch origin
git pull --ff-only origin master
$HEAD = (git rev-parse --short=12 HEAD).Trim()
Write-Host "HEAD=$HEAD"
git merge-base --is-ancestor $EXP HEAD
if ($LASTEXITCODE -ne 0) { throw "HEAD missing $EXP" }

Write-Host "== 2. markers ==" -ForegroundColor Cyan
$api = Get-Content "p\open\web\js\api.js" -Raw -Encoding UTF8
if ($api -notlike "*resolveRequestBase*") { throw "open api.js missing resolveRequestBase" }
if ($api -notlike "*/v1/billing/balance*") { throw "open api.js missing balance route split" }
$oc = Get-Content "p\open\web\console.html" -Raw -Encoding UTF8
if ($oc -notlike "*console.js?v=20260905c*") { throw "open console.html missing console.js?v=20260905c" }
if ($oc -notlike "*api.js?v=20260905a*") { throw "open console.html missing api.js?v=20260905a" }
if ($oc -notlike "*modal-byok-toggle*") { throw "open console.html missing byok toggle modal" }
if ($oc -notlike "*byokPanelMsg*") { throw "open console.html missing byokPanelMsg" }
$oj = Get-Content "p\open\web\js\console.js" -Raw -Encoding UTF8
if ($oj -notlike "*openByokToggleConfirm*") { throw "open console.js missing openByokToggleConfirm" }
if ($oj -notlike "*btn-primary*") { throw "open console.js missing Enable btn-primary" }
$wc = Get-Content "web\console.html" -Raw -Encoding UTF8
if ($wc -notlike "*console.js?v=20260905e*") { throw "www console.html missing console.js?v=20260905e" }
$wj = Get-Content "web\js\console.js" -Raw -Encoding UTF8
if ($wj -notlike "*每次进入流水页都重拉*") { throw "www console.js missing tx reload comment" }
Write-Host "markers OK" -ForegroundColor Green

Write-Host "== 3. restart (static pull; bounce for cache/health) ==" -ForegroundColor Cyan
Restart-Service AI24X-open-api -Force -ErrorAction Stop
Restart-Service AI24X-core -Force -ErrorAction Stop
Start-Sleep -Seconds 12

Write-Host "== 4. verify ==" -ForegroundColor Cyan
$ph = Invoke-RestMethod -UseBasicParsing -Uri "http://127.0.0.1:8002/health" -TimeoutSec 15
git merge-base --is-ancestor $EXP $ph.commit
if ($LASTEXITCODE -ne 0) { throw ("core health commit mismatch " + $ph.commit) }
$oh = Invoke-RestMethod -UseBasicParsing -Uri "http://127.0.0.1:18080/health" -TimeoutSec 15
if ($oh.commit) {
  git merge-base --is-ancestor $EXP $oh.commit
  if ($LASTEXITCODE -ne 0) { throw ("open health commit mismatch " + $oh.commit) }
}

$pubOpen = (Invoke-WebRequest -UseBasicParsing -Uri ("https://open.ai24x.com/console.html?x=" + $HEAD) -TimeoutSec 25).Content
if ($pubOpen -notlike "*console.js?v=20260905c*") { throw "public open console.js version stale" }
if ($pubOpen -notlike "*api.js?v=20260905a*") { throw "public open api.js version stale" }
if ($pubOpen -notlike "*modal-byok-toggle*") { throw "public open missing byok modal" }
$pubWww = (Invoke-WebRequest -UseBasicParsing -Uri ("https://www.ai24x.com/console.html?x=" + $HEAD) -TimeoutSec 25).Content
if ($pubWww -notlike "*console.js?v=20260905e*") { throw "public www console.js version stale" }

Write-Host ("DONE EXP=$EXP HEAD=$HEAD health=$($ph.commit)") -ForegroundColor Green
# ✅ 04更新完成｜open Credits+BYOK停用UX｜EXP=deed347918e5 HEAD=<HEAD> health=<commit>｜公网验收通过
