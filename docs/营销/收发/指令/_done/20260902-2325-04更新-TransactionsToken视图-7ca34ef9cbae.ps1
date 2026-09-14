$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "7ca34ef9cbae"
Set-Location $work
Write-Host "== 1. fetch + pull ==" -ForegroundColor Cyan
git fetch origin
git pull --ff-only origin master
$HEAD = (git rev-parse --short=12 HEAD).Trim()
Write-Host "HEAD=$HEAD"
git merge-base --is-ancestor $EXP HEAD
if ($LASTEXITCODE -ne 0) { throw "HEAD missing $EXP" }

Write-Host "== 2. markers ==" -ForegroundColor Cyan
$js = Get-Content "web\js\console.js" -Raw -Encoding UTF8
if ($js -notlike '*setUsageMetric*') { throw "missing setUsageMetric" }
if ($js -notlike '*tokenOnly*') { throw "missing tokenOnly auto-switch" }
if ($js -notlike '*_usageModelsCache*') { throw "missing models cache" }
$html = Get-Content "web\console.html" -Raw -Encoding UTF8
if ($html -notlike '*console.js?v=20260902d*') { throw "console.js ?v= not 20260902d" }
if ($html -notlike '*locales.js?v=20260902d*') { throw "locales.js ?v= not 20260902d" }
if ($html -notlike '*usage-metric-hint*') { throw "missing usage-metric-hint" }
$loc = Get-Content "web\config\locales.js" -Raw -Encoding UTF8
if ($loc -notlike '*page.console.transactions.amount": "变动"*') { throw "zh amount not 变动" }
if ($loc -notlike '*page.console.transactions.amount": "Change"*') { throw "en amount not Change" }
$api = Get-Content "api\token_mvp_service.py" -Raw -Encoding UTF8
if ($api -notlike '*"token_pct"*') { throw "usage_keys missing token_pct" }
Write-Host "markers OK" -ForegroundColor Green

Write-Host "== 3. restart ==" -ForegroundColor Cyan
Restart-Service AI24X-open-api -ErrorAction SilentlyContinue
Restart-Service AI24X-core -ErrorAction Stop
Start-Sleep -Seconds 16

Write-Host "== 4. verify ==" -ForegroundColor Cyan
$ph = Invoke-RestMethod -UseBasicParsing -Uri "https://api.ai24x.com/health"
git merge-base --is-ancestor $EXP $ph.commit
if ($LASTEXITCODE -ne 0) { throw ("health commit mismatch " + $ph.commit) }
$console = Invoke-WebRequest -UseBasicParsing -Uri "https://www.ai24x.com/console.html"
if ($console.Content -notlike '*console.js?v=20260902d*') { throw "public console.html missing ?v=20260902d" }
if ($console.Content -notlike '*usage-metric-hint*') { throw "public console missing hint" }
$cj = Invoke-WebRequest -UseBasicParsing -Uri "https://www.ai24x.com/js/console.js?v=20260902d"
if ($cj.Content -notlike '*setUsageMetric*') { throw "public console.js missing setUsageMetric" }
Write-Host ("DONE EXP=$EXP HEAD=$HEAD health=$($ph.commit)") -ForegroundColor Green
# ✅ 04更新完成｜Transactions Token视图｜EXP=7ca34ef9cbae HEAD=<HEAD> health=<commit>｜纯Token账户自动切Tokens
