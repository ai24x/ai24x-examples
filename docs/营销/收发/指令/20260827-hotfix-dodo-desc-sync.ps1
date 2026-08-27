$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "eb2d736"
Set-Location $work

Write-Host "== 1. fetch + pull ==" -ForegroundColor Cyan
git fetch origin
git pull --ff-only origin master
if ($LASTEXITCODE -ne 0) {
  git fetch gitee
  git pull --ff-only gitee master
}
$HEAD = (git rev-parse --short=12 HEAD).Trim()
Write-Host "HEAD=$HEAD"
git merge-base --is-ancestor $EXP HEAD
if ($LASTEXITCODE -ne 0) { throw "HEAD missing target $EXP" }

Write-Host "== 2. marker check ==" -ForegroundColor Cyan
$raw = Get-Content (Join-Path $work "api\pay_dodo_products.py") -Raw -Encoding UTF8
if ($raw -notlike "*cur_desc == description*") { throw "missing desc comparison marker" }
Write-Host "marker OK" -ForegroundColor Green

Write-Host "== 3. cleanup probe ==" -ForegroundColor Cyan
$probe = Join-Path $work "api\_probe_dodo_live_names.py"
if (Test-Path $probe) { Remove-Item -LiteralPath $probe -Force }

Write-Host "== 4. restart AI24X-core ==" -ForegroundColor Cyan
Restart-Service AI24X-core -ErrorAction Stop
Start-Sleep -Seconds 8
$h = Invoke-RestMethod -UseBasicParsing -Uri "https://api.ai24x.com/health" -Headers @{ Accept = "application/json" }
Write-Host ("health commit=" + $h.commit)

Write-Host "== 5. Dodo live sync (direct python) ==" -ForegroundColor Cyan
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

Write-Host "== 6. verify live markets desc ==" -ForegroundColor Cyan
Push-Location "$work\api"
$probe2 = Join-Path $work "api\_probe_markets_desc.py"
@'
import asyncio
import json
from pay_dodo_products import _get_products, _pay_cfg

async def main():
    cfg = _pay_cfg()
    products = await _get_products(cfg)
    rows = []
    for x in products:
        name = str(x.get("name") or "")
        if name.startswith("AI24X Markets Pro"):
            rows.append(
                {
                    "name": name,
                    "desc_ok": ("not investment advice" in (x.get("description") or "")),
                }
            )
    print(json.dumps(rows, ensure_ascii=False))

asyncio.run(main())
'@ | Out-File -FilePath $probe2 -Encoding utf8
$probeOut = python $probe2
Pop-Location
Remove-Item -LiteralPath $probe2 -Force
Write-Host $probeOut
$rows = $probeOut | ConvertFrom-Json
foreach ($r in $rows) {
  if (-not $r.desc_ok) { throw ("markets desc missing compliance clause: " + $r.name) }
}

Write-Host "HOTFIX DONE" -ForegroundColor Green
Write-Host ("DONE EXP=" + $EXP + " HEAD=" + $HEAD) -ForegroundColor Green
