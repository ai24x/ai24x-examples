$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "3d594c4b9fe6"
Set-Location $work

Write-Host "== 1. fetch + pull (origin only) ==" -ForegroundColor Cyan
git fetch origin
git pull --ff-only origin master
$HEAD = (git rev-parse --short=12 HEAD).Trim()
Write-Host "HEAD=$HEAD"
git merge-base --is-ancestor $EXP HEAD
if ($LASTEXITCODE -ne 0) { throw "HEAD missing target $EXP" }

Write-Host "== 2. marker checks ==" -ForegroundColor Cyan
$wwwCon = Get-Content (Join-Path $work "web\console.html") -Raw -Encoding UTF8
$wwwJs = Get-Content (Join-Path $work "web\js\console.js") -Raw -Encoding UTF8
$openCon = Get-Content (Join-Path $work "p\open\web\console.html") -Raw -Encoding UTF8
if ($wwwCon -notlike '*data-console-panel="transactions"*') { throw "www console missing transactions nav" }
if ($wwwCon -notlike '*locales.js?v=20260902c*') { throw "www console locales not 20260902c" }
if ($wwwCon -notlike '*console.js?v=20260902c*') { throw "www console.js not 20260902c" }
if ($wwwJs -notlike '*bindTransactionsControls*') { throw "www console.js missing transactions binder" }
if ($openCon -notlike '*page.console.byok.apiHint*') { throw "open console missing byok apiHint" }
if ($openCon -notlike '*console.js?v=20260902c*') { throw "open console.js not 20260902c" }
Write-Host "markers OK" -ForegroundColor Green

Write-Host "== 3. restart open + core ==" -ForegroundColor Cyan
Restart-Service AI24X-open-api -ErrorAction Stop
Restart-Service AI24X-core -ErrorAction Stop
Start-Sleep -Seconds 12

Write-Host "== 4. public verify ==" -ForegroundColor Cyan
$ph = Invoke-RestMethod -UseBasicParsing -Uri "https://api.ai24x.com/health"
git merge-base --is-ancestor $EXP $ph.commit
if ($LASTEXITCODE -ne 0) { throw ("public core commit mismatch: " + $ph.commit) }
$nocache = Get-Date -Format "yyyyMMddHHmmss"
$wwwPub = (Invoke-WebRequest -UseBasicParsing -Uri ("https://www.ai24x.com/console.html?v=" + $nocache) -Headers @{ Accept = "text/html" }).Content
if ($wwwPub -notlike '*data-console-panel="transactions"*') { throw "public www missing transactions nav" }
if ($wwwPub -notlike '*locales.js?v=20260902c*') { throw "public www locales stale" }
if ($wwwPub -notlike '*console.js?v=20260902c*') { throw "public www console.js stale" }
$openPub = (Invoke-WebRequest -UseBasicParsing -Uri ("https://open.ai24x.com/console.html?v=" + $nocache) -Headers @{ Accept = "text/html" }).Content
if ($openPub -notlike '*console.js?v=20260902c*') { throw "public open console.js stale" }
Write-Host "public verify OK" -ForegroundColor Green

Write-Host ("DONE EXP=" + $EXP + " HEAD=" + $HEAD + " health=" + $ph.commit) -ForegroundColor Green
# ✅ 04更新完成｜Hub Transactions侧栏｜EXP=3d594c4b9fe6 HEAD=<HEAD> health=<commit>｜www/open console 20260902c公网验收通过
