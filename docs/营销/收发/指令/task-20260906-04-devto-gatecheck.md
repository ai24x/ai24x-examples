# 【04 任务】dev.to 发布 DeepSeek 指南 + 投流门禁自查

> 通道：司令 → 04（同步）｜ 背景：X @ai24xapp 已公开，第一条已发 ✅

## 任务 A：dev.to 发布 DeepSeek 指南

### 账号
- 用 social@ai24x.com 注册/登录 dev.to（如无账号则注册）
- 04 新加坡 IP，一账号一 IP

### 发布参数
- **标题**：DeepSeek API Pricing in 2026: Peak/Off-Peak, Payment, and Getting Started
- **标签**：deepseek, pi, pricing, llm, i
- **正文**（复制以下内容直接发布）：

---
# DeepSeek API Pricing in 2026: Peak/Off-Peak, Payment, and Getting Started

*Published: 2026-09-06 · Educational content only. Not affiliated with DeepSeek.*

DeepSeek's models (V4 Flash, V4 Pro) are among the best value LLMs you can call in 2026. But two things trip up international developers: the **peak/off-peak billing model**, and the **China-only signup** requirement. Here's a practical breakdown.

## How DeepSeek Prices Work

DeepSeek uses two rate tiers based on when you call:

| Tier | Input (cache miss) | Output |
|------|-------------------|--------|
| Flash off-peak | $0.22/M | $0.66/M |
| Flash peak | $0.44/M | $1.32/M |
| Pro off-peak | $0.66/M | $1.98/M |
| Pro peak | $1.32/M | $3.96/M |

*Peak hours: 01:00–04:00 & 06:00–10:00 UTC, Mon–Fri. Weekends are all off-peak. Cache hits cost ~90% less.*

The practical impact? A developer sending 100M input + 20M output to Flash pays **$70.40/mo at peak** vs **$35.20/mo in off-peak hours**. Same model, same usage, double the bill just because of timing.

## The International Developer Problem

DeepSeek's official platform requires a Chinese phone number and CNY payment — that's a dead end for most international developers. Third-party gateways (like AI24X, OpenRouter, DeepInfra) solve this by offering DeepSeek access through standard OpenAI-compatible endpoints and accepting PayPal or international cards.

## One-Key Setup

Instead of juggling five vendor accounts, an AI gateway gives you one endpoint:

```bash
curl -X POST "https://api.ai24x.com/v1/chat/completions" \
  -H "Authorization: Bearer sk-..." \
  -d '{"model":"flash", "messages":[{"role":"user","content":"Hello"}]}'
```

That same key works for DeepSeek, Qwen, GLM, Kimi, GPT-5, and Claude — the router picks the best channel per request.

## Practical Defaults

| Workload | Recommended Model | Why |
|----------|------------------|-----|
| Chat, summarization, coding | flash | Best reasoning per dollar |
| Complex reasoning, math | pro | Stronger, ~3× cost of flash |
| Long documents, 1M context | VIP (Kimi/Qwen) | Context length is key |
| Hardest tasks | GPT-5 / Claude | Escalate when needed |

## Getting Started

1. Register at your gateway of choice
2. Create an API key (PayPal or card — no Chinese phone needed)
3. Point your existing OpenAI SDK to the new base URL — done

*All prices captured 2026-08-31 from official sources. Pricing changes often — always verify before committing budget.*

---

### 发布后
落盘 C:\Users\Administrator\ops\devto-deepseek-20260906.md：帖子链接 / 发布时间 / 自查 0

## 任务 B：投流门禁自查

在 04 本机逐项核实，结果落盘 C:\Users\Administrator\ops\gate-check-20260906.md

| # | 检查项 | 方法 | 判定 |
|---|--------|------|------|
| 1 | PayPal Live 可用 | Dodo 后台 → 支付方式 → PayPal enabled? 04 本机 curl 测试 POST /v1/billing/paypal/create-order 200? | PASS / FAIL + 说明 |
| 2 | Dodo live 商品 11 个 | 后台 GET /products page_size=100 → markets 3 + BYOK 2 + token 6，价格一致 | PASS / FAIL + 说明 |
| 3 | Webhook 正常 | Dodo 后台 → webhooks → 两个端点 active（www + open），secret 可查 | PASS / FAIL + 说明 |
| 4 | 四端点 health | curl www/open/markets/a.ai24x.com/health → 200 + commit 一致 | PASS / FAIL + 说明 |
| 5 | robots.txt | curl www.ai24x.com/robots.txt → Disallow /v1/ /api/ /r/ | PASS / FAIL + 说明 |
| 6 | 注册可用 | curl www.ai24x.com/register.html → 200 | PASS / FAIL + 说明 |
| 7 | Google OAuth | curl -s -o NUL -w \"%{redirect_url}\" \"https://www.ai24x.com/v1/auth/google/login?next=console.html\" → accounts.google.com | PASS / FAIL + 说明 |

## 回执
✅ 完成后飞书群回执（✅ 完成项 / ⚠️ 问题项，无则写「无」）
