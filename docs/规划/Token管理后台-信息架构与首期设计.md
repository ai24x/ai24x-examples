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
├─ 待履约 / 全部订单
├─ 支付通道（微信/支付宝/PayPal 就绪态 · 只读）
├─ 价表（只读 · 体验价可保留 · env 改价说明）
用户与钱包
├─ 查用户 / 加额 / VIP
├─ 用户流水
模型与系统
├─ 路由状态（upstream 模式、L1/L2/L3 · 只读）
├─ 系统开关（mock/注册 · 后续）
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
| 支付通道状态 | ✅ | `GET /v1/billing/pay/status` |
| 路由状态 | ✅ | `GET /v1/admin/token/routing` |
| 价表只读 | ✅ | `GET /v1/admin/token/plans` |
| 用户冻结 | ❌ P1 | `POST /v1/admin/users/{id}/freeze` |
| 网页改价 | ❌ 不做 | 改 `TOKEN_PRICE_*_FEN` + 重启 |

鉴权统一：`X-SMS-Internal-Key`。

---

## 3. 「支付通道」面板

- 微信 / 支付宝 / PayPal 就绪态；PayPal `mode` + webhook 是否已设  
- **不展示**密钥；国内通道保持 CNY 国内商户，**不按国际收单改造**  
- 国际 USD：**PayPal** 为主路径  

---

## 4. 「价表」面板（只读）

- 列出各套餐 CNY/USD、到账 token、是否体验价、`TOKEN_PRICE_*_FEN` 是否 env 覆盖  
- **入门包默认 ¥1 体验价继续保留**，正式规模获客前再抬  
- 改价：服务器行级改 env → 重启 API；本页无写操作  

---

## 5. 「路由状态」面板

- `upstream_mode` + 各档上游 id（运维可见）  
- 切换模式用运维指令，不网页写 Key  

---

## 6. 本迭代与优先级（已拍板）

1. ✅ 品牌隐藏 + AI24X 系统提示 + API 档位名  
2. ✅ Admin 路由 / 通道 / **价表只读**  
3. ⏸ **入门包正式价**：暂不抬；体验价保留  
4. ⏸ **PayPal Webhook**：P1 兜底（主路径 Capture 已通）  
5. ⏸ **微信/支付宝国际收单**：不做；另签国际产品再立项  
6. ⏳ 用户冻结（P1）  

---

## 7. PayPal Webhook（P1 · 说明）

- **用途**：回跳/Capture 失败时，仍靠 PayPal 服务端通知履约  
- **非阻塞**：小流量可手查 pending 履约；正式大规模对外收款前再配齐验签  

---

## 8. 用户冻结（P1）

- `freeze` / `unfreeze`；先禁 chat + 充值  

---

*设计随实现微调；不照搬行情官游戏模块。*
