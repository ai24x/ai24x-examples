# 【04 更新】token-admin 订单用户标注+后台中文化 + Dodo 支付切 LIVE

> 通道：司令直连 04（deploy04.ps1）｜ 目标提交 **26f2e6d**
> 04 主机：43.160.246.30 · 仓库 C:\ai24x01 · 服务 AI24X-core（NSSM，8002）+ AI24X-open-api（18080）
> 本次涉及 api/ 后端（订单列表返回用户邮箱/手机）+ web/token-admin.html（用户列/中文化）+ **Dodo 支付从 test 切 live（含密钥配置、live 商品同步、收银台冒烟）**
> 前置：C:\Users\Administrator\ops\dodo_env_live_20260824.ps1 已由司令 scp 到位（含 live key/webhook secret，勿外传勿提交）

## 背景
老板放行：① token-admin「支付与订单」订单列表标注下单用户（邮箱/手机号，无则 #ID），CSV 导出加 user_email/user_phone 列；后台状态/通道/套餐筛选与状态徽章全面中文化。② Dodo 支付切换正式模式（live key 有效、live 商品 0 个干净），live 商品由同步器自动创建 11 个（markets 3 + BYOK 2 + token 6），webhook ×2 已建好（www + open，事件 payment.succeeded/failed）。本地 QA：_qa_admin_orders_zh_20260824.js 11/11 全绿。

