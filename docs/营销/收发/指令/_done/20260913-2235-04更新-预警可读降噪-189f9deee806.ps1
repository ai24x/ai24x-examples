$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "189f9deee806"
Set-Location $work
git fetch origin
git pull --ff-only origin master
$HEAD = (git rev-parse --short=12 HEAD).Trim()
git merge-base --is-ancestor $EXP HEAD
if ($LASTEXITCODE -ne 0) { throw "HEAD missing $EXP" }
$oa = Get-Content "api\ops_alert.py" -Raw -Encoding UTF8
if ($oa -notlike "*_human_price_msg*") { throw "missing _human_price_msg" }
$ta = Get-Content "web\token-admin.html" -Raw -Encoding UTF8
if ($ta -like "*预警明细（实时）*") { throw "duplicate alert detail still present" }
if ($ta -notlike "*售价盖不住成本*") { throw "missing human alert label" }
# 若本机误改 model_router 与 origin 不一致，恢复仓库版（L1 默认 MiMo）；Flash 实际通道仍看 system_flags
git diff --quiet -- api/model_router.py
if ($LASTEXITCODE -ne 0) {
  Write-Host "WARN: api/model_router.py dirty on 04 → checkout to match origin" -ForegroundColor Yellow
  git checkout -- api/model_router.py
}
$openSite = "C:\sites\open.ai24x.com"
if (Test-Path $openSite) {
  robocopy "$work\p\open\web" $openSite /E /NFL /NDL /NJH /NJS /nc /ns /np
  if ($LASTEXITCODE -ge 8) { throw "open robocopy failed $LASTEXITCODE" }
}
Restart-Service AI24X-core -Force
Start-Sleep -Seconds 10
$ph = Invoke-RestMethod -UseBasicParsing -Uri "http://127.0.0.1:8002/health" -TimeoutSec 20
Write-Host ("health.commit=" + $ph.commit)
git merge-base --is-ancestor $EXP $ph.commit
if ($LASTEXITCODE -ne 0) { throw "health.commit missing $EXP" }
Write-Host ("DONE EXP=$EXP HEAD=$HEAD health=$($ph.commit)") -ForegroundColor Green
# ✅ 04更新完成｜预警可读降噪｜EXP=189f9deee806 HEAD=<HEAD> health=<commit>｜公网验收通过
