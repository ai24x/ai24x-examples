$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "ca5b2b6"
Set-Location $work

Write-Host "== 1. fetch + pull (origin only) ==" -ForegroundColor Cyan
git fetch origin
git pull --ff-only origin master
$HEAD = (git rev-parse --short=12 HEAD).Trim()
Write-Host "HEAD=$HEAD"
git merge-base --is-ancestor $EXP HEAD
if ($LASTEXITCODE -ne 0) { throw "HEAD missing target $EXP" }

Write-Host "== 2. marker checks ==" -ForegroundColor Cyan
if (-not (Test-Path (Join-Path $work "api\billing_money.py"))) { throw "api/billing_money.py missing" }
$mainPy = Get-Content (Join-Path $work "api\main.py") -Raw -Encoding UTF8
if ($mainPy -notlike "*_ADMIN_SESSION_TTL_S = 43200*") { throw "api/main.py missing 12h admin session TTL" }
$openApiJs = Get-Content (Join-Path $work "p\open\web\js\api.js") -Raw -Encoding UTF8
if ($openApiJs -notlike "*resolveRequestBase*") { throw "open api.js missing open-site billing routing" }
$openLocales = Get-Content (Join-Path $work "p\open\web\config\locales.js") -Raw -Encoding UTF8
if ($openLocales -notlike "*page.console.plans.creditsTitle*") { throw "open locales missing creditsTitle" }
$openHtml = Get-Content (Join-Path $work "p\open\web\console.html") -Raw -Encoding UTF8
if ($openHtml -notlike "*api.js?v=20260828j*") { throw "open console.html api.js cache not 20260828j" }
if ($openHtml -notlike "*locales.js?v=20260828j*") { throw "open console.html locales cache not 20260828j" }
$marketsHtml = Get-Content (Join-Path $work "p\markets\web\app.html") -Raw -Encoding UTF8
if ($marketsHtml -notlike "*payhub-btn-title-row*") { throw "markets app.html missing pay layout fix" }
$adminHtml = Get-Content (Join-Path $work "web\token-admin.html") -Raw -Encoding UTF8
if ($adminHtml.Length -lt 50000) { throw "token-admin.html seems stale/too small" }
Write-Host "markers OK" -ForegroundColor Green

Write-Host "== 3. restart services ==" -ForegroundColor Cyan
Restart-Service AI24X-core -ErrorAction Stop
Restart-Service AI24X-open-api -ErrorAction Stop
Restart-Service AI24X-markets-api -ErrorAction Stop
Start-Sleep -Seconds 12

Write-Host "== 4. public verify (on 04) ==" -ForegroundColor Cyan
$h = Invoke-RestMethod -UseBasicParsing -Uri "https://api.ai24x.com/health" -Headers @{ Accept = "application/json" }
$okCommit = $false
try { git merge-base --is-ancestor $EXP $h.commit; $okCommit = ($LASTEXITCODE -eq 0) } catch { $okCommit = $false }
if (-not $okCommit) { throw ("core commit mismatch: " + $h.commit) }

$openPlans = Invoke-RestMethod -UseBasicParsing -Uri "https://open.ai24x.com/v1/billing/plans" -Headers @{ Accept = "application/json" }
$byokCount = @($openPlans.byok_plans).Count
if ($byokCount -lt 2) { throw ("open billing/plans byok_plans count=" + $byokCount + ", expected >=2") }
Write-Host ("open byok_plans OK count=" + $byokCount) -ForegroundColor Green

$openBody = (Invoke-WebRequest -UseBasicParsing -Uri "https://open.ai24x.com/console.html" -Headers @{ Accept = "text/html" }).Content
if ($openBody -notlike "*api.js?v=20260828j*") { throw "public open console api.js version not 20260828j" }
$openJsPub = (Invoke-WebRequest -UseBasicParsing -Uri "https://open.ai24x.com/js/api.js?v=20260828j" -Headers @{ Accept = "application/javascript" }).Content
if ($openJsPub -notlike "*resolveRequestBase*") { throw "public open api.js missing BYOK routing fix" }

$marketsBody = (Invoke-WebRequest -UseBasicParsing -Uri "https://markets.ai24x.com/app.html" -Headers @{ Accept = "text/html" }).Content
if ($marketsBody -notlike "*payhub-btn-title-row*") { throw "public markets app.html missing pay layout fix" }

$adminBody = (Invoke-WebRequest -UseBasicParsing -Uri "https://www.ai24x.com/token-admin.html" -Headers @{ Accept = "text/html" }).Content
if ($adminBody.Length -lt 50000) { throw "public token-admin.html seems stale" }
Write-Host "public verify OK" -ForegroundColor Green

Write-Host ("DONE EXP=" + $EXP + " HEAD=" + $HEAD + " health=" + $h.commit) -ForegroundColor Green

# --- 04 openclaw: 指挥部飞书群发一条 ---
# ✅ 04更新完成｜BYOK+管理后台+billing_money｜EXP=ca5b2b6 HEAD=<HEAD> health=<commit>｜公网验收通过
