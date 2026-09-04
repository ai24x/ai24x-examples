$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "f2300e677d84"
Set-Location $work
git fetch origin
git pull --ff-only origin master
$HEAD = (git rev-parse --short=12 HEAD).Trim()
git merge-base --is-ancestor $EXP HEAD
if ($LASTEXITCODE -ne 0) { throw "HEAD missing $EXP" }
$html = Get-Content "p\open\web\console.html" -Raw -Encoding UTF8
if ($html -notlike "*Google Gemini*") { throw "missing Gemini" }
if ($html -notlike "*MiniMax*") { throw "missing MiniMax" }
if ($html -notlike "*20260904c*") { throw "missing ?v=20260904c" }
if ($html -like "*groupAdvanced*") { throw "advanced group should be gone" }
Restart-Service AI24X-open-api -Force -ErrorAction Stop
Start-Sleep -Seconds 10
Set-Location "$work\p\open\api"
if (Test-Path ".\venv\Scripts\python.exe") {
  & .\venv\Scripts\python.exe -c "from byok import models_catalog; c=models_catalog(); assert 'gemini' in [p['id'] for p in c['providers_ui']]; assert 'openrouter' not in [p['id'] for p in c['providers_ui']]; print('byok_rank_ok')"
} else {
  py -3 -c "import sys; sys.path.insert(0,'.'); from byok import models_catalog; c=models_catalog(); assert 'gemini' in [p['id'] for p in c['providers_ui']]; print('byok_rank_ok')"
}
Set-Location $work
$h = Invoke-WebRequest -UseBasicParsing -Uri "https://open.ai24x.com/console.html" -TimeoutSec 20
if ($h.Content -notlike "*20260904c*") { throw "public console cache bump missing" }
Write-Host ("DONE EXP=$EXP HEAD=$HEAD") -ForegroundColor Green
# ✅ 04更新完成｜BYOK名模排序去聚合｜EXP=f2300e677d84 HEAD=<HEAD> health=n/a｜Gemini+MiniMax+MiMo
