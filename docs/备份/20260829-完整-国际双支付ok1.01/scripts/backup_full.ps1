# 完整备份（代码+库+子项目）— 国际双支付 ok1.01
# UTF-8 BOM
param(
    [string]$RepoRoot = ""
)
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
if ($RepoRoot) {
    # ensure backup_full.py resolves ROOT via parents[4] from scripts/ — do not relocate; run from repo checkout
}
$py = Join-Path $here "backup_full.py"
if (-not (Test-Path -LiteralPath $py)) { throw "missing $py" }
Set-Location (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $here))))
# parents: scripts -> bundle -> 备份 -> docs -> repo root
# Actually parents[4] from scripts = repo. Stay: just run python with file path.
python $py
if ($LASTEXITCODE -ne 0) { throw "backup_full.py exit=$LASTEXITCODE" }
Write-Host "FULL BACKUP OK" -ForegroundColor Green
