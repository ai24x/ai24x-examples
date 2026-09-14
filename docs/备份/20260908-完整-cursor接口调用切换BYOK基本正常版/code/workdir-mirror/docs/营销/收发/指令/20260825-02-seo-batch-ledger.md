# 【02 任务】SEO 批次台账 + 第三批候选清单

> 通道：司令 → 02（async）｜ 02 是运营编排与数据中枢，不发布、不注册账号。

## 背景
- markets /stocks/ SEO 已量产两批（第一批 10 只 + 第二批 10 只 AVGO/COST/CRM/ORCL/UBER/ABNB/PYPL/SHOP/SNOW/COIN），第二批复盘部署中（commit 90c274d，sitemap 36 条）。
- 01 是素材生产工厂，02 负责编排与台账，04 负责发布。

## 任务
1. 在 `C:\Users\Administrator\ops\orchestrator-output\` 新建/更新 `seo-batch-ledger.md`：
   - 两批共 20 只股票清单（第一批 10 + 第二批 10）、上线日期、URL 格式（https://markets.ai24x.com/stocks/{sym}）、sitemap 状态（36 条）、GSC/Bing ping 状态（待 04 回执后补记）。
2. 产出第三批候选清单 `seo-batch3-candidates-20260825.md`：10 只美股标的（避开已上线的 20 只），每只给：symbol/公司名/一句话搜索需求理由/建议 blurb（英文一句）。要求高搜索量、有稳定日线数据、覆盖不同行业（如金融、生物科技、工业、消费、能源、通信、汽车等）。
3. 输出一份「下一批生成器改进建议」（≤5 条）：如每页 H2 差异化、FAQ 扩充、表格列、相关搜索词区块等，供司令评估。

## 完成后
- 回执落到 `C:\Users\Administrator\ops\orchestrator-output\` 同目录（✅ 已完成 3 项 / ⚠️ 问题项），并同步通知司令（本机收发目录）。
- 不要提交代码、不要改 sitemap、不要发布。
