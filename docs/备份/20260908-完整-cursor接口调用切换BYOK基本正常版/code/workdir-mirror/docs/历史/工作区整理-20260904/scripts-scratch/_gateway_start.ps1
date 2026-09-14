$ErrorActionPreference = "SilentlyContinue"
$cmdLine = 'cmd.exe /c ""C:\Users\Administrator\.openclaw\gateway.cmd" > C:\Users\Administrator\ops\gateway-debug.log 2>&1"'
$result = ([wmiclass]"\\.\root\cimv2:Win32_Process").Create($cmdLine)
Write-Output ("WMI CREATE PID=" + $result.ProcessId + " Return=" + $result.ReturnValue)
Start-Sleep -Seconds 12
Write-Output "=== PORT 18789 ==="
netstat -ano | Select-String "18789" | Select-Object -First 6
Write-Output "=== PROCS ==="
Get-CimInstance Win32_Process | Where-Object { $_.Name -match "node|cmd" -and $_.CommandLine -match "openclaw" } | Select-Object ProcessId,Name,CreationDate | Format-Table -AutoSize | Out-String -Width 300
Write-Output "=== DEBUG LOG ==="
if (Test-Path "C:\Users\Administrator\ops\gateway-debug.log") {
  Get-Content "C:\Users\Administrator\ops\gateway-debug.log" -Tail 50 | Out-String -Width 250
} else {
  Write-Output "no log file"
}
