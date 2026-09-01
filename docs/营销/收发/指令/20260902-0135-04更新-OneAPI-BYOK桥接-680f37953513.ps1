$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "680f37953513"
$nssm = "C:\nssm\nssm.exe"
Set-Location $work

Write-Host "== 1. fetch + pull (origin only) ==" -ForegroundColor Cyan
git fetch origin
git pull --ff-only origin master
$HEAD = (git rev-parse --short=12 HEAD).Trim()
Write-Host "HEAD=$HEAD"
git merge-base --is-ancestor $EXP HEAD
if ($LASTEXITCODE -ne 0) { throw "HEAD missing target $EXP" }

Write-Host "== 2. marker checks ==" -ForegroundColor Cyan
$coreSvc = Get-Content (Join-Path $work "api\services.py") -Raw -Encoding UTF8
$coreBridge = Get-Content (Join-Path $work "api\byok_bridge.py") -Raw -Encoding UTF8
$openInternal = Get-Content (Join-Path $work "p\open\api\byok_internal.py") -Raw -Encoding UTF8
$helpHtml = Get-Content (Join-Path $work "p\open\web\help.html") -Raw -Encoding UTF8
$locales = Get-Content (Join-Path $work "p\open\web\config\locales.js") -Raw -Encoding UTF8
if ($coreBridge -notlike '*route_byok_chat*') { throw "api/byok_bridge.py missing route_byok_chat" }
if ($coreSvc -notlike '*from byok_bridge import*') { throw "api/services.py missing byok_bridge integration" }
if ($openInternal -notlike '*internal_byok_route*') { throw "byok_internal.py missing route endpoint" }
if ($helpHtml -notlike '*page.help.oneApi.title*') { throw "help.html missing One API section" }
if ($locales -notlike '*20260902a*') { throw "locales.js cache bust 20260902a missing" }
if ($locales -notlike '*page.console.byok.apiHint*') { throw "locales missing byok apiHint" }
Write-Host "markers OK" -ForegroundColor Green

Write-Host "== 3. merge core NSSM BYOK bridge env (keep existing keys) ==" -ForegroundColor Cyan
$coreExtra = (& $nssm get AI24X-core AppEnvironmentExtra 2>&1 | Out-String) -replace "`0",""
$keep = New-Object System.Collections.Generic.List[string]
foreach ($row in ($coreExtra -split "`r?`n")) {
  $t = $row.Trim()
  if (-not $t) { continue }
  if ($t -match '^BYOK_BRIDGE_ENABLED=') { continue }
  if ($t -match '^OPEN_API_BASE=') { continue }
  if ($t -notmatch '^[A-Za-z0-9_]+=') { continue }
  $keep.Add($t)
}
$keep.Add("BYOK_BRIDGE_ENABLED=1")
$keep.Add("OPEN_API_BASE=http://127.0.0.1:18080")
& $nssm set AI24X-core AppEnvironmentExtra @($keep.ToArray())
if ($LASTEXITCODE -ne 0) { throw "core nssm BYOK env set failed" }
Write-Host "core NSSM BYOK keys set" -ForegroundColor Green

Write-Host "== 4. restart open + core ==" -ForegroundColor Cyan
Restart-Service AI24X-open-api -ErrorAction Stop
Restart-Service AI24X-core -ErrorAction Stop
Start-Sleep -Seconds 14

Write-Host "== 5. loopback verify ==" -ForegroundColor Cyan
$h = Invoke-RestMethod -UseBasicParsing -Uri "http://127.0.0.1:8002/health" -TimeoutSec 15
git merge-base --is-ancestor $EXP $h.commit
if ($LASTEXITCODE -ne 0) { throw ("core health commit mismatch: " + $h.commit) }
$oh = Invoke-RestMethod -UseBasicParsing -Uri "http://127.0.0.1:18080/health" -TimeoutSec 15
if ($oh.commit) {
  git merge-base --is-ancestor $EXP $oh.commit
  if ($LASTEXITCODE -ne 0) { throw ("open health commit mismatch: " + $oh.commit) }
}

function Get-EnvVal([string]$path, [string]$key) {
  $hit = Select-String -Path $path -Pattern ("^" + [regex]::Escape($key) + "=") | Select-Object -First 1
  if (-not $hit) { return $null }
  return ($hit.Line -replace '^[^=]+=','').Trim().Trim('"').Trim("'")
}
$adminKey = Get-EnvVal (Join-Path $work "api\.env") "ADMIN_API_KEY"
if (-not $adminKey) { $adminKey = Get-EnvVal (Join-Path $work "api\.env") "SMS_INTERNAL_KEY" }
if (-not $adminKey) { throw "missing ADMIN_API_KEY/SMS_INTERNAL_KEY for internal BYOK probe" }
$probe = Invoke-RestMethod -UseBasicParsing -Method POST -Uri "http://127.0.0.1:18080/v1/internal/byok/has-coverage" `
  -Headers @{ "X-Admin-Key" = $adminKey; "Content-Type" = "application/json" } `
  -Body '{"platform_user_id":1,"model":"deepseek-chat"}'
if ($null -eq $probe.coverage) { throw "internal byok has-coverage bad response" }
Write-Host ("internal byok probe coverage=" + $probe.coverage) -ForegroundColor Green

Write-Host "== 6. public verify ==" -ForegroundColor Cyan
$ph = Invoke-RestMethod -UseBasicParsing -Uri "https://api.ai24x.com/health"
git merge-base --is-ancestor $EXP $ph.commit
if ($LASTEXITCODE -ne 0) { throw ("public core commit mismatch: " + $ph.commit) }
$helpPub = (Invoke-WebRequest -UseBasicParsing -Uri ("https://open.ai24x.com/help.html?v=" + $HEAD) -Headers @{ Accept = "text/html" }).Content
if ($helpPub -notlike '*locales.js?v=20260902a*') { throw "public help.html locales version stale" }
if ($helpPub -notlike '*page.help.oneApi.title*') { throw "public help missing One API section" }
$conPub = (Invoke-WebRequest -UseBasicParsing -Uri ("https://open.ai24x.com/console.html?v=" + $HEAD) -Headers @{ Accept = "text/html" }).Content
if ($conPub -notlike '*locales.js?v=20260902a*') { throw "public console locales version stale" }
if ($conPub -notlike '*page.console.byok.apiHint*') { throw "public console missing byok apiHint" }
Write-Host "public verify OK" -ForegroundColor Green

Write-Host ("DONE EXP=" + $EXP + " HEAD=" + $HEAD + " health=" + $ph.commit) -ForegroundColor Green
# ✅ 04更新完成｜One API BYOK桥接｜EXP=680f37953513 HEAD=<HEAD> health=<commit>｜core BYOK_BRIDGE_ENABLED=1+open内部路由｜help/console One API文案已上
