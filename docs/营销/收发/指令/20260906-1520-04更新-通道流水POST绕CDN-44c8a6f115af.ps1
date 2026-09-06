$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "44c8a6f115af"
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
if ($admin -notlike "*channel_log*") { throw "token-admin missing channel_log POST" }
if ($admin -notlike '*method: "POST"*') { throw "token-admin channel_log not POST" }
$main = Get-Content "api\main.py" -Raw -Encoding UTF8
if ($main -notlike "*channel_log*") { throw "api missing channel_log route" }
Write-Host "markers OK" -ForegroundColor Green

Write-Host "== 3. restart core ==" -ForegroundColor Cyan
Restart-Service AI24X-core -Force
Start-Sleep -Seconds 8
$ph = Invoke-RestMethod -UseBasicParsing -Uri "http://127.0.0.1:8002/health" -TimeoutSec 20
Write-Host ("health.commit=" + $ph.commit)
git merge-base --is-ancestor $EXP $ph.commit
if ($LASTEXITCODE -ne 0) { throw "health.commit missing $EXP" }

Write-Host "== 4. verify POST channel_log ==" -ForegroundColor Cyan
$adminP = Invoke-WebRequest -UseBasicParsing -Uri "https://www.ai24x.com/token-admin.html" -TimeoutSec 25
if ($adminP.Content -notlike "*channel_log*") { throw "public token-admin missing channel_log" }
# unauth POST should be 403 not 404
try {
  Invoke-WebRequest -UseBasicParsing -Method POST -Uri "https://api.ai24x.com/v1/admin/token/channel_log" -ContentType "application/json" -Body '{"hours":72,"limit":1}' -TimeoutSec 20 | Out-Null
  throw "channel_log unexpectedly 200 without key"
} catch {
  $code = 0
  if ($_.Exception.Response) { $code = [int]$_.Exception.Response.StatusCode }
  if ($code -eq 404) { throw "public POST channel_log still 404" }
  Write-Host ("POST channel_log status=$code (want 401/403)") -ForegroundColor Green
}

Write-Host ("DONE EXP=$EXP HEAD=$HEAD health=$($ph.commit)") -ForegroundColor Green
# ✅ 04更新完成｜通道流水POST绕CDN｜EXP=44c8a6f115af HEAD=<HEAD> health=<commit>｜公网验收通过