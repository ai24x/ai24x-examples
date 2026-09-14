$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "af072137cdd3"
Set-Location $work

Write-Host "== 1. fetch + pull ==" -ForegroundColor Cyan
git fetch origin
git pull --ff-only origin master
$HEAD = (git rev-parse --short=12 HEAD).Trim()
Write-Host "HEAD=$HEAD"
git merge-base --is-ancestor $EXP HEAD
if ($LASTEXITCODE -ne 0) { throw "HEAD missing $EXP" }

Write-Host "== 2. markers ==" -ForegroundColor Cyan
$oc = Get-Content "p\open\web\console.html" -Raw -Encoding UTF8
if ($oc -notlike "*console.js?v=20260905f*") { throw "open console.html missing console.js?v=20260905f" }
if ($oc -notlike "*locales.js?v=20260905f*") { throw "open console.html missing locales.js?v=20260905f" }
$oj = Get-Content "p\open\web\js\console.js" -Raw -Encoding UTF8
if ($oj -notlike "*下一步动作*") { throw "console.js missing action-label comment" }
if ($oj -notlike "*no-store*") { throw "console.js missing no-store" }
$br = Get-Content "p\open\api\byok_routes.py" -Raw -Encoding UTF8
if ($br -notlike "*no-store, no-cache*") { throw "byok_routes missing no-store headers" }
Write-Host "markers OK" -ForegroundColor Green

Write-Host "== 3. restart open-api ==" -ForegroundColor Cyan
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
if ($pubOpen -notlike "*console.js?v=20260905f*") { throw "public open console.js version stale" }

Write-Host ("DONE EXP=$EXP HEAD=$HEAD health=$($ph.commit)") -ForegroundColor Green
# ✅ 04更新完成｜BYOK开关动作与防缓存｜EXP=af072137cdd3 HEAD=<HEAD> health=<commit>｜公网验收通过
