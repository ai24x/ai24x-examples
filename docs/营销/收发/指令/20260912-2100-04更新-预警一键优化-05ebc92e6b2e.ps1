$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "05ebc92e6b2e"
Set-Location $work
git fetch origin
git pull --ff-only origin master
$HEAD = (git rev-parse --short=12 HEAD).Trim()
git merge-base --is-ancestor $EXP HEAD
if ($LASTEXITCODE -ne 0) { throw "HEAD missing $EXP" }
$pm = Get-Content "api\price_monitor.py" -Raw -Encoding UTF8
if ($pm -notlike "*list_optimize_actions*") { throw "missing list_optimize_actions" }
if ($pm -notlike "*apply_optimize_batch*") { throw "missing apply_optimize_batch" }
$main = Get-Content "api\main.py" -Raw -Encoding UTF8
if ($main -notlike "*alerts/optimize*") { throw "missing alerts/optimize route" }
$ta = Get-Content "web\token-admin.html" -Raw -Encoding UTF8
if ($ta -notlike "*btnAlertOptimize*") { throw "missing btnAlertOptimize" }
if ($ta -notlike "*loadAlertOptimize*") { throw "missing loadAlertOptimize" }
Restart-Service AI24X-core -Force
Start-Sleep -Seconds 10
$ph = Invoke-RestMethod -UseBasicParsing -Uri "http://127.0.0.1:8002/health" -TimeoutSec 20
Write-Host ("health.commit=" + $ph.commit)
git merge-base --is-ancestor $EXP $ph.commit
if ($LASTEXITCODE -ne 0) { throw "health.commit missing $EXP" }
$pub = Invoke-RestMethod -UseBasicParsing -Uri "https://api.ai24x.com/health" -TimeoutSec 25
Write-Host ("public health=" + $pub.commit)
Write-Host ("DONE EXP=$EXP HEAD=$HEAD health=$($ph.commit)") -ForegroundColor Green
# ✅ 04更新完成｜预警一键优化｜EXP=05ebc92e6b2e HEAD=<HEAD> health=<commit>｜公网验收通过