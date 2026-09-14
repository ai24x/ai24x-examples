$ErrorActionPreference = "Continue"
Write-Host "=== where ==="
Get-Command openclaw -ErrorAction SilentlyContinue | Format-List
Get-Command node -ErrorAction SilentlyContinue | Select-Object Source
Write-Host "=== services ==="
Get-Service | Where-Object { $_.Name -match 'openclaw|claw' } | Format-Table Name, Status -AutoSize
Write-Host "=== processes ==="
Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -and ($_.CommandLine -match 'openclaw') } |
  ForEach-Object {
    $cl = $_.CommandLine
    if ($cl.Length -gt 180) { $cl = $cl.Substring(0,180) }
    Write-Host ("pid={0} ppid={1} cl={2}" -f $_.ProcessId, $_.ParentProcessId, $cl)
  }
Write-Host "=== scheduled tasks ==="
Get-ScheduledTask -ErrorAction SilentlyContinue |
  Where-Object { $_.TaskName -match 'openclaw|claw' } |
  ForEach-Object { Write-Host $_.TaskPath $_.TaskName $_.State }

# common install paths
@(
  "$env:USERPROFILE\AppData\Roaming\npm\openclaw.cmd",
  "$env:USERPROFILE\AppData\Roaming\npm\openclaw",
  "C:\Program Files\nodejs\openclaw.cmd",
  "$env:USERPROFILE\.openclaw\*"
) | ForEach-Object { if (Test-Path $_) { Write-Host "path=$_" } }

# try npm global bin
$npm = Get-Command npm -ErrorAction SilentlyContinue
if ($npm) {
  Write-Host "npm root -g:"; npm root -g
  Write-Host "npm bin -g:"; npm bin -g 2>$null
  $bin = (npm prefix -g)
  Write-Host "npm prefix -g: $bin"
  if (Test-Path "$bin\openclaw.cmd") { Write-Host "FOUND $bin\openclaw.cmd" }
}
