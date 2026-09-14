$ErrorActionPreference = "Continue"
$Nssm = "C:\nssm\nssm.exe"

function Clean-Nssm([string]$svc, [string]$key) {
  $raw = & $Nssm get $svc $key 2>&1 | Out-String
  return (($raw -replace "`0", "").Trim())
}

Write-Host "=== NSSM core ==="
Write-Host ("App=" + (Clean-Nssm AI24X-core Application))
Write-Host ("Dir=" + (Clean-Nssm AI24X-core AppDirectory))
Write-Host ("Params=" + (Clean-Nssm AI24X-core AppParameters))
Write-Host ("AppEnvExtra length=" + ((Clean-Nssm AI24X-core AppEnvironmentExtra).Length))

$svc = Get-CimInstance Win32_Service -Filter "Name='AI24X-core'"
Write-Host ("Service PID=" + $svc.ProcessId + " State=" + $svc.State)

Write-Host "=== python processes with uvicorn ==="
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object {
  $_.CommandLine -and $_.CommandLine -like '*uvicorn*'
} | ForEach-Object {
  Write-Host ("pid=" + $_.ProcessId + " ppid=" + $_.ParentProcessId)
  Write-Host ("  " + $_.CommandLine)
}

Write-Host "=== which python in venv ==="
$venvPy = "C:\ai24x01\api\venv\Scripts\python.exe"
if (Test-Path $venvPy) {
  & $venvPy -c "import sys,uvicorn; print(sys.executable); print(uvicorn.__version__); print(sys.version)"
}

Write-Host "=== recent stderr/out tails ==="
foreach ($f in @("C:\ai24x01\logs\ai24x-core.err.log","C:\ai24x01\logs\ai24x-core.out.log")) {
  if (Test-Path $f) {
    Write-Host ("--- " + $f + " ---")
    Get-Content $f -Tail 25 -ErrorAction SilentlyContinue
  }
}
Write-Host DONE
