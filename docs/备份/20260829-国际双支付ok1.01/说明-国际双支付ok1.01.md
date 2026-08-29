# 国际双支付 OK 1.01 备份

- **备份时间**：2026-08-29
- **版本标签**：国际双支付ok1.01
- **相对 ok1.0**：含 www 计费对比/$0.35 锚点、首页模型示意、About Spend Smarter、admin 图形验证码（commit `640dd61ae4c7` / 回执 `d5b5c79`）
- **用途**：PayPal + Dodo 国际双通道 + 本批 www 体验定稿；含数据库，可回滚代码与订单/钱包状态
- **Git**：见 `manifest.json` 的 `git_head`

## 范围（代码）

| 模块 | 路径 |
|------|------|
| 支付核心 | `api/token_pay_service.py`、`api/pay_paypal.py`、`api/pay_dodo.py`、`api/billing_money.py` |
| 产品与路由 | `api/pay_products.py`、`api/main.py`、`api/schemas.py` |
| 控制台结账 | `web/js/console.js`、`web/js/api.js`、`web/console.html` |
| 定价 / 首页 / About | `web/pricing.html`、`web/index.html`、`web/about.html` |
| 管理台登录 | `web/token-admin.html` |
| 套餐覆盖 | `api/data/token_plans_override.json`、`api/data/byok_plans_override.json` |
| open 代理 | `p/open/api/main.py` |

## 范围（数据库表）

- `token_pay_orders` / `token_wallets` / `billing_ledger` / `token_credit_lots`
- 另有全库 `db/full.dump`（本机 / 04 各自落盘）

## 备份

```powershell
# 本机
powershell -NoProfile -ExecutionPolicy Bypass -File docs\备份\20260829-国际双支付ok1.01\scripts\backup.ps1

# 副脑04 生产
powershell -NoProfile -ExecutionPolicy Bypass -File C:\ai24x01\docs\备份\20260829-国际双支付ok1.01\scripts\backup.ps1 -RepoRoot C:\ai24x01 -EnvFile C:\ai24x01\api\.env
```

## 回滚

```powershell
# 仅支付表（默认干跑；加 -Apply 写入）
powershell -NoProfile -ExecutionPolicy Bypass -File docs\备份\20260829-国际双支付ok1.01\scripts\rollback.ps1 -Apply

# 代码 + 库
powershell -NoProfile -ExecutionPolicy Bypass -File docs\备份\20260829-国际双支付ok1.01\scripts\rollback.ps1 -Apply -RestoreCode
```

回滚后重启：`Restart-Service AI24X-core -Force`（动到 open 账单则一并 `AI24X-open-api`）。

## 注意

- **勿**把 `db/*.dump` 提交进 git
- 04 回滚前先确认本机 / 04 各自的 dump 路径，互不覆盖
- 国际双支付口径：PayPal + Dodo（银行卡）
