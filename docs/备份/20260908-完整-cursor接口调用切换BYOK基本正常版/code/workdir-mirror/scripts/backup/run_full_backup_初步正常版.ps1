# Full backup: main site + AI market officer -> E:\AI24X\bak
# Label: date + 初步正常版 (rollback-ready)
# ASCII-only source (avoid PS encoding issues on Chinese tags in script body where possible).
$ErrorActionPreference = "Continue"
$SourceRoot = "E:\AI24X\ai24x-website\ai24x01"
$BakRoot = "E:\AI24X\bak"
$Ts = Get-Date -Format "yyyyMMdd_HHmmss"
$StampDate = Get-Date -Format "yyyy-MM-dd"
# 初步正常版
$OkTag = [string]([char]0x521D) + [char]0x6B65 + [char]0x6B63 + [char]0x5E38 + [char]0x7248
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
$DumpedDsns = New-Object 'System.Collections.Generic.HashSet[string]'

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
    if (-not $DumpedDsns.Add($dsn)) {
      Log ("PG SKIP {0}: same DSN already dumped" -f $job.Label)
      # still write a pointer note
      $note = Join-Path $PgDir ("{0}-SAME-AS-PREVIOUS.txt" -f $job.Label)
      Set-Content -LiteralPath $note -Value ("Same DSN as another dump in this backup. Masked=" + (Mask-Url $dsn)) -Encoding UTF8
      continue
    }
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

  # Extra: git bundle for code-history rollback without full tree
  $bundle = Join-Path $Dest "ai24x01.bundle"
  Log "Creating git bundle..."
  git bundle create $bundle --all 2>$null
  if (Test-Path $bundle) {
    Log ("Git bundle OK size={0}" -f (Get-Item $bundle).Length)
  } else {
    Log "Git bundle SKIP/FAIL"
  }
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
$totalBytes = (
  Get-ChildItem -LiteralPath $Dest -Recurse -File -ErrorAction SilentlyContinue |
  Measure-Object -Property Length -Sum
).Sum
$totalMB = [math]::Round(($totalBytes / 1MB), 2)

$pgOkStr = ($PgOk -join ", ")
$pgFailStr = ($PgFail -join ", ")
$nowStr = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$shaShort = ""
if (Test-Path $GitInfo) {
  $m = Select-String -LiteralPath $GitInfo -Pattern '^sha:\s*(\S+)' | Select-Object -First 1
  if ($m) { $shaShort = $m.Matches.Groups[1].Value.Substring(0, [Math]::Min(12, $m.Matches.Groups[1].Value.Length)) }
}

$mf = @"
# AI24X Full Backup — $OkTag

- **Name**: ``$BackupName``
- **Label**: $OkTag（$StampDate，登录/发版事故修复后可回滚点）
- **Time**: $nowStr
- **Source**: ``$SourceRoot``
- **Backup**: ``$Dest``
- **Git**: ``$shaShort``
- **Purpose**: 完整回滚（代码 + env + 数据库）；含主站与 AI 行情站

## Contents

| Part | Path | Notes |
|------|------|-------|
| Code | ``code/`` | 主站 web/api + p/a + p/a1 + fisher 等 |
| Env | ``env_snapshots/`` | 各服务 .env（含密钥，勿外传） |
| SQLite | ``databases/sqlite/`` | 冷拷贝 |
| PostgreSQL | ``databases/pgsql/`` | pg_dump -Fc |
| Git bundle | ``ai24x01.bundle`` | 可用 ``git clone ai24x01.bundle`` 还原历史 |
| Meta | ``_backup_meta/`` | 日志、git tip |

## Stats

- Code files: $codeFiles
- DB files: $dbFiles
- Env snapshots: $envCount
- Size MB: $totalMB
- PG OK: $pgOkStr
- PG FAIL/SKIP: $pgFailStr

## Scope

- 主站: ``web/`` + ``api/``
- AI 行情站: ``p/a1/``（及兼容 ``p/a/``）
- 其它子项目随 ``code/`` 一并备份

## Rollback Runbook

详见同目录 ``ROLLBACK.md``。

## Security

含 .env 与全库 dump，**禁止**上传公开网盘/公开仓库。
"@

$Manifest = Join-Path $Dest "MANIFEST.md"
[System.IO.File]::WriteAllText($Manifest, $mf, [System.Text.UTF8Encoding]::new($true))

$rb = @"
# 回滚速查 — $BackupName（$OkTag）

## A. 回滚代码（主站 + 行情站）

1. 停止相关服务（本机：``pm2 stop core-8000 a1-api-18011 a1-web-18001``；生产：``a-api-8001`` / ``core-api-8002``）
2. 将当前 ``$SourceRoot`` 改名为 ``ai24x01-broken-<时间戳>``
3. 把本备份 ``code\`` 整棵复制回 ``$SourceRoot``
4. 如需一并恢复密钥：从 ``env_snapshots\`` 按文件名还原到对应 `.env`（行级核对，勿整文件乱覆盖损坏）
5. 启动服务；生产 API 有疑用 ``pm2 delete`` + ``pm2 start ecosystem.config.cjs --only ...``
6. 验收：主站 /health；行情 ``/api/public/build_stamp``；登录

## B. 仅回滚 SQLite

1. 停写
2. 用 ``databases\sqlite\`` 覆盖运行中的对应 .db
3. 启动并验证

## C. 回滚 PostgreSQL

1. **先**对当前库再 dump 一份（防二次事故）
2. ``pg_restore --clean --if-exists -d <DATABASE_URL> databases\pgsql\<label>-$Ts.dump``
3. 主站用 ``api\.env`` 的 DATABASE_URL；行情用 ``p\a1\api\server\.env`` 的 AI24X_DATABASE_URL

## D. 用 git bundle 回代码历史（可选）

```text
git clone ai24x01.bundle ai24x01-restore
cd ai24x01-restore
git checkout master
```

## E. 验收清单

- [ ] 主站页面有样式、API health 200
- [ ] 行情官登录成功（非「登录已失效」）
- [ ] build_stamp / billing plans 正常
"@
[System.IO.File]::WriteAllText((Join-Path $Dest "ROLLBACK.md"), $rb, [System.Text.UTF8Encoding]::new($true))

# Pointer file with ASCII path for easy discovery
$ptr = Join-Path $BakRoot ("LATEST_OK_POINTER-" + $Ts + ".txt")
[System.IO.File]::WriteAllText($ptr, ("BACKUP_PATH=" + $Dest + "`nTAG=" + $OkTag + "`nDATE=" + $StampDate + "`nGIT=" + $shaShort + "`n"), [System.Text.UTF8Encoding]::new($false))

Log ("Manifest written. code={0} db={1} env={2} sizeMB={3}" -f $codeFiles, $dbFiles, $envCount, $totalMB)
Log "DONE BACKUP_PATH=$Dest"
Write-Output "BACKUP_PATH=$Dest"
exit 0
