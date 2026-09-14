param([string]$TaskPattern = "")
$ErrorActionPreference = "SilentlyContinue"

$procs = Get-CimInstance Win32_Process | Where-Object { $_.Name -match "node|cmd" -and $_.CommandLine -match "openclaw" }

$stuck = $procs | Where-Object { $TaskPattern -ne "" -and $_.CommandLine -match $TaskPattern }
foreach ($p in $stuck) {
  Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
  Write-Output ("KILLED STUCK " + $p.ProcessId)
}

$zombie = $procs | Where-Object { $_.CommandLine -match "task-20260815-04-ms-cred" }
foreach ($p in $zombie) {
  Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
  Write-Output ("KILLED ZOMBIE " + $p.ProcessId)
}

$gw = $procs | Where-Object { $_.CommandLine -match "dist.index.js gateway --port 18789" }
foreach ($p in $gw) {
  Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
  Write-Output ("KILLED GATEWAY " + $p.ProcessId)
}

$gwc = Get-CimInstance Win32_Process | Where-Object { $_.Name -eq "cmd.exe" -and $_.CommandLine -match "gateway.cmd" }
foreach ($p in $gwc) {
  Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
  Write-Output ("KILLED GWC " + $p.ProcessId)
}

Start-Sleep -Seconds 3
Start-Process -FilePath "C:\Users\Administrator\.openclaw\gateway.cmd" -WindowStyle Hidden
Start-Sleep -Seconds 8

Write-Output "=== PORT 18789 ==="
netstat -ano | Select-String "18789" | Select-Object -First 5

Write-Output "=== REMAINING openclaw PROCS ==="
Get-CimInstance Win32_Process | Where-Object { $_.Name -match "node|cmd" -and $_.CommandLine -match "openclaw" } | Select-Object ProcessId,Name,CreationDate | Format-Table -AutoSize | Out-String -Width 300
