# AI24X lean full backup -> E:\AI24X\bak\ai24x01-YYYYMMDD_HHMMSS-<label>
# Excludes: *.log (esp. uvicorn), chrome profiles, node_modules, caches, docs/备份 dumps, etc.
# UTF-8
param(
    [string]$RepoRoot = "E:\AI24X\ai24x-website\ai24x01",
    [string]$BakRoot = "E:\AI24X\bak",
    [string]$Label = "BYOK基本正常版-瘦身全量",
    [switch]$SkipArchiveRetention
)

$ErrorActionPreference = "Stop"
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$destName = "ai24x01-$stamp-$Label"
$dest = Join-Path $BakRoot $destName
$codeDir = Join-Path $dest "code"
$dbDir = Join-Path $dest "databases"
$envDir = Join-Path $dest "env_snapshots"

New-Item -ItemType Directory -Force -Path $codeDir, $dbDir, $envDir | Out-Null

function Find-PgDump {
    foreach ($c in @(
        "C:\AI24X\postgresql\pgsql\bin\pg_dump.exe",
        "C:\Program Files\PostgreSQL\16\bin\pg_dump.exe",
        "C:\Program Files\PostgreSQL\15\bin\pg_dump.exe",
        "C:\Program Files\PostgreSQL\14\bin\pg_dump.exe"
    )) { if (Test-Path -LiteralPath $c) { return $c } }
    throw "pg_dump not found"
}

function Get-EnvUrls([string]$Path) {
    $out = @()
    if (-not (Test-Path -LiteralPath $Path)) { return $out }
    foreach ($line in Get-Content -LiteralPath $Path -Encoding UTF8) {
        if ($line -match '^\s*(DATABASE_URL|AI24X_DATABASE_URL|FISHER_DATABASE_URL)\s*=\s*(.+)\s*$') {
            $out += [PSCustomObject]@{ Key = $Matches[1]; Url = $Matches[2].Trim().Trim('"').Trim("'") }
        }
    }
    return $out
}

function Parse-PgUrl([string]$Url) {
    $raw = $Url -replace '^postgresql\+\w+', 'postgresql'
    if ($raw -notmatch '^postgresql(?:\+[^:]+)?://([^:]+):([^@]+)@([^:/]+)(?::(\d+))?/([^?\s]+)') {
        throw "bad DATABASE_URL"
    }
    return @{
        User = $Matches[1]
        Pass = [uri]::UnescapeDataString($Matches[2])
        Host = $Matches[3]
        Port = $(if ($Matches[4]) { $Matches[4] } else { "5432" })
        Db   = $Matches[5]
    }
}

# --- git ---
Push-Location $RepoRoot
try {
    $gitHead = (git rev-parse HEAD).Trim()
    $gitShort = (git rev-parse --short=12 HEAD).Trim()
    $gitBranch = (git rev-parse --abbrev-ref HEAD).Trim()
    $bundlePath = Join-Path $dest "ai24x01.bundle"
    Write-Host "git bundle -> $bundlePath"
    git bundle create $bundlePath --all
    if ($LASTEXITCODE -ne 0) { throw "git bundle failed" }
} finally {
    Pop-Location
}

# --- lean code mirror ---
$excludeDirNames = [System.Collections.Generic.HashSet[string]]::new([string[]]@(
    '.git','node_modules','__pycache__','.venv','venv','.cursor','agent-transcripts','terminals',
    '.pytest_cache','dist','build','Cache','Code Cache','GPUCache','component_crx_cache','WasmTtsEngine',
    '备份'  # nested docs/备份 dumps
), [StringComparer]::OrdinalIgnoreCase)

$excludeNameExact = [System.Collections.Generic.HashSet[string]]::new([string[]]@(
    '_uvicorn_stderr.log','_uvicorn_stdout.log','.env'
), [StringComparer]::OrdinalIgnoreCase)

