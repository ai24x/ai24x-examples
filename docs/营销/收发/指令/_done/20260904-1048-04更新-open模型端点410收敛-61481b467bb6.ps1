$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "61481b467bb6"
Set-Location $work

Write-Host "== 1. fetch + pull ==" -ForegroundColor Cyan
git fetch origin
git pull --ff-only origin master
$HEAD = (git rev-parse --short=12 HEAD).Trim()
Write-Host "HEAD=$HEAD"
git merge-base --is-ancestor $EXP HEAD
if ($LASTEXITCODE -ne 0) { throw "HEAD missing $EXP" }

Write-Host "== 2. markers ==" -ForegroundColor Cyan
$loc = Get-Content "p\open\web\config\locales.js" -Raw -Encoding UTF8
if ($loc -notlike "*Call models via https://api.ai24x.com/v1 with your Hub API key*") { throw "en transitional missing Hub copy" }
if ($loc -notlike "*AI24X Smart Gateway (api.ai24x.com)*") { throw "en matrix title not api" }
if ($loc -notlike "*Hub API Key*") { throw "zh transitional missing Hub API Key" }
$html = Get-Content "p\open\web\help.html" -Raw -Encoding UTF8
if ($html -notlike "*locales.js?v=20260904a*") { throw "help.html ?v= not 20260904a" }
$cons = Get-Content "p\open\web\console.html" -Raw -Encoding UTF8
if ($cons -notlike "*locales.js?v=20260904a*") { throw "console.html ?v= not 20260904a" }
if (-not (Test-Path "scripts\patch_open_nginx_close_model_api.ps1")) { throw "missing nginx patch script" }
Write-Host "markers OK" -ForegroundColor Green

Write-Host "== 3. restart open-api ==" -ForegroundColor Cyan
Restart-Service AI24X-open-api -Force -ErrorAction Stop
Start-Sleep -Seconds 8

Write-Host "== 4. nginx patch (open model API 410) ==" -ForegroundColor Cyan
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\patch_open_nginx_close_model_api.ps1"

Write-Host "== 5. verify ==" -ForegroundColor Cyan
function Get-Status([string]$Url, [string]$Method = "GET", $Body = $null) {
  try {
    if ($Method -eq "POST") {
      $r = Invoke-WebRequest -UseBasicParsing -Uri $Url -Method POST -ContentType "application/json" -Body $Body -TimeoutSec 20
    } else {
      $r = Invoke-WebRequest -UseBasicParsing -Uri $Url -Method GET -TimeoutSec 20
    }
    return [int]$r.StatusCode
  } catch {
    $resp = $_.Exception.Response
    if ($resp) { return [int]$resp.StatusCode }
    throw
  }
}

$chatBody = '{"model":"flash","messages":[{"role":"user","content":"ping"}],"max_tokens":5}'
$stChat = Get-Status "https://open.ai24x.com/v1/chat/completions" "POST" $chatBody
$stRun  = Get-Status "https://open.ai24x.com/v1/chat/run" "POST" $chatBody
$stResp = Get-Status "https://open.ai24x.com/v1/responses" "POST" '{"model":"flash","input":"ping"}'
$stModels = Get-Status "https://open.ai24x.com/v1/models"
$stPlans = Get-Status "https://open.ai24x.com/v1/billing/plans"
Write-Host "open chat=$stChat run=$stRun responses=$stResp models=$stModels plans=$stPlans"
if ($stChat -ne 410) { throw "open chat expected 410 got $stChat" }
if ($stRun -ne 410) { throw "open run expected 410 got $stRun" }
if ($stResp -ne 410) { throw "open responses expected 410 got $stResp" }
if ($stModels -ne 410) { throw "open models expected 410 got $stModels" }
if ($stPlans -ne 200) { throw "open billing/plans expected 200 got $stPlans" }

$help = Invoke-WebRequest -UseBasicParsing -Uri "https://open.ai24x.com/help.html" -TimeoutSec 20
if ($help.Content -notlike "*locales.js?v=20260904a*") { throw "public help.html missing ?v=20260904a" }
$lj = Invoke-WebRequest -UseBasicParsing -Uri "https://open.ai24x.com/config/locales.js?v=20260904a" -TimeoutSec 20
if ($lj.Content -notlike "*Hub API key*") { throw "public locales missing Hub copy" }

$ph = Invoke-RestMethod -UseBasicParsing -Uri "https://api.ai24x.com/health" -TimeoutSec 15
Write-Host ("api health commit=" + $ph.commit)

# BYOK bridge smoke via api (no key needed for this check beyond existing; just ensure api chat path not broken by nginx)
$apiModels = Get-Status "https://api.ai24x.com/v1/models"
if ($apiModels -ne 200) { throw "api /v1/models expected 200 got $apiModels" }

Write-Host ("DONE EXP=$EXP HEAD=$HEAD open410+plans200 locales20260904a") -ForegroundColor Green
# ✅ 04更新完成｜open模型端点410收敛｜EXP=61481b467bb6 HEAD=<HEAD> health=<commit>｜open chat/models=410 billing=200
