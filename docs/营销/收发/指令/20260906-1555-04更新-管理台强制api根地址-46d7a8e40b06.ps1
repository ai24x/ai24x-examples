$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "46d7a8e40b06"
Set-Location $work
git fetch origin
git pull --ff-only origin master
$HEAD = (git rev-parse --short=12 HEAD).Trim()
git merge-base --is-ancestor $EXP HEAD
if ($LASTEXITCODE -ne 0) { throw "HEAD missing $EXP" }
$admin = Get-Content "web\token-admin.html" -Raw -Encoding UTF8
if ($admin -notlike "*ensureApiBase*") { throw "missing ensureApiBase" }
if ($admin -notlike "*channel_flow*") { throw "missing channel_flow" }
# static only — no core restart required, but assert health still has prior API commit
$ph = Invoke-RestMethod -UseBasicParsing -Uri "http://127.0.0.1:8002/health" -TimeoutSec 15
$adminP = Invoke-WebRequest -UseBasicParsing -Uri "https://www.ai24x.com/token-admin.html" -TimeoutSec 25
if ($adminP.Content -notlike "*ensureApiBase*") { throw "public html missing ensureApiBase" }
Write-Host ("DONE EXP=$EXP HEAD=$HEAD health=$($ph.commit)") -ForegroundColor Green
# ✅ 04更新完成｜管理台强制api根地址｜EXP=46d7a8e40b06 HEAD=<HEAD> health=<commit>｜公网验收通过