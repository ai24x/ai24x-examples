# Token 真支付上线清单（勿改 a1 回调）

## 原则
- **绝不**修改行情官 a1 的 `wechat_notify_url` / `alipay_notify_url`
- Token 使用独立环境变量：`TOKEN_WECHAT_NOTIFY_URL` / `TOKEN_ALIPAY_NOTIFY_URL`
- 商户单号前缀：`T…`（a1 为 `M…`）
- 订单表：`token_pay_orders`（不是 `pay_orders`）
- 可与 a1 **共用同一商户号**，但回调地址必须是 Token 自己的

## 当前进度（本机）
- mock 履约：✅  
- DeepSeek / 注册 / 控制台：✅  
- 商户凭证：✅ 已从 a1 `admin_config` 安全同步到 `api/.env`（**未复制** a1 notify）  
- Token 独立 notify URL：✅ 已预填  
- `TOKEN_PAY_ENABLED`：仍为 **false**（等小额实付前再开）

同步脚本（可重复执行）：
```
python api/scripts_sync_pay_from_a1.py
pm2 restart core-8000 --update-env
```

自检：`GET http://127.0.0.1:8000/v1/billing/pay/status`  
期望：`wechat.merchant_configured=true` · `alipay.merchant_configured=true` · notify 已设 · enabled=false


## 雷总需配合提供（或从 a1 已跑通配置对照抄）

微信（v3）：
- `WECHAT_MCH_ID` / `WECHAT_APP_ID` / `WECHAT_MCH_SERIAL_NO`
- `WECHAT_MCH_PRIVATE_KEY_PATH`（或 PEM）
- `WECHAT_API_V3_KEY`

支付宝：
- `ALIPAY_APP_ID`
- `ALIPAY_MERCHANT_PRIVATE_KEY_PATH`（或 PEM）
- `ALIPAY_PUBLIC_KEY`

> a1 侧常见前缀为 `AI24X_WECHAT_*`；主站 Token 用**无前缀**的 `WECHAT_*` / `ALIPAY_*`（见 `api/config.py`）。

## 主站 `api/.env`（已建议）
```
TOKEN_PAY_ENABLED=false
TOKEN_PAY_MOCK_ENABLED=true
TOKEN_WECHAT_NOTIFY_URL=https://api.ai24x.com/v1/billing/wechat/notify
TOKEN_ALIPAY_NOTIFY_URL=https://api.ai24x.com/v1/billing/alipay/notify
TOKEN_ALIPAY_RETURN_URL=https://www.ai24x.com/console.html
```

商户平台里把 **Native/手机网站支付回调** 增加（或单独配置）上述 Token URL；**保留** a1 原回调不动。

## 开启真支付步骤
1. 凭证写入 `api/.env` 后：`pm2 restart core-8000 --update-env`
2. 打开 `/v1/billing/pay/status` → `merchant_configured=true` 且 notify 已设  
3. a1 扫码付一笔仍正常（回归）  
4. 控制台 Token 套餐小额实付一单 → 查 `token_pay_orders` + 钱包余额  
5. 确认无误再设 `TOKEN_PAY_ENABLED=true`（可先保持 mock 并行）

## 国际支付（并行申请，后接代码）
- PayPal / Stripe：现在去申请账号与商户审核即可  
- **代码接入排 Phase 2**（与英文站一起），不挡国内真付调试
