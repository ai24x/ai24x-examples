$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "947902904875"
Set-Location $work

Write-Host "== 1. fetch + pull ==" -ForegroundColor Cyan
git fetch origin
git pull --ff-only origin master
$HEAD = (git rev-parse --short=12 HEAD).Trim()
Write-Host "HEAD=$HEAD"
git merge-base --is-ancestor $EXP HEAD
if ($LASTEXITCODE -ne 0) { throw "HEAD missing $EXP" }

Write-Host "== 2. markers ==" -ForegroundColor Cyan
$wwwConsole = Get-Content "web\console.html" -Raw -Encoding UTF8
if ($wwwConsole -notlike "*api.js?v=20260906a*") { throw "www console missing api.js?v=20260906a" }
if ($wwwConsole -notlike "*console.js?v=20260906a*") { throw "www console missing console.js?v=20260906a" }
$apiJs = Get-Content "web\js\api.js" -Raw -Encoding UTF8
if ($apiJs -notlike "*billing/balance?_=*") { throw "www api.js missing balance cache bust" }
$consoleJs = Get-Content "web\js\console.js" -Raw -Encoding UTF8
if ($consoleJs -notlike '*id === "overview" || id === "billing"*') { throw "www console.js missing overview/billing refresh" }
if ($consoleJs -notlike "*Balance now $*") { throw "www console.js missing balance toast" }
if ($consoleJs -notlike "*typeof refreshAll === `"function`"*") { throw "www console.js missing refreshAll call" }
$openConsole = Get-Content "p\open\web\console.html" -Raw -Encoding UTF8
if ($openConsole -notlike "*api.js?v=20260906a*") { throw "open console missing api.js?v=20260906a" }
if ($openConsole -notlike "*console.js?v=20260906a*") { throw "open console missing console.js?v=20260906a" }
$openMain = Get-Content "p\open\api\main.py" -Raw -Encoding UTF8
if ($openMain -notlike "*no-store, no-cache, must-revalidate*") { throw "open main missing balance no-store" }
if ($openMain -notlike "*linked = getattr(u, `"platform_user_id`"*") { throw "open main missing linked platform guard" }
$coreMain = Get-Content "api\main.py" -Raw -Encoding UTF8
if ($coreMain -notlike "*no-store, no-cache, must-revalidate*") { throw "core main missing balance no-store" }
Write-Host "markers OK" -ForegroundColor Green

Write-Host "== 3. restart core + open ==" -ForegroundColor Cyan
Restart-Service AI24X-core -Force -ErrorAction Stop
Restart-Service AI24X-open-api -Force -ErrorAction Stop
Start-Sleep -Seconds 14

Write-Host "== 4. verify ==" -ForegroundColor Cyan
$ph = Invoke-RestMethod -UseBasicParsing -Uri "http://127.0.0.1:8002/health" -TimeoutSec 15
git merge-base --is-ancestor $EXP $ph.commit
if ($LASTEXITCODE -ne 0) { throw ("core health commit mismatch " + $ph.commit) }

$oh = Invoke-RestMethod -UseBasicParsing -Uri "http://127.0.0.1:18080/health" -TimeoutSec 15
if (-not $oh) { throw "open health empty" }

$www = Invoke-WebRequest -UseBasicParsing -Uri "https://www.ai24x.com/console.html" -TimeoutSec 25
if ($www.Content -notlike "*api.js?v=20260906a*") { throw "public www console missing api.js v20260906a" }
if ($www.Content -notlike "*console.js?v=20260906a*") { throw "public www console missing console.js v20260906a" }

$open = Invoke-WebRequest -UseBasicParsing -Uri "https://open.ai24x.com/console.html" -TimeoutSec 25
if ($open.Content -notlike "*api.js?v=20260906a*") { throw "public open console missing api.js v20260906a" }
if ($open.Content -notlike "*console.js?v=20260906a*") { throw "public open console missing console.js v20260906a" }

$balHdr = Invoke-WebRequest -UseBasicParsing -Uri "https://api.ai24x.com/v1/billing/balance" -TimeoutSec 20 -ErrorAction SilentlyContinue
# 未登录应 401，但仍应能看到防缓存头（若网关透传）
Write-Host ("balance_probe status=" + $(if ($balHdr) { $balHdr.StatusCode } else { "n/a" }))

Write-Host ("DONE EXP=$EXP HEAD=$HEAD health=$($ph.commit)") -ForegroundColor Green
# ✅ 04更新完成｜充值余额即时刷新｜EXP=947902904875 HEAD=<HEAD> health=<commit>｜公网验收通过
