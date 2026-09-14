$ErrorActionPreference = 'Continue'
$cmd = 'C:\Users\Administrator\ops\drive-https03-01.cmd'
Start-Process -WindowStyle Hidden -FilePath 'cmd.exe' -ArgumentList '/c', "`"$cmd`""
Write-Output "DRIVE_STARTED"
