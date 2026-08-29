$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "173dbbf8c317"
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
if (-not (Test-Path $app)) { throw "app.html missing" }
$appBody = Get-Content $app -Raw -Encoding UTF8
if ($appBody -notlike "*function apiUrl()*") { throw "app.html missing apiUrl()" }
if ($appBody -notlike "*fetch(apiUrl() + path*") { throw "app.html hubFetch not using apiUrl" }
if ($appBody -notlike "*fetch(apiUrl() + '/v1/billing/pay/status')*") { throw "app.html pay/status not using apiUrl" }
if ($appBody -like "*fetch(coreUrl() + '/v1/billing*") { throw "app.html still has coreUrl billing fetch" }
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
Start-Sleep -Seconds 8

Write-Host "== 5. public verify (on 04) ==" -ForegroundColor Cyan
$h = Invoke-RestMethod -UseBasicParsing -Uri "https://api.ai24x.com/health" -Headers @{ Accept = "application/json" }
$okCommit = $false
try { git merge-base --is-ancestor $EXP $h.commit; $okCommit = ($LASTEXITCODE -eq 0) } catch { $okCommit = $false }
if (-not $okCommit) { throw ("core commit mismatch: " + $h.commit) }

$appPub = (Invoke-WebRequest -UseBasicParsing -Uri "https://markets.ai24x.com/app.html" -Headers @{ Accept = "text/html" }).Content
if ($appPub -notlike "*function apiUrl()*") { throw "public app.html missing apiUrl()" }
if ($appPub -notlike "*fetch(apiUrl() + path*") { throw "public app.html hubFetch not using apiUrl" }
if ($appPub -like "*fetch(coreUrl() + '/v1/billing*") { throw "public app.html still has coreUrl billing fetch" }

$opt = Invoke-WebRequest -UseBasicParsing -Uri "https://api.ai24x.com/v1/billing/wechat/native" -Method Options -Headers @{
  Origin = "https://markets.ai24x.com"
  "Access-Control-Request-Method" = "POST"
  "Access-Control-Request-Headers" = "authorization,content-type"
}
if ($opt.Headers["Access-Control-Allow-Origin"] -ne "https://markets.ai24x.com") { throw "api CORS missing markets origin" }
Write-Host "public verify OK" -ForegroundColor Green

Write-Host ("DONE EXP=" + $EXP + " HEAD=" + $HEAD + " health=" + $h.commit) -ForegroundColor Green

# ✅ 04更新完成｜markets支付API修复｜EXP=173dbbf8c317 HEAD=<HEAD> health=<commit>｜app.html apiUrl+markets CORS验收通过
