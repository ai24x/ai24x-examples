# === AI24X 04 直连部署（确定性更新，绕过 openclaw LLM 层）===
# 用法: powershell -File scripts\deploy04_direct.ps1 <指令.ps1> [-DryRun] [-NoGroup]
# 适用: 标准代码更新（git pull + marker 校验 + 静态同步 + 重启 + 公网验收）
# 不适用: 需要判断的任务（DB 迁移 / nginx 编辑 / 后台操作）-> 仍走 deploy04.ps1 (openclaw)
# 原理: scp 指令 -> ssh 直跑 powershell -File（无 LLM 层）-> 解析 DONE 行 -> 飞书群回执
# 坑位:
#   - 04 远端默认 shell 是 cmd，跑 PS 必须 powershell -NoProfile -ExecutionPolicy Bypass -File
#   - 指令含中文必须 UTF-8 带 BOM，否则 PS5.1 按 GBK 误读直接解析失败（本脚本自动转 BOM）
#   - 指令末行必须有群回执模板：# ✅ 04更新完成｜标题｜EXP=<EXP> HEAD=<HEAD> health=<commit>｜验收结论
param(
  [Parameter(Mandatory = $true)][string]$TaskFile,
  [switch]$DryRun,
  [switch]$NoGroup
)

$ErrorActionPreference = "Stop"
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$SshHost = "Administrator@43.160.246.30"
$RemoteOps = "C:\Users\Administrator\ops"
$RemoteName = Split-Path $TaskFile -Leaf
$RemoteTask = "$RemoteOps\$RemoteName"
$RepoRoot = Split-Path $PSScriptRoot -Parent
$Log = Join-Path $RepoRoot "ops\deploy04-direct-$(Get-Date -Format yyyyMMdd-HHmmss).log"
$Staging = Join-Path $env:TEMP ("deploy04-" + [guid]::NewGuid().ToString("N") + ".ps1")

# 1) 读取源文件并转 UTF-8 带 BOM（防远端 GBK 误读中文）
$src = [System.IO.File]::ReadAllText((Resolve-Path $TaskFile), [System.Text.Encoding]::UTF8)
[System.IO.File]::WriteAllText($Staging, $src, (New-Object System.Text.UTF8Encoding($true)))

# 2) 从指令末行解析群回执模板（# ✅ 04更新完成｜...）
$receipt = ""
foreach ($line in ($src -split "`r?`n")) {
  if ($line -match "^#\s*✅") { $receipt = $line -replace "^#\s*", "" }
}
if (-not $receipt) { throw "指令文件缺少群回执模板行（# ✅ 04更新完成｜...）" }

if ($DryRun) {
  Write-Host "[DryRun] BOM 转换 OK -> $Staging" -ForegroundColor Green
  Write-Host "[DryRun] 回执模板: $receipt" -ForegroundColor Cyan
  Remove-Item -LiteralPath $Staging -Force
  return
}

Write-Host "==> scp 指令 -> 04" -ForegroundColor Cyan
scp -o ConnectTimeout=20 -o StrictHostKeyChecking=no $Staging "${SshHost}:${RemoteTask}"
if ($LASTEXITCODE -ne 0) { Remove-Item -LiteralPath $Staging -Force; throw "scp 失败" }
Remove-Item -LiteralPath $Staging -Force

Write-Host "==> 04 直跑部署脚本（无 LLM 层）..." -ForegroundColor Cyan
$remoteCmd = "powershell -NoProfile -ExecutionPolicy Bypass -File `"${RemoteTask}`""
# 远端 git 常往 stderr 打 wincredman 提示；PS 在 Stop 下会把 NativeCommandError 当失败
$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$out = ssh -o ConnectTimeout=20 -o StrictHostKeyChecking=no -o BatchMode=yes $SshHost $remoteCmd 2>&1
$code = $LASTEXITCODE
$ErrorActionPreference = $prevEap
$out | Out-File -FilePath $Log -Encoding utf8
$out | Select-Object -Last 60
if ($code -ne 0) { throw "04 部署脚本失败 code=$code，日志: $Log" }

# 3) 解析 DONE 行 -> 填充回执 -> 发指挥部群
$doneLine = ($out | Select-String -Pattern "DONE EXP=" | Select-Object -Last 1).Line
$exp = ""; $head = ""; $commit = ""
if ($doneLine -match "EXP=(\S+)") { $exp = $Matches[1] }
if ($doneLine -match "HEAD=(\S+)") { $head = $Matches[1] }
if ($doneLine -match "health=(\S+)") { $commit = $Matches[1] }
$msg = $receipt.Replace("<HEAD>", $head).Replace("<commit>", $commit)
Write-Host "==> 部署成功: $msg" -ForegroundColor Green
if (-not $NoGroup) {
  $fn = Join-Path $RepoRoot "api\feishu_notify.py"
  python $fn --config "E:\AI24X\OpenClaw\openclaw.json" --group $msg
  if ($LASTEXITCODE -ne 0) { Write-Host "注意: 群回执发送失败，请手动补发: $msg" -ForegroundColor Yellow }
}
Write-Host ("完成，日志: $Log") -ForegroundColor Green
