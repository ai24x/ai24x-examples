# 注册 Windows 计划任务：每天 06:00 清理 Token 超时未付订单（无交易号的超时 pending 作废）。
# 用法：powershell -ExecutionPolicy Bypass -File scripts/register_pending_cleanup_cron.ps1
# 删除：Unregister-ScheduledTask -TaskName AI24X_PendingCleanup -Confirm:$false
$ErrorActionPreference = "Stop"
$python = (Get-Command python).Source
$apiDir = "E:\AI24X\ai24x-website\ai24x01\api"
$script = Join-Path $apiDir "scripts_token_pending_cleanup.py"
$taskName = "AI24X_PendingCleanup"
$action = New-ScheduledTaskAction -Execute $python -Argument "`"$script`" --apply" -WorkingDirectory $apiDir
$trigger = New-ScheduledTaskTrigger -Daily -At "06:00"
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 10) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
Write-Host "[OK] 已注册计划任务 $taskName（每天 06:00 执行一次，自动作废无交易号的超时未付单）"
Write-Host "手动预览：python `"$script`""
Write-Host "手动执行：python `"$script`" --apply"
