# codex-commander-loop.ps1 : AI24X Codex Commander autonomous duty loop.
# Triggered by scheduled task every 2h. ASCII-only (prompt is a UTF-8 md file).
# Cheap pre-check first: only invoke Codex (LLM) when there are actionable planned goals.
param([int]$TimeoutSec = 300)

$ErrorActionPreference = 'Continue'
$WorkDir = 'E:\AI24X\ai24x-website\ai24x01'
$GoalsFile = 'E:\AI24X\OpenClaw\workspace\ops\goal-engine\goals.json'
$PromptFile = Join-Path $PSScriptRoot 'codex-commander-duty-prompt.md'
$OpsDir = 'E:\AI24X\OpenClaw\workspace\ops'
$Stamp = Get-Date -Format 'yyyyMMdd-HHmm'
$LogFile = Join-Path $OpsDir "codex-commander-$Stamp.log"
$ReplyFile = Join-Path $OpsDir "codex-commander-$Stamp.reply.txt"
$LockFile = Join-Path $OpsDir 'codex-commander.lock'

# 0) lock: skip if a previous run is still in progress (< 25 min).
if (Test-Path -LiteralPath $LockFile) {
  $lockAge = ((Get-Date) - (Get-Item -LiteralPath $LockFile).LastWriteTime).TotalMinutes
  if ($lockAge -lt 25) {
    Add-Content -LiteralPath $LogFile -Value ("SKIP-LOCKED age=" + [int]$lockAge + "min") -Encoding UTF8
    exit 0
  }
}
Set-Content -LiteralPath $LockFile -Value (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') -Encoding UTF8

# 0b) DeepSeek peak-price guard: skip the LLM invocation during weekday peak
#     hours (peak = 09:00-11:59 / 14:00-17:59 CST; weekends are all off-peak).
#     The scheduled task still runs (free pre-check), but the expensive Codex
#     exec is deferred to the next valley/weekend run.
$now = Get-Date
$isWeekend = $now.DayOfWeek -in @('Saturday', 'Sunday')
$hour = $now.Hour
$isPeak = (-not $isWeekend) -and (($hour -ge 9 -and $hour -lt 12) -or ($hour -ge 14 -and $hour -lt 18))
if ($isPeak) {
  Add-Content -LiteralPath $LogFile -Value ("PEAK-SKIP hour=" + $hour + " (DeepSeek peak price; deferred to valley run)") -Encoding UTF8
  Remove-Item -LiteralPath $LockFile -Force -ErrorAction SilentlyContinue
  exit 0
}

# 1) cheap pre-check (no LLM): count planned + unblocked + not-approval goals.
$actionable = 0
$names = @()
try {
  $goals = Get-Content -LiteralPath $GoalsFile -Raw -Encoding UTF8 | ConvertFrom-Json
  foreach ($g in $goals.goals) {
    $blocked = $false
    if ($g.block_reason) { $blocked = $true }
    if ($g.approval) { $blocked = $true }
    if ($g.status -eq 'planned' -and -not $blocked) {
      $actionable++
      if ($names.Count -lt 10) { $names += [string]$g.id }
    }
  }
} catch {
  Add-Content -LiteralPath $LogFile -Value "PRE-CHECK-ERROR: $($_.Exception.Message)" -Encoding UTF8
  Remove-Item -LiteralPath $LockFile -Force -ErrorAction SilentlyContinue
  exit 0
}

if ($actionable -le 0) {
  Add-Content -LiteralPath $LogFile -Value "NO-ACTIONABLE (planned+unblocked=0)" -Encoding UTF8
  Remove-Item -LiteralPath $LockFile -Force -ErrorAction SilentlyContinue
  exit 0
}

# 2) invoke Codex (ephemeral) with the duty prompt.
if (-not (Test-Path -LiteralPath $PromptFile)) {
  Add-Content -LiteralPath $LogFile -Value "MISSING-PROMPT-FILE: $PromptFile" -Encoding UTF8
  Remove-Item -LiteralPath $LockFile -Force -ErrorAction SilentlyContinue
  exit 0
}
$prompt = Get-Content -LiteralPath $PromptFile -Raw -Encoding UTF8
$hint = "`n`n[pre-check hint] actionable goal ids: $($names -join ', ')."
$prompt = $prompt + $hint

$env:CODEX_HOME = 'C:\Users\Admin\.codex'
$OutputEncoding = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$out = $prompt | & codex exec --ephemeral -C $WorkDir --skip-git-repo-check --sandbox danger-full-access -c "notify=[]" -o $ReplyFile - 2>&1
$code = $LASTEXITCODE
$out | Out-File -FilePath $LogFile -Encoding utf8
Add-Content -LiteralPath $LogFile -Value ("CODEX-EXIT=" + $code) -Encoding UTF8
Remove-Item -LiteralPath $LockFile -Force -ErrorAction SilentlyContinue
exit $code
