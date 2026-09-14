param([string]$TaskFile)
$LogFile = "$TaskFile.out.log"
$ErrFile  = "$TaskFile.err.log"
$OcCmd = "C:\Users\Administrator\AppData\Roaming\npm\openclaw.cmd"
$OcArgs = @('agent','--agent','main','--message-file',$TaskFile,'--json','--timeout','600')
$p = Start-Process -FilePath $OcCmd -ArgumentList $OcArgs -RedirectStandardOutput $LogFile -RedirectStandardError $ErrFile -WindowStyle Hidden -PassThru
Write-Output "ASYNC STARTED PID=$($p.Id)"