## 执行步骤（PowerShell，整段复制运行）
```powershell
$ErrorActionPreference = "Stop"
$REPO = "C:\ai24x01"
$EXP  = "26f2e6d"

Set-Location $REPO

"--- 0) 备份本批文件本地脏改动再还原（防 pull 冲突）---"
$FILES = @("web/token-admin.html","api/token_pay_service.py")
$BK = "C:\backup\tokenadmin_20260824_pre_26f2e6d"
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
$c1 = Get-Content "$REPO\web\token-admin.html" -Raw -Encoding UTF8
$c2 = Get-Content "$REPO\api\token_pay_service.py" -Raw -Encoding UTF8
$m1 = $c1.Contains('userLabel') -and $c1.Contains('marketsUserLabel') -and $c1.Contains('待支付')
$m2 = $c2.Contains('user_email') -and $c2.Contains('user_phone')
"mark_admin=$m1 mark_service=$m2"
if (-not ($m1 -and $m2)) { Write-Host "!! 文件标记缺失" -ForegroundColor Red; exit 1 }

"--- 3) 应用 Dodo LIVE 密钥补丁（core+open 两处 .env，幂等+备份+打码）---"
$PATCH = "C:\Users\Administrator\ops\dodo_env_live_20260824.ps1"
if (-not (Test-Path $PATCH)) { Write-Host "!! 补丁脚本不存在: $PATCH" -ForegroundColor Red; exit 1 }
powershell -NoProfile -ExecutionPolicy Bypass -File $PATCH
$coreMode = (Get-Content "$REPO\api\.env" | Select-String '^DODO_MODE=').Line
$openMode = (Get-Content "$REPO\p\open\api\.env" | Select-String '^DODO_MODE=').Line
"core_$coreMode open_$openMode"
if ($coreMode -ne "DODO_MODE=live" -or $openMode -ne "DODO_MODE=live") { Write-Host "!! DODO_MODE 未切 live" -ForegroundColor Red; exit 1 }

"--- 4) 重启 core(8002) + open(18080)，health commit 校验 ---"
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
Restart-Service AI24X-open-api -Force
$openOk = $false
for ($i = 0; $i -lt 24; $i++) {
  Start-Sleep -Seconds 5
  try {
    $oh = Invoke-RestMethod -Uri "http://127.0.0.1:18080/health" -TimeoutSec 10 -UseBasicParsing
    if ($oh.status -eq "ok") { $openOk = $true; break }
  } catch {}
}
"open_ok=$openOk"
if (-not $openOk) { Write-Host "!! open 未恢复" -ForegroundColor Red; exit 1 }

"--- 5) Dodo LIVE 商品同步（自动创建 11 个正式商品并回写 override）---"
$admKey = ((Get-Content "$REPO\api\.env" | Select-String '^ADMIN_API_KEY=').Line -split '=',2)[1].Trim()
if ([string]::IsNullOrEmpty($admKey)) { Write-Host "!! 未找到 ADMIN_API_KEY" -ForegroundColor Red; exit 1 }
$sync = Invoke-RestMethod -Uri "http://127.0.0.1:8002/v1/admin/products/dodo/sync" -Method Post -Headers @{ "X-Admin-Key" = $admKey } -TimeoutSec 120 -UseBasicParsing
"sync_mode=$($sync.mode) created=$($sync.summary.created) updated=$($sync.summary.updated) unchanged=$($sync.summary.unchanged) errors=$($sync.summary.errors)"
if ($sync.mode -ne "live" -or $sync.summary.created -ne 11 -or $sync.summary.errors -ne 0) {
  Write-Host "!! live 同步结果异常" -ForegroundColor Red
  $sync.items | ForEach-Object { "  " + $_.product + "/" + $_.plan + " -> " + $_.action + " " + $_.note }
  exit 1
}

"--- 6) live 商品核对（用 .env 里的 live key 拉 Dodo 后台，断言 11 个+正式价）---"
$dodoKey = ((Get-Content "$REPO\api\.env" | Select-String '^DODO_API_KEY=').Line -split '=',2)[1].Trim()
$ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
$items = @()
try {
  $resp = Invoke-RestMethod -Uri "https://live.dodopayments.com/products?page_size=100&page_number=0&archived=false" -Headers @{ "Authorization" = "Bearer $dodoKey"; "User-Agent" = $ua } -TimeoutSec 30 -UseBasicParsing
  $items = @($resp.items)
} catch { Write-Host "!! live 商品拉取失败: $($_.Exception.Message)" -ForegroundColor Red; exit 1 }
"live_products=$($items.Count)"
if ($items.Count -ne 11) { Write-Host "!! live 商品数异常" -ForegroundColor Red; exit 1 }
$metaOk = 0
$priceOk = 0
foreach ($it in $items) {
  $md = $it.metadata
  $cents = $it.price.price
  $okMeta = $md -and $md.product -and $md.plan
  $okPrice = $cents -gt 0
  if ($okMeta) { $metaOk++ }
  if ($okPrice) { $priceOk++ }
}
"meta_ok=$metaOk price_ok=$priceOk"
if ($metaOk -ne 11 -or $priceOk -ne 11) { Write-Host "!! live 商品 metadata/价格异常" -ForegroundColor Red; exit 1 }

"--- 7) live 收银台冒烟（$2 Starter 档，只建会话不付款）---"
$qaEmail = "dodo.live.qa.20260824@ai24x.local"
$qaPass = "DodoLiveQa#2026"
try {
  $reg = Invoke-RestMethod -Uri "http://127.0.0.1:8002/v1/auth/register" -Method Post -ContentType "application/json" -Body (@{ email = $qaEmail; password = $qaPass } | ConvertTo-Json) -TimeoutSec 20 -UseBasicParsing
  $qaToken = $reg.token
} catch {
  $login = Invoke-RestMethod -Uri "http://127.0.0.1:8002/v1/auth/login" -Method Post -ContentType "application/json" -Body (@{ email = $qaEmail; password = $qaPass } | ConvertTo-Json) -TimeoutSec 20 -UseBasicParsing
  $qaToken = $login.token
}
if ([string]::IsNullOrEmpty($qaToken)) { Write-Host "!! QA 用户获取 token 失败" -ForegroundColor Red; exit 1 }
$order = Invoke-RestMethod -Uri "http://127.0.0.1:8002/v1/billing/dodo/order" -Method Post -ContentType "application/json" -Headers @{ "Authorization" = "Bearer $qaToken" } -Body (@{ plan = "token_pack_10k" } | ConvertTo-Json) -TimeoutSec 30 -UseBasicParsing
$payUrl = [string]$order.pay_url
"pay_url_host=" + ([Uri]$payUrl).Host + " otn=$($order.out_trade_no) amount_usd=$($order.amount_usd)"
if ($payUrl -notmatch "checkout\.dodopayments\.com" -or $payUrl -match "test\.") {
  Write-Host "!! live 收银台 URL 异常: $payUrl" -ForegroundColor Red; exit 1
}

"--- 8) webhook 端点可达（无签名应返回 401/非 404，证明路由+live secret 已配）---"
$wh = $null
try { Invoke-RestMethod -Uri "http://127.0.0.1:8002/v1/billing/dodo/webhook" -Method Post -ContentType "application/json" -Body "{}" -TimeoutSec 10 -UseBasicParsing | Out-Null } catch { $wh = $_.Exception.Response.StatusCode.value__ }
$wh2 = $null
try { Invoke-RestMethod -Uri "http://127.0.0.1:18080/v1/billing/dodo/webhook" -Method Post -ContentType "application/json" -Body "{}" -TimeoutSec 10 -UseBasicParsing | Out-Null } catch { $wh2 = $_.Exception.Response.StatusCode.value__ }
"core_webhook_status=$wh open_webhook_status=$wh2"
if ($wh -eq 404 -or $wh2 -eq 404) { Write-Host "!! webhook 路由 404" -ForegroundColor Red; exit 1 }

"--- 9) 公网抽查（?x= 穿透）---"
$u1 = (Invoke-WebRequest -Uri "https://www.ai24x.com/token-admin.html?x=20260824live" -UseBasicParsing -TimeoutSec 25).Content
$pm1 = $u1.Contains('userLabel')
"pub_admin_mark=$pm1"
if (-not $pm1) { Write-Host "!! 公网 token-admin 内容不对（可能缓存，换 ?x= 再试）" -ForegroundColor Red; exit 1 }

Write-Host "=== 部署成功 OK（Dodo 已切 live）===" -ForegroundColor Green
```

