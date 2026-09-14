$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "2a7bcc4"
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
if ($core -notlike "*token_test_01*") { throw "core token_plans missing token_test_01" }
if ($core -notlike "*_OPEN_OVERRIDE_PATH*") { throw "core token_plans missing open mirror" }
$open = Get-Content (Join-Path $work "p\open\api\token_plans.py") -Raw -Encoding UTF8
if ($open -notlike "*token_test_01*") { throw "open token_plans missing token_test_01" }
Write-Host "markers OK" -ForegroundColor Green

Write-Host "== 3. restart core + open ==" -ForegroundColor Cyan
Restart-Service AI24X-core -ErrorAction Stop
Start-Sleep -Seconds 8
Restart-Service AI24X-open-api -ErrorAction Stop
Start-Sleep -Seconds 5

Write-Host "== 4. verify ==" -ForegroundColor Cyan
Push-Location "$work\api"
$env:PYTHONIOENCODING = "utf-8"
$coreCheck = python -c "import json; from token_plans import resolved_plans, list_public_plans; p = resolved_plans().get('token_test_01'); print(json.dumps({'defined': bool(p), 'enabled': bool(p and p.get('enabled')), 'price_usd': (p or {}).get('price_usd'), 'public': [x.get('plan') for x in list_public_plans() if x.get('plan') == 'token_test_01']}))"
Pop-Location
Write-Host ("core check: " + $coreCheck)
$coreObj = $coreCheck | ConvertFrom-Json
if (-not $coreObj.defined -or $coreObj.enabled) { throw "core test pack not defined/disabled as expected" }

$wwwPlans = Invoke-RestMethod -UseBasicParsing -Uri "https://api.ai24x.com/v1/billing/plans" -Headers @{ Accept = "application/json" }
$wwwHas = @($wwwPlans.plans | Where-Object { $_.plan -eq "token_test_01" }).Count
$openPlans = Invoke-RestMethod -UseBasicParsing -Uri "https://open.ai24x.com/v1/billing/plans" -Headers @{ Accept = "application/json" }
$openHas = @($openPlans.plans | Where-Object { $_.plan -eq "token_test_01" }).Count
Write-Host ("www public has test_pack=" + $wwwHas + " | open public has test_pack=" + $openHas)
if ($wwwHas -ne 0 -or $openHas -ne 0) { throw "test pack should be hidden when disabled" }

Write-Host "TESTPACK DEPLOY DONE" -ForegroundColor Green
Write-Host ("DONE EXP=" + $EXP + " HEAD=" + $HEAD) -ForegroundColor Green
