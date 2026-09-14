$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "897b48c931b7"
Set-Location $work

Write-Host "== 1. fetch + pull ==" -ForegroundColor Cyan
git fetch origin
git pull --ff-only origin master
$HEAD = (git rev-parse --short=12 HEAD).Trim()
Write-Host "HEAD=$HEAD"
git merge-base --is-ancestor $EXP HEAD
if ($LASTEXITCODE -ne 0) { throw "HEAD missing $EXP" }

Write-Host "== 2. markers ==" -ForegroundColor Cyan
$admin = Get-Content "web\token-admin.html" -Raw -Encoding UTF8
if ($admin -notlike "*no-store*") { throw "token-admin missing fetch no-store" }
if ($admin -notlike "*chLogHours*).onchange*") { throw "token-admin missing chLogHours onchange" }
$main = Get-Content "api\main.py" -Raw -Encoding UTF8
if ($main -notlike "*no-store, no-cache, must-revalidate*") { throw "channel_calls missing Cache-Control" }
Write-Host "markers OK" -ForegroundColor Green

Write-Host "== 3. restart core ==" -ForegroundColor Cyan
Restart-Service AI24X-core -Force
Start-Sleep -Seconds 8
$ph = Invoke-RestMethod -UseBasicParsing -Uri "http://127.0.0.1:8002/health" -TimeoutSec 20
Write-Host ("health.commit=" + $ph.commit)
git merge-base --is-ancestor $EXP $ph.commit
if ($LASTEXITCODE -ne 0) { throw "health.commit missing $EXP" }

Write-Host "== 4. public verify ==" -ForegroundColor Cyan
$adminP = Invoke-WebRequest -UseBasicParsing -Uri "https://www.ai24x.com/token-admin.html" -TimeoutSec 25
if ($adminP.Content -notlike "*no-store*") { throw "public token-admin missing no-store" }
foreach ($h in 24,72,168) {
  try {
    Invoke-WebRequest -UseBasicParsing -Uri ("https://api.ai24x.com/v1/admin/token/channel_calls?hours=$h&limit=1&_=" + [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()) -TimeoutSec 20 | Out-Null
  } catch {
    $code = [int]$_.Exception.Response.StatusCode
    if ($code -eq 404) { throw "channel_calls hours=$h still 404" }
  }
}

Write-Host ("DONE EXP=$EXP HEAD=$HEAD health=$($ph.commit)") -ForegroundColor Green
# ✅ 04更新完成｜通道流水防假404｜EXP=897b48c931b7 HEAD=<HEAD> health=<commit>｜公网验收通过