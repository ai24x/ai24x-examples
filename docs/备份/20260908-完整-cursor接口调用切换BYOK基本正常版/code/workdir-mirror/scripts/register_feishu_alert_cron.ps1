# 注册「预警→飞书私信」轮询计划任务（每 5 分钟）
# 用法：powershell -ExecutionPolicy Bypass -File scripts\register_feishu_alert_cron.ps1
# 说明：轮询器部署在可访问 openclaw.json 的机器（副脑04 云主机），凭证运行时读取，绝不硬编码。
$ErrorActionPreference = 'Stop'

$py = (Get-Command python).Source
if (-not $py) { throw 'python not found' }

# 改成实际部署路径（默认取本脚本同级的 api 目录）
$script = Join-Path $PSScriptRoot '..\api\scripts_feishu_alert_poll.py'
$script = [System.IO.Path]::GetFullPath($script)
if (-not (Test-Path $script)) { throw "poll script not found: $script" }

# 环境变量：预警接口与 key（生产必填）
# 建议直接写进系统环境变量（避免明码出现在任务命令行）：
#   OPS_ALERT_API=https://api.ai24x.com
#   OPS_ALERT_KEY=<SMS_INTERNAL_KEY 或 ADMIN_API_KEY 的值>

$action = "`"$py`" `"$script`""
schtasks /create /tn "AI24X-Alert-Feishu-PM" /tr $action /sc minute /mo 5 /ru SYSTEM /f
if ($LASTEXITCODE -ne 0) { throw "schtasks create failed: $LASTEXITCODE" }
Write-Host "计划任务 AI24X-Alert-Feishu-PM 已注册（每 5 分钟，/ru SYSTEM 系统级运行）"
schtasks /query /tn "AI24X-Alert-Feishu-PM" /v /fo list | Select-String -Pattern '任务名|状态|下次运行|上次运行'
