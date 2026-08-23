# 【03 更新】watchscore 自选删除按钮 + 居中确认弹窗

> 通道：司令直连 03（deploy03.ps1）｜ 目标提交 **140826e9c524**
> 03 主机：123.207.199.238 · 仓库 C:\ai24x01 · 服务 AI24X-a1-api（NSSM，8001）· 无 D 盘（备份落 C:\backup\ai24x_a\）
> a1 /health 无 commit 字段：验收用「文件标记 + 进程新建时间 + 服务器侧行为 QA（必要时）」

## 背景
watchscore.html（自选评分榜）新增「删除自选股」按钮：后端 /api/watchlist/remove 早已存在，本次纯前端接线。
① 表格新增「操作」列，每行删除按钮，点击弹自定义确认弹窗（居中显示，替换原生 window.confirm——原生弹窗固定在浏览器顶部体验差）；
② 删除成功后同步清理 localStorage ai24x_a_watchlist（防下次加载补推复活）；
③ 防竞态：删除瞬间评分请求在途返回时不会把已删标的重新渲染出来。
涉及文件：web/js/watchscore.js、web/css/watchscore.css、web/watchscore.html、web/account.html（account.html 复用同一模块，删除功能同步生效）。

## 执行步骤（PowerShell，整段复制运行）
```powershell
$ErrorActionPreference = "Stop"
$REPO = "C:\ai24x01"
$SRV  = "AI24X-a1-api"
$EXP  = "140826e9c524"

Set-Location $REPO

"--- 0) 备份本地脏改动再还原（防止 pull 冲突）---"
$FILES = @("p/a1/web/js/watchscore.js","p/a1/web/css/watchscore.css","p/a1/web/watchscore.html","p/a1/web/account.html")
$BK = "C:\backup\ai24x_a\20260823_pre_140826e"
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

"--- 2) 文件标记检查 ---"
$j = Get-Content "$REPO\p\a1\web\js\watchscore.js" -Raw -Encoding UTF8
"mark_js_remove=$($j.Contains('data-wl-act="remove"'))"
if (-not ($j.Contains('data-wl-act="remove"'))) { Write-Host "!! watchscore.js 删除动作缺失" -ForegroundColor Red; exit 1 }
$c = Get-Content "$REPO\p\a1\web\css\watchscore.css" -Raw -Encoding UTF8
"mark_css_mask=$($c.Contains('.wl-confirm-mask'))"
if (-not ($c.Contains('.wl-confirm-mask'))) { Write-Host "!! watchscore.css 弹窗样式缺失" -ForegroundColor Red; exit 1 }
$h = Get-Content "$REPO\p\a1\web\watchscore.html" -Raw -Encoding UTF8
"mark_html_v7=$($h.Contains('watchscore.js?v=7'))"
if (-not ($h.Contains('watchscore.js?v=7'))) { Write-Host "!! watchscore.html 版本号未升 v7" -ForegroundColor Red; exit 1 }
$a = Get-Content "$REPO\p\a1\web\account.html" -Raw -Encoding UTF8
"mark_account_v7=$($a.Contains('watchscore.css?v=7'))"
if (-not ($a.Contains('watchscore.css?v=7'))) { Write-Host "!! account.html 版本号未升 v7" -ForegroundColor Red; exit 1 }

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

"--- 4) 公网页面内容标记（静态由 Nginx 直读 web 目录，git pull 即生效）---"
$pub1 = (Invoke-WebRequest -Uri "https://a.ai24x.com/watchscore.html" -UseBasicParsing -TimeoutSec 20).Content
"pub_watchscore_v7=$($pub1.Contains('watchscore.js?v=7'))"
if (-not $pub1.Contains('watchscore.js?v=7')) { Write-Host "!! 公网 watchscore.html 版本号不对" -ForegroundColor Red; exit 1 }
$pub2 = (Invoke-WebRequest -Uri "https://a.ai24x.com/account.html" -UseBasicParsing -TimeoutSec 20).Content
"pub_account_v7=$($pub2.Contains('watchscore.css?v=7'))"
if (-not $pub2.Contains('watchscore.css?v=7')) { Write-Host "!! 公网 account.html 版本号不对" -ForegroundColor Red; exit 1 }
$pub3 = (Invoke-WebRequest -Uri "https://a.ai24x.com/js/watchscore.js" -UseBasicParsing -TimeoutSec 20).Content
"pub_js_remove=$($pub3.Contains('data-wl-act="remove"'))"
if (-not $pub3.Contains('data-wl-act="remove"')) { Write-Host "!! 公网 watchscore.js 无删除动作" -ForegroundColor Red; exit 1 }

Write-Host "=== 部署成功 OK ===" -ForegroundColor Green
```

## 验收清单（回执时逐条列出）
- HEAD=140826e9c524（merge-base 校验通过）
- 文件标记：watchscore.js `data-wl-act="remove"` / watchscore.css `.wl-confirm-mask` / watchscore.html `watchscore.js?v=7` / account.html `watchscore.css?v=7`
- 服务 PID 变化（before/after）／health 200
- 公网：watchscore.html/account.html `?v=7`、js/watchscore.js 含删除动作
- 浏览器端（Ctrl+F5，用户侧确认）：自选榜每行出现「删除」按钮，点击弹居中确认框（不再跳到浏览器顶部），确认后行消失、刷新后不再出现
- ⚠️ 问题项：无则写「无」

## 回执格式（03 自动发指挥部群）
- ✅ 已完成项：HEAD／文件标记／重启+health／公网内容标记
- ⚠️ 问题项：逐条（无则写「无」）
- 凭据纪律：不回执任何 token 明文；备份目录仅报路径。

## 回滚预案
- `git revert 140826e9c524` + `nssm restart AI24X-a1-api`；或恢复 `C:\backup\ai24x_a\20260823_pre_140826e\*.bak` + `nssm restart AI24X-a1-api`。
