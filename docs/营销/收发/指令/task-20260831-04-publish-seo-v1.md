# 任务书 · 04（AI24X 发布出口）· SEO 发布与技术执行

> 派发：2026-08-31 司令 ｜ 目标完成：2026-09-03 18:00 前 ｜ 回执：完成后自动飞书群 ✅/⚠️

## 背景

服务器已升级 4核16G；你是社媒发布与 SEO 技术执行的**唯一出口**。01 正在产 DeepSeek 主指南（09-02 18:00 前落盘），你与其并行做发布基建。

## 谷时纪律（必读）

- 谷时 = 北京时间 18:00-次日 09:00 + 周末全天；批量抓取/渲染/长任务排谷时
- 升级后 4核16G 可跑 Playwright 批量渲染验证与 sitemap 生成，放心用

## 任务清单

### 1. GSC + Bing Webmaster 提交（P0）

- 提交/核验 www.ai24x.com 与 open.ai24x.com sitemap
- www sitemap 当前 18 条，缺 `blog/kimi-api-paypal-guide.html` → 司令已排期补，你核验收录状态
- 产出 SERP 基线表（TOP20 词当前排名/收录状态）落盘 `C:\Users\Administrator\ops\orchestrator-output\serp-baseline-20260901.csv`

### 2. GitHub ai24x-examples 仓库（P0）

- 仓库名 `ai24x-examples`，README + 4 示例：curl / openai-sdk / codex / openclaw
- 示例 key 一律占位符 `sk-...`；头部加 MIT 许可与免责；发布前内容交司令抽查
- **发布动作需老板登录 04 VPS 浏览器确认**（GitHub 风控）→ 04 飞书私信雷总一次，等回复再发布；3 次未完成停 3 天

### 3. dev.to 精编转载（P0）

- 等 01 的 DeepSeek 主指南产出后，精编 800-1200 词英文版发 dev.to（AI24X 官方号），文末回链 open.ai24x.com/pricing.html
- 若 09-03 前 01 未产出，先做任务 1/2/4，转载顺延

### 4. X @ai24xapp 排期（养号期）

- 每日 ≤1 条，只发 01 备稿的观点句/转发（不硬广、不 @ 官方、不提价格战）
- 遵守一账号一 IP 一设备（新加坡出口）；验证码/人机 → 飞书私信雷总，不重试不换环境

### 5. SEO 批量能力 + 周报数据源

- 验证 Playwright 批量渲染（`p/markets/scripts/_qa_*.js` 模式）+ sitemap 生成脚本可用
- 每周向 02 提供：收录数、SEO 页面上线数、社媒发布数、注册/首充数

## 合规红线（强制）

- 禁 `official DeepSeek`、假官方站味、收益承诺；GitHub 示例 key 占位符
- dev.to/X 文案不硬广、不贬损竞品；价格数字注明核实日期

## 回执格式

✅ 已完成项（含 URL/证据） + ⚠️ 问题项（无则写「无」）。
