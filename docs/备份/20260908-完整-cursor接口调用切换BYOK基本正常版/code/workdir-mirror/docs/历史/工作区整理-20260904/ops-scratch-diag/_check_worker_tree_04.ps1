$ErrorActionPreference = "Stop"
# Broader process tree for AI24X-core
$svc = Get-CimInstance Win32_Service -Filter "Name='AI24X-core'"
Write-Host ("Service State=" + $svc.State + " PID=" + $svc.ProcessId)
$parent = Get-CimInstance Win32_Process -Filter ("ProcessId=" + $svc.ProcessId)
Write-Host ("Parent: " + $parent.Name + " " + $parent.CommandLine)
$children = Get-CimInstance Win32_Process | Where-Object { $_.ParentProcessId -eq $svc.ProcessId }
Write-Host ("Children count=" + @($children).Count)
foreach ($c in @($children)) {
  Write-Host ("  child pid=" + $c.ProcessId + " ppid=" + $c.ParentProcessId + " " + $c.Name)
  Write-Host ("    " + $c.CommandLine)
}
# all uvicorn-ish
$all = Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -and $_.CommandLine -like '*uvicorn*' }
Write-Host ("all uvicorn python count=" + @($all).Count)
foreach ($p in @($all)) {
  Write-Host ("  pid=" + $p.ProcessId + " ppid=" + $p.ParentProcessId)
  Write-Host ("    " + $p.CommandLine)
}
# recent error log if any
$err = "C:\ai24x01\api\logs"
if (Test-Path $err) {
  Get-ChildItem $err -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 3 | ForEach-Object { Write-Host ("log " + $_.Name + " " + $_.LastWriteTime) }
}
Write-Host TREE_DONE
