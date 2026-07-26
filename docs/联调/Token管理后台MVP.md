# Token 管理后台（MVP）

入口：`web/token-admin.html`（同源静态，`noindex`）。

## 鉴权

- 请求头：`X-SMS-Internal-Key` = 主站 `.env` 的 `SMS_INTERNAL_KEY`
- 密钥仅存浏览器 `sessionStorage`，关页即清

## 能力

| 功能 | API |
|------|-----|
| 看板 | `GET /v1/admin/token/summary` |
| 订单列表 | `GET /v1/admin/token/orders` |
| pending 查单履约 | `POST /v1/admin/token/orders/query_fulfill` |
| 查余额 | `GET /v1/admin/token/wallet?auth_user_id=` |
| 手工加额 | `POST /v1/admin/token/topup` |
| 按邮箱/手机找用户 | `GET /v1/admin/users/lookup` |

## 使用

1. 本地：`http://127.0.0.1:8000/token-admin.html`（API 同端口）
2. 或生产静态站打开后，把「API 根地址」填成 `https://api.ai24x.com`
3. 粘贴内部密钥 → 进入工作台

## 注意

- 勿把管理页链到公开导航
- 加额会直接改钱包，操作前确认用户 ID
- 查单履约会向微信/支付宝/PayPal 主动确认后再加 Token
