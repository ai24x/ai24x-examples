$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"

Write-Host "== 1. backup overrides ==" -ForegroundColor Cyan
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$coreOv = Join-Path $work "api\data\token_plans_override.json"
$openOv = Join-Path $work "p\open\api\data\token_plans_override.json"
Copy-Item -LiteralPath $coreOv -Destination ($coreOv + ".bak-$stamp") -Force
Copy-Item -LiteralPath $openOv -Destination ($openOv + ".bak-$stamp") -Force
Write-Host ("backups: " + $coreOv + ".bak-$stamp")

Write-Host "== 2. patch Starter to \$0.1 ==" -ForegroundColor Cyan
$patchPy = Join-Path $work "api\_patch_starter_01.py"
Copy-Item -LiteralPath "C:\Users\Administrator\ops\20260827-patch-starter-01.py" -Destination $patchPy -Force
python $patchPy
Remove-Item -LiteralPath $patchPy -Force

Write-Host "== 3. restart core + open ==" -ForegroundColor Cyan
Restart-Service AI24X-core -ErrorAction Stop
Start-Sleep -Seconds 8
Restart-Service AI24X-open-api -ErrorAction Stop
Start-Sleep -Seconds 5

Write-Host "== 4. Dodo live sync (Starter price drift -> PATCH \$0.1) ==" -ForegroundColor Cyan
Push-Location "$work\api"
$env:PYTHONIOENCODING = "utf-8"
$syncOut = python -c "import asyncio, json; from pay_dodo_products import sync_dodo_products; r = asyncio.run(sync_dodo_products()); print(json.dumps(r, ensure_ascii=False))"
Pop-Location
$sync = $syncOut | ConvertFrom-Json
if (-not $sync) { throw "Dodo sync no output" }
Write-Host ("dodo mode=" + $sync.mode)
if ($sync.mode -ne "live") { throw "Dodo sync not live mode" }
if ($sync.summary.errors -gt 0) { throw ("Dodo sync errors: " + ($sync.items | ConvertTo-Json -Compress)) }
Write-Host ("dodo summary=" + (($sync.summary | ConvertTo-Json -Compress)))
$sync.items | Where-Object { $_.action -ne "unchanged" } | ForEach-Object { Write-Host ("  " + $_.product + " :: " + $_.plan_id + " :: " + $_.action) }

Write-Host "== 5. verify plans API (www + open) ==" -ForegroundColor Cyan
$wwwPlans = Invoke-RestMethod -UseBasicParsing -Uri "https://api.ai24x.com/v1/billing/plans" -Headers @{ Accept = "application/json" }
$wwwStarter = $wwwPlans.plans | Where-Object { $_.plan -eq "token_pack_10k" }
Write-Host ("www starter price_usd=" + $wwwStarter.price_usd)
if ([double]$wwwStarter.price_usd -ne 0.1) { throw "www starter price not 0.1" }
$openPlans = Invoke-RestMethod -UseBasicParsing -Uri "https://open.ai24x.com/v1/billing/plans" -Headers @{ Accept = "application/json" }
$openStarter = $openPlans.plans | Where-Object { $_.plan -eq "token_pack_10k" }
Write-Host ("open starter price_usd=" + $openStarter.price_usd)
if ([double]$openStarter.price_usd -ne 0.1) { throw "open starter price not 0.1" }

Write-Host "== 6. verify live Dodo product price (Starter = 10 cents) ==" -ForegroundColor Cyan
Push-Location "$work\api"
$probe = Join-Path $work "api\_probe_dodo_starter.py"
@'
import asyncio
import json
from pay_dodo_products import _get_products, _pay_cfg

async def main():
    cfg = _pay_cfg()
    products = await _get_products(cfg)
    for x in products:
        if str(x.get("product_id") or "") == "pdt_0Nm4miLZyMCVqx6jdyN0i":
            print(json.dumps({"name": x.get("name"), "price": x.get("price"), "description": (x.get("description") or "")[:120]}, ensure_ascii=False))
            return
    print("{}")

asyncio.run(main())
'@ | Out-File -FilePath $probe -Encoding utf8
$probeOut = python $probe
Pop-Location
Remove-Item -LiteralPath $probe -Force
Write-Host $probeOut
$prod = $probeOut | ConvertFrom-Json
$price = $prod.price
if ($price -is [string]) { $price = $price | ConvertFrom-Json }
$cents = if ($price -is [int]) { $price } else { [int]$price.price }
if ($cents -ne 10) { throw ("live Starter price cents=" + $cents + " expected 10") }

Write-Host "STARTER 0.1 LIVE DONE" -ForegroundColor Green
