# === AI24X 指令直连 04 部署派发（openclaw 模式；标准代码更新请用 deploy04_direct.ps1）===
# 用法: powershell -File scripts\deploy04.ps1 <任务.ps1 或 .md>
# 说明: 跳过主脑中转, 直接 scp 指令到 04 并 ssh 驱动 04 的 openclaw 执行部署+验收+飞书群回执
# 04 主机: 运维SG 43.160.246.30（国际生产 www/api/open/markets）
param([Parameter(Mandatory = $true)][string]$TaskFile)

$ErrorActionPreference = "Stop"
$SshHost = "Administrator@43.160.246.30"
$RemoteOps = "C:\Users\Administrator\ops"
$TaskName = Split-Path $TaskFile -Leaf
$RemoteTask = "$RemoteOps\$TaskName"
$Log = Join-Path (Split-Path $PSScriptRoot -Parent) "ops\deploy04-$(Get-Date -Format HHmmss).log"

Write-Host "==> 确保 04 远端 ops 目录存在" -ForegroundColor Cyan
ssh -o ConnectTimeout=20 -o StrictHostKeyChecking=no -o BatchMode=yes $SshHost "powershell -NoProfile -Command New-Item -ItemType Directory -Force -Path C:\Users\Administrator\ops" 2>&1 | Out-Null

Write-Host "==> scp 指令 -> 04" -ForegroundColor Cyan
scp -o ConnectTimeout=20 -o StrictHostKeyChecking=no $TaskFile "${SshHost}:${RemoteTask}"
if ($LASTEXITCODE -ne 0) { throw "scp 失败" }

Write-Host "==> 驱动 04 执行 (openclaw agent, timeout 600)..." -ForegroundColor Cyan
$cmd = "openclaw agent --agent main --message-file ${RemoteTask} --json --timeout 600"
$sshOut = ssh -o ConnectTimeout=20 -o StrictHostKeyChecking=no -o BatchMode=yes $SshHost $cmd 2>&1
$sshOut | Out-File -FilePath $Log -Encoding utf8
Write-Host "==> 完成, 日志: $Log" -ForegroundColor Green
$sshOut | Select-Object -Last 40
