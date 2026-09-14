# AI行情官 a1 专项备份（支持回滚）——代码 + PostgreSQL 数据库 + .env
$ErrorActionPreference = "Continue"
$Source = "E:\AI24X\ai24x-website\ai24x01\p\a1"
$RepoRoot = "E:\AI24X\ai24x-website\ai24x01"
$BakRoot = "E:\AI24X\bak"
$Label = "AI行情官新增同花顺数据版本"
$Ts = Get-Date -Format "yyyyMMdd_HHmmss"
$Dest = Join-Path $BakRoot ("{0}-{1}" -f $Label, $Ts)
$DbDir = Join-Path $Dest "databases\pgsql"
$EnvDir = Join-Path $Dest "env_snapshots"
$MetaDir = Join-Path $Dest "_backup_meta"
New-Item -ItemType Directory -Force -Path $Dest, $DbDir, $EnvDir, $MetaDir | Out-Null
$LogFile = Join-Path $MetaDir "backup.log"
function Log([string]$m) { $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $m; Add-Content -Path $LogFile -Value $line -Encoding UTF8; Write-Host $line }

Log "START $Label backup -> $Dest"
if (-not (Test-Path $Source)) { Log "ERROR: source missing $Source"; exit 1 }

# 1) 代码（排除生成物/备份/内存）
$CodeDest = Join-Path $Dest "code"
$ExcludeDirs = @(".venv", "venv", "__pycache__", "logs", "web_bak_0519_1636", ".workbuddy", "signal_cache", "_chrome_profile5", "_chrome_profile", "_cdp_*")
$Xd = @(); foreach ($d in $ExcludeDirs) { $Xd += "/XD"; $Xd += $d }
$rcLog = Join-Path $MetaDir "robocopy.log"
& robocopy $Source $CodeDest /E /COPY:DAT /R:1 /W:1 /NFL /NDL /NP /XF "*.pyc" "*.log" @Xd /LOG:$rcLog | Out-Null
$rc = $LASTEXITCODE
Log ("Robocopy exit: {0} [0-7 OK]" -f $rc)
if ($rc -ge 8) { Log "ERROR robocopy"; exit 1 }

# 2) PostgreSQL dump（ai24x_a_pre）
$PgDump = "C:\Program Files\PostgreSQL\15\bin\pg_dump.exe"
$OutFile = Join-Path $DbDir ("ai24x_a_pre-{0}.dump" -f $Ts)
$ErrFile = Join-Path $MetaDir "pg_dump.err.txt"
$env:PGPASSWORD = "Ai24x@2026"
$DsArgs = @("-Fc", "-Z", "6", "-h", "127.0.0.1", "-U", "ai24x_a", "-d", "ai24x_a_pre", "-f", $OutFile)
if (Test-Path $PgDump) {
    Log "pg_dump start"
    & $PgDump @DsArgs 2> $ErrFile
    $code = $LASTEXITCODE
    if ($code -eq 0 -and (Test-Path $OutFile) -and ((Get-Item $OutFile).Length -gt 0)) {
        Log ("PG OK size={0}" -f (Get-Item $OutFile).Length)
    } else { Log ("PG FAIL exit={0}" -f $code); if (Test-Path $ErrFile) { Log ((Get-Content $ErrFile -Raw -ErrorAction SilentlyContinue)) }; exit 1 }
} else { Log "ERROR pg_dump not found"; exit 1 }

# 3) .env 快照
Copy-Item -LiteralPath (Join-Path $Source "api\server\.env") -Destination (Join-Path $EnvDir "api_server_.env") -Force
Copy-Item -LiteralPath (Join-Path $Source "api\server\.env.example") -Destination (Join-Path $EnvDir "api_server_.env.example") -Force
Log "ENV snapshot OK"

# 4) Git 信息
$branch = ""; $sha = ""
Push-Location $RepoRoot
try {
    $branch = git rev-parse --abbrev-ref HEAD 2>$null
    $sha = git rev-parse HEAD 2>$null
    $status = git status -sb 2>$null
    [System.IO.File]::WriteAllText((Join-Path $MetaDir "git_tip.txt"), "branch: $branch`nsha: $sha`nstatus:`n$status`n", [System.Text.UTF8Encoding]::new($false))
    Log ("Git: {0} @ {1}" -f $branch, $sha)
} catch { Log "git info failed" }
Pop-Location

# 5) 清单 + 回滚说明
$nowStr = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$mf = @"
# AI行情官 新增同花顺数据版本 备份（支持回滚）

- 标签: $Label
- 时间: $nowStr
- 来源: $Source
- 备份: $Dest
- Git: $branch @ $sha

## 内容
| 部分 | 路径 |
|------|------|
| 代码（含未提交改动） | code/ |
| PostgreSQL 数据库 | databases/pgsql/ai24x_a_pre-*.dump |
| 环境变量（含密钥，勿外传） | env_snapshots/ |
| 元信息 | _backup_meta/ |
"@
[System.IO.File]::WriteAllText((Join-Path $Dest "MANIFEST.md"), $mf, [System.Text.UTF8Encoding]::new($true))
$rb = @"
# 回滚速查 — $Label（$nowStr）

## 代码
1. 停 a1 服务（pm2: a-api-8001 / 本地: 18011 与 18001）
2. 把当前 p/a1 改名 p/a1-broken-<ts>
3. 复制本备份 code/ 回 $Source
4. 从 env_snapshots/ 还原 api/server/.env
5. 启动并验收 /health、登录、K线

## 数据库
1. 建新库：createdb -U postgres ai24x_a_restore
2. 恢复：pg_restore --clean --if-exists -d <DATABASE_URL> databases/pgsql/ai24x_a_pre-*.dump
3. 若覆盖原库：恢复后需重启 a1 API

注意：回滚到更早代码版本时若表结构不兼容，应同时恢复对应时间点的 dump。
"@
[System.IO.File]::WriteAllText((Join-Path $Dest "ROLLBACK.md"), $rb, [System.Text.UTF8Encoding]::new($true))

$sizeMB = [math]::Round(((Get-ChildItem -LiteralPath $Dest -Recurse -File -EA SilentlyContinue | Measure-Object Length -Sum).Sum / 1MB), 2)
Log ("DONE sizeMB={0}" -f $sizeMB)
Write-Output "BACKUP_PATH=$Dest"