## 验收清单（回执时逐条列出）
- HEAD=26f2e6d（merge-base 校验通过）／文件标记 2 条（token-admin userLabel+marketsUserLabel+待支付；token_pay_service user_email/user_phone）
- Dodo live 密钥补丁应用成功（core/open DODO_MODE=live，备份 .bak-dodo-live-*；**不回执任何 key/secret 明文**）
- core 8002 PID 变化 + health commit=26f2e6d；open 18080 health ok
- live 商品同步：mode=live、created=11、errors=0；live 后台商品 11 个、metadata/price 全对
- live 收银台冒烟：$2 Starter（token_pack_10k）pay_url host=checkout.dodopayments.com 且不含 test.（QA 用户 dodo.live.qa.20260824@ai24x.local，仅建会话未付款，订单待过期清理）
- webhook 端点 core/open 均非 404；公网 token-admin.html 含 userLabel
- ⚠️ 问题项：无则写「无」

## 回执格式（04 自动发指挥部群）
- ✅ 已完成项：HEAD／文件标记／DODO_MODE=live／core+open 重启 health／live 同步 created=11／收银台冒烟 host／webhook 非 404／公网标记
- ⚠️ 问题项：逐条（无则写「无」）
- 凭据纪律：不回执 DODO key、webhook secret、ADMIN_API_KEY 任何明文；备份目录仅报路径

## 回滚预案
- 密钥回滚：恢复 core/open .env 的 `.bak-dodo-live-*` 备份并改回 DODO_MODE=test，重启两服务
- 代码回滚：`git revert 26f2e6d` + `Restart-Service AI24X-core -Force`；或恢复 `C:\backup\tokenadmin_20260824_pre_26f2e6d\*.bak`
