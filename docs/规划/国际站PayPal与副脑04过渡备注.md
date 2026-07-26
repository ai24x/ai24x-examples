# 国际站 · PayPal · 副脑04 过渡备注

> 日期：2026-07-27  
> 状态：PayPal 商户审核中；代码已具备 Sandbox 骨架

---

## 1. 域名最终分配（拍板口径）

| 域名 | 机器 | 说明 |
|------|------|------|
| `www.ai24x.com` | **副脑04**（国际正式） | 品牌站 / 控制台 / 英文默认 |
| `api.ai24x.com` | **副脑04** | Token / 登录 / **PayPal Live** / 国际库 |
| `a.ai24x.com` | **副脑03** | 行情官 + 微信/支付宝（Native 回调继续挂 a1） |

过渡期（当前）：`www`+`api` 仍在 **副脑03** 验闭环；迁 04 时同构搬迁，不重做业务。

---

## 2. 开发顺序（已确认）

1. 本机跑通功能与流程  
2. 副脑03 公网跑通（微信/支付宝已通）  
3. PayPal：**Sandbox 任意环境调** → **Live 只开 04**  
4. 迁 `www`+`api` 到 04；`a.` 留 03  

**不要**在 03 上开 PayPal Live 养国际用户再整库搬 04。

---

## 3. PayPal 代码入口（已落地）

| 项 | 路径 |
|----|------|
| 客户端 | `api/pay_paypal.py` |
| 下单/Capture | `POST /v1/billing/paypal/order` · `POST /v1/billing/paypal/capture` |
| Webhook | `POST /v1/billing/paypal/webhook` |
| 控制台 | `paypal_ready` 时显示 PayPal 按钮；return `?paypal=1&out_trade_no=` 自动确认 |
| 金额 | `token_pay_orders.amount_fen` 对 PayPal = **USD 美分** |

环境变量见 `api/.env.example`：`PAYPAL_CLIENT_ID` / `SECRET` / `MODE=sandbox` / `WEBHOOK_ID` / `TOKEN_PAYPAL_*_URL`。

信任页（审核用）：`web/privacy.html` · `web/terms.html`

---

## 4. 微信 Native 唯一回调

商户后台 Native 回调**只能填一个** → **继续 a1**。  
Token 靠查单/自动确认到账；订单参数里仍可带 Token notify（若微信按订单 URL 通知则更好）。

---

## 5. 醒后联调清单

见 `memory/daily/2026-07-27.md`。
