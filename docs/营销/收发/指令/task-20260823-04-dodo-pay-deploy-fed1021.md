# 【04 更新部署验收】Dodo 支付接入上线（www core + open.ai24x.com）· fed1021

> 司令已提交并双推（gitee + origin 均为 `fed1021`）；老板已放行（2026-08-23）。
> 执行人：副脑04（本机 `C:\ai24x01`；服务 `AI24X-core` 8002 + `AI24X-open-api` 18080）。

## 一、任务背景
- Dodo Payments（国际 USD，MoR 模式）接入：
  - www core（api/）：Dodo 代码已在 046d4d9 就位，本次只补 `DODO_*` 环境变量并重启。
  - open.ai24x.com（p/open/api）：本次新增 `pay_dodo.py` + `/v1/billing/dodo/{order,query,webhook}` + 套餐 `dodo_product_id`；控制台 BYOK 改列表式、平台托管选套餐弹窗、套餐价统一美元（中文界面也显示 `$`）。
- 版本号：open 全站共享资源 `v=20260823b`。
- 生产仍为 `DODO_MODE=test`（与本地一致，老板已核对商品价格）；切 live 见文末备注。

## 二、前置：密钥补丁脚本
- 司令已直接 scp：`C:\Users\Administrator\ops\dodo_env_20260823.ps1`（含 www core + open 两处 .env 的 DODO_*，执行时只打码回显前 6 位）。
- **若该文件不存在，先停在这里联系司令，勿自行猜值。**

## 三、部署步骤（整段复制运行；每段失败先看日志再继续）

### A. 拉取代码 + 校验
```powershell
$ErrorActionPreference = "Stop"
$REPO = "C:\ai24x01"
$EXP  = "fed1021"
Set-Location $REPO
$dirty = git status --porcelain -- p/open p/markets/scripts/_qa_open_dodo_20260823.js p/markets/scripts/_qa_www_dodo_20260823.js
if ($dirty) { Write-Host "目标路径有本地改动，先备份再 stash：" -ForegroundColor Yellow; $dirty; git stash push -u -m "open-dodo-before-fed1021" }
git pull --ff-only
$HEAD = (git rev-parse --short=12 HEAD).Trim()
"HEAD=$HEAD"
git merge-base --is-ancestor $EXP HEAD
if ($LASTEXITCODE -ne 0) { Write-Host "!! 目标 commit 不在历史" -ForegroundColor Red; exit 1 }
git diff --quiet $EXP HEAD -- p/open
if ($LASTEXITCODE -ne 0) { Write-Host "!! p/open 与目标不一致" -ForegroundColor Red; exit 1 }
Write-Host "A 代码校验通过" -ForegroundColor Green
```

### B. 应用 DODO 环境变量（密钥脚本）
```powershell
$patch = "C:\Users\Administrator\ops\dodo_env_20260823.ps1"
if (-not (Test-Path $patch)) { Write-Host "!! 缺少密钥补丁脚本，停住联系司令" -ForegroundColor Red; exit 1 }
powershell -NoProfile -ExecutionPolicy Bypass -File $patch
if ($LASTEXITCODE -ne 0) { Write-Host "!! 环境变量补丁失败" -ForegroundColor Red; exit 1 }
Write-Host "B 环境变量已应用" -ForegroundColor Green
```

### C. 重启服务
```powershell
Restart-Service AI24X-core -Force
Restart-Service AI24X-open-api -Force
```

