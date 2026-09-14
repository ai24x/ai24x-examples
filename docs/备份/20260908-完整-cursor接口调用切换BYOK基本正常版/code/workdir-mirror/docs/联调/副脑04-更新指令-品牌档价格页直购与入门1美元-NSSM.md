# 副脑04 · 更新指令（品牌档表 + 价格页直购 + 入门包 $1）

> 发令：2026-08-01  
> **进程：NSSM `AI24X-core`（禁止 pm2 启停 core）**  
> **禁止**整文件覆盖 `api/.env`  
> 远端：`git pull origin master`（或 `gitee master`）

## 本包内容

| 项 | 说明 |
|----|------|
| 调用名页 | 增加 **AI24X 品牌档**表（auto/flash/pro/ultra/shared）+ 整理 VIP 点名单表 |
| 价格页 | 套餐卡直接 **微信 / 支付宝 / PayPal** 下单（图标）；控制台管 Key/订单 |
| 入门包 | 锚定 **$1**（CNY≈¥7.20），每账号限购 1 次 |
| 控制台 | 价格页 `?plan=&pay=` 深链自动点开对应支付按钮 |

## `.env` 行级核对

若入门包仍显示旧价（¥1 / ¥9.9），删掉或改写：

```
# 删除该行，或改为（与 $1×7.2 对齐）：
TOKEN_PRICE_TOKEN_PACK_10K_FEN=720
```

管理台价表若写死入门包分，一并改成 **720** 或清覆盖。改完必须重启 core。

---

## 执行（PowerShell · 整段复制）

```powershell
Set-Location C:\ai24x01

git status
git checkout master
git pull origin master
# 若失败：git pull gitee master
git log -1 --oneline
# 期望含：$1 / brand tiers / pricing pay 一类说明

Select-String -Path C:\ai24x01\api\.env -Pattern "^TOKEN_PRICE_TOKEN_PACK_10K_FEN="

Get-Service AI24X-core | Format-Table Name, Status
Restart-Service AI24X-core
Start-Sleep -Seconds 5
Get-Service AI24X-core | Format-Table Name, Status

try { (Invoke-WebRequest "http://127.0.0.1:8002/health" -UseBasicParsing -TimeoutSec 15).StatusCode } catch { $_.Exception.Message }

$plans = (Invoke-WebRequest "http://127.0.0.1:8002/v1/billing/plans" -UseBasicParsing -TimeoutSec 20).Content | ConvertFrom-Json
$p10 = @($plans.plans | Where-Object { $_.plan -eq "token_pack_10k" })[0]
"10k_yuan=$($p10.price_yuan) usd=$($p10.price_usd) promo=$($p10.promo) max=$($p10.promo_max_purchases)"

curl.exe -sS -o NUL -w "pricing=%{http_code}`n" https://www.ai24x.com/pricing.html
curl.exe -sS -o NUL -w "vip_picks=%{http_code}`n" https://www.ai24x.com/models/vip-picks.html
curl.exe -sS -o NUL -w "console=%{http_code}`n" https://www.ai24x.com/console.html
```

---

## 验收（回报主脑）

1. `git log -1` 为本包提交  
2. core Running · health **200**  
3. `10k_usd=1` 或 `1.0` · `10k_yuan`≈`7.20` · `max=1`  
4. Ctrl+F5：  
   - https://www.ai24x.com/models/vip-picks.html → 有「AI24X 品牌档位」表 + VIP 点名表  
   - https://www.ai24x.com/pricing.html → 套餐卡有微信/支付宝/PayPal 按钮（通道就绪时）  
5. （可选）登录后点价格页 PayPal，应跳转控制台并自动打开支付  

## 不要做

- 不要 `pm2 restart` core  
- 不要整文件覆盖 `.env`  
- 不要再开模拟到账  
