$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "f9610fd0457e"
Set-Location $work
git fetch origin
git pull --ff-only origin master
$HEAD = (git rev-parse --short=12 HEAD).Trim()
git merge-base --is-ancestor $EXP HEAD
if ($LASTEXITCODE -ne 0) { throw "HEAD missing $EXP" }

$pm = Get-Content "api\price_monitor.py" -Raw -Encoding UTF8
if ($pm -notlike "*cost_from_admin*") { throw "missing cost_from_admin" }
if ($pm -notlike "*skipped_cost*") { throw "missing skipped_cost hike skip" }
if ($pm -notlike "*官方成本高于聚合商最低*") { throw "missing softened market flag copy" }
$op = Get-Content "p\open\api\price_monitor.py" -Raw -Encoding UTF8
if ($op -notlike "*cost_from_admin*") { throw "open mirror missing cost_from_admin" }

Restart-Service AI24X-core -Force
if (Get-Service AI24X-open-api -ErrorAction SilentlyContinue) {
  Restart-Service AI24X-open-api -Force
}
Start-Sleep -Seconds 12
$ph = Invoke-RestMethod -UseBasicParsing -Uri "http://127.0.0.1:8002/health" -TimeoutSec 20
Write-Host ("health.commit=" + $ph.commit)
git merge-base --is-ancestor $EXP $ph.commit
if ($LASTEXITCODE -ne 0) { throw "health.commit missing $EXP" }

$pub = Invoke-RestMethod -UseBasicParsing -Uri "https://api.ai24x.com/health" -TimeoutSec 25
Write-Host ("public health=" + $pub.commit)
Write-Host ("DONE EXP=$EXP HEAD=$HEAD health=$($ph.commit)") -ForegroundColor Green
# ✅ 04更新完成｜供应链监控成本口径｜EXP=f9610fd0457e HEAD=<HEAD> health=<commit>｜公网验收通过