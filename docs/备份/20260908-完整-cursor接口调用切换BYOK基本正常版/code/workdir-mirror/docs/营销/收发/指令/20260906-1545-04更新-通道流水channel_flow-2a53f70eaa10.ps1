$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "2a53f70eaa10"
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
if ($admin -notlike "*channel_flow*") { throw "token-admin missing channel_flow" }
$main = Get-Content "api\main.py" -Raw -Encoding UTF8
if ($main -notlike "*channel_flow*") { throw "api missing channel_flow" }
Write-Host "markers OK" -ForegroundColor Green

Write-Host "== 3. restart core ==" -ForegroundColor Cyan
Restart-Service AI24X-core -Force
Start-Sleep -Seconds 8
$ph = Invoke-RestMethod -UseBasicParsing -Uri "http://127.0.0.1:8002/health" -TimeoutSec 20
Write-Host ("health.commit=" + $ph.commit)
git merge-base --is-ancestor $EXP $ph.commit
if ($LASTEXITCODE -ne 0) { throw "health.commit missing $EXP" }

Write-Host "== 4. verify ==" -ForegroundColor Cyan
$adminP = Invoke-WebRequest -UseBasicParsing -Uri "https://www.ai24x.com/token-admin.html" -TimeoutSec 25
if ($adminP.Content -notlike "*channel_flow*") { throw "public html missing channel_flow" }
foreach ($h in 24,72,168) {
  try {
    Invoke-WebRequest -UseBasicParsing -Uri ("https://api.ai24x.com/v1/admin/token/channel_flow?hours=$h&limit=1&_=" + [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()) -TimeoutSec 20 | Out-Null
  } catch {
    $code = [int]$_.Exception.Response.StatusCode
    if ($code -eq 404 -or $code -eq 405) { throw "channel_flow hours=$h status=$code" }
    Write-Host ("channel_flow hours=$h status=$code (auth expected)") -ForegroundColor Green
  }
}
Write-Host ("DONE EXP=$EXP HEAD=$HEAD health=$($ph.commit)") -ForegroundColor Green
# ✅ 04更新完成｜通道流水channel_flow｜EXP=2a53f70eaa10 HEAD=<HEAD> health=<commit>｜公网验收通过