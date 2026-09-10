$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "b3d447f4863c"
Set-Location $work
git fetch origin
git pull --ff-only origin master
$HEAD = (git rev-parse --short=12 HEAD).Trim()
git merge-base --is-ancestor $EXP HEAD
if ($LASTEXITCODE -ne 0) { throw "HEAD missing $EXP" }

$tm = Get-Content "api\token_mvp_service.py" -Raw -Encoding UTF8
if ($tm -notlike "*_is_user_hidden_ledger*") { throw "missing _is_user_hidden_ledger" }
if ($tm -notlike "*hold_settle_refund:%*") { throw "missing hold_settle_refund hide filter" }
$ot = Get-Content "p\open\api\token_mvp_service.py" -Raw -Encoding UTF8
if ($ot -notlike "*_is_user_hidden_ledger*") { throw "open mirror missing hide helper" }
$cj = Get-Content "web\js\console.js" -Raw -Encoding UTF8
if ($cj -notlike "*hold_settle_refund*") { throw "console.js missing hold note humanize" }
$ch = Get-Content "web\console.html" -Raw -Encoding UTF8
if ($ch -notlike "*console.js?v=20260910c*") { throw "www console.js cache bump missing" }
$och = Get-Content "p\open\web\console.html" -Raw -Encoding UTF8
if ($och -notlike "*console.js?v=20260910c*") { throw "open console.js cache bump missing" }

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
$www = (Invoke-WebRequest -UseBasicParsing -Uri "https://www.ai24x.com/console.html" -TimeoutSec 25).Content
if ($www -notlike "*console.js?v=20260910c*") { throw "public console.html missing v=20260910c" }
Write-Host ("DONE EXP=$EXP HEAD=$HEAD health=$($ph.commit)") -ForegroundColor Green
# ✅ 04更新完成｜Transactions隐藏预扣流水｜EXP=b3d447f4863c HEAD=<HEAD> health=<commit>｜公网验收通过