# Token 管理后台 · 信息架构与首期设计（设计稿）

> 2026-07-30 · 承接 `Token管理后台与品牌对外口径.md`  
> 入口：`web/token-admin.html`（已有左导航壳）  
> 原则：先本机 → 再生产；**禁止**网页改写生产 `.env` 密钥

---

## 1. 导航结构（对标行情官壳，内容独立）

```
总览
├─ 看板（今日充值/消耗/新用户/失败单）
支付与订单
├─ 待履约
├─ 全部订单
├─ 支付通道（微信/支付宝/PayPal 就绪态 · 只读）
用户与钱包
├─ 查用户 / 加额 / VIP
├─ 用户流水
模型与系统
├─ 路由状态（upstream 模式、L1/L2/L3 档位映射 · 只读）
├─ 系统开关（价表/mock/注册 · 白名单配置，后续）
```

用户端永不展示上游品牌；**本后台可展示** upstream id（运维需要）。

---

## 2. 首期 API（已有 / 待补）

| 能力 | 状态 | 路径 |
|------|------|------|
| 看板 summary | ✅ | `GET /v1/admin/token/summary` |
| 订单列表/履约 | ✅ | `GET/POST /v1/admin/token/orders*` |
| 查用户/加额 | ✅ | `GET /v1/admin/users/lookup` · `POST .../topup` |
| 流水 | ✅ | `GET /v1/admin/token/ledger` |
| 支付通道状态 | ✅ | `GET /v1/billing/pay/status`（admin 面板只读展示） |
| 路由状态 | ✅ | `GET /v1/admin/token/routing` → mode、L0–L3/QI、key_set |
| 用户冻结 | ❌ P1 | `POST /v1/admin/users/{id}/freeze` |
| 系统开关 | ❌ P2 | 配置表或受限 env 白名单 |

鉴权统一：`X-SMS-Internal-Key`（与现 token-admin 一致）。

---

## 3. 「支付通道」面板设计

每通道一张卡（只读）：

- 名称：微信 / 支付宝 / PayPal  
- 状态：就绪 / 未配置 / mock  
- PayPal：`mode=sandbox|live`，webhook 是否配置  
- **不展示** Client Secret、商户私钥；仅 `configured=true` + 末四位 mask（若有）  
- 文案：「改密钥请服务器行级改 `.env` + 重启服务」

---

## 4. 「路由状态」面板设计

- `upstream_mode`: openrouter | direct  
- 对外档 → 上游 id 表（admin 可见 DeepSeek/MiMo）  
- 提示：切换模式用运维指令，不提供网页写 Key  
- 按钮：「复制副脑切换指令」→ 剪贴板文本（无密钥）

---

## 5. 本迭代编码顺序

1. ✅ 用户控制台品牌隐藏 + 系统提示 + API 档位名  
2. ✅ Admin：`GET /v1/admin/token/routing` + token-admin「路由状态」面板  
3. ✅ Admin：通道面板接 `pay/status` 细化（脱敏 mode / webhook）  
4. ⏳ PayPal Webhook（本机 Sandbox）  
5. ⏳ 入门包正式价  

---

## 6. 下一迭代设计（本机优先）

### 6.1 PayPal Webhook（履约兜底）

- **目标**：用户关页/回跳失败时，Webhook 仍能把 pending → paid 并入账  
- **本机**：Sandbox webhook → 本机隧道或先 mock 验签路径；验 `PAYPAL_WEBHOOK_ID`  
- **生产**：Live webhook 仍挂 API 宿主；改 `.env` 行级 + 重启  
- **管理台**：通道卡已显示 `webhook: 已设/未设`；后续可加「最近 webhook 事件」只读（P1）

### 6.2 入门包正式价

- 价表拆：`starter` 正式价（国际口径）+ 可选 `debug` / 内部 SKU（仅 mock 或白名单）  
- 控制台默认只展示正式档；debug 不进公网页  
- 改价后回归：plans API、创建单金额、到账 tokens 一致

### 6.3 用户冻结（P1）

- `POST /v1/admin/users/{id}/freeze` + `unfreeze`  
- 冻结后：禁登录 JWT 新签 / 禁 chat / 禁充值（择一先做 chat+充值）  
- token-admin 用户行增加按钮 + 原因备注

---

*设计可随实现微调；不照搬行情官游戏模块。*
