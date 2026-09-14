$ErrorActionPreference = "Stop"
$Nssm = "C:\nssm\nssm.exe"
$core = ((& $Nssm get AI24X-core AppParameters 2>&1 | Out-String) -replace "`0","").Trim()
$open = ((& $Nssm get AI24X-open-api AppParameters 2>&1 | Out-String) -replace "`0","").Trim()
Write-Host "core=$core"
Write-Host "open=$open"
$procs = Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" | Where-Object {
  $_.CommandLine -and $_.CommandLine -like '*8002*'
}
Write-Host ("python*8002 count=" + @($procs).Count)
foreach ($p in @($procs)) {
  $cl = $p.CommandLine
  if ($cl.Length -gt 140) { $cl = $cl.Substring(0,140) + "..." }
  Write-Host ("  pid=" + $p.ProcessId + " " + $cl)
}
$ph = Invoke-RestMethod -UseBasicParsing -Uri "https://api.ai24x.com/health"
Write-Host ("health=" + $ph.status + " commit=" + $ph.commit)
# quick loop health x3
1..3 | ForEach-Object {
  $t0 = Get-Date
  $h = Invoke-RestMethod -UseBasicParsing -Uri "https://api.ai24x.com/health"
  $ms = [int]((Get-Date) - $t0).TotalMilliseconds
  Write-Host ("health_probe $_ ms=$ms commit=" + $h.commit)
}
if ($core -notlike '*--workers 4*') { throw 'core workers missing' }
Write-Host 'VERIFY_OK'
