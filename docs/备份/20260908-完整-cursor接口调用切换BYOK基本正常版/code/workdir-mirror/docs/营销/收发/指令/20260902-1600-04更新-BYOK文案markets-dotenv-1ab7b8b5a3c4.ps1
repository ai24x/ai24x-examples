$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "1ab7b8b5a3c4"
Set-Location $work

Write-Host "== 1. fetch + pull (origin only) ==" -ForegroundColor Cyan
git fetch origin
git pull --ff-only origin master
$HEAD = (git rev-parse --short=12 HEAD).Trim()
Write-Host "HEAD=$HEAD"
git merge-base --is-ancestor $EXP HEAD
if ($LASTEXITCODE -ne 0) { throw "HEAD missing target $EXP" }

Write-Host "== 2. marker checks ==" -ForegroundColor Cyan
$byok = Get-Content (Join-Path $work "p\open\api\byok.py") -Raw -Encoding UTF8
$mkMain = Get-Content (Join-Path $work "p\markets\api\server\app\main.py") -Raw -Encoding UTF8
if ($byok -notlike '*Gateway service fee only*') { throw "byok.py missing EN service_fee_note" }
if ($mkMain -notlike '*load_dotenv*') { throw "markets main missing load_dotenv bootstrap" }
Write-Host "markers OK" -ForegroundColor Green

Write-Host "== 3. restart open + markets + core ==" -ForegroundColor Cyan
Restart-Service AI24X-open-api -ErrorAction Stop
Restart-Service AI24X-markets-api -ErrorAction Stop
Restart-Service AI24X-core -ErrorAction Stop
Start-Sleep -Seconds 14

Write-Host "== 4. public verify ==" -ForegroundColor Cyan
$ph = Invoke-RestMethod -UseBasicParsing -Uri "https://api.ai24x.com/health"
git merge-base --is-ancestor $EXP $ph.commit
if ($LASTEXITCODE -ne 0) { throw ("public core commit mismatch: " + $ph.commit) }
$oh = Invoke-RestMethod -UseBasicParsing -Uri "https://open.ai24x.com/health"
if ($oh.commit) {
  git merge-base --is-ancestor $EXP $oh.commit
  if ($LASTEXITCODE -ne 0) { throw ("open commit mismatch: " + $oh.commit) }
}
$mh = Invoke-RestMethod -UseBasicParsing -Uri "http://127.0.0.1:18012/health" -TimeoutSec 15
if (-not $mh) { throw "markets loopback health failed" }
Write-Host "public verify OK" -ForegroundColor Green

Write-Host ("DONE EXP=" + $EXP + " HEAD=" + $HEAD + " health=" + $ph.commit) -ForegroundColor Green
# ✅ 04更新完成｜BYOK文案+markets dotenv｜EXP=1ab7b8b5a3c4 HEAD=<HEAD> health=<commit>｜open/markets/core已重启验收通过
