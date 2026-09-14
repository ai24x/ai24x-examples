$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "928a89ae9601"
# 含：主打一键切通道安全优化 + BYOK 名模排序/去聚合（f2300e6）
Set-Location $work

Write-Host "== 1. fetch + pull ==" -ForegroundColor Cyan
git fetch origin
git pull --ff-only origin master
$HEAD = (git rev-parse --short=12 HEAD).Trim()
Write-Host "HEAD=$HEAD"
git merge-base --is-ancestor $EXP HEAD
if ($LASTEXITCODE -ne 0) { throw "HEAD missing $EXP" }
# 关键代码点不得漏
git merge-base --is-ancestor "f2300e677d84" HEAD
if ($LASTEXITCODE -ne 0) { throw "HEAD missing BYOK commit f2300e677d84" }
git merge-base --is-ancestor "95e3e2996b59" HEAD
if ($LASTEXITCODE -ne 0) { throw "HEAD missing hero-safety 95e3e2996b59" }

Write-Host "== 2. markers ==" -ForegroundColor Cyan
$pm = Get-Content "api\price_monitor.py" -Raw -Encoding UTF8
if ($pm -notlike "*def apply_hero_pick*") { throw "missing apply_hero_pick" }
if ($pm -notlike "*def list_hero_ops_alerts*") { throw "missing list_hero_ops_alerts" }
$ta = Get-Content "web\token-admin.html" -Raw -Encoding UTF8
if ($ta -notlike "*btn-hero-apply*") { throw "token-admin missing apply btn" }
if ($ta -notlike "*pmHeroPending*") { throw "token-admin missing pending strip" }
$byok = Get-Content "p\open\api\byok.py" -Raw -Encoding UTF8
if ($byok -notlike "*gemini*") { throw "byok missing gemini" }
if ($byok -notlike "*minimax*") { throw "byok missing minimax" }
if ($byok -notlike "*ui_hidden*") { throw "byok missing ui_hidden aggregators" }
if ($byok -notlike "*mimo*") { throw "byok missing mimo" }
$html = Get-Content "p\open\web\console.html" -Raw -Encoding UTF8
if ($html -notlike "*Google Gemini*") { throw "console missing Gemini" }
if ($html -notlike "*MiniMax*") { throw "console missing MiniMax" }
if ($html -notlike "*20260904c*") { throw "console missing ?v=20260904c" }
if ($html -like "*groupAdvanced*") { throw "advanced aggregator group should be gone" }
Write-Host "markers OK" -ForegroundColor Green

Write-Host "== 3. restart core + open ==" -ForegroundColor Cyan
Restart-Service AI24X-core -Force -ErrorAction Stop
Restart-Service AI24X-open-api -Force -ErrorAction Stop
Start-Sleep -Seconds 14

Write-Host "== 4. verify ==" -ForegroundColor Cyan
$ph = Invoke-RestMethod -UseBasicParsing -Uri "http://127.0.0.1:8002/health" -TimeoutSec 15
git merge-base --is-ancestor $EXP $ph.commit
if ($LASTEXITCODE -ne 0) { throw ("core health commit mismatch " + $ph.commit) }

Set-Location "$work\api"
& .\venv\Scripts\python.exe -c "from price_monitor import snapshot; s=snapshot(); assert 'pending_alerts' in s.get('hero_picks',{}); print('hero_ok')"
Set-Location "$work\p\open\api"
if (Test-Path ".\venv\Scripts\python.exe") {
  & .\venv\Scripts\python.exe -c "from byok import models_catalog; c=models_catalog(); u=[p['id'] for p in c['providers_ui']]; assert 'gemini' in u and 'minimax' in u and 'openrouter' not in u; print('byok_ok', u[:6])"
} else {
  py -3 -c "import sys; sys.path.insert(0,'.'); from byok import models_catalog; c=models_catalog(); u=[p['id'] for p in c['providers_ui']]; assert 'gemini' in u and 'openrouter' not in u; print('byok_ok')"
}
Set-Location $work

$taW = Invoke-WebRequest -UseBasicParsing -Uri "https://www.ai24x.com/token-admin.html" -TimeoutSec 20
if ($taW.Content -notlike "*pmHeroPending*") { throw "public token-admin missing pmHeroPending" }
$oc = Invoke-WebRequest -UseBasicParsing -Uri "https://open.ai24x.com/console.html" -TimeoutSec 20
if ($oc.Content -notlike "*20260904c*") { throw "public open console missing ?v=20260904c" }
if ($oc.Content -notlike "*Google Gemini*") { throw "public open console missing Gemini" }

Write-Host ("DONE EXP=$EXP HEAD=$HEAD health=$($ph.commit)") -ForegroundColor Green
# ✅ 04更新完成｜hero+BYOK全量同步｜EXP=d03d1a8a866e HEAD=<HEAD> health=<commit>｜core+open双重启验收通过
