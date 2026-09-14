$ErrorActionPreference = "Continue"
function Show-Tree([int]$Pid, [int]$Depth = 0) {
  $pad = "  " * $Depth
  $p = Get-CimInstance Win32_Process -Filter ("ProcessId=" + $Pid) -ErrorAction SilentlyContinue
  if (-not $p) { return }
  $cl = $p.CommandLine
  if ($cl -and $cl.Length -gt 100) { $cl = $cl.Substring(0,100) + "..." }
  Write-Host ($pad + "pid=" + $p.ProcessId + " " + $p.Name + " " + $cl)
  Get-CimInstance Win32_Process | Where-Object { $_.ParentProcessId -eq $Pid } | ForEach-Object {
    Show-Tree -Pid $_.ProcessId -Depth ($Depth + 1)
  }
}
Write-Host "== core master 4156 =="
Show-Tree -Pid 4156
Write-Host "== child 8964 =="
Show-Tree -Pid 8964
# Event log / recent stderr - nssm AppStderr
$Nssm = "C:\nssm\nssm.exe"
foreach ($k in @("AppStdout","AppStderr","AppDirectory","AppEnvironmentExtra")) {
  $v = ((& $Nssm get AI24X-core $k 2>&1 | Out-String) -replace "`0","").Trim()
  Write-Host ("NSSM $k = $v")
}
Write-Host DONE
