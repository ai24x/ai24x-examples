$ErrorActionPreference = "Continue"
$Nssm = "C:\nssm\nssm.exe"
function Clean([string]$s,[string]$k){ (((& $Nssm get $s $k 2>&1 | Out-String) -replace "`0","").Trim()) }
Write-Host "core Params=" (Clean AI24X-core AppParameters)
Write-Host "core State=" ((Get-Service AI24X-core).Status)
$svc = Get-CimInstance Win32_Service -Filter "Name='AI24X-core'"
Write-Host "nssm pid=" $svc.ProcessId

function Show([int]$id,[int]$d=0){
  $p=Get-CimInstance Win32_Process -Filter ("ProcessId="+$id) -EA SilentlyContinue
  if(-not $p){return}
  $cl=$p.CommandLine; if($cl -and $cl.Length -gt 140){$cl=$cl.Substring(0,140)+"..."}
  Write-Host (("  "*$d)+"pid="+$p.ProcessId+" "+$p.Name+" "+$cl)
  Get-CimInstance Win32_Process | ? { $_.ParentProcessId -eq $id } | % { Show $_.ProcessId ($d+1) }
}
Show ([int]$svc.ProcessId)

Write-Host "=== netstat 8002 ==="
netstat -ano | findstr ":8002"

Write-Host "=== spawn_main count ==="
@(Get-CimInstance Win32_Process -Filter "Name='python.exe'" | ? { $_.CommandLine -like '*multiprocessing.spawn*' }).Count
Write-Host DONE
