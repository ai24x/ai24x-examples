# 【04 任务】Reddit 贡献稿审核 + 首篇发布（u/AI24X）

> 通道：司令 → 04（同步）｜ 稿子来自 01（已司令抽查零红线）｜ 风控铁律优先于一切进度
> 草稿位置：`C:\Users\Administrator\ops\reddit-drafts-20260825\`

## 背景
- u/AI24X 已养号 30 天，可开始「贡献式运营」：先输出有价值的技术分析，不硬广。
- 01 产出 3 篇草稿（COST / COIN / AVGO，数据 as of 2026-08-24，已与 markets 页面实测复核）。

## 第一步：审核（逐篇）
1. 事实核对：打开 `https://markets.ai24x.com/stocks/{cost|coin|avgo}`，确认草稿中的收盘价/均线/RSI/区间位置/量能描述与页面一致（页面标注 as of 2026-08-24）。
2. 措辞红线扫描（全部 3 篇）：
   `Select-String -Path 'C:\Users\Administrator\ops\reddit-drafts-20260825\reddit-draft-*.md' -Pattern '\b(buy|sell|hold|accumulate|recommend|signal|target price|guarantee|tips|picks|trading advice)\b'` → 期望 0 命中。
3. 无品牌/无链接检查：正文不得出现 AI24X、markets.ai24x.com、任何 URL。
4. 确认每篇结尾有免责声明行。
任一不通过 → 不发布，回传司令。

## 第二步：检查 Reddit 账号状态（u/AI24X）
- 用 04 既有浏览器/登录态确认 u/AI24X 处于已登录、无警告状态。
- 若需登录/验证码/出现风控提示 → **立即停止，私信雷总**（平台+需要什么+在哪操作+预期耗时），不重试、不换环境。

## 第三步：发布（仅当第一、二步全过）
- 发布顺序：#1 COST → r/stocks；#2 COIN → r/investing；#3 AVGO → r/stocks。
- **今天先发布 #1 COST**；#2 安排 ≥24h 后（建议 36-48h 后同时间段），#3 再 ≥24h 后。若你能挂 cron/提醒则挂上，不能则在回执里写明建议日期，司令后续重派。
- 发帖格式：标题取草稿第一行（去掉 `# `）；正文取剩余部分（保留加粗标记，Reddit 支持），结尾免责声明行保留；不要用表格；不要贴链接。
- 发布后 24h 内留意回复：正常讨论礼貌回复；任何警告/限流提示 → 立即停止后续发布并私信雷总。

## 完成后回执（落盘 + 司令收发，不群发）
- 落盘：`C:\Users\Administrator\ops\accounts-registry.md` 追加一条（发布日期/URL/状态）+ `ops\reddit-publish-20260825.md` 记录审核与发布证据。
- 通知司令：本机收发目录留回执文件（✅ 审核 3/3 / ✅ 发布 #1 URL / ⚠️ 问题项）。
- **不发指挥部群**（正常完成属 🟢/🟡 级，并入晨报即可）；只有风控/异常才私信雷总。
