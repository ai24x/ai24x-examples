# Full backup OK-version -> E:\AI24X\bak
# ASCII-only source to avoid Windows PowerShell encoding issues.
$ErrorActionPreference = "Continue"
$SourceRoot = "E:\AI24X\ai24x-website\ai24x01"
$BakRoot = "E:\AI24X\bak"
$Ts = Get-Date -Format "yyyyMMdd_HHmmss"
$StampDate = Get-Date -Format "yyyy-MM-dd"
$OkTag = "OK" + [char]0x7248
$BackupName = "ai24x01-$Ts-$OkTag"
$Dest = Join-Path $BakRoot $BackupName
$DbDir = Join-Path $Dest "databases"
$LogDir = Join-Path $Dest "_backup_meta"
$PgBin = "C:\Program Files\PostgreSQL\15\bin"

New-Item -ItemType Directory -Force -Path $Dest, $DbDir, $LogDir | Out-Null
$LogFile = Join-Path $LogDir "backup.log"

function Log([string]$msg) {
  $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $msg
  Add-Content -Path $LogFile -Value $line -Encoding UTF8
  Write-Host $line
}

Log "START backup -> $Dest"
Log "Source: $SourceRoot"

$ExcludeDirs = @(
  "node_modules", ".git", "__pycache__", ".venv", "venv",
  ".pytest_cache", ".mypy_cache", "dist", "build",
  ".workbuddy", ".codebuddy", "web_bak_0519_1636",
  "archive", "bak"
)
$XdArgs = @()
foreach ($d in $ExcludeDirs) { $XdArgs += "/XD"; $XdArgs += $d }

$CodeDest = Join-Path $Dest "code"
New-Item -ItemType Directory -Force -Path $CodeDest | Out-Null
Log "Robocopy program files..."
$rcLog = Join-Path $LogDir "robocopy.log"
$rcArgs = @(
  $SourceRoot, $CodeDest, "/E", "/COPY:DAT", "/R:1", "/W:1",
  "/NFL", "/NDL", "/NP", "/XF", "*.pyc", "*.log"
) + $XdArgs + @("/LOG:$rcLog")
& robocopy @rcArgs | Out-Null
$rc = $LASTEXITCODE
Log ("Robocopy exit code: {0} [0-7 = success]" -f $rc)
if ($rc -ge 8) { Log "ERROR: robocopy failed"; exit 1 }

$SqliteDir = Join-Path $DbDir "sqlite"
New-Item -ItemType Directory -Force -Path $SqliteDir | Out-Null
$SqliteTargets = @(
  @{ Rel = "api\data\api_auth.db"; Name = "main_api_auth.db" },
  @{ Rel = "data\ai24x.db"; Name = "root_ai24x.db" },
  @{ Rel = "p\a\api\server\data\ai24x.db"; Name = "p_a_ai24x.db" },
  @{ Rel = "p\a1\api\server\data\ai24x.db"; Name = "p_a1_ai24x.db" },
  @{ Rel = "p\fisher\api\server\data\fisher.db"; Name = "p_fisher_fisher.db" }
)
foreach ($t in $SqliteTargets) {
  $src = Join-Path $SourceRoot $t.Rel
  if (Test-Path $src) {
    $dst = Join-Path $SqliteDir $t.Name
    Copy-Item -LiteralPath $src -Destination $dst -Force
    $sz = (Get-Item $dst).Length
    Log ("SQLite OK: {0} -> {1} size={2}" -f $t.Rel, $t.Name, $sz)
  } else {
    Log ("SQLite SKIP missing: {0}" -f $t.Rel)
  }
}

$EnvSnap = Join-Path $Dest "env_snapshots"
New-Item -ItemType Directory -Force -Path $EnvSnap | Out-Null
$EnvFiles = @(
  "api\.env",
  "p\a\api\server\.env",
  "p\a1\api\server\.env",
  "p\fisher\api\server\.env"
)
foreach ($rel in $EnvFiles) {
  $src = Join-Path $SourceRoot $rel
  if (Test-Path $src) {
    $safeName = ($rel -replace '[\\/]', '__')
    Copy-Item -LiteralPath $src -Destination (Join-Path $EnvSnap $safeName) -Force
    Log ("ENV OK: {0}" -f $rel)
  } else {
    Log ("ENV SKIP missing: {0}" -f $rel)
  }
}

