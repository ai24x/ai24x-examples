$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "65ad0ab08940"
Set-Location $work
git fetch origin
git pull --ff-only origin master
$HEAD = (git rev-parse --short=12 HEAD).Trim()
git merge-base --is-ancestor $EXP HEAD
if ($LASTEXITCODE -ne 0) { throw "HEAD missing $EXP" }
$pm = Get-Content "api\price_monitor.py" -Raw -Encoding UTF8
if ($pm -notlike "*effective_l1_lane*") { throw "missing effective_l1_lane in price_monitor" }
Restart-Service AI24X-core -Force
Start-Sleep -Seconds 10
$ph = Invoke-RestMethod -UseBasicParsing -Uri "http://127.0.0.1:8002/health" -TimeoutSec 20
Write-Host ("health.commit=" + $ph.commit)
git merge-base --is-ancestor $EXP $ph.commit
if ($LASTEXITCODE -ne 0) { throw "health.commit missing $EXP" }
Write-Host ("DONE EXP=$EXP HEAD=$HEAD health=$($ph.commit)") -ForegroundColor Green
# ✅ 04更新完成｜预警通道对齐｜EXP=65ad0ab08940 HEAD=<HEAD> health=<commit>｜公网验收通过