$maxFileBytes = 50MB
$copied = 0
$skippedBytes = 0L
$skipLog = New-Object System.Collections.Generic.List[string]

Write-Host "mirroring code (lean) -> $codeDir"
function Should-SkipDir([string]$name) {
    if ($excludeDirNames.Contains($name)) { return $true }
    if ($name.StartsWith('.chrome_tmp')) { return $true }
    if ($name.StartsWith('_chrome')) { return $true }
    if ($name.StartsWith('.bak')) { return $true }
    return $false
}

$enum = [System.IO.Directory]::EnumerateFileSystemEntries($RepoRoot, '*', [System.IO.SearchOption]::AllDirectories)
# Use Get-ChildItem pipeline for PowerShell compatibility
$stack = New-Object System.Collections.Generic.Stack[string]
$stack.Push($RepoRoot)
while ($stack.Count -gt 0) {
    $cur = $stack.Pop()
    $relRoot = $cur.Substring($RepoRoot.Length).TrimStart('\')
    # skip if any path part is 备份
    if ($relRoot -match '(^|\\)备份(\\|$)') { continue }

    try {
        foreach ($d in [System.IO.Directory]::EnumerateDirectories($cur)) {
            $dn = Split-Path $d -Leaf
            if (Should-SkipDir $dn) { continue }
            if ($dn -eq '备份') { continue }
            $stack.Push($d)
        }
        foreach ($f in [System.IO.Directory]::EnumerateFiles($cur)) {
            $fn = Split-Path $f -Leaf
            $ext = [System.IO.Path]::GetExtension($fn).ToLowerInvariant()
            if ($excludeNameExact.Contains($fn)) {
                $skippedBytes += (Get-Item -LiteralPath $f).Length
                continue
            }
            if ($ext -in @('.log','.pyc','.pyo','.dump','.bundle','.zip','.mp4','.webm','.map')) {
                $skippedBytes += (Get-Item -LiteralPath $f -EA SilentlyContinue).Length
                continue
            }
            if ($fn -eq '.env' -or $fn.EndsWith('.env') -or $fn.StartsWith('.env.')) { continue }
            if ($fn -like '*_uvicorn_*') { continue }
            $fi = Get-Item -LiteralPath $f -EA SilentlyContinue
            if (-not $fi) { continue }
            if ($fi.Length -gt $maxFileBytes) {
                $skippedBytes += $fi.Length
                [void]$skipLog.Add(("big:{0}:{1}" -f $fi.Length, ($f.Substring($RepoRoot.Length+1))))
                continue
            }
            $rel = $f.Substring($RepoRoot.Length).TrimStart('\')
            $dst = Join-Path $codeDir $rel
            $dstParent = Split-Path $dst -Parent
            if (-not (Test-Path -LiteralPath $dstParent)) {
                New-Item -ItemType Directory -Force -Path $dstParent | Out-Null
            }
            [System.IO.File]::Copy($f, $dst, $true)
            $copied++
            if (($copied % 2000) -eq 0) { Write-Host "  copied $copied ..." }
        }
    } catch {
        Write-Host "WARN walk $cur : $($_.Exception.Message)"
    }
}
Write-Host "code files=$copied skippedBytesMB=$([math]::Round($skippedBytes/1MB,1))"

# --- env snapshots ---
$envPairs = @(
    @{ Src = Join-Path $RepoRoot "api\.env"; Dst = "api.env" },
    @{ Src = Join-Path $RepoRoot "p\open\api\.env"; Dst = "open.env" },
    @{ Src = Join-Path $RepoRoot "p\markets\api\server\.env"; Dst = "markets.env" },
    @{ Src = Join-Path $RepoRoot "p\a1\api\server\.env"; Dst = "a1.env" }
)
$envSaved = @()
foreach ($e in $envPairs) {
    if (Test-Path -LiteralPath $e.Src) {
        Copy-Item -LiteralPath $e.Src -Destination (Join-Path $envDir $e.Dst) -Force
        $envSaved += $e.Dst
    }
}

# --- databases ---
$pgDump = Find-PgDump
$seenDb = @{}
$dbRows = @()
foreach ($envFile in @((Join-Path $RepoRoot "api\.env"), (Join-Path $RepoRoot "p\open\api\.env"), (Join-Path $RepoRoot "p\markets\api\server\.env"), (Join-Path $RepoRoot "p\a1\api\server\.env"))) {
    foreach ($u in (Get-EnvUrls $envFile)) {
        try {
            $info = Parse-PgUrl $u.Url
        } catch {
            $dbRows += @{ ok = $false; error = $_.Exception.Message; env = $envFile }
            continue
        }
        if ($seenDb.ContainsKey($info.Db)) { continue }
        $seenDb[$info.Db] = $true
        $out = Join-Path $dbDir ($info.Db + ".dump")
        $env:PGPASSWORD = $info.Pass
        Write-Host "pg_dump $($info.Db) -> $out"
        & $pgDump -h $info.Host -p $info.Port -U $info.User -d $info.Db -Fc -f $out
        if ($LASTEXITCODE -ne 0) {
            $dbRows += @{ ok = $false; database = $info.Db; error = "pg_dump exit $LASTEXITCODE" }
        } else {
            $dbRows += @{
                ok = $true
                database = $info.Db
                host = $info.Host
                dump = "databases/$($info.Db).dump"
                bytes = (Get-Item $out).Length
                source_env = $envFile.Substring($RepoRoot.Length+1).Replace('\','/')
            }
        }
    }
}
Remove-Item Env:PGPASSWORD -EA SilentlyContinue

# --- MANIFEST + ROLLBACK ---
$codeSize = (Get-ChildItem $codeDir -Recurse -File -EA SilentlyContinue | Measure-Object Length -Sum).Sum
$totalSize = (Get-ChildItem $dest -Recurse -File -EA SilentlyContinue | Measure-Object Length -Sum).Sum
$dbOkList = @($dbRows | Where-Object { $_.ok })
$dbFailList = @($dbRows | Where-Object { -not $_.ok })
$dbOk = $dbOkList.Count
$dbFail = $dbFailList.Count
$dbLines = ($dbOkList | ForEach-Object { "- $($_.database) ($([math]::Round($_.bytes/1MB,1)) MB) — $($_.source_env)" }) -join "`n"
if (-not $dbLines) { $dbLines = "- (none)" }
$failLines = ($dbFailList | ForEach-Object { "- FAIL $($_.database) $($_.error)" }) -join "`n"
$envLines = ($envSaved | ForEach-Object { "- env_snapshots/$_" }) -join "`n"

$manifest = @"
# AI24X 完整备份快照（瘦身全量）

## 备份时间
$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') CST

## 备份标签
$Label

## 代码版本
HEAD commit: $gitShort ($gitHead)
Branch: $gitBranch
Git bundle: ai24x01.bundle
Code files: $copied
Code size MB: $([math]::Round($codeSize/1MB,1))
Total size MB: $([math]::Round($totalSize/1MB,1))
Skipped heavy bytes MB: $([math]::Round($skippedBytes/1MB,1))

## 瘦身排除（相对胖备份）
- ``*.log`` / ``_uvicorn_*.log``（此前胖备份主因 ~58GB）
- ``.chrome_tmp*`` / ``_chrome*`` / Cache / node_modules / .venv
- ``docs/备份`` 嵌套 dump 树
- 单文件 >50MB

## 数据库
$dbLines
$failLines
格式: pg_dump -Fc

## 环境变量
$envLines
注意: .env 含密钥, 勿外传

## 回滚方法
见 ``ROLLBACK.md``。恢复后重启 AI24X-core / AI24X-open-api / AI24X-markets-api（按需）。

## 规则
正式全量位置: E:\AI24X\bak\ （见 docs\备份\备份归类规则.md）
"@
[System.IO.File]::WriteAllText((Join-Path $dest "MANIFEST.md"), $manifest, [Text.UTF8Encoding]::new($false))

$rollback = @"
# 回滚说明 — $destName

## 1. 代码
``````powershell
# 方式 A：从 bundle 检出
git clone `"$dest\ai24x01.bundle`" restored-repo

# 方式 B：覆盖工作区 code\（先停服务）
robocopy `"$dest\code`" `"$RepoRoot`" /E /XO
``````

## 2. 数据库
``````powershell
`$env:PGPASSWORD = '<from env_snapshots>'
pg_restore --clean --if-exists -h 127.0.0.1 -U <user> -d ai24x_a_pre `"$dest\databases\ai24x_a_pre.dump`"
pg_restore --clean --if-exists -h 127.0.0.1 -U <user> -d ai24x_open_pre `"$dest\databases\ai24x_open_pre.dump`"
``````

## 3. 密钥
从 ``env_snapshots\`` 按需还原到 ``api\.env`` / ``p\open\api\.env``（勿提交 git）。

## 4. 重启
Restart-Service AI24X-core, AI24X-open-api
"@
[System.IO.File]::WriteAllText((Join-Path $dest "ROLLBACK.md"), $rollback, [Text.UTF8Encoding]::new($false))

# skip log sample
if ($skipLog.Count -gt 0) {
    ($skipLog | Select-Object -First 50) | Set-Content (Join-Path $dest "skip-large-files.txt") -Encoding UTF8
}

# --- LATEST pointers ---
$latestBody = @"
BACKUP_ROOT=$dest
LABEL=$Label
NOTE=瘦身全量（排除 uvicorn log / chrome / node_modules）
CREATED=$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
GIT=$gitShort
DBS=$((($dbRows | Where-Object ok | ForEach-Object { $_.database }) -join ','))
MANIFEST=$dest\MANIFEST.md
TOTAL_MB=$([math]::Round($totalSize/1MB,1))
RULE=$RepoRoot\docs\备份\备份归类规则.md
"@
Set-Content -Path (Join-Path $BakRoot "LATEST_FULL.txt") -Value $latestBody -Encoding UTF8
$backupsPtr = Join-Path $RepoRoot "_backups"
New-Item -ItemType Directory -Force -Path $backupsPtr | Out-Null
Set-Content -Path (Join-Path $backupsPtr "LATEST_FULL.txt") -Value $latestBody -Encoding UTF8

# --- retention: keep 2 full (MANIFEST + size > 100MB) ---
if (-not $SkipArchiveRetention) {
    $hist = "E:\AI24X\archive\bak-historical"
    New-Item -ItemType Directory -Force -Path $hist | Out-Null
    $fulls = Get-ChildItem $BakRoot -Directory | Where-Object {
        (Test-Path (Join-Path $_.FullName "MANIFEST.md")) -and
        (((Get-ChildItem $_.FullName -Recurse -File -EA SilentlyContinue | Measure-Object Length -Sum).Sum) -gt 100MB)
    } | Sort-Object LastWriteTime -Descending
    if ($fulls.Count -gt 2) {
        $fulls | Select-Object -Skip 2 | ForEach-Object {
            $target = Join-Path $hist $_.Name
            Write-Host "ARCHIVE old full -> $target"
            if (Test-Path $target) { Remove-Item $target -Recurse -Force }
            Move-Item -LiteralPath $_.FullName -Destination $target
        }
    }
}

Write-Host "OK LEAN FULL $dest"
Write-Host "files=$copied totalMB=$([math]::Round($totalSize/1MB,1)) db_ok=$dbOk db_fail=$dbFail"
if ($dbFail -gt 0) { exit 3 }
if ($dbOk -lt 1) { exit 2 }
exit 0
