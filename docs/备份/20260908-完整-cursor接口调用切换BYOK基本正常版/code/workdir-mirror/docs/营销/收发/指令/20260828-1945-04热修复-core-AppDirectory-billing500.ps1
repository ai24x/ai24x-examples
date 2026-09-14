$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "6ea0c61"
$NSSM = "C:\Program Files\nssm\nssm.exe"
$coreApi = Join-Path $work "api"
Set-Location $work

Write-Host "== 1. fetch + pull ==" -ForegroundColor Cyan
git fetch origin
git pull --ff-only origin master
$HEAD = (git rev-parse --short=12 HEAD).Trim()
Write-Host "HEAD=$HEAD"

Write-Host "== 2. fix AI24X-core AppDirectory (was E:\ clone, deploy uses C:\ai24x01) ==" -ForegroundColor Cyan
if (-not (Test-Path $NSSM)) { throw "nssm not found at $NSSM" }
if (-not (Test-Path (Join-Path $coreApi "billing_money.py"))) { throw "C:\ai24x01\api\billing_money.py missing" }
$cur = (& $NSSM get AI24X-core AppDirectory 2>$null | Out-String).Trim()
Write-Host "current AppDirectory=$cur"
if ($cur -ne $coreApi) {
  & $NSSM set AI24X-core AppDirectory $coreApi | Out-Null
  Write-Host "set AppDirectory -> $coreApi" -ForegroundColor Yellow
}
$cur2 = (& $NSSM get AI24X-core AppDirectory 2>$null | Out-String).Trim()
if ($cur2 -ne $coreApi) { throw "AppDirectory still $cur2" }

Write-Host "== 3. restart AI24X-core ==" -ForegroundColor Cyan
Restart-Service AI24X-core -ErrorAction Stop
Start-Sleep -Seconds 12

Write-Host "== 4. verify billing + health ==" -ForegroundColor Cyan
$h = Invoke-RestMethod -UseBasicParsing -Uri "https://api.ai24x.com/health" -Headers @{ Accept = "application/json" }
$plans = Invoke-RestMethod -UseBasicParsing -Uri "https://api.ai24x.com/v1/billing/plans" -Headers @{ Accept = "application/json" }
$pc = @($plans.plans).Count
if ($pc -lt 1) { throw "billing/plans empty" }
Write-Host ("billing/plans OK count=" + $pc) -ForegroundColor Green
$products = Invoke-RestMethod -UseBasicParsing -Uri "https://api.ai24x.com/v1/billing/products" -Headers @{ Accept = "application/json" }
if (-not $products.products) { throw "billing/products empty" }
Write-Host "billing/products OK" -ForegroundColor Green

Write-Host ("DONE EXP=" + $EXP + " HEAD=" + $HEAD + " health=" + $h.commit + " AppDirectory=" + $coreApi) -ForegroundColor Green

# --- 04 openclaw: 指挥部飞书群发一条 ---
# ✅ 04热修复｜core指向C盘api｜billing/plans恢复200｜EXP=6ea0c61 HEAD=<HEAD> health=<commit>
