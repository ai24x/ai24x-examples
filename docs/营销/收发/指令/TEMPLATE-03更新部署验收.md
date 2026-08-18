# 【03 更新】<标题>

> 通道：司令直连 03（deploy03.ps1）｜ 目标提交 **<EXP>**
> 03 主机：123.207.199.238 · 仓库 C:\ai24x01 · 服务 AI24X-a1-api（NSSM，8001）· 无 D 盘（备份落 C:\backup\ai24x_a\）
> a1 /health 无 commit 字段：验收用「文件标记 + 进程新建时间 + 服务器侧行为 QA（必要时）」

## 背景
<一句话说明改动与理由>

## 执行步骤（PowerShell，整段复制运行）
```powershell
$ErrorActionPreference = "Stop"
$REPO = "C:\ai24x01"
$SRV  = "AI24X-a1-api"
$EXP  = "<EXP>"

Set-Location $REPO

"--- 0) 备份本地脏改动再还原（防止 pull 冲突）---"
$FILES = @("<涉及文件1>","<涉及文件2>")
$BK = "C:\backup\ai24x_a\<YYYYMMDD>_pre_<EXP>"
New-Item -ItemType Directory -Force -Path $BK | Out-Null
foreach ($x in $FILES) {
  if (Test-Path "$REPO\$x") {
    $chg = git -C $REPO status --porcelain -- $x
    if ($chg) { Copy-Item "$REPO\$x" "$BK\$(Split-Path $x -Leaf).bak" -Force; git -C $REPO checkout -- $x }
  }
}
"备份目录: $BK"

"--- 1) 拉码 + HEAD 校验 ---"
git pull
$HEAD = (git rev-parse --short=12 HEAD).Trim()
"HEAD=$HEAD"
git merge-base --is-ancestor $EXP HEAD
if ($LASTEXITCODE -ne 0) { Write-Host "!! HEAD 不含目标提交 $EXP" -ForegroundColor Red; exit 1 }

"--- 2) 文件标记检查（纪律：单引号内直接写引号字符，勿写 \`" 转义——PowerShell 单引号不解析转义） ---"
$f = Get-Content "$REPO\<文件>" -Raw -Encoding UTF8
"mark1=$($f.Contains('<标记>'))"
if (-not ($f.Contains('<标记>'))) { Write-Host "!! 文件标记缺失" -ForegroundColor Red; exit 1 }

"--- 3) 重启 AI24X-a1-api (8001)：服务 PID 断言 + nssm 兜底 ---"
$beforePid = (Get-CimInstance Win32_Service -Filter "Name='$SRV'").ProcessId
"svc_pid_before=$beforePid"
Restart-Service $SRV -Force
$ok = $false
$afterPid = $beforePid
for ($i = 0; $i -lt 20; $i++) {
  Start-Sleep -Seconds 5
  try {
    $svc = Get-CimInstance Win32_Service -Filter "Name='$SRV'"
    if ($svc) { $afterPid = $svc.ProcessId }
    $h = Invoke-RestMethod -Uri "http://127.0.0.1:8001/health" -TimeoutSec 10 -UseBasicParsing
    if ($afterPid -gt 0 -and $afterPid -ne $beforePid) { $ok = $true; break }
  } catch {}
}
"svc_pid_after=$afterPid  health_ok=$ok"
if (-not $ok) {
  Write-Host "!! Restart-Service 未真正重启（PID 未变），兜底 nssm restart" -ForegroundColor Yellow
  & nssm restart $SRV 2>$null
  if ($LASTEXITCODE -ne 0) { & "C:\Program Files\NSSM\nssm.exe" restart $SRV 2>$null }
  for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Seconds 5
    try {
      $svc2 = Get-CimInstance Win32_Service -Filter "Name='$SRV'"
      if ($svc2) { $afterPid = $svc2.ProcessId }
      $h2 = Invoke-RestMethod -Uri "http://127.0.0.1:8001/health" -TimeoutSec 10 -UseBasicParsing
      if ($afterPid -gt 0 -and $afterPid -ne $beforePid) { $ok = $true; break }
    } catch {}
  }
}
if (-not $ok) { Write-Host "!! 服务仍未重启（before=$beforePid after=$afterPid），需人工处理" -ForegroundColor Red; exit 1 }
"health=$($h.status)"

"--- 4) 公网页面内容标记（静态变更必查；后端变更可跳） ---"
$pub = (Invoke-WebRequest -Uri "https://a.ai24x.com/<页面>" -UseBasicParsing -TimeoutSec 20).Content
"pub_mark=$($pub.Contains('<标记>'))"
if (-not $pub.Contains('<标记>')) { Write-Host "!! 公网内容不对" -ForegroundColor Red; exit 1 }

Write-Host "=== 部署成功 OK ===" -ForegroundColor Green
```

## 验收清单（回执时逐条列出）
- HEAD=<EXP>（merge-base 校验通过）／文件标记（逐条）
- 服务 PID 变化（before/after）／health 200
- 公网页面/资源内容标记
- 浏览器端（Ctrl+F5，用户侧确认）：<用户侧验收点>
- ⚠️ 问题项：无则写「无」

## 回执格式（03 自动发指挥部群）
- ✅ 已完成项：HEAD／文件标记／重启+health／公网内容标记
- ⚠️ 问题项：逐条（无则写「无」）
- 凭据纪律：不回执任何 token 明文；备份目录仅报路径。

## 回滚预案
- `git revert <EXP>` + `nssm restart AI24X-a1-api`；或恢复 `C:\backup\ai24x_a\<YYYYMMDD>_pre_<EXP>\*.bak` + `nssm restart AI24X-a1-api`。
