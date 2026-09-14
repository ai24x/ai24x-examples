$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "8f4fb253e52b"
Set-Location $work
git fetch origin
git pull --ff-only origin master
$HEAD = (git rev-parse --short=12 HEAD).Trim()
git merge-base --is-ancestor $EXP HEAD
if ($LASTEXITCODE -ne 0) { throw "HEAD missing $EXP" }

$pm = Get-Content "api\price_monitor.py" -Raw -Encoding UTF8
if ($pm -notlike "*_is_stale_default_catalog*") { throw "missing stale default demotion" }
$fp = Get-Content "api\scripts_feishu_alert_poll.py" -Raw -Encoding UTF8
if ($fp -notlike "*_run_digest*") { throw "missing feishu digest" }
if ($fp -notlike "*127.0.0.1:8002*") { throw "missing default API 8002" }
$ta = Get-Content "web\token-admin.html" -Raw -Encoding UTF8
if ($ta -notlike "*formatAlertListHtml*") { throw "missing alert list UI" }
if ($ta -notlike "*ops-block*") { throw "missing supply ops-block" }
if (-not (Test-Path "api\run_feishu_alert_poll.cmd")) { throw "missing run_feishu_alert_poll.cmd" }

foreach ($tn in @("AI24X-Alert-Feishu-PM","AI24X-Alert-Feishu-PM-Evening")) {
  schtasks /Query /TN $tn 2>$null | Out-Null
  if ($LASTEXITCODE -ne 0) { Write-Host ("skip missing task " + $tn); continue }
  schtasks /Change /TN $tn /TR "C:\ai24x01\api\run_feishu_alert_poll.cmd --digest" | Out-Null
  Write-Host ("task updated: " + $tn)
}

Restart-Service AI24X-core -Force
if (Get-Service AI24X-open-api -ErrorAction SilentlyContinue) { Restart-Service AI24X-open-api -Force }
Start-Sleep -Seconds 14
$ph = Invoke-RestMethod -UseBasicParsing -Uri "http://127.0.0.1:8002/health" -TimeoutSec 20
Write-Host ("health.commit=" + $ph.commit)
git merge-base --is-ancestor $EXP $ph.commit
if ($LASTEXITCODE -ne 0) { throw "health.commit missing $EXP" }

Set-Location C:\ai24x01\api
& .\venv\Scripts\python.exe _verify_stale_ds_alarm.py
if ($LASTEXITCODE -ne 0) { throw "stale DS alarm still present" }
cmd /c "run_feishu_alert_poll.cmd --digest"

$pub = Invoke-RestMethod -UseBasicParsing -Uri "https://api.ai24x.com/health" -TimeoutSec 25
Write-Host ("public health=" + $pub.commit)
Write-Host ("DONE EXP=$EXP HEAD=$HEAD health=$($ph.commit)") -ForegroundColor Green
# ✅ 04更新完成｜告警列表与飞书摘要｜EXP=8f4fb253e52b HEAD=<HEAD> health=<commit>｜公网验收通过
