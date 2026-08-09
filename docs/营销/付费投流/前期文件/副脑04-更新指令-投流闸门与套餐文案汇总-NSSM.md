# 副脑04 · 更新指令（投流前闸门 + 5 档套餐 + 账单文案汇总 · NSSM）

> 发令：2026-08-05 · **副脑04 = 对外生产**（www.ai24x.com / api.ai24x.com）
> 目标提交：`e5e2680`（`git log -1 --oneline` 应显示该 hash）
> **禁止**整文件覆盖 `api/.env`；只改需要的行
> 远端：`git pull origin master`（失败再 `git pull gitee master`）

## 本包

| 项 | 说明 |
|----|------|
| 安全闸门 | client_ip 信任链、登录 8/IP 30 频控、OTP 错 5 锁 15min、生产 PayPal 验签（无 WEBHOOK_ID→503）、CORS 收窄、X-Admin-Key |
| 套餐 | 5 档：Starter $2 / VIP Pass $15（30 天资格·无额度）/ Builder $20 / Advanced $49 / Scale $99（365 天 VIP + 2 亿） |
| 账单 UI | 订单金额按渠道显示（PayPal 美元 / 微信支付宝人民币）；VIP Pass「无额度」；点名模列区分「有（需额度）」 |
| 文案/i18n | 中英同步、去掉「自定义充值即将开放」、FAQ pro/ultra 非 VIP 门槛、英文弱化 CNY 表述 |

## 执行

```powershell
Set-Location C:\ai24x01

git status
git checkout master
git pull origin master
git log -1 --oneline   # 期望 e5e2680

# API 侧：重启 core（新表启动自动 create_all）
Get-Service AI24X-core | Format-Table Name, Status
Restart-Service AI24X-core
Start-Sleep -Seconds 3
Get-Service AI24X-core | Format-Table Name, Status
```

## 生产 api/.env 必查（实付口径）

```
APP_ENV=production
TOKEN_PAY_ENABLED=true
TOKEN_PAY_MOCK_ENABLED=false
PAYPAL_MODE=live
PAYPAL_WEBHOOK_ID=xxxx          # 非空；缺失时 /v1/billing 相关会 503
CORS_ORIGINS=* 或显式 www/ai24x.com
ADMIN_API_KEY=xxxx              # 可选；不配则管理接口仍兼容旧 SMS 钥
TOKEN_WECHAT_NOTIFY_URL=https://api.ai24x.com/v1/billing/wechat/notify
TOKEN_ALIPAY_NOTIFY_URL=https://api.ai24x.com/v1/billing/alipay/notify
TOKEN_ALIPAY_RETURN_URL=https://www.ai24x.com/console.html
```

改完 env 后：`Restart-Service AI24X-core`。

## 验收

1. 环回与公网均 200：
```powershell
curl.exe -sS http://127.0.0.1:8002/health
curl.exe -sS -o NUL -w "%{http_code}" https://api.ai24x.com/health
curl.exe -sS -o NUL -w "%{http_code}" https://www.ai24x.com/console.html
```
2. 套餐接口 5 档：`/v1/billing/plans` 含 Starter/VIP Pass/Builder/Advanced/Scale
3. 控制台 Billing：Scale 推荐位；VIP Pass 显示「无额度/No credits」；点名模列「有（需额度）」
4. 订单列表：PayPal 单显示 `$`，微信/支付宝单显示 `¥`/`CNY`
5. 可选冒烟：`python api/scripts_gate_smoke.py --base https://api.ai24x.com`
6. 公网硬刷新（Ctrl+F5）console.html / pricing.html

## 回滚

```powershell
Set-Location C:\ai24x01
git log -5 --oneline
git checkout <上一稳定 commit>
Restart-Service AI24X-core
```
紧急关支付：`TOKEN_PAY_ENABLED=false` → 重启 core。
