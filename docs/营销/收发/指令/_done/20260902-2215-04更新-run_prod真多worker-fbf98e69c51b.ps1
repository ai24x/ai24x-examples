$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "fbf98e69c51b"
$Nssm = "C:\nssm\nssm.exe"
Set-Location $work
Write-Host "== 1. fetch + pull ==" -ForegroundColor Cyan
git fetch origin
git pull --ff-only origin master
$HEAD = (git rev-parse --short=12 HEAD).Trim()
Write-Host "HEAD=$HEAD"
git merge-base --is-ancestor $EXP HEAD
if ($LASTEXITCODE -ne 0) { throw "HEAD missing $EXP" }

Write-Host "== 2. markers ==" -ForegroundColor Cyan
if (-not (Test-Path "api\run_prod.py")) { throw "missing api/run_prod.py" }
if (-not (Test-Path "p\open\api\run_prod.py")) { throw "missing open run_prod.py" }
if (-not (Test-Path "scripts\verify_uvicorn_workers.ps1")) { throw "missing verify script" }
$rp = Get-Content "api\run_prod.py" -Raw -Encoding UTF8
if ($rp -notlike "*freeze_support*") { throw "run_prod missing freeze_support" }
if ($rp -notlike "*workers=workers*") { throw "run_prod missing workers" }
Write-Host "markers OK" -ForegroundColor Green

Write-Host "== 3. NSSM -> run_prod.py ==" -ForegroundColor Cyan
function Get-NssmClean([string]$Service, [string]$Key) {
  $raw = & $Nssm get $Service $Key 2>&1 | Out-String
  return (($raw -replace "`0", "").Trim())
}
$bakDir = "C:\Users\Administrator\ops\nssm-bak"
New-Item -ItemType Directory -Force -Path $bakDir | Out-Null
$ts = Get-Date -Format "yyyyMMdd-HHmmss"

function Switch-ToRunProd([string]$Service, [string]$ExpectDir) {
  $old = Get-NssmClean $Service "AppParameters"
  $dir = Get-NssmClean $Service "AppDirectory"
  Set-Content -LiteralPath (Join-Path $bakDir ($Service + "-AppParameters-" + $ts + ".txt")) -Value $old -Encoding UTF8
  Write-Host ("  " + $Service + " Dir=" + $dir)
  Write-Host ("  " + $Service + " OLD Params=" + $old)
  if ($dir -notlike ("*" + $ExpectDir + "*")) {
    Write-Host ("  WARN: AppDirectory unexpected, leave as-is: " + $dir) -ForegroundColor Yellow
  }
  & $Nssm set $Service AppParameters "run_prod.py"
  if ($LASTEXITCODE -ne 0) { throw ("nssm set failed " + $Service) }
  $got = Get-NssmClean $Service "AppParameters"
  Write-Host ("  " + $Service + " NEW Params=" + $got)
  if ($got -ne "run_prod.py") { throw ("params mismatch " + $got) }
}

Switch-ToRunProd -Service "AI24X-core" -ExpectDir "ai24x01\api"
Switch-ToRunProd -Service "AI24X-open-api" -ExpectDir "open\api"

Write-Host "== 4. restart ==" -ForegroundColor Cyan
Restart-Service AI24X-open-api -ErrorAction SilentlyContinue
Restart-Service AI24X-core -ErrorAction Stop
Start-Sleep -Seconds 20

Write-Host "== 5. verify ==" -ForegroundColor Cyan
$ph = Invoke-RestMethod -UseBasicParsing -Uri "https://api.ai24x.com/health"
git merge-base --is-ancestor $EXP $ph.commit
if ($LASTEXITCODE -ne 0) { throw ("health commit mismatch " + $ph.commit) }
Write-Host ("health OK commit=" + $ph.commit)

# copy verify script path from repo
& powershell -NoProfile -ExecutionPolicy Bypass -File "C:\ai24x01\scripts\verify_uvicorn_workers.ps1" -Port 8002 -Expect 4
& powershell -NoProfile -ExecutionPolicy Bypass -File "C:\ai24x01\scripts\verify_uvicorn_workers.ps1" -Port 18080 -Expect 4

1..3 | ForEach-Object {
  $t0 = Get-Date
  $null = Invoke-RestMethod -UseBasicParsing -Uri "https://api.ai24x.com/health"
  $ms = [int]((Get-Date) - $t0).TotalMilliseconds
  Write-Host ("health_probe $_ ms=$ms")
}

Write-Host ("DONE EXP=$EXP HEAD=$HEAD health=$($ph.commit) run_prod+workers4") -ForegroundColor Green
# ✅ 04更新完成｜run_prod真多worker｜EXP=fbf98e69c51b HEAD=<HEAD> health=<commit>｜spawn_workers≥4
