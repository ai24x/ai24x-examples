# 副脑03 · 更新指令（PayPal 审核露出 + Capture 幂等）

> 发令时间：2026-07-27  
> 目标：拉最新 `master`，让 **www 控制台可见 PayPal 购买按钮**（Sandbox 即可过审），并更新静态价格页 / paypal 说明页。  
> **勿动** a1 支付回调、行情官、微信/支付宝商户号。  
> **禁止**整文件 Write 生产 `api/.env`（只行级增改）。

## 本次上线目的

1. 公网可走：`pricing.html` → 登录 → `console.html` → **PayPal** → Sandbox/Live 结账  
2. 审核页：`https://www.ai24x.com/paypal.html`  
3. API：PayPal 二次 Capture（`ORDER_ALREADY_CAPTURED`）改为查单履约，不再对用户甩原始报错  

## 改动范围

| 路径 | 说明 |
|------|------|
| `web/paypal.html` | 审核说明页（noindex） |
| `web/pricing.html` · `web/config/locales.js` | PayPal CTA |
| `web/console.html` · `web/js/console.js` | PayPal 按钮 / 回跳确认 |
| `api/token_pay_service.py` 等 | Capture 幂等 + Token 支付相关 |
| `api/.env.example` | 仅示例键名，**无密钥** |

---

## 执行步骤（PowerShell，仓库根）

```powershell
cd <你的仓库根目录>

git fetch origin
git checkout master
git pull origin master

git rev-parse --short HEAD
git log -1 --oneline
Test-Path web/paypal.html
Test-Path web/js/console.js
Select-String -Path web/js/console.js -Pattern "ALREADY_CAPTURED" -SimpleMatch
```

### A. 静态（必须）

确认 www 静态根已含：

- `web/paypal.html`
- `web/pricing.html`
- `web/console.html`
- `web/js/console.js`（`?v=20260727pp2` 或更新）
- `web/config/locales.js`

若用拷贝发布：同步上述文件到静态根。纯静态一般**不必**重启行情官。

### B. 生产 `api/.env`（行级，必须有 PayPal 键才会出按钮）

在现有 `.env` **末尾追加或改行**（值用你们 Sandbox；**先不要 Live**，等商户审核通过）：

```
TOKEN_PAY_ENABLED=true
PAYPAL_MODE=sandbox
PAYPAL_CLIENT_ID=<Sandbox Client ID>
PAYPAL_CLIENT_SECRET=<Sandbox Secret>
TOKEN_PAYPAL_RETURN_URL=https://www.ai24x.com/console.html
TOKEN_PAYPAL_CANCEL_URL=https://www.ai24x.com/console.html
```

自检：`DATABASE_URL` 等行**不得**出现省略号 `…`。

然后加载新代码 + 新环境（二选一，优先能确认跑的是新代码）：

```powershell
# 推荐：若你们习惯 delete+start（见事故文档）
pm2 describe core-api-8002
pm2 restart core-api-8002 --update-env

# 若怀疑未加载新代码：按你们既有门禁 delete 后再按 ecosystem 拉起 core-api-8002
pm2 list
```

---

## 验收（更新后回复主脑）

1. `git rev-parse --short HEAD` + `git log -1 --oneline`  
2. 无痕打开：  
   - `https://www.ai24x.com/paypal.html` → 200  
   - `https://www.ai24x.com/pricing.html` → 有 PayPal /「PayPal 购买」  
3. 登录演示账号进控制台：套餐卡片出现 **PayPal** 按钮  
4. （API）`GET https://api.ai24x.com/v1/billing/pay/status` 或控制台拉 plans：`paypal_ready` / `paypal.ui_ready` 为 **true**  
5. **不要**在公网页写演示密码；密码只留在 PayPal 后台「其他信息」

## 回滚

```powershell
# 静态：回上一提交的 web 相关文件（提交号问主脑或用 pull 前 HEAD）
git checkout <旧SHA> -- web/paypal.html web/pricing.html web/console.html web/js/console.js web/config/locales.js

# API：回退 api 相关后 pm2 restart core-api-8002 --update-env
# 若 PayPal 键导致异常：行级注释掉 PAYPAL_* 后同样 --update-env（按钮会隐藏，不影响微信/支付宝）
```

## 注意

- 本次 **RETURN/CANCEL 必须是 www console**，不要写成 `127.0.0.1`。  
- Live 密钥待 PayPal 商户审核通过后再切；切时仍只行级改 `.env`。  
- 禁止动 `p/a1/**` 支付回调。  