### D. 本机验收
```powershell
# core 8002
$ok = $false
for ($i = 0; $i -lt 24; $i++) { Start-Sleep -Seconds 5; try { $h = Invoke-RestMethod -Uri "http://127.0.0.1:8002/health" -TimeoutSec 10 -UseBasicParsing; $ok = $true; break } catch {} }
if (-not $ok) { Write-Host "!! core /health 未就绪" -ForegroundColor Red; exit 1 }
"core health status=$($h.status) commit=$($h.commit)"
if ($h.status -ne "healthy" -or "$($h.commit)" -notlike "$EXP*") { Write-Host "!! core 未生效" -ForegroundColor Red; exit 1 }

# open 18080
$ok2 = $false
for ($i = 0; $i -lt 24; $i++) { Start-Sleep -Seconds 5; try { $h2 = Invoke-RestMethod -Uri "http://127.0.0.1:18080/health" -TimeoutSec 10 -UseBasicParsing; $ok2 = $true; break } catch {} }
if (-not $ok2) { Write-Host "!! open /health 未就绪，看 C:\ai24x01\logs\open-api.err.log" -ForegroundColor Red; exit 1 }
"open health status=$($h2.status) commit=$($h2.commit)"
if ($h2.status -ne "healthy" -or "$($h2.commit)" -notlike "$EXP*") { Write-Host "!! open 未生效" -ForegroundColor Red; exit 1 }

# open dodo 路由
$spec = Invoke-RestMethod -Uri "http://127.0.0.1:18080/openapi.json" -TimeoutSec 10 -UseBasicParsing
$paths = $spec.paths.PSObject.Properties.Name
"dodo order route: " + ($paths -contains "/v1/billing/dodo/order")
"dodo query route: " + ($paths -contains "/v1/billing/dodo/query")
"dodo webhook route: " + ($paths -contains "/v1/billing/dodo/webhook")
if (($paths -contains "/v1/billing/dodo/order") -and ($paths -contains "/v1/billing/dodo/query") -and ($paths -contains "/v1/billing/dodo/webhook")) { Write-Host "D-route OK" -ForegroundColor Green } else { Write-Host "!! dodo 路由缺失" -ForegroundColor Red; exit 1 }

# dodo_ready 自检（公开接口）
$ps = Invoke-RestMethod -Uri "http://127.0.0.1:8002/v1/billing/pay/status" -TimeoutSec 10 -UseBasicParsing
"core dodo_configured=" + $ps.dodo_configured
$ps2 = Invoke-RestMethod -Uri "http://127.0.0.1:18080/v1/billing/pay/status" -TimeoutSec 10 -UseBasicParsing
"open dodo_configured=" + $ps2.dodo_configured
if (-not $ps.dodo_configured -or -not $ps2.dodo_configured) { Write-Host "!! dodo_configured 为假，检查 .env" -ForegroundColor Red; exit 1 }

# 版本号 + 价格美元
$html = Get-Content -Raw -Encoding UTF8 "C:\ai24x01\p\open\web\console.html"
if ($html -notmatch 'js/api\.js\?v=20260823b') { Write-Host "!! open 版本号不是 20260823b" -ForegroundColor Red; exit 1 }
$apiJs = Get-Content -Raw -Encoding UTF8 "C:\ai24x01\p\open\web\js\api.js"
if ($apiJs -match 'if \(isZhUi\(\)\) return "¥"') { Write-Host "!! 中文 ¥ 分支未移除" -ForegroundColor Red; exit 1 }
Write-Host "D 本机验收全部通过" -ForegroundColor Green
```

### E. 公网验收（04 服务器侧执行）
```powershell
$h3 = Invoke-RestMethod -Uri "https://www.ai24x.com/health" -TimeoutSec 15 -UseBasicParsing
"www health commit=$($h3.commit)"
$h4 = Invoke-RestMethod -Uri "https://open.ai24x.com/health" -TimeoutSec 15 -UseBasicParsing
"open health commit=$($h4.commit)"
$ps3 = Invoke-RestMethod -Uri "https://www.ai24x.com/v1/billing/pay/status" -TimeoutSec 15 -UseBasicParsing
"www dodo_configured=$($ps3.dodo_configured)"
$ps4 = Invoke-RestMethod -Uri "https://open.ai24x.com/v1/billing/pay/status" -TimeoutSec 15 -UseBasicParsing
"open dodo_configured=$($ps4.dodo_configured)"
$web = (Invoke-WebRequest -Uri "https://open.ai24x.com/console.html?x=1" -UseBasicParsing -TimeoutSec 15).Content
"open version 20260823b: " + ($web -match 'js/api\.js\?v=20260823b')
Write-Host "E 公网验收完成" -ForegroundColor Green
```

## 四、验收清单（回执时逐项列 ✅/⚠️）
1. www `https://www.ai24x.com/health` commit = fed1021
2. open `https://open.ai24x.com/health` commit = fed1021
3. open `/openapi.json` 含 dodo order/query/webhook 三路由
4. www + open `/v1/billing/pay/status` dodo_configured = true
5. open console.html 引用 `js/api.js?v=20260823b`（公网无旧版本残留）
6. open `api.js` 无中文 ¥ 分支（平台托管套餐价统一美元）
7. 服务重启后 core 8002 / open 18080 均 healthy

## 五、备注（重要，不在本次步骤内）
- **webhook**：需老板在 Dodo 后台创建（生产环境）：
  - open：`https://open.ai24x.com/v1/billing/dodo/webhook`
  - www：`https://www.ai24x.com/v1/billing/dodo/webhook`
  - 订阅事件：`payment.succeeded` + `payment.failed`；webhook secret 创建后请老板发回司令核验。
- **live 切换**：当前 `DODO_MODE=test`（test.dodopayments.com）。真实收款前需老板在 Dodo **live** 后台创建同款商品（markets 周/月/年、token 六包、BYOK 月/年）并把商品 ID 同步回来，04 再改 `DODO_MODE=live` 重启。**本次保持 test 模式，勿自行改 live。**
- open 控制台登录验收：`https://open.ai24x.com/console.html` 登录后 Plans → 平台托管 / BYOK 列表应显示美元价并可弹窗选择 Dodo 支付。

## 六、回执格式（完成后发指挥部群）
```text
✅ 已完成项：
1. ...
⚠️ 问题项：
1. 无（或具体说明）
```
