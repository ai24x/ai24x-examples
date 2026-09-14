# === AI24X deploy04 ASYNC (long-task dispatch) ===
# Usage: powershell -File scripts\deploy04_async.ps1 <task-md>
# Sends task to 04 and triggers openclaw in BACKGROUND via runner (returns ~5-10s).
# 04 sends group receipt via Feishu when done. Progress: ssh ... "dir ops\<task>.out.log"
param([Parameter(Mandatory=$true)][string]$TaskFile)

$ErrorActionPreference = "Stop"
$SshHost = "Administrator@43.160.246.30"
$RemoteOps = "C:\Users\Administrator\ops"
$TaskName = Split-Path $TaskFile -Leaf
$RemoteTask = "$RemoteOps\$TaskName"

$RunnerLocal = Join-Path $env:TEMP "run_async_04.ps1"
$RunnerRemote = "$RemoteOps\run_async_04.ps1"

# build runner (ASCII only, here-string keeps $ literal)
$runnerBody = @'
param([string]$TaskFile)
$LogFile = "$TaskFile.out.log"
$argLine = 'openclaw agent --agent main --message-file "' + $TaskFile + '" --json --timeout 600 > "' + $LogFile + '" 2>&1'
Start-Process -FilePath "cmd.exe" -ArgumentList "/c", $argLine -WindowStyle Hidden
Write-Output "ASYNC STARTED"
'@
Set-Content -LiteralPath $RunnerLocal -Value $runnerBody -Encoding UTF8

Write-Host "==> scp task + runner -> 04" -ForegroundColor Cyan
scp -o ConnectTimeout=20 -o StrictHostKeyChecking=no $TaskFile "${SshHost}:${RemoteTask}"
if ($LASTEXITCODE -ne 0) { throw "scp task FAILED" }
scp -o ConnectTimeout=20 -o StrictHostKeyChecking=no $RunnerLocal "${SshHost}:${RunnerRemote}"
if ($LASTEXITCODE -ne 0) { throw "scp runner FAILED" }

Write-Host "==> trigger background run on 04..." -ForegroundColor Cyan
ssh -o ConnectTimeout=20 -o StrictHostKeyChecking=no -o BatchMode=yes $SshHost "powershell -NoProfile -ExecutionPolicy Bypass -File $RunnerRemote $RemoteTask"
if ($LASTEXITCODE -ne 0) { throw "ssh trigger FAILED" }

Remove-Item -LiteralPath $RunnerLocal -Force -ErrorAction SilentlyContinue
Write-Host "==> ASYNC dispatched OK. 04 running in background; group receipt will follow." -ForegroundColor Green
Write-Host "    Progress: ssh $SshHost dir $RemoteOps\$TaskName.out.log"