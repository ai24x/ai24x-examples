$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "56d46c2876b2"
$Nssm = "C:\nssm\nssm.exe"
Set-Location $work
Write-Host "== 1. fetch + pull ==" -ForegroundColor Cyan
git fetch origin
git pull --ff-only origin master
$HEAD = (git rev-parse --short=12 HEAD).Trim()
Write-Host "HEAD=$HEAD"
git merge-base --is-ancestor $EXP HEAD
if ($LASTEXITCODE -ne 0) { throw "HEAD missing $EXP" }

Write-Host "== 2. markers (sync chat + thread limiter) ==" -ForegroundColor Cyan
$core = Get-Content "api\main.py" -Raw -Encoding UTF8
if ($core -notlike '*P0 阻塞加固：用同步 def*') { throw "api missing sync chat_run marker" }
if ($core -notlike '*anyio thread limiter*') { throw "api missing thread limiter" }
if ($core -notmatch '(?m)^def chat_completions\(') { throw "api chat_completions still async?" }
if ($core -notmatch '(?m)^def openai_responses_create\(') { throw "api responses still async?" }
$open = Get-Content "p\open\api\main.py" -Raw -Encoding UTF8
if ($open -notmatch '(?m)^def chat_completions\(') { throw "open chat_completions still async?" }
Write-Host "markers OK" -ForegroundColor Green

Write-Host "== 3. NSSM --workers 4 (hardcode; strip UTF-16 nulls) ==" -ForegroundColor Cyan
if (-not (Test-Path $Nssm)) { throw "nssm missing: $Nssm" }
$bakDir = "C:\Users\Administrator\ops\nssm-bak"
New-Item -ItemType Directory -Force -Path $bakDir | Out-Null
$ts = Get-Date -Format "yyyyMMdd-HHmmss"

function Get-NssmParamClean([string]$Service, [string]$Key) {
  $raw = & $Nssm get $Service $Key 2>&1 | Out-String
  return (($raw -replace "`0","").Trim())
}

function Set-UvicornWorkersHard([string]$Service, [string]$FixedParams) {
  $old = Get-NssmParamClean $Service "AppParameters"
  Set-Content -LiteralPath (Join-Path $bakDir ($Service + "-AppParameters-" + $ts + ".txt")) -Value $old -Encoding UTF8
  Write-Host ("  " + $Service + " OLD: " + $old)
  & $Nssm set $Service AppParameters $FixedParams
  if ($LASTEXITCODE -ne 0) { throw ("nssm set failed for " + $Service) }
  $got = Get-NssmParamClean $Service "AppParameters"
  Write-Host ("  " + $Service + " NEW: " + $got)
  if ($got -ne $FixedParams) { throw ("workers not applied for " + $Service + " got=" + $got) }
}

Set-UvicornWorkersHard -Service "AI24X-core" -FixedParams "-m uvicorn main:app --host 127.0.0.1 --port 8002 --workers 4"
try {
  Set-UvicornWorkersHard -Service "AI24X-open-api" -FixedParams "-m uvicorn main:app --host 127.0.0.1 --port 18080 --workers 4"
} catch {
  Write-Host ("  open-api workers skip: " + $_.Exception.Message) -ForegroundColor Yellow
}

Write-Host "== 4. restart ==" -ForegroundColor Cyan
Restart-Service AI24X-open-api -ErrorAction SilentlyContinue
Restart-Service AI24X-core -ErrorAction Stop
Start-Sleep -Seconds 18

Write-Host "== 5. verify ==" -ForegroundColor Cyan
$ph = Invoke-RestMethod -UseBasicParsing -Uri "https://api.ai24x.com/health"
git merge-base --is-ancestor $EXP $ph.commit
if ($LASTEXITCODE -ne 0) { throw ("health commit mismatch " + $ph.commit) }
Write-Host ("health OK commit=" + $ph.commit) -ForegroundColor Green

$procs = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -and $_.CommandLine -like '*8002*' }
Write-Host ("python*8002 count=" + @($procs).Count)
if (@($procs).Count -lt 2) {
  Write-Host "WARN: expected multi-process with --workers 4; count < 2" -ForegroundColor Yellow
} else {
  Write-Host "multi-process OK" -ForegroundColor Green
}

$coreParams = Get-NssmParamClean "AI24X-core" "AppParameters"
if ($coreParams -notlike '*--workers 4*') { throw ("post-restart core params missing workers: " + $coreParams) }

Write-Host ("DONE EXP=$EXP HEAD=$HEAD health=$($ph.commit) workers=4") -ForegroundColor Green
# ✅ 04更新完成｜单点阻塞P0 sync+workers｜EXP=56d46c2876b2 HEAD=<HEAD> health=<commit>｜chat同步线程池+uvicorn×4
