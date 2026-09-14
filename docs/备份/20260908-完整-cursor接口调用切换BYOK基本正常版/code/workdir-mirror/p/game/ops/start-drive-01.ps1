$ErrorActionPreference = 'Continue'
# 用 cmd /c start 后台启动驱动脚本（独立于 SSH 会话，防 exec 超时杀进程树）
$cmd = 'C:\Users\Administrator\ops\drive-gameweb-01.cmd'
Start-Process -WindowStyle Hidden -FilePath 'cmd.exe' -ArgumentList '/c', "`"$cmd`"" 
Write-Output "DRIVE_STARTED"
