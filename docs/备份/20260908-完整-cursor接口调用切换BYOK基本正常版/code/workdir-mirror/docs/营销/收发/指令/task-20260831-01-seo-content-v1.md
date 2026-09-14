# 任务书 · 01（AI24X 内容工厂）· SEO 第一波内容生产

> 派发：2026-08-31 司令 ｜ 目标完成：2026-09-02 18:00 前落盘 ｜ 回执：完成后自动飞书群 ✅/⚠️
> 对齐：`海外SEO与微付费汇总方案-1.3.md`（01 可读取本机 docs\营销\SEO自然流\）

## 背景

国际站系统与支付已就绪（Dodo live / PayPal / Google 登录），内容方案 v1.3 已定稿。你是内容生产主力，VPN 已可用，**只抓公开数据调研、只产素材，不登任何社媒账号**（社媒发布唯一出口是 04）。

## 谷时纪律（必读）

- DeepSeek 官方峰时 = 北京时间 09:00-12:00 / 14:00-18:00（工作日）；**谷时 = 18:00-次日 09:00 + 周末全天**
- 长文生成/竞品抓取一律排谷时；长会话复用，勿每任务新建会话

## 任务清单

### 1. DeepSeek 主指南正文（P0，最高优先）

- 语言：英文；2000-3000 词；输出 Markdown 落盘 `C:\Users\Administrator\ops\worker\seo-content\deepseek-guide-20260901.md`
- 建议 title A/B 两版（如 `DeepSeek API Pricing (2026)` / `Use DeepSeek API Outside China`），正文一套
- 必含锚点：
  1. **三列价格表**：DeepSeek 官方峰谷价 vs AI24X 一口价 vs OpenRouter/DeepInfra 参照（注明「price as of YYYY-MM-DD」；官方价按 8-13 公告口径，写「官方近期上调/峰谷计价」，具体数字以官方页为准）
  2. 中国手机号/支付限制 → PayPal · Card · 无需中国号
  3. 一个 Key 调 DeepSeek + Qwen + GLM + Kimi + 世界名模 + 智能路由
  4. 免费口径：余额空时 100K tokens/日共享通道（**严禁写「注册送 5,000」**，线上无此活动）
  5. 可复制配置：`base_url` + Codex / OpenClaw 配置块（参考 web/guides/openclaw.html 现有文案口径）
  6. 明示：AI Gateway / aggregator，**非官方**
  7. FAQ 5 条（供 FAQPage schema 用）：价格/峰谷、境外支付、兼容性、免费额度、退款
  8. CTA：www 注册拿 Key → console#billing 充值；open 开发者主站

### 2. 三模对比文（P0.5，DeepSeek 主指南后 7 天内）

- `DeepSeek vs Qwen vs GLM (2026)`：选型场景/价格/工具支持/适合谁；客观陈述，禁贬损
- 落盘 `C:\Users\Administrator\ops\worker\seo-content\china-llm-comparison-20260901.md`

### 3. X 备稿 3 条（交 04 发布）

- 2 条蹭 DeepSeek 涨价/境外支付热点（观点句，不硬广、不 @ 官方、不提价格战）
- 1 条 AI Gateway 卖点（One API · Every AI · Pay Less / Spend Smarter）
- 落盘 `C:\Users\Administrator\ops\worker\seo-content\x-pool-20260901.md`

### 4. 竞品 SERP 调研（补差异锚点）

- 抓 AiCredits / deepseekapi.dev / OpenRouter / SiliconFlow 的 DeepSeek 相关页结构（价格/支付/SEO 手法）
- 产出「我们差异化锚点补充清单」落盘 `C:\Users\Administrator\ops\worker\seo-content\deepseek-competitor-notes-20260901.md`

## 合规红线（强制）

- 禁 `official DeepSeek`、假官方站味、收益承诺、目标价、推荐买入类措辞
- 禁写「注册送 5,000」；免费额度口径以线上为准（100K tokens/日共享）
- 价格数字注明核实日期；不确定的数字写「see official pricing」并给官方链接
- 全站英文 UI；教育/信息用途声明（educational purposes only — not investment advice 不适用于 API 产品，但禁止任何金融投资暗示）

## 产出格式

每个 md 文件头部写：目标词 / Title 建议 / Meta 建议 / 上线建议 URL（open 或 www /blog/）。完成后回执 ✅ 已完成项 + ⚠️ 问题项（无则写「无」）。
