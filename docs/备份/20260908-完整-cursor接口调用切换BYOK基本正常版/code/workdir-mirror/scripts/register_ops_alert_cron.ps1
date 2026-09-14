# 注册 Windows 计划任务：每 15 分钟运行运维预警巡检（含飞书推送）。
# 用法：powershell -ExecutionPolicy Bypass -File scripts/register_ops_alert_cron.ps1
# 删除：Unregister-ScheduledTask -TaskName AI24X_OpsAlert -Confirm:$false
$ErrorActionPreference = "Stop"
$python = (Get-Command python).Source
$apiDir = "E:\AI24X\ai24x-website\ai24x01\api"
$script = Join-Path $apiDir "scripts_ops_alert.py"
$taskName = "AI24X_OpsAlert"
$action = New-ScheduledTaskAction -Execute $python -Argument "`"$script`"" -WorkingDirectory $apiDir
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 15)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 5) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
Write-Host "[OK] 已注册计划任务 $taskName（每 15 分钟一次）"
Write-Host "手动运行一次：python `"$script`""
Write-Host "dry-run 预览：python `"$script`" --dry-run"