function Get-EnvValue([string]$envPath, [string]$key) {
  if (!(Test-Path $envPath)) { return $null }
  $line = Get-Content -LiteralPath $envPath -Encoding UTF8 |
    Where-Object { $_ -match ("^\s*" + [regex]::Escape($key) + "\s*=") } |
    Select-Object -First 1
  if (-not $line) { return $null }
  return (($line -split "=", 2)[1].Trim().Trim('"').Trim("'"))
}

function Mask-Url([string]$url) {
  if ([string]::IsNullOrWhiteSpace($url)) { return "" }
  return [regex]::Replace($url, '://([^:/@]+):([^@]+)@', '://$1:***@')
}

$PgDump = Join-Path $PgBin "pg_dump.exe"
$PgDir = Join-Path $DbDir "pgsql"
New-Item -ItemType Directory -Force -Path $PgDir | Out-Null
$PgOk = New-Object System.Collections.Generic.List[string]
$PgFail = New-Object System.Collections.Generic.List[string]

$PgJobs = @(
  @{ Label = "main_api"; Env = "api\.env"; UrlKeys = @("DATABASE_URL") },
  @{ Label = "p_a"; Env = "p\a\api\server\.env"; UrlKeys = @("AI24X_DATABASE_URL", "DATABASE_URL") },
  @{ Label = "p_a1"; Env = "p\a1\api\server\.env"; UrlKeys = @("AI24X_DATABASE_URL", "DATABASE_URL") },
  @{ Label = "fisher"; Env = "p\fisher\api\server\.env"; UrlKeys = @("FISHER_DATABASE_URL", "DATABASE_URL") }
)

if (Test-Path $PgDump) {
  Log "pg_dump found"
  foreach ($job in $PgJobs) {
    $envPath = Join-Path $SourceRoot $job.Env
    $url = $null
    foreach ($k in $job.UrlKeys) {
      $url = Get-EnvValue $envPath $k
      if ($url) { break }
    }
    if (-not $url) {
      Log ("PG SKIP {0}: no URL" -f $job.Label)
      continue
    }
    $dsn = $url -replace '^postgresql\+psycopg2://', 'postgresql://'
    $dsn = $dsn -replace '^postgres\+psycopg2://', 'postgresql://'
    $outFile = Join-Path $PgDir ("{0}-{1}.dump" -f $job.Label, $Ts)
    $errFile = Join-Path $LogDir ("pg_dump_{0}.err.txt" -f $job.Label)
    Log ("PG dump start: {0} url={1}" -f $job.Label, (Mask-Url $dsn))
    $p = Start-Process -FilePath $PgDump -ArgumentList @(
      "-Fc", "-Z", "6", "-f", $outFile, $dsn
    ) -Wait -PassThru -NoNewWindow -RedirectStandardError $errFile
    if ($p.ExitCode -eq 0 -and (Test-Path $outFile) -and ((Get-Item $outFile).Length -gt 0)) {
      Log ("PG OK: {0} size={1}" -f $job.Label, (Get-Item $outFile).Length)
      [void]$PgOk.Add($job.Label)
    } else {
      Log ("PG FAIL: {0} exit={1}" -f $job.Label, $p.ExitCode)
      [void]$PgFail.Add($job.Label)
    }
  }
} else {
  Log "WARN: pg_dump not found - SQLite only"
}

$GitInfo = Join-Path $LogDir "git_tip.txt"
Push-Location $SourceRoot
try {
  $branch = git rev-parse --abbrev-ref HEAD 2>$null
  $sha = git rev-parse HEAD 2>$null
  $status = git status -sb 2>$null
  $gitText = "branch: $branch`nsha: $sha`nstatus:`n$status`n"
  [System.IO.File]::WriteAllText($GitInfo, $gitText, [System.Text.UTF8Encoding]::new($false))
  Log ("Git tip: {0} @ {1}" -f $branch, $sha)
} catch {
  Log "Git tip skipped"
} finally {
  Pop-Location
}

