$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "6b9d5ec26207"
Set-Location $work
git fetch origin
git pull --ff-only origin master
$HEAD = (git rev-parse --short=12 HEAD).Trim()
git merge-base --is-ancestor $EXP HEAD
if ($LASTEXITCODE -ne 0) { throw "HEAD missing $EXP" }

$sv = Get-Content "api\services.py" -Raw -Encoding UTF8
if ($sv -notlike "*daily_request_limit*") { throw "missing daily_request_limit code" }
if ($sv -notlike "*last_day < today*") { throw "missing calendar-day reset" }
$tm = Get-Content "api\token_mvp_service.py" -Raw -Encoding UTF8
if ($tm -notlike "*GATEWAY_PREPAID_DAILY_REQ*") { throw "missing prepaid daily cap" }
if ($tm -notlike "*HTTP_402_PAYMENT_REQUIRED*") { throw "missing 402 insufficient_credits" }
$oc = Get-Content "api\openai_compat.py" -Raw -Encoding UTF8
if ($oc -notlike "*detail_code or*") { throw "missing 429 detail_code passthrough" }

Restart-Service AI24X-core -Force
if (Get-Service AI24X-open-api -ErrorAction SilentlyContinue) {
  Restart-Service AI24X-open-api -Force
}
Start-Sleep -Seconds 12
$ph = Invoke-RestMethod -UseBasicParsing -Uri "http://127.0.0.1:8002/health" -TimeoutSec 20
Write-Host ("health.commit=" + $ph.commit)
git merge-base --is-ancestor $EXP $ph.commit
if ($LASTEXITCODE -ne 0) { throw "health.commit missing $EXP" }

# 飞书运维号 auth_40：同步预充日帽并清零当日计数
python "C:\Users\Administrator\ops\_reset_feishu_gateway_daily_04.py"

$pub = Invoke-RestMethod -UseBasicParsing -Uri "https://api.ai24x.com/health" -TimeoutSec 25
Write-Host ("public health=" + $pub.commit)
Write-Host ("DONE EXP=$EXP HEAD=$HEAD health=$($ph.commit)") -ForegroundColor Green
# ✅ 04更新完成｜网关日请求帽与402｜EXP=6b9d5ec26207 HEAD=<HEAD> health=<commit>｜公网验收通过
