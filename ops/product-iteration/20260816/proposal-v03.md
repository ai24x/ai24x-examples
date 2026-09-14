# markets 国际版 v0.3 产品提案（2026-08-16 周复盘手动补跑）

> 状态：提案待雷总拍板 · 只出提案未改码 · 基线 commit 133119c + c385e19（均已上线）

## 一句话定调
v0.2 主链路已跑通，v0.3 先修支付链路两个硬伤（PayPal 回跳无确认、取消回跳 404），再做合规死代码清理与激活引导，最后补埋点/SEO/增长。

## 走查发现（新用户+海外散户视角）
- 首页 → 登录：Sign in 跳 www 老站 login.html（跨子域 cookie 登录态）；无 Google/Apple 一键登录 → 海外转化流失点
- app 默认 AAPL 出图 ✓；搜索 + symbol not found 明确报错 ✓
- AI Brief：未登录引导登录 ✓；额度用尽有升级提示，但无「明日重置」召回
- Watchlist：未登录点星引导登录 ✓；免费3/Pro50 配额提示 ✓
- 订阅→PayPal：checkout 建单跳 PayPal ✓；但 **return_url 默认不含 order_id → 回跳后无即时确认（等 webhook）**；**cancel_url 指向不存在的 pricing.html → 取消支付 404**；支付成功后无下一步引导
- ToS/Privacy 页脚可达 ✓；死代码：app.html 内 i18n zh 字典 + lang-switch CSS/JS 残留（运行时不显示）

## P0（建议默认开工）
- [P0] PayPal 回跳修复：return_url 带 order_id（app.html?pay=done&token=<id>，doCapture 逻辑已就绪只差参数）| 支付确认链路断点 | 需审批-支付
- [P0] cancel_url 修正：取消支付回跳改 /app.html#sub（现指向不存在的 pricing.html 404）| 支付断点 | 需审批-支付
- [P0] 死代码清理：删除 app.html zh 字典 + lang-switch 残留 CSS/JS | 合规收紧、减维护面 | 无
- [P0] 支付成功引导（#8）：回跳/捕获成功后弹「Pro 已激活」+ 下一步（生成 AI Brief / 加自选）| 提升激活转化 | 无（纯前端）
- [P0] 轻量埋点（#9）：页面浏览/搜索/AI 点击/额度用尽/订阅点击/支付回跳事件 | 增长决策依据 | 需审批-新功能上线（接第三方统计如 GA4/Plausible 需定选型）

## P1（建议默认开工或拍板后开工）
- [P1] 免费额度用尽召回（#10）：用尽提示加「明日 3 次重置」+ 升级 CTA 强化 | 召回留存 | 无
- [P1] Google/Apple 一键登录（www 核心层扩展，markets 侧仅按钮）| 海外转化 | 需审批-新功能上线
- [P1] SEO 技术分析落地页（#11）：「{symbol} technical analysis」静态页 + sitemap 扩充 | 自然流 | 需审批-对外承诺（内容合规不承诺收益）

## P2（拍板后开工）
- [P2] 社媒分享/邀请（#12）：K 线图分享卡 + 邀请码 | 增长 | 需审批-新功能上线
- [P2] 独立 pricing.html（当前价目仅 index/app 内嵌）| 完整落地页 | 无

## 建议下周开工项
P0 全部（支付两处 + 死代码 + 激活引导）可一次提交；埋点、一键登录、SEO 落地页等雷总拍板后再进 P1。
