# VIP 订单与后台管理（核心）

## 数据与状态

- 订单表：`pay_orders`（`out_trade_no`、`user_id`、`plan`、`amount_fen`、`status`：`pending` / `paid`、`transaction_id` 等）。
- 支付成功发 VIP：`admin_ops_ledger` 中 `action` 含 **`billing:vip`**（与配额 `quota` 同事务写入）。

## 管理后台能力

| 能力 | 说明 |
|------|------|
| 列表 / 筛选 | 用户 ID、状态、套餐、**关键词 `q`**（商户单号 / 微信单号模糊；纯数字额外匹配 `user_id`） |
| 分页 | `limit`（10–200）、`offset`；切换左侧「VIP 订单」会回到第一页并自动刷新 |
| 导出 | **导出 CSV**（UTF-8 BOM，当前筛选，默认最多 **5000** 条；URL 参数 `cap` 可调至 10000） |
| 客诉联查 | **点击订单行** → 打开「用户与配额」并选中该用户 → 下方 **运维操作记录** 可看 `billing:vip` |

## API（均需管理员登录）

- `GET /api/admin/pay_orders` — JSON 列表（支持 `user_id`、`status`、`plan`、`q`、`limit`、`offset`）。
- `GET /api/admin/pay_orders_export` — CSV（支持同上筛选参数 + `cap`）。

## 部署注意

- 改后端后需 **重启 p/a API 进程**（如 `pm2 restart a-api-18031`），浏览器 F5 才会拿到新逻辑。

## 后期（未做）

- 微信已付、本地未到账时的 **补记账 / 安全重放**（须审计与权限分级）。
- 退款态 `refunded`、与微信账单 **自动对账**。
