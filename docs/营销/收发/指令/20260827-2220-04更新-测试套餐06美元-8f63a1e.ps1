$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "8f63a1e"
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
if ($core -notlike "*`"price_usd`": 0.6*") { throw "core token_plans missing 0.6 test pack" }
$openTp = Get-Content (Join-Path $work "p\open\api\token_plans.py") -Raw -Encoding UTF8
if ($openTp -notlike "*`"price_usd`": 0.6*") { throw "open token_plans missing 0.6 test pack" }
Write-Host "markers OK" -ForegroundColor Green

Write-Host "== 3. update prod overrides (Test Pack .5 -> .6, Starter stays `$2) ==" -ForegroundColor Cyan
$ovPaths = @(
  (Join-Path $work "api\data\token_plans_override.json"),
  (Join-Path $work "p\open\api\data\token_plans_override.json")
)
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
foreach ($p in $ovPaths) {
  Copy-Item -LiteralPath $p -Destination ($p + ".bak-" + $stamp) -Force
  $o = Get-Content -LiteralPath $p -Raw -Encoding UTF8 | ConvertFrom-Json
  $s = $o.plans.token_pack_10k
  if (-not $s -or [double]$s.price_usd -ne 2.0) { throw ("starter not 2.0 in " + $p) }
  $t = $o.plans.token_test_01
  if (-not $t) { throw ("missing token_test_01 in " + $p) }
  $t.price_usd = 0.6
  $t.price_fen = 432
  $t.enabled = $true
  $t.note_zh = "小额支付测试包：`$0.6 试水 100 万 credits（约数千次 flash 调用）。默认开放；管理员可在后台价表关闭。仅用于支付通道小额实测。额度 12 个月有效。"
  $t.note_en = "Small-amount payment test pack: `$0.6 for 1M credits (~thousands of flash calls). Enabled by default; admins can disable it from the dashboard. For payment-channel testing. Valid 12 months."
  $json = $o | ConvertTo-Json -Depth 8
  [System.IO.File]::WriteAllText($p, $json, (New-Object System.Text.UTF8Encoding($false)))
  Write-Host ("updated " + $p)
}

Write-Host "== 4. restart core (load new plans) ==" -ForegroundColor Cyan
Restart-Service AI24X-core -ErrorAction Stop
Start-Sleep -Seconds 8

Write-Host "== 5. Dodo live sync (Test Pack PATCH to 60 cents) ==" -ForegroundColor Cyan
Push-Location (Join-Path $work "api")
$env:PYTHONIOENCODING = "utf-8"
$syncOut = python -c "import asyncio, json; from pay_dodo_products import sync_dodo_products; print(json.dumps(asyncio.run(sync_dodo_products()), ensure_ascii=False))"
Pop-Location
Write-Host ("sync: " + $syncOut)
$sync = $syncOut | ConvertFrom-Json
if (-not $sync) { throw "dodo sync returned empty" }

Write-Host "== 6. verify overrides + restart open ==" -ForegroundColor Cyan
$coreOv = Get-Content (Join-Path $work "api\data\token_plans_override.json") -Raw -Encoding UTF8 | ConvertFrom-Json
$openOv = Get-Content (Join-Path $work "p\open\api\data\token_plans_override.json") -Raw -Encoding UTF8 | ConvertFrom-Json
if ([double]$coreOv.plans.token_test_01.price_usd -ne 0.6) { throw "core test pack price wrong" }
if (-not $coreOv.plans.token_test_01.dodo_product_id) { throw "core test pack missing dodo_product_id" }
if ([double]$openOv.plans.token_test_01.price_usd -ne 0.6) { throw "open test pack price wrong" }
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
if (-not $test -or [double]$test.price_usd -ne 0.6) { throw "www test pack not `$0.6" }
$openPlans = Invoke-RestMethod -UseBasicParsing -Uri "https://open.ai24x.com/v1/billing/plans" -Headers @{ Accept = "application/json" }
$oTest = $openPlans.plans | Where-Object { $_.plan -eq "token_test_01" } | Select-Object -First 1
if (-not $oTest -or [double]$oTest.price_usd -ne 0.6) { throw "open test pack not `$0.6" }
Write-Host "public verify OK" -ForegroundColor Green

Write-Host "TEST PACK 0.6 + STARTER 2 DEPLOY DONE" -ForegroundColor Green
Write-Host ("DONE EXP=" + $EXP + " HEAD=" + $HEAD) -ForegroundColor Green
