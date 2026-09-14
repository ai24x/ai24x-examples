$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "2c0125f"
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
if ($wwwHtml -notlike '*data-console-mode="hub"*') { throw "www console missing hub mode" }
if ($wwwHtml -notlike "*hub-launch-grid*") { throw "www console missing hub launcher" }
if ($wwwHtml -notlike "*console.js?v=20260829g*") { throw "www console.html cache not 20260829g" }
$openHtml = Get-Content (Join-Path $work "p\open\web\console.html") -Raw -Encoding UTF8
if ($openHtml -notlike '*data-console-mode="workspace"*') { throw "open console missing workspace mode" }
if ($openHtml -notlike "*ws-quick-actions*") { throw "open console missing workspace quick actions" }
if ($openHtml -notlike "*console.js?v=20260829j*") { throw "open console.html cache not 20260829j" }
$wwwJs = Get-Content (Join-Path $work "web\js\console.js") -Raw -Encoding UTF8
if ($wwwJs -notlike "*data-hub-external*") { throw "www console.js missing hub external links" }
if (-not (Test-Path (Join-Path $work "web\js\ai24x-chrome.js"))) { throw "www ai24x-chrome.js missing" }
if (-not (Test-Path (Join-Path $work "p\open\web\js\ai24x-chrome.js"))) { throw "open ai24x-chrome.js missing" }
if (-not (Test-Path (Join-Path $work "p\markets\web\js\ai24x-chrome.js"))) { throw "markets ai24x-chrome.js missing" }
Write-Host "markers OK" -ForegroundColor Green

Write-Host "== 3. sync markets static ==" -ForegroundColor Cyan
$site = "C:\sites\markets.ai24x.com"
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$bak = "$site.bak-$stamp"
if (Test-Path $site) {
  Copy-Item -LiteralPath $site -Destination $bak -Recurse -Force
}
robocopy (Join-Path $work "p\markets\web") $site /E /NFL /NDL /NJH /NJS /NP
if ($LASTEXITCODE -ge 8) { throw "robocopy markets failed code=$LASTEXITCODE" }
Write-Host "markets synced, backup=$bak"

Write-Host "== 4. restart services ==" -ForegroundColor Cyan
Restart-Service AI24X-core -ErrorAction Stop
Restart-Service AI24X-open-api -ErrorAction Stop
Restart-Service AI24X-markets-api -ErrorAction Stop
Start-Sleep -Seconds 12

Write-Host "== 5. public verify (on 04) ==" -ForegroundColor Cyan
$h = Invoke-RestMethod -UseBasicParsing -Uri "https://api.ai24x.com/health" -Headers @{ Accept = "application/json" }
$okCommit = $false
try { git merge-base --is-ancestor $EXP $h.commit; $okCommit = ($LASTEXITCODE -eq 0) } catch { $okCommit = $false }
if (-not $okCommit) { throw ("core commit mismatch: " + $h.commit) }

$wwwBody = (Invoke-WebRequest -UseBasicParsing -Uri "https://www.ai24x.com/console.html" -Headers @{ Accept = "text/html" }).Content
if ($wwwBody -notlike '*data-console-mode="hub"*') { throw "public www console missing hub mode" }
if ($wwwBody -notlike "*console.js?v=20260829g*") { throw "public www console version not 20260829g" }
$openBody = (Invoke-WebRequest -UseBasicParsing -Uri "https://open.ai24x.com/console.html" -Headers @{ Accept = "text/html" }).Content
if ($openBody -notlike '*data-console-mode="workspace"*') { throw "public open console missing workspace mode" }
if ($openBody -notlike "*console.js?v=20260829j*") { throw "public open console version not 20260829j" }
$mkBody = (Invoke-WebRequest -UseBasicParsing -Uri "https://markets.ai24x.com/" -Headers @{ Accept = "text/html" }).Content
if ($mkBody -notlike "*ai24x-chrome.js?v=20260829c*") { throw "public markets missing ai24x-chrome" }
$chromePub = (Invoke-WebRequest -UseBasicParsing -Uri "https://markets.ai24x.com/js/ai24x-chrome.js?v=20260829c" -Headers @{ Accept = "application/javascript" }).Content
if ($chromePub -notlike "*AI24X_CHROME*") { throw "public markets ai24x-chrome.js 404 or stale" }
Write-Host "public verify OK" -ForegroundColor Green

Write-Host ("DONE EXP=" + $EXP + " HEAD=" + $HEAD + " health=" + $h.commit) -ForegroundColor Green

# --- 04 openclaw：脚本成功后请在指挥部飞书群发一条精简确认（勿省略）---
# ✅ 04更新完成｜HubGateway分轨｜EXP=2c0125f HEAD=<HEAD> health=<commit>｜www+open+markets 公网验收通过
