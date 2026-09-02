# Count real uvicorn worker processes on Windows (spawn_main children).
# Usage (on 04): powershell -File scripts\verify_uvicorn_workers.ps1 -Port 8002 -Expect 4

param(
  [int]$Port = 8002,
  [int]$Expect = 4
)

$ErrorActionPreference = "Stop"
$all = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'")
$parents = @($all | Where-Object {
  $_.CommandLine -and (
    ($_.CommandLine -like ("*--" + "port " + $Port + "*") -or $_.CommandLine -like ("*:$Port*")) -and
    ($_.CommandLine -like "*uvicorn*" -or $_.CommandLine -like "*run_prod.py*")
  )
})

$workers = @()
foreach ($p in $parents) {
  $workers += @($all | Where-Object {
    $_.ParentProcessId -eq $p.ProcessId -and
    $_.CommandLine -and
    $_.CommandLine -like "*multiprocessing.spawn*"
  })
}
# Also: parent itself may be intermediate; scan one more level
foreach ($p in $parents) {
  $mids = @($all | Where-Object { $_.ParentProcessId -eq $p.ProcessId })
  foreach ($m in $mids) {
    $workers += @($all | Where-Object {
      $_.ParentProcessId -eq $m.ProcessId -and
      $_.CommandLine -and
      $_.CommandLine -like "*multiprocessing.spawn*"
    })
  }
}
$workers = @($workers | Sort-Object ProcessId -Unique)

Write-Host ("uvicorn_parents=" + $parents.Count + " spawn_workers=" + $workers.Count + " expect>=" + $Expect)
foreach ($w in $workers) {
  Write-Host ("  worker pid=" + $w.ProcessId + " ppid=" + $w.ParentProcessId)
}
if ($workers.Count -lt $Expect) {
  throw ("worker count " + $workers.Count + " < " + $Expect)
}
Write-Host "WORKERS_OK"
