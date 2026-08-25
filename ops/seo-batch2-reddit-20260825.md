# SEO 第二批 + Reddit 首篇（2026-08-25 晚 · 按 C）

## C1 · SEO 第二批 ✅ 已上线
- commit `90c274d`（+docs `bff6ee1`/`de6124f`）已双推并部署 04，公网 7/7 验收通过，群回执已发。
- `/stocks/` 新增 10 页：AVGO/COST/CRM/ORCL/UBER/ABNB/PYPL/SHOP/SNOW/COIN（累计 20 页）。
- **顺带修复首批 bug**：旧 10 页图片相对路径在 /stocks/ 下 404 → 本批统一绝对 `/seo/assets/{sym}.svg`（公网实测 imgAbs=True）。
- sitemap 重建 36 条（6 主页面 + 20 股票 + 10 对比/教程）；GSC/Bing 旧 ping 端点已废弃（404/410），04 改走 Search Console API 提交。
- 生成器 `seo_gen.py` 升级：支持 stocks 路径 + `--stocks-only`；QA 脚本 `_qa_seo_batch2_20260825.js` 22/22。
- 备份：04 `seo.bak-seo2-20260825-212813`。

## C2 · Reddit 贡献稿 ⚠️ 发布被平台拦截，已上浮审批
- 01 产稿 3 篇（COST/COIN/AVGO，数据 as of 08-24，curl 实测复核）→ 司令抽查零红线 → 04 审核 3/3 全过。
- 04 发布 #1 COST → **r/stocks 拦截**：「AI-generated or AI polished content is not allowed」，按钮禁用；#2/#3 暂缓。
- 合规处理：不绕过检测器、不重试；04 已落盘 `ops/reddit-publish-20260825.md` + 账号台账，账号无警告。
- 已发雷总审批（收发\指令\20260825-2149-01…）：推荐 A（查 r/investing 版规试发）→ 不行转 C（Reddit 只读养号，产能转 SEO + X）；主脑指挥已背书 A→C。

## 01/02 派发（已完成）
- 01：3 篇 Reddit 草稿落 `C:\Users\Administrator\ops\worker\seo-content\reddit-drafts\`。
- 02：`seo-batch-ledger.md` + `seo-batch3-candidates-20260825.md`（JPM/V/LLY/JNJ/PFE/XOM/BA/CAT/NKE/DIS）+ 生成器改进建议 ≤5 条。
- ⚠️ 记录：deploy01/02 **async 通道本次未启动**（out.log 0B、无新 session），改用前台 ssh 直驱 openclaw 成功；后续 01/02 派发优先同步直驱，async runner 待修。

## 待雷总
- Reddit 审批 A/B/C（其余 SEO 批次不受影响，第三批候选已备好）。

## C 定案执行（2026-08-25 晚，雷总「按你建议执行」）
- **r/investing 核查结论（04）＝不允许**：Rule 1 原文「Any post that contains large amounts of Gen AI text is considered low-effort.」；r/stocks 是提交时实时拦截，r/investing 是发布后处罚（移除+可能封号）。账号无警告。
- **按 C 执行**：Reddit 暂停发帖、只读养号；COIN/AVGO 稿不发（草稿归档 `reddit-drafts-20260825/`，留待人工改写或转 X 素材）；任务书 `task-20260825-04-reddit-post-coin-rinvesting.md` 标记 CANCELLED。
- 产能转 SEO + X：01 转产 X 备稿池；02 出 SEO 第四批候选；04 继续 SEO 发布 + X/Reddit 只读养号。
- **SEO 第三批已上线**：commit `eb5b12b`（+docs `b738b48`）已双推，10 页 /stocks/（JPM/V/LLY/JNJ/PFE/XOM/BA/CAT/NKE/DIS）累计 30 页；sitemap 46 条；QA batch3 32/32 + batch2 回归 22/22；红线词扫尾 0（仅免责否定句式）。
- 🟡 晨报素材：Reddit r/stocks + r/investing 均禁止 AI 生成内容 → 官方 Reddit 贡献式运营策略冻结（只读养号），引流重心转向 SEO 量产 + X 养号期后发布。
