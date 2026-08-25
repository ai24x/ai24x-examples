# 【04 更新】Markets Phase1 规则化改造（简报/试用/Alert/多因子Screener/每日简报页）+ core 短信三通道自动兜底

> 通道：司令直连 04（deploy04.ps1）｜ 目标提交 **f2bd73b**
> 04 主机：43.160.246.30 · 仓库 C:\ai24x01 · 服务 AI24X-core（NSSM，8002）+ AI24X-markets-api（18012）
> 前置：`C:\Users\Administrator\ops\_patch_prod_sms_config_20260825.py` 已由司令 scp 到位（含腾讯/聚合短信密钥，勿外传勿提交）

## 背景
老板放行：AI24X Markets 国际版 Phase 1 合规+降本改造（规则技术简报零 LLM / 7 天 Pro 体验券 / Alert 提醒 / Screener 多因子 / 每日简报页），并连带上一批 core 管理后台「短信多通道热配置（tencent→106→juhe 自动兜底）+ 邮件系统配置」。
本地 QA：`_qa_rule_brief_20260825.py` 17/17、`_qa_phase1_ui_20260825.js` 21/21、Alert E2E + 试用 E2E 全绿、core 导入/重启/health 正常。

## 执行步骤（PowerShell，整段复制运行）
```powershell
$ErrorActionPreference = "Stop"
$REPO = "C:\ai24x01"
$EXP  = "f2bd73b"

Set-Location $REPO

"--- 0) 备份本批文件本地脏改动再还原（防 pull 冲突）---"
$FILES = @("api/main.py","api/email_smtp.py","api/schemas.py","web/token-admin.html","web/paypal.html","p/markets/api/server/app/main.py","p/markets/api/server/app/ai_brief.py","p/markets/api/server/app/billing.py","p/markets/api/server/app/screener.py","p/markets/api/server/app/providers_us.py","p/markets/web/app.html","p/markets/web/screener.html","p/markets/web/index.html","p/markets/web/sitemap.xml")
$BK = "C:\backup\markets_phase1_20260825"
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
$c1 = Get-Content "$REPO\api\main.py" -Raw -Encoding UTF8
$c2 = Get-Content "$REPO\p\markets\api\server\app\alerts.py" -Raw -Encoding UTF8
$c3 = Get-Content "$REPO\p\markets\api\server\app\key_levels.py" -Raw -Encoding UTF8
$c4 = Get-Content "$REPO\p\markets\web\daily\index.html" -Raw -Encoding UTF8
$m1 = $c1.Contains('admin_sms_config') -and $c1.Contains('send_with_failover') -and $c1.Contains('/api/brief/latest') -and $c1.Contains('/api/alerts/evaluate')
$m2 = $c2.Contains('evaluate_user_alerts') -and $c2.Contains('send_alert_email')
$m3 = $c3.Contains('compute_key_levels') -and $c3.Contains('pos_52w_pct')
$m4 = $c4.Contains('Daily US Market Brief') -and $c4.Contains('/api/brief/latest')
"mark_main=$m1 mark_alerts=$m2 mark_keylevels=$m3 mark_daily=$m4"
if (-not ($m1 -and $m2 -and $m3 -and $m4)) { Write-Host "!! 文件标记缺失" -ForegroundColor Red; exit 1 }

"--- 3) 应用生产短信通道配置补丁（腾讯主源+聚合兜底，含密钥，不入 git）---"
$PATCH = "C:\Users\Administrator\ops\_patch_prod_sms_config_20260825.py"
if (-not (Test-Path $PATCH)) { Write-Host "!! 补丁脚本不存在: $PATCH" -ForegroundColor Red; exit 1 }
$py = "C:\Users\Administrator\AppData\Local\Programs\Python\Python314\python.exe"
if (-not (Test-Path $py)) { $py = "python" }
& $py $PATCH
if ($LASTEXITCODE -ne 0) { Write-Host "!! 短信配置补丁执行失败" -ForegroundColor Red; exit 1 }

"--- 4) 重启 core(8002) + markets(18012)，health commit 校验 ---"
$beforePid = (Get-CimInstance Win32_Service -Filter "Name='AI24X-core'").ProcessId
"core_pid_before=$beforePid"
Restart-Service AI24X-core -Force
$ok = $false
for ($i = 0; $i -lt 24; $i++) {
  Start-Sleep -Seconds 5
  try {
    $svc = Get-CimInstance Win32_Service -Filter "Name='AI24X-core'"
    $afterPid = $svc.ProcessId
    $h = Invoke-RestMethod -Uri "http://127.0.0.1:8002/health" -TimeoutSec 10 -UseBasicParsing
    if ($afterPid -gt 0 -and $afterPid -ne $beforePid -and $h.commit -and $h.commit -like "$EXP*") { $ok = $true; break }
  } catch {}
}
"core_pid_after=$afterPid health_ok=$ok commit=$($h.commit)"
if (-not $ok) { Write-Host "!! core 未按预期重启或 commit 不符" -ForegroundColor Red; exit 1 }

"--- 5) 重启 markets(18012) ---"
$mkPids = @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match '18012' -and $_.Name -match 'python' } | ForEach-Object { $_.ProcessId })
foreach ($p in $mkPids) { Stop-Process -Id $p -Force }
Start-Sleep -Seconds 2
Start-Process -FilePath $py -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port','18012') -WorkingDirectory "$REPO\p\markets\api\server" -WindowStyle Hidden -RedirectStandardOutput "$REPO\p\markets\api\server\uvicorn-18012.out.log" -RedirectStandardError "$REPO\p\markets\api\server\uvicorn-18012.err.log"
$mkOk = $false
for ($i = 0; $i -lt 20; $i++) {
  Start-Sleep -Seconds 3
  try {
    $mk = Invoke-RestMethod -Uri "http://127.0.0.1:18012/health" -TimeoutSec 5 -UseBasicParsing
    if ($mk.status -eq "ok") { $mkOk = $true; break }
  } catch {}
}
"markets_ok=$mkOk"
if (-not $mkOk) { Write-Host "!! markets 未恢复" -ForegroundColor Red; exit 1 }

"--- 6) markets 静态同步到站点目录（先备份）---"
$SITE = "C:\sites\markets.ai24x.com"
$STAMP = Get-Date -Format "yyyyMMdd-HHmmss"
Copy-Item "$SITE\app.html" "$SITE\app.html.bak-$STAMP" -Force
Copy-Item "$SITE\screener.html" "$SITE\screener.html.bak-$STAMP" -Force
Copy-Item "$SITE\index.html" "$SITE\index.html.bak-$STAMP" -Force
Copy-Item "$SITE\sitemap.xml" "$SITE\sitemap.xml.bak-$STAMP" -Force
Copy-Item "$REPO\p\markets\web\app.html" "$SITE\app.html" -Force
Copy-Item "$REPO\p\markets\web\screener.html" "$SITE\screener.html" -Force
Copy-Item "$REPO\p\markets\web\index.html" "$SITE\index.html" -Force
Copy-Item "$REPO\p\markets\web\sitemap.xml" "$SITE\sitemap.xml" -Force
New-Item -ItemType Directory -Force -Path "$SITE\daily" | Out-Null
Copy-Item "$REPO\p\markets\web\daily\index.html" "$SITE\daily\index.html" -Force
"static_synced=yes backup=$STAMP"

"--- 7) markets 新端点冒烟 ---"
$s1 = Invoke-RestMethod -Uri "http://127.0.0.1:18012/api/brief/latest" -TimeoutSec 15 -UseBasicParsing
"brief_available=$($s1.data.available) dates=$($s1.data.dates -join ',')"
if ($s1.code -ne 0) { Write-Host "!! brief 端点异常" -ForegroundColor Red; exit 1 }

"--- 8) 每日简报定时任务（04:30 CST 工作日；幂等）---"
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"C:\ai24x01\p\markets\scripts\run_daily_brief.ps1`" -Python `"C:\Users\Administrator\AppData\Local\Programs\Python\Python314\python.exe`""
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At 04:30
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd
Register-ScheduledTask -TaskName "AI24X-Markets-DailyBrief" -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
$task = Get-ScheduledTask -TaskName "AI24X-Markets-DailyBrief"
"task_created=$($task.State)"
if ($task.State -ne "Ready") { Write-Host "!! 计划任务未就绪" -ForegroundColor Red; exit 1 }

"=== ALL DONE ==="
```

