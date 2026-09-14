$ErrorActionPreference = "Stop"
$Nssm = "C:\nssm\nssm.exe"

function Clean-Nssm([string]$svc, [string]$key) {
  $raw = & $Nssm get $svc $key 2>&1 | Out-String
  return (($raw -replace "`0", "").Trim())
}

Write-Host "core App=" (Clean-Nssm AI24X-core Application)
Write-Host "core Dir=" (Clean-Nssm AI24X-core AppDirectory)
Write-Host "core Params=" (Clean-Nssm AI24X-core AppParameters)
Write-Host "open App=" (Clean-Nssm AI24X-open-api Application)
Write-Host "open Dir=" (Clean-Nssm AI24X-open-api AppDirectory)
Write-Host "open Params=" (Clean-Nssm AI24X-open-api AppParameters)

# probe kill tree keys
foreach ($k in @("AppKillProcessTree","AppStopMethodSkip","AppExit","AppThrottle")) {
  try {
    $v = Clean-Nssm AI24X-core $k
    Write-Host ("core " + $k + "=" + $v)
  } catch {
    Write-Host ("core " + $k + "=N/A")
  }
}
Write-Host DONE
