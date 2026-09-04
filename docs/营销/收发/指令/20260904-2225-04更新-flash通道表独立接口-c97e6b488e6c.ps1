$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "c97e6b488e6c"
Set-Location $work

Write-Host "== 1. fetch + pull ==" -ForegroundColor Cyan
git fetch origin
git pull --ff-only origin master
$HEAD = (git rev-parse --short=12 HEAD).Trim()
Write-Host "HEAD=$HEAD"
git merge-base --is-ancestor $EXP HEAD
if ($LASTEXITCODE -ne 0) { throw "HEAD missing $EXP" }

Write-Host "== 2. markers ==" -ForegroundColor Cyan
$main = Get-Content "api\main.py" -Raw -Encoding UTF8
if ($main -notlike "*admin_price_flash_lanes*") { throw "main missing flash-lanes route" }
if ($main -notlike "*price/flash-lanes*") { throw "main missing /price/flash-lanes" }
$ta = Get-Content "web\token-admin.html" -Raw -Encoding UTF8
if ($ta -notlike "*flash-lanes-v20260904d*") { throw "token-admin missing marker v20260904d" }
if ($ta -notlike "*price/flash-lanes*") { throw "token-admin missing flash-lanes fetch" }
Write-Host "markers OK" -ForegroundColor Green

Write-Host "== 3. restart core ==" -ForegroundColor Cyan
Restart-Service AI24X-core -Force -ErrorAction Stop
Start-Sleep -Seconds 12

Write-Host "== 4. verify ==" -ForegroundColor Cyan
$ph = Invoke-RestMethod -UseBasicParsing -Uri "http://127.0.0.1:8002/health" -TimeoutSec 15
git merge-base --is-ancestor $EXP $ph.commit
if ($LASTEXITCODE -ne 0) { throw ("core health commit mismatch " + $ph.commit) }

Set-Location "$work\api"
$envLine = (Select-String -Path .\.env -Pattern "^ADMIN_API_KEY=" | Select-Object -First 1).Line
$key = $envLine.Substring("ADMIN_API_KEY=".Length).Trim().Trim('"').Trim("'")
$headers = @{ "X-Admin-Key" = $key; "X-SMS-Internal-Key" = $key }
$fl = Invoke-RestMethod -UseBasicParsing -Uri "http://127.0.0.1:8002/v1/admin/price/flash-lanes" -Headers $headers -TimeoutSec 30
if (-not $fl.lanes -or @($fl.lanes).Count -lt 1) { throw "flash-lanes empty" }
Write-Host ("flash_lanes_http_ok " + $fl.active + " " + @($fl.lanes).Count)
Set-Location $work

$taW = Invoke-WebRequest -UseBasicParsing -Uri "https://www.ai24x.com/token-admin.html" -TimeoutSec 20
if ($taW.Content -notlike "*flash-lanes-v20260904d*") { throw "public token-admin missing marker" }

Write-Host ("DONE EXP=$EXP HEAD=$HEAD health=$($ph.commit)") -ForegroundColor Green
# ✅ 04更新完成｜flash通道表独立接口｜EXP=c97e6b488e6c HEAD=<HEAD> health=<commit>｜公网验收通过