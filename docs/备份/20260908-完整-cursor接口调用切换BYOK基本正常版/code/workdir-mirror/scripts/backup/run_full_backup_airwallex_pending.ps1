# Full backup -> E:\AI24X\bak  (date + OK tag, rollback-ready)
# Fixes: normalize postgresql+psycopg:// before DSN dedupe; pg_dump timeout.
$ErrorActionPreference = "Continue"
$SourceRoot = "E:\AI24X\ai24x-website\ai24x01"
$BakRoot = "E:\AI24X\bak"
$Ts = Get-Date -Format "yyyyMMdd_HHmmss"
$StampDate = Get-Date -Format "yyyy-MM-dd"
$BackupNote = "待Airwallex空中云汇接入：本地集成 Airwallex（国际卡收单）前的完整基线备份（代码+数据库+env，可回滚）"
$OkTag = "OK待Airwallex空中云汇接入"
$BackupName = "ai24x01-$Ts-$OkTag"
$Dest = Join-Path $BakRoot $BackupName
$DbDir = Join-Path $Dest "databases"
$LogDir = Join-Path $Dest "_backup_meta"
$PgBin = "C:\Program Files\PostgreSQL\15\bin"
$PgDumpTimeoutSec = 180

New-Item -ItemType Directory -Force -Path $Dest, $DbDir, $LogDir | Out-Null
$LogFile = Join-Path $LogDir "backup.log"

function Log([string]$msg) {
  $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $msg
  Add-Content -Path $LogFile -Value $line -Encoding UTF8
  Write-Host $line
}

function Normalize-Dsn([string]$url) {
  if ([string]::IsNullOrWhiteSpace($url)) { return "" }
  $dsn = $url.Trim()
  $dsn = $dsn -replace '^postgresql\+psycopg2://', 'postgresql://'
  $dsn = $dsn -replace '^postgresql\+psycopg://', 'postgresql://'
  $dsn = $dsn -replace '^postgres\+psycopg2://', 'postgresql://'
  $dsn = $dsn -replace '^postgres\+psycopg://', 'postgresql://'
  $dsn = $dsn -replace '^postgres://', 'postgresql://'
  return $dsn
}

Log "START backup -> $Dest"
Log "Source: $SourceRoot"
Log "Tag: $OkTag / $StampDate"

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
  "/NFL", "/NDL", "/NP", "/XF", "*.pyc", "*.log", "nul"
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
    Log ("SQLite OK: {0} size={1}" -f $t.Name, (Get-Item $dst).Length)
  } else {
    Log ("SQLite SKIP missing: {0}" -f $t.Rel)
  }
}

