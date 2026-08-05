# AI24X × Airwallex 空中云汇 国际卡收单集成设计 1.0

> 状态：规划中（Airwallex 账号已注册，待审核开放「在线收单」权限）
> 目标：Airwallex 卡片收单作为国际站主支付通道，PayPal 保留兜底；微信/支付宝仅服务中文区。

## 1. 通道布局与主备策略

| 通道 | 定位 | 币种/金额口径 | 超时窗口 |
|---|---|---|---|
| Airwallex（卡收单 Visa/MC） | **主（国际站）** | USD 美分（同 PayPal 口径） | 72h（清理/对账窗口，与 PayPal 对齐） |
| PayPal | 兜底（国际站） | USD 美分 | 72h |
| 微信 / 支付宝 | 中文区专用 | CNY 分 | 24h |
| mock | 本地/联调 | 随通道 | 24h |

- 下单优先级：按 `PAY_CHANNEL_PRIORITY=airwallex,paypal` 顺序选择可用通道；`public_plans().pay.airwallex_ready` 为 false 时自动跳过 Airwallex，走 PayPal。
- 主通道创建失败（凭证无效/网络/风控拒绝）→ 返回降级通道（PayPal）支付链接，不阻断用户。
- 前端展示：国际站只展示 Airwallex + PayPal 两个入口；中文站展示微信/支付宝（现状不变）。

## 2. 前置条件（审核开放权限后确认）

- [ ] Airwallex 商户主体入驻完成（申请类别：数字类软件开发）。
- [ ] 确认开通权限范围：**在线收单（Card Acquiring）**，而非仅全球账户/收款。
- [ ] 拿到沙箱凭证：`CLIENT_ID` + `API_KEY(Secret)` + Webhook Secret；沙箱地址 `https://api-demo.airwallex.com/api/v1/`。
- [ ] 与商务确认：预充值 token（先收款后交付）业务的准入与风控政策、默认拒付率红线、结算周期。
- [ ] 生产域名 `https://api.ai24x.com` 加入 Airwallex 允许列表；Webhook URL 需公网可达。

## 3. 配置清单（api/.env 新增）

```
AIRWALLEX_CLIENT_ID=
AIRWALLEX_API_KEY=            # client secret，绝不硬编码
AIRWALLEX_MODE=sandbox        # sandbox/live
AIRWALLEX_API_BASE=https://api-demo.airwallex.com   # live 时 https://api.airwallex.com
AIRWALLEX_WEBHOOK_SECRET=
AIRWALLEX_RETURN_URL=https://www.ai24x.com/console.html
AIRWALLEX_CANCEL_URL=https://www.ai24x.com/pricing.html
AIRWALLEX_INTENT_TTL_MINUTES=1440   # PaymentIntent 有效期，默认 24h
PAY_CHANNEL_PRIORITY=airwallex,paypal
```

- `config.py` 增加对应字段（沿用现有 `paypal_*` 字段风格）。
- 生产 `AIRWALLEX_MODE=live` 后才允许真实收款；`public_plans().pay` 新增 `airwallex_configured` / `airwallex_ready` / `airwallex_mode`，沿用现有通道就绪逻辑。

## 4. 技术设计

### 4.1 新增/改动文件
- 新增 `api/pay_airwallex.py`：OAuth 取 token、创建/确认 PaymentIntent、查询 intent、Webhook 验签、退款/查捕获（结构对齐 `pay_paypal.py`）。
- 改动 `api/token_pay_service.py`：
  - `create_pending_order`：`channel == "airwallex"` 走 USD 美分口径（同 paypal 分支）。
  - 新增 `create_airwallex_order(db, auth_user_id, plan)`：镜像 `create_paypal_order`。
  - `pending_order_expired`：airwallex 归入 72h 组（同 paypal）。
  - `public_plans()`：pay 状态加 airwallex 三项。
  - 清理/对账/确认未收款（`cleanup_expired_pending_orders` / `confirm_order_unpaid` / `admin_list_orders`）：airwallex 与 paypal 同规则——有交易号且未确认未收款保留待对账，确认未收款后超时作废。
- 改动 `api/main.py`：
  - `POST /v1/token/pay/airwallex`（下单，返回 `client_secret`/托管页 URL 或降级通道）。
  - `POST /v1/pay/airwallex/webhook`（无需管理钥，验签后处理）。
  - 可选 `GET /v1/pay/airwallex/status?out_trade_no=`（前端轮询兜底）。
- 改动 `api/admin_ops_service.py` / `api/ops_alert.py`：`airwallex_not_ready` 预警 + 通道就绪统计。
- 前端：`console.html`/`pricing.html` 支付区新增 Airwallex 按钮与 Drop-in 渲染（或用托管支付页跳转，最小改动）。

