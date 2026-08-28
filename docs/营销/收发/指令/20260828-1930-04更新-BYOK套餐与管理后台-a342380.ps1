$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "a342380"
Set-Location $work

Write-Host "== 1. fetch + pull (origin only) ==" -ForegroundColor Cyan
git fetch origin
git pull --ff-only origin master
$HEAD = (git rev-parse --short=12 HEAD).Trim()
Write-Host "HEAD=$HEAD"
git merge-base --is-ancestor $EXP HEAD
if ($LASTEXITCODE -ne 0) { throw "HEAD missing target $EXP" }

Write-Host "== 2. marker checks ==" -ForegroundColor Cyan
$mainPy = Get-Content (Join-Path $work "api\main.py") -Raw -Encoding UTF8
if ($mainPy -notlike "*_ADMIN_SESSION_TTL_S = 43200*") { throw "api/main.py missing 12h admin session TTL" }
$openApiJs = Get-Content (Join-Path $work "p\open\web\js\api.js") -Raw -Encoding UTF8
if ($openApiJs -notlike "*resolveRequestBase*") { throw "open api.js missing open-site billing routing" }
if ($openApiJs -notlike "*isOpenSitePage*") { throw "open api.js missing isOpenSitePage" }
$openHtml = Get-Content (Join-Path $work "p\open\web\console.html") -Raw -Encoding UTF8
if ($openHtml -notlike "*api.js?v=20260828j*") { throw "open console.html api.js cache not 20260828j" }
$adminHtml = Get-Content (Join-Path $work "web\token-admin.html") -Raw -Encoding UTF8
if ($adminHtml.Length -lt 50000) { throw "token-admin.html seems stale/too small" }
Write-Host "markers OK" -ForegroundColor Green

Write-Host "== 3. restart services ==" -ForegroundColor Cyan
Restart-Service AI24X-core -ErrorAction Stop
Restart-Service AI24X-open-api -ErrorAction Stop
Start-Sleep -Seconds 10

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

$adminBody = (Invoke-WebRequest -UseBasicParsing -Uri "https://www.ai24x.com/token-admin.html" -Headers @{ Accept = "text/html" }).Content
if ($adminBody.Length -lt 50000) { throw "public token-admin.html seems stale" }
Write-Host "public verify OK" -ForegroundColor Green

Write-Host ("DONE EXP=" + $EXP + " HEAD=" + $HEAD + " health=" + $h.commit) -ForegroundColor Green

# --- 04 openclaw: 指挥部飞书群发一条 ---
# ✅ 04更新完成｜BYOK套餐+管理后台｜EXP=a342380 HEAD=<HEAD> health=<commit>｜open BYOK Pro 套餐+admin 12h 会话