function Count-Files([string]$path) {
  if (!(Test-Path $path)) { return 0 }
  return @(Get-ChildItem -LiteralPath $path -Recurse -File -ErrorAction SilentlyContinue).Count
}

$codeFiles = Count-Files $CodeDest
$dbFiles = Count-Files $DbDir
$envCount = Count-Files $EnvSnap
$totalBytes = (
  Get-ChildItem -LiteralPath $Dest -Recurse -File -ErrorAction SilentlyContinue |
  Measure-Object -Property Length -Sum
).Sum
$totalMB = [math]::Round(($totalBytes / 1MB), 2)

$pgOkStr = ($PgOk -join ", ")
$pgFailStr = ($PgFail -join ", ")
$nowStr = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

$mf = @"
# AI24X Full Backup ($OkTag)

- **Name**: ``$BackupName``
- **Note**: $OkTag + $StampDate
- **Time**: $nowStr
- **Source**: ``$SourceRoot``
- **Backup**: ``$Dest``
- **Purpose**: Full rollback (code + env + databases)

## Contents

| Part | Path | Notes |
|------|------|-------|
| Code | ``code/`` | Main site + subprojects a / a1 / fisher |
| Env | ``env_snapshots/`` | Service .env snapshots (SECRETS - do not share) |
| SQLite | ``databases/sqlite/`` | Cold copy DB files |
| PostgreSQL | ``databases/pgsql/`` | pg_dump -Fc custom format |
| Meta | ``_backup_meta/`` | Logs, git tip |

## Stats

- Code files: $codeFiles
- DB files: $dbFiles
- Env snapshots: $envCount
- Size MB: $totalMB
- PG OK: $pgOkStr
- PG FAIL/SKIP: $pgFailStr

## Scope

- Main: web/ + api/
- AI market officer: p/a/ + p/a1/
- Fisher: p/fisher/
- Other under p/ included in code/

## Rollback Runbook

### A. Rollback code

1. Stop services (PM2 / uvicorn / static)
2. Rename current ``$SourceRoot`` to ``ai24x01-broken-<timestamp>``
3. Copy ``code\`` from this backup to ``$SourceRoot``
4. Restore ``.env`` from ``env_snapshots\`` if needed
5. Start services and health-check

### B. Rollback SQLite

1. Stop write traffic
2. Overwrite runtime .db with files under ``databases\sqlite\``
3. Start and verify

### C. Rollback PostgreSQL

1. Take a fresh snapshot of current DB BEFORE restore
2. Run: pg_restore --clean --if-exists -d <DATABASE_URL> databases\pgsql\<label>-$Ts.dump

### D. Verify

1. Main site CSS/API OK
2. AI market officer login + quota path
3. fisher core APIs if enabled

## Security

This folder contains .env and full DBs. Do not upload to public repos.
"@

$Manifest = Join-Path $Dest "MANIFEST.md"
[System.IO.File]::WriteAllText($Manifest, $mf, [System.Text.UTF8Encoding]::new($true))

$rb = @"
# Rollback cheat sheet ($BackupName)

## Code rollback

1. Stop services
2. Rename live tree to broken-*
3. Copy this backup code\ to live root
4. Restore env_snapshots if needed
5. Start services

## DB

- SQLite: overwrite from databases\sqlite\
- PG: pg_restore --clean --if-exists -d <URL> databases\pgsql\*.dump
"@
[System.IO.File]::WriteAllText((Join-Path $Dest "ROLLBACK.md"), $rb, [System.Text.UTF8Encoding]::new($true))

Log ("Manifest written. code={0} db={1} env={2} sizeMB={3}" -f $codeFiles, $dbFiles, $envCount, $totalMB)
Log "DONE BACKUP_PATH=$Dest"
Write-Output "BACKUP_PATH=$Dest"
exit 0
