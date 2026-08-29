# 国际双支付 ok1.01 — 回滚（数据库 + 可选代码）
# UTF-8 BOM
param(
    [switch]$Apply,
    [switch]$RestoreCode,
    [string]$RepoRoot = "",
    [string]$EnvFile = "",
    [string]$PgRestore = "C:\Program Files\PostgreSQL\15\bin\pg_restore.exe",
    [ValidateSet("payment", "full")]
    [string]$Mode = "payment"
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

$manifestPath = Join-Path $bundle "manifest.json"
if (-not (Test-Path -LiteralPath $manifestPath)) {
    throw "manifest.json missing — run backup.ps1 first"
}
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json

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

Write-Host "ROLLBACK label=$($manifest.label) git=$($manifest.git_short) Apply=$Apply RestoreCode=$RestoreCode Mode=$Mode"

if ($RestoreCode) {
    $codeDir = Join-Path $bundle "code"
    $map = @{
        "api__token_pay_service.py" = "api\token_pay_service.py"
        "api__pay_paypal.py" = "api\pay_paypal.py"
        "api__pay_dodo.py" = "api\pay_dodo.py"
        "api__pay_creem.py" = "api\pay_creem.py"
        "api__billing_money.py" = "api\billing_money.py"
        "api__pay_products.py" = "api\pay_products.py"
        "api__main.py" = "api\main.py"
        "api__schemas.py" = "api\schemas.py"
        "api__models.py" = "api\models.py"
        "web__js__console.js" = "web\js\console.js"
        "web__js__api.js" = "web\js\api.js"
        "web__console.html" = "web\console.html"
        "web__pricing.html" = "web\pricing.html"
        "web__index.html" = "web\index.html"
        "web__about.html" = "web\about.html"
        "web__token-admin.html" = "web\token-admin.html"
        "web__config__locales.js" = "web\config\locales.js"
        "api__data__token_plans_override.json" = "api\data\token_plans_override.json"
        "api__data__byok_plans_override.json" = "api\data\byok_plans_override.json"
        "p__open__api__main.py" = "p\open\api\main.py"
    }
    foreach ($entry in $map.GetEnumerator()) {
        $src = Join-Path $codeDir $entry.Key
        $dst = Join-Path $RepoRoot $entry.Value
        if (-not (Test-Path -LiteralPath $src)) { continue }
        if ($Apply) {
            $bak = "$dst.bak-rollback-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
            if (Test-Path -LiteralPath $dst) { Copy-Item -LiteralPath $dst -Destination $bak -Force }
            Copy-Item -LiteralPath $src -Destination $dst -Force
            Write-Host "code restored $($entry.Value)"
        } else {
            Write-Host "[dry] would restore $($entry.Value) <- $($entry.Key)"
        }
    }
}

$dumpName = if ($Mode -eq "full") { "full.dump" } else { "payment_tables.dump" }
$dumpPath = Join-Path $bundle "db\$dumpName"
if (-not (Test-Path -LiteralPath $dumpPath)) {
    throw "dump not found: $dumpPath"
}

$pyRollback = Join-Path $here "rollback_db.py"
if (-not (Test-Path -LiteralPath $pyRollback)) {
    throw "rollback_db.py missing"
}
if ($Apply) {
    python $pyRollback --mode $Mode --apply
    if ($LASTEXITCODE -ne 0) { Write-Warning "rollback_db.py exit=$LASTEXITCODE" }
    Write-Host "database restored from $dumpName"
    Write-Host "restart: Restart-Service AI24X-core -Force  (+ AI24X-open-api if open billing touched)"
} else {
    python $pyRollback --mode $Mode
    Write-Host "Pass -Apply to execute. Add -RestoreCode to restore code snapshots too."
}
