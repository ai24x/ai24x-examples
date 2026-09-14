# Creem 国际支付接入（Token 平台）1.0

> 状态：代码已接入（本地），待 Creem 审核通过后填 key 联调
> 注册：creem.io（店铺 ai24x）；KYC 以 Individual 身份，选择 "Product ready for production = Yes"
> 我方已具备：隐私政策 / 服务条款页（Creem 审核要求）

## 1. 为什么接 Creem
- MoR 模式（Merchant of Record）：190+ 国税务代缴，大陆主体无需海外实体
- 费率 3.9% + $0.40 固定（比 Paddle/LS 5%+50¢ 便宜约 22%）
- AI 聚合类目友好：非生成式（文本/API 网关）不强制 Moderation API
- 与 PayPal 同构：Checkout 下单 + Webhook(HMAC-SHA256) + metadata 关联，改造小
- 无支付宝/微信（对国际站无碍）；作 PayPal 之外的第二国际通道 / 备用

## 2. 已落地代码
| 文件 | 内容 |
|---|---|
| api/pay_creem.py | 新建：creem_api_base / creem_configured / create_checkout_session / verify_webhook_signature / extract_checkout_data |
| api/config.py | 新增 CREEM_API_KEY / CREEM_WEBHOOK_SECRET / CREEM_MODE / CREEM_RETURN_URL |
| api/token_plans.py | 套餐新增可编辑字段 creem_product_id（管理后台可见，公共接口不暴露） |
| api/token_pay_service.py | pay_settings_ns 加 creem 配置；public_plans 加 creem_configured/creem_ready；create_pending_order 支持 creem（USD 美分）；新增 create_creem_order / query_creem_order；admin 汇总 by_channel_paid 加 creem |
| api/main.py | POST /v1/billing/creem/order、POST /v1/billing/creem/query、POST /v1/billing/creem/webhook；/v1/billing/pay/status 加 creem 块 |
| web/js/api.js | billingCreemOrder；billingQueryFulfill 支持 creem |
| web/js/console.js | 通道标签/图标/按钮/买流程/订单金额 $ / return 自动确认 |
| web/token-admin.html | 通道卡片、筛选、汇总统计、fenLabel 支持 creem |
| api/.env.example | Creem 配置模板 |

## 3. 配置步骤（拿到 key 后）
1. Creem 后台为 5 档套餐各建 1 个商品（Product），复制 product_id
2. 管理后台「套餐管理」把 product_id 填入对应套餐的 creem_product_id 字段（保存即生效）
3. api/.env 配置：
   ```
   CREEM_MODE=test            # 联调用 test；上线前改 live
   CREEM_API_KEY=xxx
   CREEM_WEBHOOK_SECRET=xxx
   CREEM_RETURN_URL=https://www.ai24x.com/console.html
   ```
4. Creem 后台配置 Webhook URL：https://api.ai24x.com/v1/billing/creem/webhook
   （本地联调可用内网穿透；Webhook Secret 与 .env 一致）
5. 重启 core（本地 pm2 restart core-api-8002 --update-env / 生产同款）
6. 验证：
   - GET /v1/billing/pay/status → creem.merchant_configured=true
   - 控制台购买出现 Creem 按钮；下单返回 checkout_url
   - 测试卡支付 → 回跳 console?creem=1&out_trade_no=T… → 自动确认到账
   - Creem 后台发测试 Webhook → 订单变 paid、余额到账

## 4. Webhook 说明（checkout.completed）
- 验签：header `creem-signature` = HMAC-SHA256(webhook_secret, raw body) hex，`hmac.compare_digest` 比较
- 生产/live：未配置 secret → 400；验签失败 → 400（与 PayPal 同策略）
- test/sandbox/dev：验签失败仅告警放行（本地联调方便），生产绝不
- 履约字段：object.request_id（我方单号 T…）、object.order.id（ord_，作 transaction_id）、object.product.id、object.order.amount（分）
- 金额策略：以本地订单金额履约（Creem order.amount 可能含税），若金额不同仅记日志；产品 ID 不匹配则拒绝
- 幂等：沿用 token_pay_orders 原子抢占（pending→paid），重复 webhook 返回 duplicate

## 5. 回滚
- 代码：git revert 对应 commit + 重启 core
- 配置：删 .env 中 CREEM_* 行 + 重启
- 数据：token_pay_orders / BillingLedger 已有常规备份

## 6. 待办（需人工）
- [ ] Creem 审核通过（KYC Individual + Product readiness）
- [ ] 建 5 个商品并填 product_id
- [ ] 提供 test key + webhook secret
- [ ] 本地 test 联调（建议先 test 后 live）
- [ ] 生产 live key + 生产 webhook 配置