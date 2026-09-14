# Register daily BYOK Pro renewal reminder on Windows (副脑04 / open-api).
# Usage: powershell -ExecutionPolicy Bypass -File scripts\register_byok_renewal_cron.ps1
$ErrorActionPreference = "Stop"
$TaskName = "AI24X-BYOK-RenewalRemind"
$Repo = Split-Path $PSScriptRoot -Parent
$Py = Join-Path $Repo "p\open\api\scripts_byok_renewal_remind.py"
$Work = Join-Path $Repo "p\open\api"
$LogDir = Join-Path $Repo "ops\logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Log = Join-Path $LogDir "byok_renewal.log"

if (-not (Test-Path $Py)) { throw "missing $Py" }

$action = New-ScheduledTaskAction -Execute "python" -Argument "`"$Py`" --apply --lang en >> `"$Log`" 2>&1" -WorkingDirectory $Work
$trigger = New-ScheduledTaskTrigger -Daily -At 09:00
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
Write-Host "OK registered $TaskName daily 09:00 -> $Py --apply"
