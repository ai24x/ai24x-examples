# Count real uvicorn worker processes on Windows (spawn_main children).
# Usage (on 04): powershell -File scripts\verify_uvicorn_workers.ps1 -Port 8002 -Expect 4
# Also matches NSSM entry `run_prod.py` (port is inside the script, not on argv).

param(
  [int]$Port = 8002,
  [int]$Expect = 4
)

$ErrorActionPreference = "Stop"
$all = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'")

function Is-UvicornParent([string]$cl, [int]$Port) {
  if (-not $cl) { return $false }
  if ($cl -like "*run_prod.py*") { return $true }
  $portHit = ($cl -like ("*--port " + $Port + "*")) -or ($cl -like ("*--" + "port=" + $Port + "*"))
  $uviHit = ($cl -like "*uvicorn*")
  return ($portHit -and $uviHit)
}

$parents = @($all | Where-Object { Is-UvicornParent $_.CommandLine $Port })

# Prefer parents whose listen port matches: if Port given, keep those with netstat owner
$listenPids = @()
try {
  $lines = netstat -ano | Select-String -Pattern ("TCP\s+127\.0\.0\.1:" + $Port + "\s+.*LISTENING\s+(\d+)") 
  foreach ($m in $lines) {
    if ($m.Matches.Count -gt 0) {
      $listenPids += [int]$m.Matches[0].Groups[1].Value
    }
  }
} catch {}
$listenPids = @($listenPids | Select-Object -Unique)

$workers = @()
$roots = @()
if ($listenPids.Count -gt 0) {
  $roots = @($all | Where-Object { $listenPids -contains $_.ProcessId })
  # also include their parents (venv launcher)
  foreach ($r in @($roots)) {
    $par = $all | Where-Object { $_.ProcessId -eq $r.ParentProcessId }
    if ($par) { $roots += $par }
  }
  $roots = @($roots | Sort-Object ProcessId -Unique)
} else {
  $roots = $parents
}

foreach ($p in $roots) {
  $workers += @($all | Where-Object {
    $_.ParentProcessId -eq $p.ProcessId -and
    $_.CommandLine -and
    $_.CommandLine -like "*multiprocessing.spawn*"
  })
  # one more level (venv stub -> real python -> spawn)
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

Write-Host ("listen_pids=" + ($listenPids -join ',') + " roots=" + $roots.Count + " spawn_workers=" + $workers.Count + " expect>=" + $Expect)
foreach ($w in $workers) {
  Write-Host ("  worker pid=" + $w.ProcessId + " ppid=" + $w.ParentProcessId)
}
if ($workers.Count -lt $Expect) {
  throw ("worker count " + $workers.Count + " < " + $Expect)
}
Write-Host "WORKERS_OK"
