param(
    [string]$Api = "http://127.0.0.1:18012",
    [string]$Python = "python"
)
# AI24X Markets · 每日美股简报定时生成（04 服务器 04:30 CST 计划任务调用）
# 纪律：美股收盘定型后运行；周末/已生成当日份则跳过；失败发告警到 stderr（计划任务可配错误重试）。
$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
$BriefDir = Join-Path $Root "data\brief"
$Today = Get-Date -Format "yyyyMMdd"

if ((Get-Date).DayOfWeek -in @([System.DayOfWeek]::Saturday, [System.DayOfWeek]::Sunday)) {
    Write-Output "weekend - skip daily brief"
    exit 0
}
$todayFile = Join-Path $BriefDir "$Today\brief.md"
if (Test-Path $todayFile) {
    Write-Output "brief already exists for $Today - skip"
    exit 0
}

& $Python (Join-Path $ScriptDir "brief_gen.py") --api $Api
if ($LASTEXITCODE -ne 0) {
    Write-Error "daily brief generation failed with exit code $LASTEXITCODE"
    exit $LASTEXITCODE
}
Write-Output "daily brief generated: $todayFile"
