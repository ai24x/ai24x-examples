$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "f1d5624"
Set-Location $work

Write-Host "== 1. fetch + pull (origin only) ==" -ForegroundColor Cyan
git fetch origin
git pull --ff-only origin master
$HEAD = (git rev-parse --short=12 HEAD).Trim()
Write-Host "HEAD=$HEAD"
git merge-base --is-ancestor $EXP HEAD
if ($LASTEXITCODE -ne 0) { throw "HEAD missing target $EXP" }

Write-Host "== 2. marker checks ==" -ForegroundColor Cyan
$mkCss = Join-Path $work "p\markets\web\css\mk-site.css"
if (-not (Test-Path $mkCss)) { throw "mk-site.css missing" }
$mkCssBody = Get-Content $mkCss -Raw -Encoding UTF8
if ($mkCssBody -notlike "*scrollbar-gutter*") { throw "mk-site.css missing scrollbar-gutter" }
if ($mkCssBody -notlike "*translate(-50%*") { throw "mk-site.css missing centered nav" }
$pricing = Get-Content (Join-Path $work "p\markets\web\pricing.html") -Raw -Encoding UTF8
if ($pricing -notlike "*mk-site.css?v=20260829r*") { throw "pricing.html cache not 20260829r" }
if ($pricing -notlike "*brand-group*") { throw "pricing.html missing brand-group" }
if (-not (Test-Path (Join-Path $work "p\markets\web\help.html"))) { throw "help.html missing" }
$help = Get-Content (Join-Path $work "p\markets\web\help.html") -Raw -Encoding UTF8
if ($help -notlike "*mk-site.css?v=20260829r*") { throw "help.html cache not 20260829r" }
$chrome = Get-Content (Join-Path $work "web\js\ai24x-chrome.js") -Raw -Encoding UTF8
if ($chrome -notlike "*data-hub-external*") { throw "www ai24x-chrome missing hub-external keep-blank" }
$product = Get-Content (Join-Path $work "web\product.html") -Raw -Encoding UTF8
if ($product -notlike "*data-hub-external*") { throw "www product.html missing data-hub-external" }
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

$mkHome = (Invoke-WebRequest -UseBasicParsing -Uri "https://markets.ai24x.com/" -Headers @{ Accept = "text/html" }).Content
if ($mkHome -notlike "*mk-site.css?v=20260829r*") { throw "public markets home missing mk-site 20260829r" }
$mkPrice = (Invoke-WebRequest -UseBasicParsing -Uri "https://markets.ai24x.com/pricing.html" -Headers @{ Accept = "text/html" }).Content
if ($mkPrice -notlike "*mk-site.css?v=20260829r*") { throw "public pricing missing mk-site 20260829r" }
if ($mkPrice -notlike "*brand-group*") { throw "public pricing missing brand-group" }
$mkHelp = (Invoke-WebRequest -UseBasicParsing -Uri "https://markets.ai24x.com/help.html" -Headers @{ Accept = "text/html" }).Content
if ($mkHelp -notlike "*Markets help*") { throw "public help.html missing" }
$cssPub = (Invoke-WebRequest -UseBasicParsing -Uri "https://markets.ai24x.com/css/mk-site.css?v=20260829r" -Headers @{ Accept = "text/css" }).Content
if ($cssPub -notlike "*scrollbar-gutter*") { throw "public mk-site.css stale" }
$wwwProduct = (Invoke-WebRequest -UseBasicParsing -Uri "https://www.ai24x.com/product.html" -Headers @{ Accept = "text/html" }).Content
if ($wwwProduct -notlike "*data-hub-external*") { throw "public www product missing data-hub-external" }
Write-Host "public verify OK" -ForegroundColor Green

Write-Host ("DONE EXP=" + $EXP + " HEAD=" + $HEAD + " health=" + $h.commit) -ForegroundColor Green

# --- 04 openclaw：脚本成功后请在指挥部飞书群发一条精简确认（勿省略）---
# ✅ 04更新完成｜Markets顶栏文案｜EXP=f1d5624 HEAD=<HEAD> health=<commit>｜公网验收通过