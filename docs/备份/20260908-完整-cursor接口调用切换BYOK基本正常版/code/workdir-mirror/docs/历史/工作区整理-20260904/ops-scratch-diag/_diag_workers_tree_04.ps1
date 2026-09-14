$ErrorActionPreference = "Continue"

function Show-Descendants([int]$RootPid, [int]$Depth = 0) {
  $pad = "  " * $Depth
  $p = Get-CimInstance Win32_Process -Filter ("ProcessId=" + $RootPid) -ErrorAction SilentlyContinue
  if (-not $p) { Write-Host ($pad + "missing pid=" + $RootPid); return }
  $cl = $p.CommandLine
  if ($cl -and $cl.Length -gt 160) { $cl = $cl.Substring(0, 160) + "..." }
  Write-Host ($pad + "pid=" + $p.ProcessId + " ppid=" + $p.ParentProcessId + " " + $p.Name)
  Write-Host ($pad + "  " + $cl)
  Get-CimInstance Win32_Process | Where-Object { $_.ParentProcessId -eq $RootPid } | ForEach-Object {
    Show-Descendants -RootPid $_.ProcessId -Depth ($Depth + 1)
  }
}

$svc = Get-CimInstance Win32_Service -Filter "Name='AI24X-core'"
Write-Host ("NSSM service ProcessId=" + $svc.ProcessId)
Show-Descendants -RootPid ([int]$svc.ProcessId)

Write-Host "`n=== count python by parent ==="
$allPy = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'")
Write-Host ("total python.exe=" + $allPy.Count)
# Find uvicorn master for 8002
$masters = $allPy | Where-Object { $_.CommandLine -like '*8002*' -and $_.CommandLine -like '*workers*' }
foreach ($m in $masters) {
  $kids = @($allPy | Where-Object { $_.ParentProcessId -eq $m.ProcessId })
  Write-Host ("master pid=" + $m.ProcessId + " direct_children=" + $kids.Count)
  foreach ($k in $kids) {
    $gk = @($allPy | Where-Object { $_.ParentProcessId -eq $k.ProcessId })
    Write-Host ("  child=" + $k.ProcessId + " grandchildren_python=" + $gk.Count)
  }
}

Write-Host "`n=== startup complete count since last restart ==="
$log = "C:\ai24x01\logs\ai24x-core.err.log"
Select-String -Path $log -Pattern "Application startup complete|Started server process|Waiting for child|Booting worker|child process" |
  Select-Object -Last 40 | ForEach-Object { $_.Line }

Write-Host DONE
