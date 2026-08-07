# 邮箱验证码联调（SMTP）

## 目标
注册「获取验证码」走真实发信；生产不在接口里回传验证码。

> **长期选型（国际优先）**见：[`docs/规划/邮件通道-国际优先选型备注.md`](../规划/邮件通道-国际优先选型备注.md)  
> QQ 个人邮仅适合短期联调；正式对外推荐 Resend / Postmark，而非腾讯企业邮作主通道。

## 1. 配置 `api/.env`

```
SMTP_HOST=smtp.qq.com
SMTP_PORT=587
SMTP_USER=你的邮箱@qq.com
SMTP_PASSWORD=授权码（不是登录密码）
SMTP_FROM=你的邮箱@qq.com
SMTP_USE_TLS=true
SMTP_USE_SSL=false
EMAIL_OTP_SUBJECT=【AI24X】验证码
```

常见端口：
- 587 + `SMTP_USE_TLS=true`（推荐）
- 465 + `SMTP_USE_SSL=true`、`SMTP_USE_TLS=false`

然后：

```
pm2 restart core-8000 --update-env
```

## 1.5 主备双通道（2026-08-07 新增）

- 支持 **主 SMTP + 备用 SMTP**：主通道失败自动切备用（`email_smtp.py` 已实现）。
- 推荐：主通道 Zoho Mail（`smtppro.zoho.com:465 SSL 或 587 TLS`，`support@ai24x.com`），备用 QQ 个人邮。
- 主通道配置：`SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` / `SMTP_FROM` / `SMTP_USE_TLS` / `SMTP_USE_SSL`
- 备用通道配置（均带 `_BACKUP_`）：`SMTP_BACKUP_HOST` / `SMTP_BACKUP_PORT` / `SMTP_BACKUP_USER` / `SMTP_BACKUP_PASSWORD` / `SMTP_BACKUP_FROM` / `SMTP_BACKUP_USE_TLS` / `SMTP_BACKUP_USE_SSL`
- 状态接口 `GET /v1/auth/email/status` 新增字段：`smtp_configured`（主）、`smtp_backup_configured`、`smtp_primary`、`smtp_backup`；保留旧 `smtp_host` 兼容。
- 未配任何 SMTP 时行为不变：非生产走 local 卡片，生产直接失败。
## 2. 自检

```
GET http://127.0.0.1:8000/v1/auth/email/status
```

期望：`smtp_configured: true`。

## 3. 发一封

注册页填真实邮箱 →「获取验证码」→ 响应 `channel=smtp`，**无** `local_code` → 邮箱收信 → 注册。

## 4. 未配 SMTP 时

- `APP_ENV=dev`：`channel=local`，页面显示本地验证码卡片（联调）
- `APP_ENV=prod`：直接失败「邮件服务未配置」

## 5. 安全

- 勿把 SMTP 密码提交 git
- 生产务必 `APP_ENV=production`，且已配 SMTP
