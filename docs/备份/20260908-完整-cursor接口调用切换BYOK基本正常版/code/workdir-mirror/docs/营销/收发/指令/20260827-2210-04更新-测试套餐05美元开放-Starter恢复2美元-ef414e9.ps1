$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "ef414e9"
Set-Location $work

Write-Host "== 1. fetch + pull ==" -ForegroundColor Cyan
git fetch origin
git pull --ff-only origin master
$HEAD = (git rev-parse --short=12 HEAD).Trim()
Write-Host "HEAD=$HEAD"
git merge-base --is-ancestor $EXP HEAD
if ($LASTEXITCODE -ne 0) { throw "HEAD missing target $EXP" }

Write-Host "== 2. marker checks ==" -ForegroundColor Cyan
$core = Get-Content (Join-Path $work "api\token_plans.py") -Raw -Encoding UTF8
if ($core -notlike "*`"price_usd`": 0.5*") { throw "core token_plans missing 0.5 test pack" }
if ($core -notlike "*`"enabled`": True*") { throw "core token_plans test pack not enabled default" }
$openTp = Get-Content (Join-Path $work "p\open\api\token_plans.py") -Raw -Encoding UTF8
if ($openTp -notlike "*`"price_usd`": 0.5*") { throw "open token_plans missing 0.5 test pack" }
$wwwApi = Get-Content (Join-Path $work "web\js\api.js") -Raw -Encoding UTF8
if ($wwwApi -like "*¥*") { throw "www api.js still has CNY display" }
if ($wwwApi -notlike "*`"$`" + p.price_usd*") { throw "www api.js missing USD label" }
$wwwConsole = Get-Content (Join-Path $work "web\js\console.js") -Raw -Encoding UTF8
if ($wwwConsole -like "*¥*") { throw "www console.js still has CNY display" }
$wwwC = Get-Content (Join-Path $work "web\console.html") -Raw -Encoding UTF8
if ($wwwC -notlike "*api.js?v=20260827c*" -or $wwwC -notlike "*console.js?v=20260827c*") { throw "www version not 20260827c" }
$openC = Get-Content (Join-Path $work "p\open\web\console.html") -Raw -Encoding UTF8
if ($openC -notlike "*api.js?v=20260827c*" -or $openC -notlike "*console.js?v=20260827c*") { throw "open version not 20260827c" }
Write-Host "markers OK" -ForegroundColor Green

Write-Host "== 3. update prod overrides (Starter back to `$2, Test Pack `$0.5 enabled) ==" -ForegroundColor Cyan
$ovPaths = @(
  (Join-Path $work "api\data\token_plans_override.json"),
  (Join-Path $work "p\open\api\data\token_plans_override.json")
)
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
foreach ($p in $ovPaths) {
  Copy-Item -LiteralPath $p -Destination ($p + ".bak-" + $stamp) -Force
  $o = Get-Content -LiteralPath $p -Raw -Encoding UTF8 | ConvertFrom-Json
  $s = $o.plans.token_pack_10k
  if (-not $s) { throw ("missing token_pack_10k in " + $p) }
  $s.price_usd = 2.0
  $s.price_fen = 1440
  $s.enabled = $true
  $s.note_en = "Starter: `$2 for 1M credits (~thousands of flash calls). Credits only-no named-model access; choose Scale to name models. Valid 12 months."
  $s.note_zh = "小额体验包：`$2 试水 100 万 token（约数千次 flash 调用）。仅预充额度，不含名模资格；要点名请选 Scale。额度 12 个月有效。"
  $t = [PSCustomObject]@{
    price_usd = 0.5
    price_fen = 360
    credit_tokens = 1000000
    validity_days = 365
    enabled = $true
    note_zh = "小额支付测试包：`$0.5 试水 100 万 credits（约数千次 flash 调用）。默认开放；管理员可在后台价表关闭。仅用于支付通道小额实测。额度 12 个月有效。"
    note_en = "Small-amount payment test pack: `$0.5 for 1M credits (~thousands of flash calls). Enabled by default; admins can disable it from the dashboard. For payment-channel testing. Valid 12 months."
  }
  $o.plans | Add-Member -NotePropertyName token_test_01 -NotePropertyValue $t -Force
  $json = $o | ConvertTo-Json -Depth 8
  [System.IO.File]::WriteAllText($p, $json, (New-Object System.Text.UTF8Encoding($false)))
  Write-Host ("updated " + $p)
}

Write-Host "== 4. restart core (load new plans) ==" -ForegroundColor Cyan
Restart-Service AI24X-core -ErrorAction Stop
Start-Sleep -Seconds 8

Write-Host "== 5. Dodo live sync (Starter `$2 PATCH + Test Pack `$0.5 create/update) ==" -ForegroundColor Cyan
Push-Location (Join-Path $work "api")
$env:PYTHONIOENCODING = "utf-8"
$syncOut = python -c "import asyncio, json; from pay_dodo_products import sync_dodo_products; print(json.dumps(asyncio.run(sync_dodo_products()), ensure_ascii=False))"
Pop-Location
Write-Host ("sync: " + $syncOut)
$sync = $syncOut | ConvertFrom-Json
if (-not $sync) { throw "dodo sync returned empty" }

Write-Host "== 6. verify overrides got product id + restart open ==" -ForegroundColor Cyan
$coreOv = Get-Content (Join-Path $work "api\data\token_plans_override.json") -Raw -Encoding UTF8 | ConvertFrom-Json
$openOv = Get-Content (Join-Path $work "p\open\api\data\token_plans_override.json") -Raw -Encoding UTF8 | ConvertFrom-Json
if (-not $coreOv.plans.token_test_01.dodo_product_id) { throw "core test pack missing dodo_product_id after sync" }
if (-not $openOv.plans.token_test_01.dodo_product_id) { throw "open test pack missing dodo_product_id after mirror" }
Write-Host ("test pack dodo id: " + $coreOv.plans.token_test_01.dodo_product_id)
Restart-Service AI24X-open-api -ErrorAction Stop
Start-Sleep -Seconds 5

Write-Host "== 7. public verify ==" -ForegroundColor Cyan
$h = Invoke-RestMethod -UseBasicParsing -Uri "https://api.ai24x.com/health" -Headers @{ Accept = "application/json" }
$okCommit = $false
try { git merge-base --is-ancestor $EXP $h.commit; $okCommit = ($LASTEXITCODE -eq 0) } catch { $okCommit = $false }
if (-not $okCommit) { throw ("core commit mismatch: " + $h.commit) }
$wwwPlans = Invoke-RestMethod -UseBasicParsing -Uri "https://www.ai24x.com/v1/billing/plans" -Headers @{ Accept = "application/json" }
$starter = $wwwPlans.plans | Where-Object { $_.plan -eq "token_pack_10k" } | Select-Object -First 1
$test = $wwwPlans.plans | Where-Object { $_.plan -eq "token_test_01" } | Select-Object -First 1
if (-not $starter -or [double]$starter.price_usd -ne 2.0) { throw "www starter not `$2" }
if (-not $test -or [double]$test.price_usd -ne 0.5) { throw "www test pack not visible at `$0.5" }
$openPlans = Invoke-RestMethod -UseBasicParsing -Uri "https://open.ai24x.com/v1/billing/plans" -Headers @{ Accept = "application/json" }
$oStarter = $openPlans.plans | Where-Object { $_.plan -eq "token_pack_10k" } | Select-Object -First 1
$oTest = $openPlans.plans | Where-Object { $_.plan -eq "token_test_01" } | Select-Object -First 1
if (-not $oStarter -or [double]$oStarter.price_usd -ne 2.0) { throw "open starter not `$2" }
if (-not $oTest -or [double]$oTest.price_usd -ne 0.5) { throw "open test pack not visible at `$0.5" }
$wwwBody = (Invoke-WebRequest -UseBasicParsing -Uri "https://www.ai24x.com/console.html?lang=zh" -Headers @{ Accept = "text/html" }).Content
if ($wwwBody -like "*¥*") { throw "public www console.html still has CNY" }
if ($wwwBody -notlike "*api.js?v=20260827c*" -or $wwwBody -notlike "*console.js?v=20260827c*") { throw "public www version missing 20260827c" }
$openBody = (Invoke-WebRequest -UseBasicParsing -Uri "https://open.ai24x.com/console.html?lang=zh" -Headers @{ Accept = "text/html" }).Content
if ($openBody -notlike "*api.js?v=20260827c*" -or $openBody -notlike "*console.js?v=20260827c*") { throw "public open version missing 20260827c" }
Write-Host "public verify OK" -ForegroundColor Green

Write-Host "TEST PACK 0.5 + STARTER 2 + USD-ZH DEPLOY DONE" -ForegroundColor Green
Write-Host ("DONE EXP=" + $EXP + " HEAD=" + $HEAD) -ForegroundColor Green
