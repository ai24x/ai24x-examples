# 副脑04 · 更新指令（支付图标 + VIP 预估消耗 + 入门包 ¥9.9 限购）

> 发令：2026-08-01  
> **进程：NSSM `AI24X-core`（禁止 pm2 启停 core）**  
> **禁止**整文件覆盖 `api/.env`  
> 远端：`git pull origin master`（或 `gitee master`）

## 本包内容

| 项 | 说明 |
|----|------|
| 控制台 | 微信 / 支付宝 / PayPal 按钮前小图标 |
| VIP 点名 | 倍率旁「预估消耗」（中文约¥/百万 · 英文约$/1M，按开发包折算） |
| 入门包 | 默认 **¥9.9**（约 $1.38），**每账号限购 1 次**（防刷） |
| 文件 | `api/token_plans.py`、`api/token_pay_service.py`、`api/model_warehouse.py`、`web/js/console.js`、`web/models/vip-picks.html`、locales、base.css |

## `.env` 行级核对（重要）

若仍显示 **¥1**，多半是旧覆盖，请记事本改/删：

```
# 有则改为 990，或删除该行让代码默认生效：
TOKEN_PRICE_TOKEN_PACK_10K_FEN=990
```

管理台「价表」若写死了入门包 100 分，一并改成 990 或清覆盖。  
**不要**动 `DATABASE_URL`。改完必须 `Restart-Service AI24X-core`。

---

## 执行（PowerShell · 整段复制）

```powershell
Set-Location C:\ai24x01

git status
git checkout master
git pull origin master
# 若失败：git pull gitee master
git log -1 --oneline
# 期望含：pay icons / starter promo / vip est 一类说明

# 入门包价覆盖（有旧 100 才改）
Select-String -Path C:\ai24x01\api\.env -Pattern "^TOKEN_PRICE_TOKEN_PACK_10K_FEN="
# 若为 =100 → 记事本改为 =990 或删除该行

Get-Service AI24X-core | Format-Table Name, Status
Restart-Service AI24X-core
Start-Sleep -Seconds 5
Get-Service AI24X-core | Format-Table Name, Status

try { (Invoke-WebRequest "http://127.0.0.1:8002/health" -UseBasicParsing -TimeoutSec 15).StatusCode } catch { $_.Exception.Message }

$plans = (Invoke-WebRequest "http://127.0.0.1:8002/v1/billing/plans" -UseBasicParsing -TimeoutSec 20).Content | ConvertFrom-Json
$p10 = @($plans.plans | Where-Object { $_.plan -eq "token_pack_10k" })[0]
"10k_yuan=$($p10.price_yuan) usd=$($p10.price_usd) promo=$($p10.promo) max=$($p10.promo_max_purchases)"

$m = (Invoke-WebRequest "http://127.0.0.1:8002/v1/models" -UseBasicParsing -TimeoutSec 20).Content | ConvertFrom-Json
$v = @($m.vip_picks | Select-Object -First 1)[0]
"vip_sample=$($v.id) mult=$($v.billing_mult) est_cny=$($v.est_cny_per_m) est_usd=$($v.est_usd_per_m)"

curl.exe -sS -o NUL -w "console=%{http_code}`n" https://www.ai24x.com/console.html
curl.exe -sS -o NUL -w "vip_picks=%{http_code}`n" https://www.ai24x.com/models/vip-picks.html
```

---

## 验收（回报主脑）

1. `git log -1` 为本包提交  
2. `AI24X-core` Running · health **200**  
3. `10k_yuan=9.90`（或 `9.9`）· `promo=True` · `max=1`  
4. `est_cny` / `est_usd` 有数值（非空）  
5. 浏览器 **Ctrl+F5**：  
   - 控制台支付按钮有小图标；入门包显示约 **¥9.9**  
   - https://www.ai24x.com/models/vip-picks.html 有「预估消耗」列  

## 不要做

- 不要 `pm2 restart` core  
- 不要整文件覆盖 `.env`  
- 不要再开 `TOKEN_PAY_MOCK_ENABLED=true`  
