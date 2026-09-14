# 山海渔·渔悦：拆分独立 PostgreSQL 库（需 postgres 超级账号口令）
# 用法：powershell -ExecutionPolicy Bypass -File .\scripts\init_fisher_db.ps1
# 效果：建用户 fisher / 建库 fisher / 恢复样本快照 -> 之后改 .env 指向独立库

param(
  [string]$PgBin = "C:\Program Files\PostgreSQL\15\bin",
  [string]$SuperUser = "postgres",
  [string]$DumpFile = (Join-Path $PSScriptRoot "..\db\fisher_dump_20260812.dump")
)

$psql = Join-Path $PgBin "psql.exe"
$pgrestore = Join-Path $PgBin "pg_restore.exe"

if (-not (Test-Path $psql)) { Write-Error "psql not found: $psql"; exit 1 }
if (-not (Test-Path $DumpFile)) { Write-Error "dump not found: $DumpFile"; exit 1 }

$pw = Read-Host -AsSecureString "postgres 超级账号口令"
$bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($pw)
$plain = [System.Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
[System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)

$env:PGPASSWORD = $plain
Write-Host "[1/3] 创建用户 fisher ..."
& $psql -U $SuperUser -h 127.0.0.1 -p 5432 -d postgres -v ON_ERROR_STOP=1 -c "DO \$\$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='fisher') THEN CREATE ROLE fisher LOGIN PASSWORD 'fisher'; END IF; END \$\$;" 
if ($LASTEXITCODE -ne 0) { exit 1 }

Write-Host "[2/3] 创建数据库 fisher ..."
& $psql -U $SuperUser -h 127.0.0.1 -p 5432 -d postgres -v ON_ERROR_STOP=1 -c "SELECT 'CREATE DATABASE fisher OWNER fisher' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname='fisher')\gexec"
if ($LASTEXITCODE -ne 0) { exit 1 }

Write-Host "[3/3] 恢复样本快照 -> fisher 库 ..."
& $pgrestore -U $SuperUser -h 127.0.0.1 -p 5432 -d fisher --no-owner --role=fisher $DumpFile
if ($LASTEXITCODE -ne 0) { exit 1 }

Write-Host ""
Write-Host "完成。请把 api/server/.env 的 FISHER_DATABASE_URL 改为："
Write-Host "  postgresql+psycopg2://fisher:fisher@127.0.0.1:5432/fisher"
Write-Host "然后重启 fisher-api 服务。"
