$ErrorActionPreference = "Stop"
$Nssm = "C:\nssm\nssm.exe"
$fixed = "-m uvicorn main:app --host 127.0.0.1 --port 8002 --workers 4"
Write-Host "Setting AI24X-core AppParameters to:"
Write-Host $fixed
& $Nssm set AI24X-core AppParameters $fixed
if ($LASTEXITCODE -ne 0) { throw "nssm set core failed" }

# Decode get as unicode (nssm often emits UTF-16)
$raw = & $Nssm get AI24X-core AppParameters 2>&1 | Out-String
$clean = ($raw -replace "`0","").Trim()
Write-Host "GET(clean)=$clean"
if ($clean -notlike "*--workers 4*") { throw "verify failed: $clean" }

# open-api if exists
try {
  $fixedOpen = "-m uvicorn main:app --host 127.0.0.1 --port 18080 --workers 4"
  $oldOpenRaw = & $Nssm get AI24X-open-api AppParameters 2>&1 | Out-String
  $oldOpen = ($oldOpenRaw -replace "`0","").Trim()
  Write-Host "open OLD(clean)=$oldOpen"
  if ($oldOpen -like "*uvicorn*" -and $oldOpen -like "*18080*") {
    & $Nssm set AI24X-open-api AppParameters $fixedOpen
    Write-Host "open set OK"
  } else {
    Write-Host "open skip (unexpected params)"
  }
} catch {
  Write-Host ("open skip: " + $_.Exception.Message)
}

Restart-Service AI24X-core -ErrorAction Stop
Restart-Service AI24X-open-api -ErrorAction SilentlyContinue
Start-Sleep -Seconds 16
$ph = Invoke-RestMethod -UseBasicParsing -Uri "https://api.ai24x.com/health"
Write-Host ("health commit=" + $ph.commit + " status=" + $ph.status)
$svc = Get-Service AI24X-core
Write-Host ("AI24X-core=" + $svc.Status)
if ($svc.Status -ne "Running") { throw "core not running" }
Write-Host "RECOVERY_OK"
