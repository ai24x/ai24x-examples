# Daily full backup wrapper: full backup + retention
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File run_daily_backup.ps1
$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$FullScript = Join-Path $Root "run_full_backup_ok_label.ps1"
$BakRoot = "E:\AI24X\bak"
$KeepDays = 14
$MinKeep = 3

Write-Output "[daily] START $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
# Run full backup in a child powershell so its `exit` does not kill this wrapper
& powershell -NoProfile -ExecutionPolicy Bypass -File $FullScript
if ($LASTEXITCODE -ne 0) {
  Write-Error "[daily] full backup failed exit=$LASTEXITCODE"
  exit 1
}

# Retention: keep newest $MinKeep, and anything newer than $KeepDays
$targets = @(Get-ChildItem -LiteralPath $BakRoot -Directory -Filter "ai24x01-*" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending)
$cutoff = (Get-Date).AddDays(-$KeepDays)
$toDelete = @()
for ($i = $MinKeep; $i -lt $targets.Count; $i++) {
  if ($targets[$i].LastWriteTime -lt $cutoff) { $toDelete += $targets[$i] }
}
$resolvedRoot = $BakRoot.TrimEnd('\') + '\'
$pruned = 0
$warned = 0
foreach ($t in $toDelete) {
  # Safety: only delete under BakRoot (use raw FullName; GetFullPath mangles reserved names like "nul")
  if (-not $t.FullName.StartsWith($resolvedRoot, [System.StringComparison]::OrdinalIgnoreCase)) { continue }
  try {
    Remove-Item -LiteralPath ("\\?\" + $t.FullName) -Recurse -Force -ErrorAction Stop
    Write-Output "[daily] PRUNED $($t.FullName)"
    $pruned++
  } catch {
    $warned++
    Write-Output "[daily] WARN prune failed: $($t.FullName) -> $($_.Exception.Message)"
  }
}
Write-Output "[daily] retention done kept=$($targets.Count - $pruned) pruned=$pruned warn=$warned"
Write-Output "[daily] DONE $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
exit 0