## 验收清单（04 回执格式）
1. HEAD=f2bd73b（12 位短哈希一致）｜ core 8002 health commit 一致
2. markets 18012 healthy；`/api/brief/latest` 返回 available=true（含已有 20260817 样例）
3. 文件标记 4/4（main/alerts/key_levels/daily）
4. markets 静态 app/screener/index/sitemap/daily 已同步（备份 .bak-$STAMP）
5. 计划任务 AI24X-Markets-DailyBrief = Ready（工作日 04:30）
6. core 新管理端点存在：/v1/admin/sms/effective、/v1/admin/sms/config、/v1/admin/email/effective、/v1/admin/email/config（200 或 401 均算端点存在）
7. 短信配置补丁已写入 `api/data/admin_sms_config.json`（active_provider=tencent，含 106/腾讯/聚合三通道）

## 注意事项
- 本次为重大项（定价/导航/账户相关），老板已本地过目并放行。
- 工作树有大量无关 docs 删除/改动，**禁止 git add -A**；04 侧 git pull 前仅还原本批 14 个文件脏改动（第 0 步）。
- 生产短信通道密钥已在补丁脚本内，勿打印明文、勿进 git、勿发群。
- 04 每日简报任务运行前先手动跑一次：`python C:\ai24x01\p\markets\scripts\brief_gen.py --api http://127.0.0.1:18012`（生成当日份后再交由计划任务）。
