$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "a2c30f43b529"
Set-Location $work

Write-Host "== 1. fetch + pull ==" -ForegroundColor Cyan
git fetch origin
git pull --ff-only origin master
$HEAD = (git rev-parse --short=12 HEAD).Trim()
Write-Host "HEAD=$HEAD"
git merge-base --is-ancestor $EXP HEAD
if ($LASTEXITCODE -ne 0) { throw "HEAD missing $EXP" }

Write-Host "== 2. markers ==" -ForegroundColor Cyan
$oc = Get-Content "p\open\web\console.html" -Raw -Encoding UTF8
if ($oc -notlike "*console.js?v=20260905d*") { throw "open console.html missing console.js?v=20260905d" }
if ($oc -notlike "*base.css?v=20260905a*") { throw "open console.html missing base.css?v=20260905a" }
if ($oc -notlike "*locales.js?v=20260905d*") { throw "open console.html missing locales.js?v=20260905d" }
$oj = Get-Content "p\open\web\js\console.js" -Raw -Encoding UTF8
if ($oj -notlike "*btn-byok-on*") { throw "console.js missing btn-byok-on" }
if ($oj -notlike "*byok-key-state*") { throw "console.js missing byok-key-state" }
$css = Get-Content "p\open\web\css\base.css" -Raw -Encoding UTF8
if ($css -notlike "*btn-byok-off*") { throw "base.css missing btn-byok-off" }
Write-Host "markers OK" -ForegroundColor Green

Write-Host "== 3. restart ==" -ForegroundColor Cyan
Restart-Service AI24X-open-api -Force -ErrorAction Stop
Restart-Service AI24X-core -Force -ErrorAction Stop
Start-Sleep -Seconds 12

Write-Host "== 4. verify ==" -ForegroundColor Cyan
$ph = Invoke-RestMethod -UseBasicParsing -Uri "http://127.0.0.1:8002/health" -TimeoutSec 15
git merge-base --is-ancestor $EXP $ph.commit
if ($LASTEXITCODE -ne 0) { throw ("core health commit mismatch " + $ph.commit) }

$pubOpen = (Invoke-WebRequest -UseBasicParsing -Uri ("https://open.ai24x.com/console.html?x=" + $HEAD) -TimeoutSec 25).Content
if ($pubOpen -notlike "*console.js?v=20260905d*") { throw "public open console.js version stale" }
if ($pubOpen -notlike "*base.css?v=20260905a*") { throw "public open base.css version stale" }

Write-Host ("DONE EXP=$EXP HEAD=$HEAD health=$($ph.commit)") -ForegroundColor Green
# ✅ 04更新完成｜BYOK On/Off状态按钮｜EXP=a2c30f43b529 HEAD=<HEAD> health=<commit>｜公网验收通过
