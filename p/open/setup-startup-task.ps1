# Create Windows scheduled task to auto-start PM2 services on boot
$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c cd /d E:\AI24X\ai24x-website\ai24x01 && pm2 resurrect"
$trigger = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId "Admin" -RunLevel Highest
Register-ScheduledTask -TaskName "AI24X-PM2-Startup" -Action $action -Trigger $trigger -Principal $principal -Force
Write-Host "OK - Scheduled task created"
