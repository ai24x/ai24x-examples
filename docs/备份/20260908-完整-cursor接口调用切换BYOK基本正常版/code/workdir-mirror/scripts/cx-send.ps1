# cx-send.ps1 : Codex -> main-brain (openclaw) immediate trigger (no 10-min bridge polling wait)
# Usage: powershell -File cx-send.ps1 -InstrFile <instruction file absolute path>
# Notes: instruction file is first written by Codex into the tx/rx dir (persistent record + fallback),
#        then main-brain is triggered immediately. Bridge cron polling is fallback only.
param(
  [Parameter(Mandatory=$true)][string]$InstrFile,
  [int]$TimeoutSec = 90
)
$ErrorActionPreference = 'Continue'

if (-not (Test-Path -LiteralPath $InstrFile)) {
  Write-Output "CX-SEND ERROR: file not found: $InstrFile"
  exit 1
}

$env:OPENCLAW_STATE_DIR = 'E:\AI24X\OpenClaw'
Write-Output "CX-SEND: triggering main-brain with $InstrFile"
$out = openclaw agent --agent main --message-file $InstrFile --json --timeout $TimeoutSec 2>&1
$code = $LASTEXITCODE
Write-Output "CX-SEND exit=$code"
if ($out) {
  Write-Output "--- main-brain output ---"
  Write-Output ($out -join "`n")
}
if ($code -eq 0) {
  Write-Output "CX-SEND OK: main-brain accepted (async execution continues if timed out)"
} else {
  Write-Output "CX-SEND WARN: trigger returned exit=$code; bridge cron will catch it as fallback"
}
