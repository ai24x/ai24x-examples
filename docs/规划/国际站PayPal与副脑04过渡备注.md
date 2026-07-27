# 国际站 · PayPal · 副脑04 过渡备注

> 日期：2026-07-27  
> 状态：PayPal 商户审核中；代码已具备 Sandbox 骨架  
> 岗位总纲：`docs/规划/主脑副脑岗位与国际Token供给-1.0.md`

---

## 1. 域名最终分配（拍板口径）

| 域名 | 机器 | 说明 |
|------|------|------|
| `www.ai24x.com` | **副脑04**（国际正式） | 品牌站 / 控制台 / 英文默认 |
| `api.ai24x.com` | **副脑04** | Token / 登录 / **PayPal Live** / 国际库 |
| `a.ai24x.com` | **副脑03** | 行情官 + 微信/支付宝（Native 回调继续挂 a1） |

过渡期（当前）：`www`+`api` 仍在 **副脑03** 验闭环；迁 04 时同构搬迁，不重做业务。

**节点策略**：国际入口 **先 1× 新加坡**；不加美/欧主机，除非稳定流水 + 延迟/合规证据（先升配 SG → 再美西 → 再欧区）。

---

## 2. 开发顺序（已确认）

1. 本机跑通功能与流程  
2. 副脑03 公网跑通（微信/支付宝已通）  
3. PayPal：**Sandbox 任意环境调** → **Live 只开 04**  
4. 迁 `www`+`api` 到 04；`a.` 留 03  
5. **无独立预发机**：本机合格 → Gitee → 生产门禁（环回+公网+回滚）

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
收款说明页（审核用，noindex）：`web/paypal.html`  
价格页已强化 PayPal CTA → 控制台 `?pay=paypal`

---

## 3.1 商户审核 · 网站集成说明（打回「未集成 PayPal」时用）

### 产品路径（拍板）

- **真收款**：登录后在 **控制台** 点 PayPal（需账户才能入账 Token）
- **公开露出**：[`pricing.html`](../../web/pricing.html) 写明 PayPal（USD）+「PayPal 购买」深链；[`paypal.html`](../../web/paypal.html) 英文流程说明
- **审核员登录**：专用演示账号写在 PayPal 后台「其他信息」，**不要**写进公开页面

### 店铺链接建议

- `https://www.ai24x.com/paypal.html`
- `https://www.ai24x.com/pricing.html`
- `https://www.ai24x.com/console.html`

### 「其他信息」模板（粘贴 + 附图）

```
【PayPal 收款说明 / How buyers pay】
Product: AI24X prepaid Token plans (digital API credits, no shipping)
Site: https://www.ai24x.com
Flow:
1) https://www.ai24x.com/pricing.html — choose a plan → “Pay with PayPal”
2) Sign in → https://www.ai24x.com/console.html?pay=paypal
3) Click the PayPal button on the plan card
4) Complete checkout on PayPal.com; return URL credits Token wallet
Guide page: https://www.ai24x.com/paypal.html
Privacy / Terms: /privacy.html · /terms.html

Demo login (reviewers only — do not publish):
URL: https://www.ai24x.com/login.html?next=console.html%3Fpay%3Dpaypal
Email: <填演示邮箱>
Password: <填演示密码>

Screenshots attached: pricing PayPal CTA, console PayPal button, PayPal checkout page.
```

### 生产露出按钮（过审前提）

生产 `api/.env` **行级**配置（禁止整文件 Write）：

```
TOKEN_PAY_ENABLED=true
PAYPAL_MODE=sandbox
PAYPAL_CLIENT_ID=...
PAYPAL_CLIENT_SECRET=...
TOKEN_PAYPAL_RETURN_URL=https://www.ai24x.com/console.html
TOKEN_PAYPAL_CANCEL_URL=https://www.ai24x.com/console.html
```

然后：`pm2 restart core-api-8002 --update-env`  
验收：`GET /v1/billing/pay/status` → `paypal.ready` / plans 里 `paypal_ready=true`，控制台出现 PayPal 按钮。  
Live 密钥待商户审核通过后再切。

---

## 4. 微信 Native 唯一回调

商户后台 Native 回调**只能填一个** → **继续 a1**。  
Token 靠查单/自动确认到账；订单参数里仍可带 Token notify（若微信按订单 URL 通知则更好）。

---

## 5. 模型供给（国际网关侧）

欧盟默认 **Qwen 国际**；非欧盟默认 **DeepSeek**；高峰不对用户加价，路由切固定价上游。详见岗位总纲 §四。

---

## 6. 醒后联调清单

见 `memory/daily/2026-07-27.md`。
