$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "03031712879e"
Set-Location $work

Write-Host "== 1. fetch + pull ==" -ForegroundColor Cyan
git fetch origin
git pull --ff-only origin master
$HEAD = (git rev-parse --short=12 HEAD).Trim()
Write-Host "HEAD=$HEAD"
git merge-base --is-ancestor $EXP HEAD
if ($LASTEXITCODE -ne 0) { throw "HEAD missing $EXP" }

Write-Host "== 2. markers ==" -ForegroundColor Cyan
$byok = Get-Content "p\open\api\byok.py" -Raw -Encoding UTF8
if ($byok -notlike '*"group": "china"*') { throw "byok missing china group" }
$html = Get-Content "p\open\web\console.html" -Raw -Encoding UTF8
if ($html -notlike "*groupChina*") { throw "console missing groupChina" }
if ($html -notlike "*20260904b*") { throw "console missing ?v=20260904b" }
Write-Host "markers OK" -ForegroundColor Green

Write-Host "== 3. restart open-api ==" -ForegroundColor Cyan
Restart-Service AI24X-open-api -Force -ErrorAction Stop
Start-Sleep -Seconds 10

Write-Host "== 4. verify ==" -ForegroundColor Cyan
# open static often served from repo path under nginx; smoke API import
Set-Location "$work\p\open\api"
if (Test-Path ".\venv\Scripts\python.exe") {
  & .\venv\Scripts\python.exe -c "from byok import models_catalog; c=models_catalog(); assert any(p['group']=='china' for p in c['providers']); print('byok_groups_ok')"
} else {
  py -3 -c "import sys; sys.path.insert(0,'.'); from byok import models_catalog; c=models_catalog(); assert any(p['group']=='china' for p in c['providers']); print('byok_groups_ok')"
}
Set-Location $work

$h = Invoke-WebRequest -UseBasicParsing -Uri "https://open.ai24x.com/console.html" -TimeoutSec 20
if ($h.Content -notlike "*groupChina*" -and $h.Content -notlike "*中国名模*") { throw "public console missing BYOK groups" }
if ($h.Content -notlike "*20260904b*") { throw "public console missing locales/js bump" }

Write-Host ("DONE EXP=$EXP HEAD=$HEAD") -ForegroundColor Green
# ✅ 04更新完成｜BYOK名模分组｜EXP=03031712879e HEAD=<HEAD> health=n/a｜console optgroup+byok.py
