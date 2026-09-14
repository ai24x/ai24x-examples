param([string]$TaskFile)
# 03 后台运行 openclaw：Start-Process powershell（openclaw 是 .ps1 包装器）
$LogFile = "$TaskFile.out.log"
$ErrFile = "$TaskFile.err.log"
$oc = "C:\Users\Administrator\AppData\Roaming\npm\openclaw.ps1"
$args = @('-NoProfile','-ExecutionPolicy','Bypass','-File', $oc, 'agent','--agent','main','--message-file',$TaskFile,'--json','--timeout','600')
$p = Start-Process -FilePath "powershell.exe" -ArgumentList $args -WindowStyle Hidden -RedirectStandardOutput $LogFile -RedirectStandardError $ErrFile -PassThru
Write-Output ("STARTED PID=" + $p.Id)
