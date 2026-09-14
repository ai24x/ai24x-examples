Write-Output "=== scheduled task result ==="
Get-ScheduledTaskInfo -TaskName "AI24X_Dev03_20260818170111" -ErrorAction SilentlyContinue | Select-Object TaskName,LastRunTime,LastTaskResult | Format-List

Write-Output "=== services powershell cmdlines ==="
Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" | Select-Object ProcessId,CommandLine | Format-List

Write-Output "=== node cmdlines ==="
Get-CimInstance Win32_Process -Filter "Name='node.exe'" | Select-Object ProcessId,CommandLine | Format-List

Write-Output "=== out.log raw ==="
$log = "C:\Users\Administrator\ops\20260818-1646-03开发-板块排名与主线判定优化任务书.md.out.log"
if (Test-Path $log) {
    Get-Item $log | Select-Object Length,LastWriteTime | Format-List
    Get-Content $log -Tail 20 -ErrorAction SilentlyContinue
} else {
    Write-Output "out.log missing"
}
