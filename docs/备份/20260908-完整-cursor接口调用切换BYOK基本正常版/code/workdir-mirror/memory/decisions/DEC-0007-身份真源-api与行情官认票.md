# DEC-0007：身份真源在 `api/`，行情官「认票」+ 影子用户

## 状态

已定稿（2026-04-18）

## 背景

AI 行情官需尽快上线，且注册为 **手机 | 邮箱** 二选一、**均需验证码**；同时避免与后续 **主站 Token 自由 / 统一计费** 再做一遍用户迁移。

## 决策

1. **终端用户真源**：账号表 **`auth_users`** 落在主仓 **`api/`**（与现有 `users` API Key 网关表 **分离**），字段含 `phone` / `email`（可空但注册路径各自必填其一）、`password_hash`、`phone_verified_at` / `email_verified_at`。
2. **JWT**：由 `api/` 使用环境变量 **`SECRET_KEY`** 签发；载荷与行情官原实现一致：`sub`（平台用户 id）、`email`、`phone`、`iat`、`exp`；**`AUTH_JWT_EXPIRE_DAYS`** 默认与行情官 `AI24X_JWT_EXPIRE_DAYS` 对齐（默认 7 天）。
3. **行情官 `p/a`**：  
   - 环境变量 **`AI24X_JWT_SECRET` 必须与 `api` 的 `SECRET_KEY` 同值**；  
   - 环境变量 **`AI24X_IDENTITY_API_BASE`** 指向 `api` 根 URL（如 `http://127.0.0.1:8000`）；  
   - **`AI24X_SMS_INTERNAL_KEY`** 与 `api` 的 **`SMS_INTERNAL_KEY`** 一致，供本站 **服务端** 代理 `/v1/auth/sms/send` 时带 `X-SMS-Internal-Key`；  
   - 每个需登录的接口在解析 JWT 后调用 **`ensure_platform_user(sub, email, phone)`**，在本地 `users` / `quota` 写入或更新 **影子行**（**`users.id` = 平台 id**），保证邀请/计次/支付外键不变。
4. **邮箱验证码（MVP）**：`api` 进程内 **`email_otp_memory`** + 非生产返回 `dev_code`；生产接 SMTP 后发信，不在本 DEC 展开。

## 理由

- **一条用户线** 支撑 www、a、及后续 `api.ai24x.com` 的 Key/计费。  
- **子域工程边界** 保留：`p/a` 不复制用户主库，只同步业务所需的影子表。  
- **安全**：短信 internal key 不出浏览器，由 `p/a` 反向代理注入。

## 后果与后续

- 已存在的 **纯本地邮箱 1234** 开发用户与平台 id **不连续**，接受为开发期代价；生产以 `auth_users` 为准。  
- **中期**：www 静态注册页可直接调 `api` 或经 BFF，与 `a` 共用同一套 `/v1/auth/*`。
