param([string]$TaskFile)
# 03 后台运行 openclaw 的 schtasks 方案（脱离 ssh 会话，由 Task Scheduler 服务托管）
$LogFile = "$TaskFile.out.log"
$ts = Get-Date -Format "yyyyMMddHHmmss"
$taskName = "AI24X_Dev03_" + $ts
$oc = (Get-Command openclaw -ErrorAction SilentlyContinue).Source
if (-not $oc) { $oc = "C:\Users\Administrator\AppData\Roaming\npm\openclaw.ps1" }
# openclaw 是 .ps1 包装器，cmd 无法直接执行 → 用 powershell -File 包装
$argLine = '/c powershell -NoProfile -ExecutionPolicy Bypass -File "' + $oc + '" agent --agent main --message-file "' + $TaskFile + '" --json --timeout 600 > "' + $LogFile + '" 2>&1'
$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument $argLine -WorkingDirectory "C:\ai24x01"
Register-ScheduledTask -TaskName $taskName -Action $action -Force | Out-Null
Start-ScheduledTask -TaskName $taskName
Write-Output "SCHTASK STARTED: $taskName"
