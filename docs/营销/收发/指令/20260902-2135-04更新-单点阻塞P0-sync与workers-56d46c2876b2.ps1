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

Write-Host "== 3. NSSM --workers 4 (backup + set) ==" -ForegroundColor Cyan
if (-not (Test-Path $Nssm)) { throw "nssm missing: $Nssm" }
$bakDir = "C:\Users\Administrator\ops\nssm-bak"
New-Item -ItemType Directory -Force -Path $bakDir | Out-Null
$ts = Get-Date -Format "yyyyMMdd-HHmmss"

function Set-UvicornWorkers([string]$Service, [string]$ExpectPort, [int]$Workers = 4) {
  $old = & $Nssm get $Service AppParameters 2>$null
  if (-not $old) { throw "cannot read AppParameters for $Service" }
  $old = [string]$old
  Set-Content -LiteralPath (Join-Path $bakDir "$Service-AppParameters-$ts.txt") -Value $old -Encoding UTF8
  Write-Host ("  $Service OLD: " + $old)
  # Keep host/port; ensure --workers N
  $parts = $old -split '\s+' | Where-Object { $_ -ne '' }
  $newParts = New-Object System.Collections.Generic.List[string]
  $skipNext = $false
  foreach ($p in $parts) {
    if ($skipNext) { $skipNext = $false; continue }
    if ($p -eq '--workers') { $skipNext = $true; continue }
    [void]$newParts.Add($p)
  }
  [void]$newParts.Add('--workers')
  [void]$newParts.Add([string]$Workers)
  $new = ($newParts -join ' ')
  if ($new -notlike "*--port $ExpectPort*" -and $new -notlike "*=$ExpectPort*") {
    # soft check: port string present
    if ($new -notlike "*$ExpectPort*") { Write-Host "  WARN: port $ExpectPort not obvious in: $new" -ForegroundColor Yellow }
  }
  & $Nssm set $Service AppParameters $new
  if ($LASTEXITCODE -ne 0) { throw "nssm set failed for $Service" }
  $got = [string](& $Nssm get $Service AppParameters)
  Write-Host ("  $Service NEW: " + $got)
  if ($got -notlike "*--workers $Workers*") { throw "workers not applied for $Service: $got" }
}

Set-UvicornWorkers -Service "AI24X-core" -ExpectPort "8002" -Workers 4
# open 同机：一并加固（18080）
try {
  Set-UvicornWorkers -Service "AI24X-open-api" -ExpectPort "18080" -Workers 4
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

# 进程数：uvicorn master + workers（Windows 下至少 >1）
$procs = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -and ($_.CommandLine -like '*uvicorn*main:app*8002*' -or ($_.CommandLine -like '*uvicorn*' -and $_.CommandLine -like '*8002*')) }
Write-Host ("python uvicorn@8002 count=" + @($procs).Count)
foreach ($p in @($procs)) {
  Write-Host ("  pid=" + $p.ProcessId + " " + (($p.CommandLine -replace '.{120}$','...') ))
}
if (@($procs).Count -lt 2) {
  Write-Host "WARN: expected multi-process with --workers 4; count < 2 — check NSSM / uvicorn Windows spawn" -ForegroundColor Yellow
} else {
  Write-Host "multi-process OK" -ForegroundColor Green
}

# 参数回读
$coreParams = [string](& $Nssm get AI24X-core AppParameters)
if ($coreParams -notlike '*--workers 4*') { throw "post-restart core params missing workers: $coreParams" }

Write-Host ("DONE EXP=$EXP HEAD=$HEAD health=$($ph.commit) workers=4") -ForegroundColor Green
# ✅ 04更新完成｜单点阻塞P0 sync+workers｜EXP=56d46c2876b2 HEAD=<HEAD> health=<commit>｜chat同步线程池+uvicorn×4
