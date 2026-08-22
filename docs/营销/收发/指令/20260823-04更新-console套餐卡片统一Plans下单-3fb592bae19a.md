# 【04 更新】console overview 套餐卡片 + Upgrade 统一跳 Plans 下单 + pricing 按钮改跳用户中心

> 通道：司令直连 04（deploy04.ps1）｜ 目标提交 **3fb592bae19a**
> 04 主机：43.160.246.30 · 仓库 C:\ai24x01 · 服务 AI24X-core（NSSM，8002）· 静态 web/ 由仓库直读
> 本次为纯 www 静态变更（console.html / console.js / pricing.html），无 markets 后端变更、无 DB 迁移；04 若发现 markets 相关脏改动勿动

## 背景
老板拍板：用户中心（console）Overview 直接放 Markets 套餐卡片（免费/周/月/年），两处 Upgrade to Pro 改为站内跳 Plans 统一下单；www pricing.html 四个升级按钮统一深链 console.html?plan=xxx#billing。本地 QA 3 套 48 项全绿后老板已放行。

## 执行步骤（PowerShell，整段复制运行）
```powershell
$ErrorActionPreference = "Stop"
$REPO = "C:\ai24x01"
$SRV  = "AI24X-core"
$EXP  = "3fb592bae19a"

Set-Location $REPO

"--- 0) 备份本地脏改动再还原（防止 pull 冲突；只动本次 3 个文件）---"
$FILES = @("web/console.html","web/js/console.js","web/pricing.html")
$BK = "C:\backup\www_20260823_pre_3fb592b"
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

"--- 2) 文件标记检查（仓库源码）---"
$c1 = Get-Content "$REPO\web\console.html" -Raw -Encoding UTF8
$c2 = Get-Content "$REPO\web\js\console.js" -Raw -Encoding UTF8
$c3 = Get-Content "$REPO\web\pricing.html" -Raw -Encoding UTF8
$m1 = $c1.Contains('id="marketsPlansGrid"')
$m2 = $c1.Contains('console.js?v=20260823a')
$m3 = $c2.Contains('function renderOverviewMarketsPlans')
$m4 = $c3.Contains('console.html?plan=weekly#billing')
"mark_console_grid=$m1 mark_console_ver=$m2 mark_console_js=$m3 mark_pricing_link=$m4"
if (-not ($m1 -and $m2 -and $m3 -and $m4)) { Write-Host "!! 文件标记缺失" -ForegroundColor Red; exit 1 }

"--- 3) 重启 AI24X-core (8002)：PID 断言 + health commit 校验 ---"
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
    $h = Invoke-RestMethod -Uri "http://127.0.0.1:8002/health" -TimeoutSec 10 -UseBasicParsing
    if ($afterPid -gt 0 -and $afterPid -ne $beforePid -and $h.commit -and $h.commit -like "$($EXP.Substring(0,12))*") { $ok = $true; break }
  } catch {}
}
"svc_pid_after=$afterPid  health_ok=$ok  commit=$($h.commit)"
if (-not $ok) {
  Write-Host "!! 服务未按预期重启或 commit 不符，需人工处理" -ForegroundColor Red; exit 1
}

"--- 4) 公网页面内容标记（?x= 缓存穿透）---"
$u1 = (Invoke-WebRequest -Uri "https://www.ai24x.com/console.html?x=20260823a" -UseBasicParsing -TimeoutSec 25).Content
$u2 = (Invoke-WebRequest -Uri "https://www.ai24x.com/pricing.html?x=20260823a" -UseBasicParsing -TimeoutSec 25).Content
$pm1 = $u1.Contains('id="marketsPlansGrid"')
$pm2 = $u1.Contains('console.js?v=20260823a')
$pm3 = $u2.Contains('console.html?plan=weekly#billing')
"pub_console_grid=$pm1 pub_console_ver=$pm2 pub_pricing_link=$pm3"
if (-not ($pm1 -and $pm2 -and $pm3)) { Write-Host "!! 公网内容不对（可能缓存，换 ?x= 再试）" -ForegroundColor Red; exit 1 }

Write-Host "=== 部署成功 OK ===" -ForegroundColor Green
```

## 验收清单（回执时逐条列出）
- HEAD=3fb592bae19a（merge-base 校验通过）／文件标记 4 条（console grid / console.js?v=20260823a / console js 函数 / pricing 深链）
- AI24X-core PID 变化（before/after）／health 200 + commit 字段=3fb592bae19a
- 公网标记 3 条（console.html / pricing.html，?x=20260823a 穿透）
- 浏览器端（老板 Ctrl+F5 后用户侧确认）：console #overview 4 张套餐卡片、Upgrade 跳 Plans、pricing 按钮跳 console Plans
- ⚠️ 问题项：无则写「无」

## 回执格式（04 自动发指挥部群）
- ✅ 已完成项：HEAD／文件标记／重启+health+commit／公网内容标记
- ⚠️ 问题项：逐条（无则写「无」）
- 凭据纪律：不回执任何 token 明文；备份目录仅报路径。

## 回滚预案
- `git revert 3fb592bae19a` + `Restart-Service AI24X-core -Force`；或恢复 `C:\backup\www_20260823_pre_3fb592b\*.bak` + 重启 AI24X-core。
