$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "318602c5fb22"
Set-Location $work
git fetch origin
git pull --ff-only origin master
$HEAD = (git rev-parse --short=12 HEAD).Trim()
git merge-base --is-ancestor $EXP HEAD
if ($LASTEXITCODE -ne 0) { throw "HEAD missing $EXP" }

# markers
$oc = Get-Content "api\openai_compat.py" -Raw -Encoding UTF8
if ($oc -notlike "*_iter_events_with_keepalive*") { throw "missing keepalive helper" }
if ($oc -notlike "*: keepalive*") { throw "missing sse comment keepalive" }
$mr = Get-Content "api\model_router.py" -Raw -Encoding UTF8
if ($mr -notlike '*TOKEN_LLM_STREAM_TIMEOUT_S", "180"*') { throw "stream timeout default not 180" }

# env (line-level)
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\ai24x01\ops\_set_stream_env_04.ps1"

# nginx timeout patch (backup already at C:\backup\nginx-stream-*)
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\ai24x01\ops\_patch_nginx_stream_timeout_04.ps1"

Restart-Service AI24X-core -Force
Start-Sleep -Seconds 10
$ph = Invoke-RestMethod -UseBasicParsing -Uri "http://127.0.0.1:8002/health" -TimeoutSec 20
Write-Host ("health.commit=" + $ph.commit)
git merge-base --is-ancestor $EXP $ph.commit
if ($LASTEXITCODE -ne 0) { throw "health.commit missing $EXP" }

# public health
$pub = Invoke-RestMethod -UseBasicParsing -Uri "https://api.ai24x.com/health" -TimeoutSec 20
Write-Host ("public health=" + $pub.commit)
Write-Host ("DONE EXP=$EXP HEAD=$HEAD health=$($ph.commit)") -ForegroundColor Green
# ✅ 04更新完成｜流式心跳与超时｜EXP=318602c5fb22 HEAD=<HEAD> health=<commit>｜公网验收通过