$EnvSnap = Join-Path $Dest "env_snapshots"
New-Item -ItemType Directory -Force -Path $EnvSnap | Out-Null
if (Test-Path "C:\env-pack") {
  $EnvPackDest = Join-Path $EnvSnap "env-pack"
  New-Item -ItemType Directory -Force -Path $EnvPackDest | Out-Null
  Copy-Item -LiteralPath "C:\env-pack\*" -Destination $EnvPackDest -Recurse -Force
  Log "ENV OK: env-pack (core token env snapshot)"
} else {
  Log "ENV SKIP: C:\env-pack missing"
}
foreach ($rel in @("api\.env", "p\a\api\server\.env", "p\a1\api\server\.env", "p\fisher\api\server\.env")) {
  $src = Join-Path $SourceRoot $rel
  if (Test-Path $src) {
    Copy-Item -LiteralPath $src -Destination (Join-Path $EnvSnap ($rel -replace '[\\/]', '__')) -Force
    Log ("ENV OK: {0}" -f $rel)
  } else {
    Log ("ENV SKIP: {0}" -f $rel)
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
$DumpedDsns = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)

$PgJobs = @(
  @{ Label = "main_api"; Env = "api\.env"; UrlKeys = @("DATABASE_URL") },
  @{ Label = "p_a"; Env = "p\a\api\server\.env"; UrlKeys = @("AI24X_DATABASE_URL", "DATABASE_URL") },
  @{ Label = "p_a1"; Env = "p\a1\api\server\.env"; UrlKeys = @("AI24X_DATABASE_URL", "DATABASE_URL") },
  @{ Label = "fisher"; Env = "p\fisher\api\server\.env"; UrlKeys = @("FISHER_DATABASE_URL", "DATABASE_URL") }
  @{ Label = "core_token"; Env = "C:\env-pack\api.env"; UrlKeys = @("DATABASE_URL"); Fallback = "postgresql://ai24x_a:Ai24x%402026@127.0.0.1:5432/ai24x_core_pre" }
)

if (Test-Path $PgDump) {
  Log "pg_dump found"
  foreach ($job in $PgJobs) {
    $envPath = Join-Path $SourceRoot $job.Env
    if ([System.IO.Path]::IsPathRooted($job.Env)) { $envPath = $job.Env }
    $url = $null
    foreach ($k in $job.UrlKeys) {
      $url = Get-EnvValue $envPath $k
      if ($url) { break }
    }
    if (-not $url) {
      $url = $job.Fallback
      if (-not $url) {
        Log ("PG SKIP {0}: no URL" -f $job.Label)
        continue
      }
    }
    $dsn = Normalize-Dsn $url
    if (-not $DumpedDsns.Add($dsn)) {
      Log ("PG SKIP {0}: same DSN already dumped ({1})" -f $job.Label, (Mask-Url $dsn))
      Set-Content -LiteralPath (Join-Path $PgDir ("{0}-SAME-AS-PREVIOUS.txt" -f $job.Label)) -Value ("Same DSN. Masked=" + (Mask-Url $dsn)) -Encoding UTF8
      continue
    }
    $outFile = Join-Path $PgDir ("{0}-{1}.dump" -f $job.Label, $Ts)
    $errFile = Join-Path $LogDir ("pg_dump_{0}.err.txt" -f $job.Label)
    Log ("PG dump start: {0} url={1}" -f $job.Label, (Mask-Url $dsn))
    $psi = [System.Diagnostics.ProcessStartInfo]::new()
    $psi.FileName = $PgDump
    $psi.Arguments = ("-Fc -Z 6 -f `"{0}`" `"{1}`"" -f $outFile, $dsn)
    $psi.UseShellExecute = $false
    $psi.RedirectStandardError = $true
    $proc = [System.Diagnostics.Process]::Start($psi)
    if (-not $proc.WaitForExit($PgDumpTimeoutSec * 1000)) {
      try { $proc.Kill() } catch {}
      Log ("PG TIMEOUT: {0} after {1}s" -f $job.Label, $PgDumpTimeoutSec)
      [void]$PgFail.Add($job.Label)
      continue
    }
    $pgCode = $proc.ExitCode
    if ($pgCode -eq 0 -and (Test-Path $outFile) -and ((Get-Item $outFile).Length -gt 0)) {
      Log ("PG OK: {0} size={1}" -f $job.Label, (Get-Item $outFile).Length)
      [void]$PgOk.Add($job.Label)
    } else {
      Log ("PG FAIL: {0} exit={1}" -f $job.Label, $pgCode)
      [void]$PgFail.Add($job.Label)
    }
  }
} else {
  Log "WARN: pg_dump not found"
}

$shaShort = ""
$GitInfo = Join-Path $LogDir "git_tip.txt"
Push-Location $SourceRoot
try {
  $branch = git rev-parse --abbrev-ref HEAD 2>$null
  $sha = git rev-parse HEAD 2>$null
  if ($sha) { $shaShort = $sha.Substring(0, [Math]::Min(12, $sha.Length)) }
  $status = git status -sb 2>$null
  [System.IO.File]::WriteAllText($GitInfo, "branch: $branch`nsha: $sha`nstatus:`n$status`n", [System.Text.UTF8Encoding]::new($false))
  Log ("Git tip: {0} @ {1}" -f $branch, $sha)
  $bundle = Join-Path $Dest "ai24x01.bundle"
  Log "Creating git bundle..."
  git bundle create $bundle --all 2>$null
  if (Test-Path $bundle) { Log ("Git bundle OK size={0}" -f (Get-Item $bundle).Length) }
} catch {
  Log "Git tip/bundle skipped"
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
$totalMB = [math]::Round(((Get-ChildItem -LiteralPath $Dest -Recurse -File -EA SilentlyContinue | Measure-Object Length -Sum).Sum / 1MB), 2)
$nowStr = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$pgOkStr = ($PgOk -join ", ")
$pgFailStr = ($PgFail -join ", ")

$mf = @"
# AI24X Full Backup — $OkTag

- **Name**: ``$BackupName``
- **Label**: $OkTag（$StampDate）
- **Time**: $nowStr
- **Source**: ``$SourceRoot``
- **Backup**: ``$Dest``
- **Git**: ``$shaShort``
- **Purpose**: 完整可回滚（代码 + env + 数据库）；主站 + AI行情站
- **Note**: ``$BackupNote``

## Contents

| Part | Path |
|------|------|
| Code | ``code/`` |
| Env | ``env_snapshots/``（含密钥，勿外传） |
| SQLite | ``databases/sqlite/`` |
| PostgreSQL | ``databases/pgsql/`` |
| Git bundle | ``ai24x01.bundle`` |
| Meta | ``_backup_meta/`` |

## Stats

- Code files: $codeFiles
- DB files: $dbFiles
- Env: $envCount
- Size MB: $totalMB
- PG OK: $pgOkStr
- PG FAIL/SKIP: $pgFailStr

## Rollback

见 ``ROLLBACK.md``。
"@
[System.IO.File]::WriteAllText((Join-Path $Dest "MANIFEST.md"), $mf, [System.Text.UTF8Encoding]::new($true))

$rb = @"
# 回滚速查 — $BackupName（$OkTag / $StampDate $nowStr）

> 备注：$BackupNote

## 代码

1. 停服务（本机 pm2 / 生产 a-api-8001 + core-api-8002）
2. 当前目录改名为 ai24x01-broken-<ts>
3. 复制本备份 ``code\`` 回 ``$SourceRoot``
4. 需要时从 ``env_snapshots\`` 还原 .env
5. 启动；生产 API 有疑：pm2 delete + start ecosystem.config.cjs
6. 验收 health / 登录 / build_stamp

## 数据库

- SQLite: 用 ``databases\sqlite\`` 覆盖对应 .db
- PG: 先对新库再 dump，再 ``pg_restore --clean --if-exists -d <URL> databases\pgsql\*.dump``

## Git bundle（可选）

``git clone ai24x01.bundle ai24x01-restore``
"@
[System.IO.File]::WriteAllText((Join-Path $Dest "ROLLBACK.md"), $rb, [System.Text.UTF8Encoding]::new($true))

$ptr = Join-Path $BakRoot ("LATEST_OK-" + $Ts + ".txt")
[System.IO.File]::WriteAllText($ptr, "BACKUP_PATH=$Dest`nTAG=$OkTag`nDATE=$StampDate`nTIME=$nowStr`nGIT=$shaShort`n", [System.Text.UTF8Encoding]::new($false))

Log ("DONE code={0} db={1} env={2} sizeMB={3}" -f $codeFiles, $dbFiles, $envCount, $totalMB)
Log "DONE BACKUP_PATH=$Dest"
Write-Output "BACKUP_PATH=$Dest"
exit 0