### 4.2 下单流程（服务端）
1. `create_pending_order(channel="airwallex")` → `amount_fen`=USD 美分。
2. `pay_airwallex.create_payment_intent`：`amount`(cents)、`currency=USD`、`merchant_order_id=out_trade_no`、`request_id=out_trade_no`（幂等）。
3. 存 `row.transaction_id = payment_intent_id`、`row.code_url = client_secret`（或托管页 URL）。
4. 返回给前端：`{ client_secret, intent_id, channel:"airwallex", amount_usd }`；前端用 Airwallex.js Drop-in 完成卡片支付（含 3DS）。
5. 兜底轮询：前端 5s 轮询订单状态接口，或直接等 Webhook 后刷新。

### 4.3 Webhook 验签与事件处理
- 事件：订阅 `payment_intent.completed`、`payment_intent.cancelled`（沙箱联调时以实际可用事件名为准；拒付/退款事件后续按需订阅）。
- 验签：HMAC-SHA256（webhook secret + 时间戳 + body），比对 `x-signature`/`x-timestamp` 头；时间戳超 5 分钟拒绝（防重放）。
- 幂等：按 payload 内事件稳定 `id` 去重（落 `webhook_events` 表或复用订单流水），Airwallex 3 天指数退避重试，必须返回 200。
- 事件顺序不保证：以 `created_at` 排序；`completed` 才履约（`_fulfill_order_row`，事务内校验金额/币种/单号一致）。
- `cancelled` 且未 paid → 置 `failed`（超时/用户放弃）。

### 4.4 超时、清理、对账、预警（复用现有机制）
- 超时 72h 无 `completed` → 进入清理逻辑（有交易号保留待对账，与 PayPal 相同）。
- 对账：扩展现有 L3 每日 01:00 对账任务，增加 Airwallex 结算报表核对；查单履约/确认未收款流程直接复用（含已上线的 `confirm_order_unpaid` 与每日 06:00 清理任务）。
- 预警：`pay_airwallex_not_ready`（缺 Key 或 sandbox/live 未配齐）；有效待履约/待对账口径自动纳入 airwallex 订单。

### 4.5 风控与合规
- 强制/推荐 3DS（Airwallex Drop-in 默认支持）。
- 站内明确 T&Cs 与退款政策；发货（credits 到账）记录留存，用于拒付申诉。
- 订阅拒付/争议事件，接现有「拒付 Runbook」流程。
- 上线初期限流：单账号每日购买次数/金额上限（可复用现有 promo 限制与 admin 冻结能力）。

## 5. 开发分期与验收

### 阶段 0：权限开通（当前）
- Airwallex 审核通过后：拿沙箱凭证、确认收单权限、与商务过一遍 token 业务风控。

### 阶段 1：沙箱联调（本地 + 测试环境）
- 验收：
  - 下单 → Drop-in/托管页 → 沙箱测试卡支付成功 → Webhook `completed` → credits 到账、订单 paid。
  - 验签失败/重放/金额不符 → 拒绝且不履约。
  - 取消支付 → `cancelled` → 订单 failed。
  - 超时单：保留待对账；`confirm_order_unpaid` 标记后清理任务作废（与 PayPal 同套验证脚本）。
  - `public_plans().pay` 三字段正确；`alerts/live` 显示 `airwallex_*` 状态。

### 阶段 2：灰度（生产小额）
- 只对部分用户/入口开放；PayPal 仍主通道；观察真实拒付率与结算。
- 验证生产 Webhook URL、3DS 真实流程、对账任务。

### 阶段 3：切主
- `PAY_CHANNEL_PRIORITY=airwallex,paypal`；PayPal 兜底自动接管。
- 对账/预警跑通一周后，将「待对账积压提醒」等优化按需补上。

## 6. 回滚
- 一键回退：`PAY_CHANNEL_PRIORITY=paypal` + 重启 core，即可切回 PayPal 主通道；Airwallex 代码/配置保留无害。
- 若需彻底下线：去掉 `airwallex` 优先级与前端入口即可，历史订单不受影响（已完成对账/清理流程复用）。

## 7. 待人工确认清单（发给 Airwallex 商务 / 内部确认）
1. 申请的主体能否开通「在线收单（Card Acquiring）」？大陆主体是否只能全球账户？
2. 预充值 token 业务的准入与风控政策、拒付率红线、结算周期、手续费率（含跨境/币种转换）。
3. 沙箱凭证与生产开通流程、审核时长。
4. 是否支持 `payment_intent.cancelled` 等所需事件；Webhook IP 白名单范围。
5. 退款/拒付流程与手续费承担方式。
