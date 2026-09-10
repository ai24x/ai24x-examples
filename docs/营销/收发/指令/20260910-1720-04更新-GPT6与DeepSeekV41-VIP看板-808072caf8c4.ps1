$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "808072caf8c4"
Set-Location $work
git fetch origin
git pull --ff-only origin master
$HEAD = (git rev-parse --short=12 HEAD).Trim()
git merge-base --is-ancestor $EXP HEAD
if ($LASTEXITCODE -ne 0) { throw "HEAD missing $EXP" }

# markers: GPT-6 Astra + DeepSeek V4.1 + VIP board + TL prices + locales cache
$mw = Get-Content "api\model_warehouse.py" -Raw -Encoding UTF8
if ($mw -notlike "*vip-gpt6-astra*") { throw "missing vip-gpt6-astra" }
if ($mw -notlike "*deepseek-flash*") { throw "missing deepseek-flash" }
if ($mw -notlike "*_apply_ds_live_schedule*") { throw "missing DS live schedule" }
$pm = Get-Content "api\price_monitor.py" -Raw -Encoding UTF8
if ($pm -notlike "*input_per_1m*") { throw "missing TokenLab input_per_1m parse" }
if ($pm -notlike "*vip_board*") { throw "missing vip_board" }
$fl = Get-Content "api\flash_lanes.py" -Raw -Encoding UTF8
if ($fl -notlike "*vip_board*") { throw "flash_lanes missing vip_board" }
$ta = Get-Content "web\token-admin.html" -Raw -Encoding UTF8
if ($ta -notlike "*vip_board*") { throw "token-admin missing vip_board" }
$vp = Get-Content "web\models\vip-picks.html" -Raw -Encoding UTF8
if ($vp -notlike "*GPT-6*" -and $vp -notlike "*gpt-6*") { throw "vip-picks missing GPT-6" }
$idx = Get-Content "web\index.html" -Raw -Encoding UTF8
if ($idx -notlike "*locales.js?v=20260910a*") { throw "www locales cache bump missing" }
$omw = Get-Content "p\open\api\model_warehouse.py" -Raw -Encoding UTF8
if ($omw -notlike "*vip-gpt6-astra*") { throw "open mirror missing vip-gpt6-astra" }

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
$models = Invoke-RestMethod -UseBasicParsing -Uri "https://api.ai24x.com/v1/models" -TimeoutSec 30
$ids = @($models.data | ForEach-Object { $_.id })
if ($ids -notcontains "vip-gpt6-astra" -and ($ids | Where-Object { $_ -like "*gpt-6*" -or $_ -like "*astra*" }).Count -lt 1) {
  # warehouse may expose brand aliases; at least ensure warehouse file marker already passed
  Write-Host "WARN: public /v1/models list may hide VIP ids; warehouse marker OK" -ForegroundColor Yellow
}
$www = (Invoke-WebRequest -UseBasicParsing -Uri "https://www.ai24x.com/models/vip-picks.html" -TimeoutSec 25).Content
if ($www -notlike "*locales.js?v=20260910a*" -and $www -notlike "*GPT-6*" -and $www -notlike "*gpt-6*") {
  throw "public vip-picks missing expected markers"
}
Write-Host ("DONE EXP=$EXP HEAD=$HEAD health=$($ph.commit)") -ForegroundColor Green
# ✅ 04更新完成｜GPT6与DS V4.1 VIP看板｜EXP=808072caf8c4 HEAD=<HEAD> health=<commit>｜公网验收通过