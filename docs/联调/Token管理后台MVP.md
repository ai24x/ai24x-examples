# Token 管理后台（MVP）

入口：`web/token-admin.html`（同源静态，`noindex`）。

## 鉴权

- 请求头：`X-SMS-Internal-Key` = 主站 `api/.env` 的 **`SMS_INTERNAL_KEY`**
- **不是** 行情官登录密钥 `AI24X_ADMIN_KEY`（两者不同；填错会「禁止访问」）
- 本机联调：API 根地址填 `http://127.0.0.1:8000`（`api.ai24x.com` 可能尚未部署本管理接口）
- 密钥仅存浏览器 `sessionStorage`，关页即清

## 能力

| 功能 | API |
|------|-----|
| 看板 | `GET /v1/admin/token/summary`（含有效批次/批次余额） |
| 订单列表 | `GET /v1/admin/token/orders`（支持 `status` / `channel` / `q`） |
| 订单 CSV | `GET /v1/admin/token/orders/export.csv` |
| pending 查单履约 | `POST /v1/admin/token/orders/query_fulfill` |
| 查余额 | `GET /v1/admin/token/wallet?auth_user_id=`（含 `credits_expire_at`） |
| 手工加额 | `POST /v1/admin/token/topup`（可传 `validity_days`，默认 365） |
| 按邮箱/手机找用户 | `GET /v1/admin/users/lookup` |

## 页面结构（对齐行情官管理台）

- **左侧一级**：运营总览 / 支付与订单 / 用户与钱包
- **右侧子导航**：当前一级下的功能页（看板、订单、通道、加额）
- 布局参考 `p/a1/.../admin_ui.py`：一级在左，二级渲染到右侧 pills

## 本机联测清单（无 PayPal 密钥也可跑）

1. 打开 `http://127.0.0.1:8000/token-admin.html`，API 填同地址，粘贴 `SMS_INTERNAL_KEY`
2. 看板：支付通道 pill +「有效批次 / 批次余额」有数字
3. 订单：按通道筛选 → **导出 CSV**（Excel 打开无乱码）
4. 钱包：查余额应见 `credits_expire_at`；加额填「有效天数」后余额增加
5. （可选）控制台登录 → 套餐页看「额度有效 N 天」；模拟到账后余额与到期日更新
6. PayPal：需先在 `api/.env` 配 `PAYPAL_CLIENT_ID` / `PAYPAL_CLIENT_SECRET`，看板 PayPal=就绪后再测

## 使用

1. 本地：`http://127.0.0.1:8000/token-admin.html`（API 同端口）
2. 或生产静态站打开后，把「API 根地址」填成 `https://api.ai24x.com`
3. 粘贴内部密钥 → 进入工作台

## 注意

- 勿把管理页链到公开导航
- 加额会直接改钱包批次，操作前确认用户 ID 与有效天数
- 查单履约会向微信/支付宝/PayPal 主动确认后再加 Token
