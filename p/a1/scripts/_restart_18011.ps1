$c = Get-NetTCPConnection -LocalPort 18011 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty OwningProcess
if ($c) { Stop-Process -Id $c -Force }
Start-Sleep -Seconds 3
$c2 = Get-NetTCPConnection -LocalPort 18011 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty OwningProcess
Write-Output ("old=" + $c + " new=" + $c2)
