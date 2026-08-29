# 国际双支付 ok1.01 — 代码快照 + PostgreSQL 备份
# UTF-8 BOM
param(
    [string]$RepoRoot = "",
    [string]$EnvFile = "",
    [string]$PgDump = "C:\Program Files\PostgreSQL\15\bin\pg_dump.exe"
)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$bundle = Split-Path -Parent $here
if (-not $RepoRoot) {
    $RepoRoot = (Resolve-Path (Join-Path $here "..\..\..\..")).Path
}
if (-not $EnvFile) {
    $EnvFile = Join-Path $RepoRoot "api\.env"
}

$codeDir = Join-Path $bundle "code"
$dbDir = Join-Path $bundle "db"
New-Item -ItemType Directory -Force -Path $codeDir, $dbDir | Out-Null

$relFiles = @(
    "api\token_pay_service.py",
    "api\pay_paypal.py",
    "api\pay_dodo.py",
    "api\pay_creem.py",
    "api\billing_money.py",
    "api\pay_products.py",
    "api\main.py",
    "api\schemas.py",
    "api\models.py",
    "web\js\console.js",
    "web\js\api.js",
    "web\console.html",
    "web\pricing.html",
    "web\index.html",
    "web\about.html",
    "web\token-admin.html",
    "web\config\locales.js",
    "api\data\token_plans_override.json",
    "api\data\byok_plans_override.json",
    "p\open\api\main.py"
)

$copied = @()
foreach ($rel in $relFiles) {
    $src = Join-Path $RepoRoot $rel
    if (-not (Test-Path -LiteralPath $src)) { continue }
    $dst = Join-Path $codeDir ($rel -replace '[\\/]', '__')
    Copy-Item -LiteralPath $src -Destination $dst -Force
    $copied += $rel
}

function Get-DatabaseUrl {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    foreach ($line in Get-Content -LiteralPath $Path -Encoding UTF8) {
        if ($line -match '^\s*DATABASE_URL\s*=\s*(.+)\s*$') {
            return $Matches[1].Trim().Trim('"').Trim("'")
        }
    }
    return $null
}

$gitHead = ""
$gitShort = ""
try {
    Push-Location $RepoRoot
    $gitHead = (git rev-parse HEAD 2>$null)
    $gitShort = (git rev-parse --short=12 HEAD 2>$null)
} finally {
    Pop-Location
}

$tables = @(
    "token_pay_orders",
    "token_wallets",
    "billing_ledger",
    "token_credit_lots"
)

$dbUrl = Get-DatabaseUrl -Path $EnvFile
$dbResult = @{ ok = $false; message = "skipped" }
$pyDb = Join-Path $here "backup_db.py"
if (Test-Path -LiteralPath $pyDb) {
    try {
        python $pyDb
        if ($LASTEXITCODE -eq 0) {
            $metaPath = Join-Path $dbDir "backup_meta.json"
            if (Test-Path -LiteralPath $metaPath) {
                $dbResult = Get-Content -LiteralPath $metaPath -Raw -Encoding UTF8 | ConvertFrom-Json
            }
        } else {
            $dbResult = @{ ok = $false; message = "backup_db.py exit=$LASTEXITCODE" }
        }
    } catch {
        $dbResult = @{ ok = $false; message = $_.Exception.Message }
    }
} elseif ($dbUrl -and (Test-Path -LiteralPath $PgDump)) {
    $env:PGPASSWORD = $null
    if ($dbUrl -match '^postgresql(?:\+[^:]+)?://([^:]+):([^@]+)@([^:/]+)(?::(\d+))?/(.+)$') {
        $pgUser = $Matches[1]
        $pgPass = $Matches[2]
        $pgHost = $Matches[3]
        $pgPort = if ($Matches[4]) { $Matches[4] } else { "5432" }
        $pgDb = ($Matches[5] -split '\?')[0]
        $env:PGPASSWORD = $pgPass
        $fullDump = Join-Path $dbDir "full.dump"
        & $PgDump -h $pgHost -p $pgPort -U $pgUser -d $pgDb -Fc -f $fullDump
        if ($LASTEXITCODE -ne 0) { throw "pg_dump full failed exit=$LASTEXITCODE" }
        $payDump = Join-Path $dbDir "payment_tables.dump"
        $tableArgs = $tables | ForEach-Object { "-t"; $_ }
        & $PgDump -h $pgHost -p $pgPort -U $pgUser -d $pgDb -Fc -f $payDump @tableArgs
        if ($LASTEXITCODE -ne 0) { throw "pg_dump tables failed exit=$LASTEXITCODE" }
        $dbResult = @{
            ok = $true
            host = $pgHost
            database = $pgDb
            full = "db/full.dump"
            payment_tables = "db/payment_tables.dump"
            tables = $tables
        }
    } else {
        $dbResult = @{ ok = $false; message = "DATABASE_URL parse failed" }
    }
} elseif (-not (Test-Path -LiteralPath $PgDump)) {
    $dbResult = @{ ok = $false; message = "pg_dump not found: $PgDump" }
} else {
    $dbResult = @{ ok = $false; message = "no DATABASE_URL in $EnvFile" }
}

$manifest = @{
    label = "国际双支付ok1.01"
    created_at = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
    git_head = $gitHead
    git_short = $gitShort
    repo_root = $RepoRoot
    code_files = $copied
    database = $dbResult
}
$manifestPath = Join-Path $bundle "manifest.json"
$manifestJson = $manifest | ConvertTo-Json -Depth 6
[System.IO.File]::WriteAllText($manifestPath, $manifestJson, (New-Object System.Text.UTF8Encoding $true))

Write-Host "OK bundle=$bundle"
Write-Host "git=$gitShort files=$($copied.Count) db=$($dbResult.ok)"
if ($dbResult.ok) {
    Write-Host "db: $($dbResult.database) @ $($dbResult.host)"
}
