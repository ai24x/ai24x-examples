$ErrorActionPreference = 'Continue'
$cmd = 'C:\Users\Administrator\ops\drive-ph3-02-v2.cmd'
Start-Process -WindowStyle Hidden -FilePath 'cmd.exe' -ArgumentList '/c', "`"$cmd`""
Write-Output "DRIVE_STARTED"
