$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "9be765744f09"
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
if ($admin -notlike "*p-channel-log*") { throw "token-admin missing p-channel-log" }
if ($admin -notlike "*channel_calls*") { throw "token-admin missing channel_calls API call" }
if ($admin -notlike "*NAV_PANEL_KEY*") { throw "token-admin missing NAV_PANEL_KEY" }
$main = Get-Content "api\main.py" -Raw -Encoding UTF8
if ($main -notlike "*channel_calls*") { throw "api/main.py missing channel_calls route" }
$ops = Get-Content "api\admin_ops_service.py" -Raw -Encoding UTF8
if ($ops -notlike "*def admin_channel_calls*") { throw "admin_ops_service missing admin_channel_calls" }
Write-Host "markers OK" -ForegroundColor Green

Write-Host "== 3. restart core (soft-migrate chat_requests + new route) ==" -ForegroundColor Cyan
Restart-Service AI24X-core -Force
Start-Sleep -Seconds 8
$ph = Invoke-RestMethod -UseBasicParsing -Uri "http://127.0.0.1:8002/health" -TimeoutSec 20
Write-Host ("health.commit=" + $ph.commit)
git merge-base --is-ancestor $EXP $ph.commit
if ($LASTEXITCODE -ne 0) { throw "health.commit missing $EXP" }

Write-Host "== 4. public verify ==" -ForegroundColor Cyan
$adminP = Invoke-WebRequest -UseBasicParsing -Uri "https://www.ai24x.com/token-admin.html" -TimeoutSec 25
if ($adminP.Content -notlike "*p-channel-log*") { throw "public token-admin missing p-channel-log" }
if ($adminP.Content -notlike "*channel_calls*") { throw "public token-admin missing channel_calls" }
if ($adminP.Content -notlike "*NAV_PANEL_KEY*") { throw "public token-admin missing NAV_PANEL_KEY" }
# route exists (401/403 with no key is OK; 404 means not deployed)
try {
  Invoke-WebRequest -UseBasicParsing -Uri "https://api.ai24x.com/v1/admin/token/channel_calls?hours=1&limit=1" -TimeoutSec 20 | Out-Null
  throw "channel_calls unexpectedly 200 without key"
} catch {
  $code = $null
  if ($_.Exception.Response) { $code = [int]$_.Exception.Response.StatusCode }
  if ($code -eq 404) { throw "public channel_calls still 404" }
  if ($code -ne 401 -and $code -ne 403) {
    Write-Host ("channel_calls status=$code (acceptable if not 404)") -ForegroundColor Yellow
  } else {
    Write-Host ("channel_calls status=$code (route live)") -ForegroundColor Green
  }
}

Write-Host ("DONE EXP=$EXP HEAD=$HEAD health=$($ph.commit)") -ForegroundColor Green
# ✅ 04更新完成｜通道流水+导航记忆｜EXP=9be765744f09 HEAD=<HEAD> health=<commit>｜公网验收通过
