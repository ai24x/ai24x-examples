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

## 开启真支付步骤（副脑03 实付）
1. 凭证写入生产 `api/.env` 后：`pm2 restart core-api-8002 --update-env`
2. 打开 `/v1/billing/pay/status` → `merchant_configured=true`；`/v1/billing/plans` → `wechat_ready`/`alipay_ready` 为 true
3. a1 扫码付一笔仍正常（回归）  
4. 设 `TOKEN_PAY_ENABLED=true` 且 **`TOKEN_PAY_MOCK_ENABLED=false`**（关模拟；只留「确认到账」）
5. 控制台 Token 套餐小额实付一单 → 查 `token_pay_orders` + 钱包余额  
6. 详见 `docs/联调/Token发版-Gitee与副脑03.md`

### 线上现象对照（2026-07-27）
`https://www.ai24x.com/console.html` 只显示「下单/支付通道未就绪」且无法跳转支付：  
因 `api.ai24x.com` 上 **`TOKEN_PAY_ENABLED=true` 但 `wechat_configured`/`alipay_configured` 均为 false**（商户号/密钥路径未进 **core** 的 `api/.env`，私钥 path 不存在）。  
本机 `:8000` 有微信/支付宝按钮 = 本机商户已配齐。  
**修复**：把 a1 已跑通的商户项按无前缀变量写入 `C:\ai24x01\api\.env`（**禁止 Write 整文件覆盖**），确认私钥文件路径对 core 进程可读，再 `--update-env` 重启。

### 推荐：直接复用行情官 a1 商户密钥（2026-07-27）

**可以共用**：商户号、AppId、序列号、API v3、私钥文件/PEM、支付宝密钥。  
**不能共用**：支付回调 URL（Token 必须用 `TOKEN_WECHAT_NOTIFY_URL` / `TOKEN_ALIPAY_NOTIFY_URL`）。

代码默认 `TOKEN_PAY_REUSE_A1=true`：core 里空的或 `***` 损坏字段，运行时从 a1 `admin_config` 或 `p/a1/api/server/.env` 的 `AI24X_*` 自动补齐。

副脑03 最少只需保证：

```
TOKEN_PAY_ENABLED=true
TOKEN_PAY_MOCK_ENABLED=false
TOKEN_PAY_REUSE_A1=true
TOKEN_WECHAT_NOTIFY_URL=https://api.ai24x.com/v1/billing/wechat/notify
TOKEN_ALIPAY_NOTIFY_URL=https://api.ai24x.com/v1/billing/alipay/notify
TOKEN_ALIPAY_RETURN_URL=https://www.ai24x.com/console.html
```

并把 core `.env` 里写成 `***` 的 `WECHAT_MCH_PRIVATE_KEY_PEM` / `ALIPAY_MERCHANT_PRIVATE_KEY_PEM` **删掉或清空**（避免挡住回退），然后 `pm2 restart core-api-8002 --update-env`。

### 备选：本机导出同步包 → 副脑03 一键应用（避免 PEM 被打成 `***`）

本机（主脑）已通支付后：

```powershell
Set-Location E:\AI24X\ai24x-website\ai24x01
python api/scripts_export_token_pay_bundle.py
# 生成 E:\AI24X\bak\token-pay-bundle-时间戳\ 与同名 .zip（含 certs/*.pem + pay.env）
```

把 **zip**（勿进 git）拷到副脑03，例如 `C:\ai24x-transfer\token-pay-bundle.zip`，然后：

```powershell
Set-Location C:\ai24x01
git pull origin master
Set-Location C:\ai24x01\api
python scripts_apply_token_pay_bundle.py C:\ai24x-transfer\token-pay-bundle.zip
curl.exe -sS http://127.0.0.1:8002/v1/billing/plans
```

说明：脚本把私钥落到 `api/certs\`，`.env` 只写 **PATH**，清空 PEM 内联，避免聊天/Cursor 脱敏成 `***`。

## 国际支付（并行申请，后接代码）
- PayPal / Stripe：现在去申请账号与商户审核即可  
- **代码接入排 Phase 2**（与英文站一起），不挡国内真付调试
