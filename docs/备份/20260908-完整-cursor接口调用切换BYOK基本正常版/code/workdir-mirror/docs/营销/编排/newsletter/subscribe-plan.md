# Newsletter 订阅方案 · Subscribe Plan

> 负责：02（方案设计）→ 司令/04（开发落地）
> 版本：v1.0 | 2026-08-23

## 产品定位

**AI24X Daily Market Brief** — 每日 3 Things 美股技术分析简报，纯描述性指标，免费订阅。

## 订阅流程（GDPR/CAN-SPAM 合规）

```
用户访问订阅页
  ↓
输入邮箱地址 + 点击「Subscribe」
  ↓
显示「请查收确认邮件」（Double Opt-in 第一步）
  ↓
用户收到确认邮件 → 点击确认链接
  ↓
订阅生效（Double Opt-in 第二步）
  ↓
每日收到简报邮件
  ↓
每封邮件底部含「Unsubscribe」退订链接
  ↓
点击退订 → 立即生效 + 显示「已退订」页面
```

## 页面文案

### 订阅页标题
```
AI24X Daily Market Brief
3 Things in Technical Analysis — Every Trading Day
```

### 订阅页副标题
```
Free, data-driven market insights delivered to your inbox.
No hype. No recommendations. Just technical analysis.
```

### 订阅表单
```
[Email Address]  [Subscribe →]
```

### 订阅后确认页
```
Check your inbox! 📧

We've sent a confirmation email to [email].
Click the link inside to activate your subscription.

Didn't receive it? Check your spam folder or contact support@ai24x.com.
```

### 确认邮件内容
```
Subject: Confirm your subscription — AI24X Daily Market Brief

Hi there,

You've signed up for the AI24X Daily Market Brief.

To confirm your subscription, click the link below:

[Confirm Subscription →]

This link expires in 24 hours.

—
AI24X Markets
markets.ai24x.com
```

### 退订页
```
You've been unsubscribed.

You will no longer receive the AI24X Daily Market Brief.
If this was a mistake, you can re-subscribe at markets.ai24x.com/newsletter.
```

## 合规清单

| 要求 | 实现 |
|------|------|
| Double Opt-in（双确认） | ✅ 注册 → 确认邮件 → 激活 |
| 退订链接 | ✅ 每封邮件底部 |
| 退订即时生效 | ✅ 点击后立即移除 |
| 发件人信息 | ✅ AI24X Markets <newsletter@ai24x.com> |
| 物理地址 | ✅ 需补充公司注册地址（CAN-SPAM 要求） |
| 隐私政策链接 | ✅ 需在订阅页底部添加 |
| 数据存储声明 | ✅ 隐私政策中说明邮箱存储方式与期限 |
| GDPR 数据删除权 | ✅ 退订时可选「删除我的数据」 |

## 技术需求清单（交司令/04）

1. **订阅页**：`markets.ai24x.com/newsletter` — 邮箱输入 + 提交
2. **后端 API**：`POST /api/newsletter/subscribe` — 存储邮箱 + 触发确认邮件
3. **确认邮件**：发送确认链接（24h 有效期）
4. **退订接口**：`GET /api/newsletter/unsubscribe?token=xxx` — 即时退订
5. **邮件发送**：Mailchimp/Beehiiv/SendGrid（需注册账号）
6. **隐私政策页**：`markets.ai24x.com/privacy` — 数据收集/使用/删除说明

## 发送节奏

- **频率**：每个交易日（美东 Mon-Fri）
- **时间**：美东收盘后 1 小时（北京时间次日 05:00）
- **内容**：3 Things + Quick Hits 表格 + 免责声明
- **模板**：已产 5 期样板（`newsletter/issue-001~005-*.md`）

## 待拍板事项

1. 选择邮件发送平台（Mailchimp / Beehiiv / SendGrid）
2. 注册账号（需雷总/04 执行）
3. 确认公司物理地址（CAN-SPAM 合规）
4. 隐私政策页内容审核
