$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "54784d7"
Set-Location $work

Write-Host "== 1. fetch + pull ==" -ForegroundColor Cyan
git fetch origin
git pull --ff-only origin master
$HEAD = (git rev-parse --short=12 HEAD).Trim()
Write-Host "HEAD=$HEAD"
git merge-base --is-ancestor $EXP HEAD
if ($LASTEXITCODE -ne 0) { throw "HEAD missing target $EXP" }

Write-Host "== 2. marker checks ==" -ForegroundColor Cyan
$wwwJs = Get-Content (Join-Path $work "web\js\console.js") -Raw -Encoding UTF8
if ($wwwJs -notlike "*function isMobileCheckout*") { throw "www console.js missing isMobileCheckout" }
if ($wwwJs -notlike "*window.location.href = r.pay_url*") { throw "www console.js missing same-tab redirect" }
$openJs = Get-Content (Join-Path $work "p\open\web\js\console.js") -Raw -Encoding UTF8
if ($openJs -notlike "*function isMobileCheckout*") { throw "open console.js missing isMobileCheckout" }
if ($openJs -notlike "*window.location.href = r.pay_url*") { throw "open console.js missing same-tab redirect" }
$mkHtml = Get-Content (Join-Path $work "p\markets\web\app.html") -Raw -Encoding UTF8
if ($mkHtml -notlike "*mobileCheckout*") { throw "markets app.html missing mobileCheckout" }
$wwwC = Get-Content (Join-Path $work "web\console.html") -Raw -Encoding UTF8
if ($wwwC -notlike "*console.js?v=20260827b*") { throw "www console.html version not bumped" }
$openC = Get-Content (Join-Path $work "p\open\web\console.html") -Raw -Encoding UTF8
if ($openC -notlike "*console.js?v=20260827b*") { throw "open console.html version not bumped" }
Write-Host "markers OK" -ForegroundColor Green

Write-Host "== 3. sync markets static (backup first) ==" -ForegroundColor Cyan
$site = "C:\sites\markets.ai24x.com"
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
Copy-Item -LiteralPath (Join-Path $site "app.html") -Destination (Join-Path $site ("app.html.bak-" + $stamp)) -Force
Copy-Item -LiteralPath (Join-Path $work "p\markets\web\app.html") -Destination (Join-Path $site "app.html") -Force
Write-Host ("markets app.html synced, backup .bak-" + $stamp)

Write-Host "== 4. restart services ==" -ForegroundColor Cyan
Restart-Service AI24X-markets-api -ErrorAction Stop
Start-Sleep -Seconds 5
Restart-Service AI24X-open-api -ErrorAction Stop
Start-Sleep -Seconds 5
Restart-Service AI24X-core -ErrorAction Stop
Start-Sleep -Seconds 8

Write-Host "== 5. public verify ==" -ForegroundColor Cyan
$h = Invoke-RestMethod -UseBasicParsing -Uri "https://api.ai24x.com/health" -Headers @{ Accept = "application/json" }
if ($h.commit -notlike "$EXP*") { throw ("core commit mismatch: " + $h.commit) }
$wwwBody = (Invoke-WebRequest -UseBasicParsing -Uri "https://www.ai24x.com/console.html" -Headers @{ Accept = "text/html" }).Content
if ($wwwBody -notlike "*console.js?v=20260827b*") { throw "public www console.html version missing" }
$openBody = (Invoke-WebRequest -UseBasicParsing -Uri "https://open.ai24x.com/console.html" -Headers @{ Accept = "text/html" }).Content
if ($openBody -notlike "*console.js?v=20260827b*") { throw "public open console.html version missing" }
$mkBody = (Invoke-WebRequest -UseBasicParsing -Uri "https://markets.ai24x.com/app.html" -Headers @{ Accept = "text/html" }).Content
if ($mkBody -notlike "*mobileCheckout*") { throw "public markets app.html missing mobileCheckout" }
Write-Host "public verify OK" -ForegroundColor Green

Write-Host "MOBILE PAY FIX DEPLOY DONE" -ForegroundColor Green
Write-Host ("DONE EXP=" + $EXP + " HEAD=" + $HEAD) -ForegroundColor Green
