$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "050a4d28ccc7"
Set-Location $work

Write-Host "== 1. fetch + pull (origin only) ==" -ForegroundColor Cyan
git fetch origin
git pull --ff-only origin master
$HEAD = (git rev-parse --short=12 HEAD).Trim()
Write-Host "HEAD=$HEAD"
git merge-base --is-ancestor $EXP HEAD
if ($LASTEXITCODE -ne 0) { throw "HEAD missing target $EXP" }

Write-Host "== 2. marker checks ==" -ForegroundColor Cyan
$app = Join-Path $work "p\markets\web\app.html"
$chrome = Join-Path $work "p\markets\web\js\ai24x-chrome.js"
$appBody = Get-Content $app -Raw -Encoding UTF8
$chromeBody = Get-Content $chrome -Raw -Encoding UTF8
if ($appBody -notlike "*ai24x-chrome.js?v=20260830p*") { throw "app.html cache bust not 20260830p" }
if ($chromeBody -notlike "*__ai24xBillingFetchPatched*") { throw "ai24x-chrome missing billing fetch shim" }
if ($chromeBody -notlike "*apiBase*") { throw "ai24x-chrome missing apiBase" }
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
Restart-Service AI24X-markets-api -ErrorAction Stop
Start-Sleep -Seconds 6

Write-Host "== 5. public verify (on 04) ==" -ForegroundColor Cyan
$appPub = (Invoke-WebRequest -UseBasicParsing -Uri "https://markets.ai24x.com/app.html?nocache=20260830p" -Headers @{ Accept = "text/html" }).Content
if ($appPub -notlike "*ai24x-chrome.js?v=20260830p*") { throw "public app.html missing 20260830p" }
$chromePub = (Invoke-WebRequest -UseBasicParsing -Uri "https://markets.ai24x.com/js/ai24x-chrome.js?v=20260830p" -Headers @{ Accept = "application/javascript" }).Content
if ($chromePub -notlike "*__ai24xBillingFetchPatched*") { throw "public ai24x-chrome missing fetch shim" }
$opt = Invoke-WebRequest -UseBasicParsing -Uri "https://api.ai24x.com/v1/billing/wechat/native" -Method Options -Headers @{
  Origin = "https://markets.ai24x.com"
  "Access-Control-Request-Method" = "POST"
  "Access-Control-Request-Headers" = "authorization,content-type"
}
if ($opt.Headers["Access-Control-Allow-Origin"] -ne "https://markets.ai24x.com") { throw "api CORS missing markets origin" }
Write-Host "public verify OK" -ForegroundColor Green

Write-Host ("DONE EXP=" + $EXP + " HEAD=" + $HEAD) -ForegroundColor Green

# ✅ 04更新完成｜markets支付缓存兜底｜EXP=050a4d28ccc7 HEAD=<HEAD> health=<commit>｜fetch shim+20260830p公网验收通过
