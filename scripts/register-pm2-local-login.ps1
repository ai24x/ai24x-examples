#Requires -Version 5.1
<#
  Registers a Windows scheduled task: on user logon, run pm2 resurrect for this repo.
  Prerequisite: at least once run start_local.bat (or pm2 start ecosystem.local.config.js) then: pm2 save

  Usage (from repo root, PowerShell):
    powershell -ExecutionPolicy Bypass -File .\scripts\register-pm2-local-login.ps1
#>
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$batPath = Join-Path $scriptDir "pm2-resurrect-local.bat"

if (-not (Test-Path -LiteralPath $batPath)) {
  throw "Missing: $batPath"
}
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot "ecosystem.local.config.js"))) {
  throw "Repo root looks wrong (no ecosystem.local.config.js): $repoRoot"
}

$taskName = "AI24X-PM2-Local-Dev"

Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

# Prefer schtasks: more reliable across Windows builds than Register-ScheduledTask + principal combos.
# /sc onlogon = current user logon; /f = overwrite if exists.
$trArg = "`"$batPath`""
$exit = 0
& schtasks.exe /create /tn $taskName /tr $trArg /sc onlogon /rl LIMITED /f 2>&1 | ForEach-Object { Write-Host $_ }
if ($LASTEXITCODE -ne 0) {
  # Fallback: interactive task (some builds reject /rl LIMITED here)
  & schtasks.exe /delete /tn $taskName /f 2>$null
  & schtasks.exe /create /tn $taskName /tr $trArg /sc onlogon /f 2>&1 | ForEach-Object { Write-Host $_ }
  if ($LASTEXITCODE -ne 0) { $exit = $LASTEXITCODE }
} else {
  $exit = 0
}

if ($exit -ne 0) {
  throw "schtasks failed (exit $exit). Try: right-click PowerShell -> Run as Administrator, then run this script again."
}

Write-Host "OK: Scheduled task '$taskName' registered for user logon (schtasks)."
Write-Host "Bat: $batPath"
Write-Host "Tip: If resurrect does nothing, run start_local.bat once then: pm2 save"
