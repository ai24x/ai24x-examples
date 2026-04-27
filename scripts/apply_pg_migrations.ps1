param(
  [string]$Root = "C:\ai24x01",
  [string]$EnvFile = "",
  [string]$PgBin = "C:\Program Files\PostgreSQL\15\bin",
  [string]$MigrationsDir = "",
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Die([string]$msg) { throw $msg }

if ([string]::IsNullOrWhiteSpace($EnvFile)) {
  $EnvFile = Join-Path $Root "p\a1\api\server\.env"
}
if ([string]::IsNullOrWhiteSpace($MigrationsDir)) {
  $MigrationsDir = Join-Path $Root "db\migrations"
}

if (!(Test-Path $Root)) { Die "ROOT not found: $Root" }
if (!(Test-Path $EnvFile)) { Die "EnvFile not found: $EnvFile" }
if (!(Test-Path $MigrationsDir)) { Die "MigrationsDir not found: $MigrationsDir" }

$psql = Join-Path $PgBin "psql.exe"
if (!(Test-Path $psql)) { Die "psql.exe not found: $psql" }

$dsnLine = (Get-Content $EnvFile | Where-Object { $_ -like "AI24X_DATABASE_URL=*" } | Select-Object -First 1)
if ([string]::IsNullOrWhiteSpace([string]$dsnLine)) { Die "AI24X_DATABASE_URL missing in $EnvFile" }
$dsn = ($dsnLine -split "=",2)[1].Trim()
if ([string]::IsNullOrWhiteSpace([string]$dsn)) { Die "AI24X_DATABASE_URL empty in $EnvFile" }

Write-Host ("ROOT=" + $Root)
Write-Host ("ENV=" + $EnvFile)
Write-Host ("MIGRATIONS=" + $MigrationsDir)
Write-Host ("DSN=" + ($dsn -replace ":(.*?)@", ":***@"))

if ($DryRun) {
  Write-Host "DryRun=ON (will not execute SQL)."
}

# Ensure migration table exists
$initSql = @"
CREATE TABLE IF NOT EXISTS schema_migrations(
  id TEXT PRIMARY KEY,
  applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"@

if (-not $DryRun) {
  & $psql "$dsn" -v ON_ERROR_STOP=1 -c $initSql | Out-Null
}

$files = Get-ChildItem -Path $MigrationsDir -Filter "*.sql" | Sort-Object Name
if ($files.Count -eq 0) {
  Write-Host "No migrations (*.sql) found. Done."
  exit 0
}

foreach ($f in $files) {
  $id = $f.Name

  $checkSql = "SELECT 1 FROM schema_migrations WHERE id='$id' LIMIT 1;"
  $already = $false
  if (-not $DryRun) {
    $out = & $psql "$dsn" -t -A -v ON_ERROR_STOP=1 -c $checkSql
    if (($out | Out-String).Trim() -eq "1") { $already = $true }
  }

  if ($already) {
    Write-Host ("SKIP " + $id)
    continue
  }

  Write-Host ("APPLY " + $id)
  if ($DryRun) { continue }

  & $psql "$dsn" -v ON_ERROR_STOP=1 -f $f.FullName | Out-Null

  $markSql = "INSERT INTO schema_migrations(id) VALUES ('$id');"
  & $psql "$dsn" -v ON_ERROR_STOP=1 -c $markSql | Out-Null
}

Write-Host "OK: migrations applied."

