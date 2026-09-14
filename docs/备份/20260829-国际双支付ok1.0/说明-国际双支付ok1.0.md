# 国际双支付 OK 1.0 备份

- **备份时间**：2026-08-29
- **版本标签**：国际双支付ok1.0
- **用途**：PayPal + Dodo（银行卡）国际双通道支付中台稳定快照；含数据库，可回滚代码与订单/钱包状态
- **Git 提交**：见 `manifest.json` 的 `git_head`

## 范围（代码）

| 模块 | 路径 |
|------|------|
| 支付核心 | `api/token_pay_service.py`、`api/pay_paypal.py`、`api/pay_dodo.py`、`api/billing_money.py` |
| 产品与路由 | `api/pay_products.py`、`api/main.py`（billing 段）、`api/schemas.py` |
| 控制台结账 | `web/js/console.js`、`web/js/api.js`、`web/console.html` |
| 定价页 | `web/pricing.html` |
| 套餐覆盖 | `api/data/token_plans_override.json`、`api/data/byok_plans_override.json` |
| open 代理 | `p/open/api/main.py`（billing 代理段） |

## 范围（数据库表）

- `token_pay_orders` — 支付订单（channel: paypal / dodo / wechat / alipay …）
- `token_wallets` — 用户钱包余额
- `billing_ledger` — 账务流水
- `token_credit_lots` — 额度批次（充值履约）

完整库快照另见 `db/full.dump`（若本机有库连接）。

## 使用

### 备份（本机或 04）

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File docs\备份\20260829-国际双支付ok1.0\scripts\backup.ps1
```

可选：`-EnvFile C:\ai24x01\api\.env`（04 生产）、`-RepoRoot C:\ai24x01`

### 回滚

```powershell
# 仅恢复数据库（默认干跑，加 -Apply 才写入）
powershell -NoProfile -ExecutionPolicy Bypass -File docs\备份\20260829-国际双支付ok1.0\scripts\rollback.ps1 -Apply

# 代码 + 数据库
powershell -NoProfile -ExecutionPolicy Bypass -File docs\备份\20260829-国际双支付ok1.0\scripts\rollback.ps1 -Apply -RestoreCode
```

回滚后：**重启 `AI24X-core`**（及涉及 `AI24X-open-api` 时一并重启）。

## 验收口径（OK 1.0）

- 控制台 `#billing` 可见 PayPal + 银行卡（Dodo）通道（`paypal_ready` / `dodo_ready`）
- `POST /v1/billing/paypal/order`、`POST /v1/billing/dodo/order` 可建单
- 履约后 `token_pay_orders.status=paid` 且钱包/流水一致

## 注意

- **勿**把 `db/*.dump` 或 `.env` 提交进 git（含用户与订单数据）
- 04 回滚前先在服务器执行 `backup.ps1` 再改库
- Creem 已停用展示；本快照以 **PayPal + Dodo** 为国际双支付口径
