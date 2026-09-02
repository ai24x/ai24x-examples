# === AI24X 04 preflight: block partial deploys ===
# Usage: powershell -File scripts\preflight_04_scope.ps1 [-AllowDirty]
param(
  [switch]$AllowDirty,
  [string]$RepoRoot = ""
)

$ErrorActionPreference = "Stop"
if (-not $RepoRoot) {
  $RepoRoot = Split-Path $PSScriptRoot -Parent
}
Set-Location $RepoRoot

# Code that ships to 04 via git pull (exclude docs/shots/env noise)
$Watch = @(
  "api/",
  "web/",
  "p/open/api/",
  "p/open/web/",
  "p/markets/api/",
  "p/markets/web/",
  "scripts/deploy04",
  "scripts/preflight_04"
)

function Test-Watched([string]$path) {
  $p = ($path -replace "\\", "/").TrimStart("./")
  # noise exclusions
  if ($p -match '(^|/)\.env$' -or $p -match '\.env\.local$') { return $false }
  if ($p -match '\.(png|jpg|jpeg|webp|gif)$') { return $false }
  if ($p -match '(^|/)(_qa_shots|_shots_|_shot_)') { return $false }
  if ($p -match '(^|/)docs/') { return $false }
  if ($p -match '/_tmp_' -or $p -match '/_qa_') { return $false }
  foreach ($w in $Watch) {
    if ($p.StartsWith($w) -or $p -like ($w.TrimEnd("/") + "/*")) { return $true }
    # allow scripts/deploy04*.ps1 prefix match
    if ($w.StartsWith("scripts/") -and $p.StartsWith($w)) { return $true }
  }
  return $false
}

Write-Host "== preflight_04_scope ==" -ForegroundColor Cyan

$unpushed = @()
try {
  $unpushed = @(git log origin/master..HEAD --oneline 2>$null)
} catch {
  $unpushed = @()
}
if ($unpushed.Count -gt 0) {
  Write-Host ("!! " + $unpushed.Count + " local commit(s) not on origin (04 cannot pull):") -ForegroundColor Yellow
  $unpushed | Select-Object -First 20 | ForEach-Object { Write-Host ("   " + $_) }
  if (-not $AllowDirty) {
    Write-Host "Fix: git push origin master (and gitee). Or pass -AllowDirty." -ForegroundColor Yellow
    exit 1
  }
} else {
  Write-Host "OK: origin/master includes local HEAD" -ForegroundColor Green
}

$status = @(git status --porcelain)
$dirty = @()
foreach ($line in $status) {
  if (-not $line) { continue }
  $path = $line.Substring(3).Trim()
  if ($path -match " -> ") { $path = ($path -split " -> ")[-1].Trim() }
  $path = $path.Trim('"')
  if (Test-Watched $path) { $dirty += ($line.Substring(0, 2) + " " + $path) }
}

if ($dirty.Count -gt 0) {
  Write-Host ("!! " + $dirty.Count + " uncommitted production path change(s) would be missed by 04:") -ForegroundColor Red
  $dirty | Select-Object -First 40 | ForEach-Object { Write-Host ("   " + $_) }
  Write-Host "Fix: git add <files> -> commit -> push gitee+origin. Or -AllowDirty." -ForegroundColor Yellow
  if (-not $AllowDirty) {
    exit 1
  }
  Write-Host "WARN: -AllowDirty set; dirty files will NOT go to 04" -ForegroundColor Yellow
} else {
  Write-Host "OK: production paths clean" -ForegroundColor Green
}

Write-Host "Tip: if you changed console/locales, bump ?v= in the same commit." -ForegroundColor DarkGray
Write-Host "preflight OK" -ForegroundColor Green
exit 0
