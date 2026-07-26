# 邮箱验证码联调（SMTP）

## 目标
注册「获取验证码」走真实发信；生产不在接口里回传验证码。

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
