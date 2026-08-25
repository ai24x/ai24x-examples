# SEO 第三批候选清单（2026-08-25）

> 负责：02（编排）｜10 只候选，避开已上线/部署中的 20+ 只（含 QQQ/SPY/MSTR/MU/TSM）
> 口径：高搜索量、稳定日线数据、跨行业分散；blurb 为英文一句，供页面 meta/H1 复用
> 合规：纯描述性，无买卖建议

| # | Symbol | 公司 | 行业 | 搜索需求理由 | 建议 blurb (EN) |
|---|--------|------|------|--------------|-----------------|
| 1 | JPM | JPMorgan Chase & Co. | 金融 | 美国最大银行，财报季搜索量巨大，散户与从业者均高频查询 | JPMorgan Chase (JPM) stock overview: latest close, RSI(14), MACD and 50/200-day trend signals, updated daily. |
| 2 | V | Visa Inc. | 金融/支付 | 全球支付龙头，长期定投人群常查，搜索稳定 | Visa (V) stock analysis page: descriptive technicals — closing price, momentum (RSI), MACD status and moving-average structure. |
| 3 | LLY | Eli Lilly and Company | 生物科技/医药 | 减重药热度带动 LLY 成为医疗板块第一热搜股 | Eli Lilly (LLY) stock dashboard: daily-updated price, RSI, MACD and trend-structure readouts for research purposes. |
| 4 | JNJ | Johnson & Johnson | 医疗健康 | 防御型蓝筹，长线投资者高频检索 | Johnson & Johnson (JNJ) stock snapshot: key technical indicators including SMA50/SMA200 positioning, refreshed each trading day. |
| 5 | PFE | Pfizer Inc. | 生物科技/医药 | 疫苗后时代持续被关注，波动话题带来搜索 | Pfizer (PFE) stock page: objective daily metrics — close, RSI(14), MACD histogram and long-term moving averages. |
| 6 | XOM | Exxon Mobil Corporation | 能源 | 能源板块旗舰，油价波动直接带动股票搜索 | Exxon Mobil (XOM) stock overview: daily descriptive signals on price momentum, MACD trend and 200-day average context. |
| 7 | BA | The Boeing Company | 工业 | 航空工业龙头，新闻事件驱动型高搜索量标的 | Boeing (BA) stock analysis: current close with RSI, MACD and SMA-based trend structure, for educational reference only. |
| 8 | CAT | Caterpillar Inc. | 工业 | 基建/机械景气度风向标，机构与散户双高频 | Caterpillar (CAT) stock snapshot: daily technical readouts — momentum (RSI 14), MACD status and key moving averages. |
| 9 | NKE | Nike Inc. | 消费 | 全球消费品牌顶流，财报与新品周期带动检索 | Nike (NKE) stock page: descriptive daily indicators — price level, RSI reading, MACD direction and MA trend context. |
| 10 | DIS | The Walt Disney Company | 通信/传媒 | 流媒体+主题公园双话题，长期稳定大搜索量 | Walt Disney (DIS) stock overview: updated-daily close, RSI(14), MACD and 50/200-day structure, educational use only. |

## 覆盖检查
- 行业分布：金融×2、医药×2、能源×1、工业×2、消费×1、通信传媒×1、支付×1 ✅ 无同行业扎堆
- 与已上线 20+ 只零重复 ✅
- 全部为超大盘 S&P 500 成分股，日线数据稳定性风险极低 ✅

---

# 附：下一批生成器改进建议（≤5 条）

1. **H2 差异化：** 目前每页 H2 结构雷同（What/Is/Trend 三段式），建议按指标状态动态生成 H2 文案（如 "RSI Near Overbought" / "Price Below 200-Day Average"），提高页间差异性、降低模板化判定。
2. **FAQ 扩充至 4–5 条：** 在现有 FAQ 基础上增加 "What sector is {SYM} in?"、"Does {SYM} pay a dividend?"、"How volatile is {SYM}?" 类通用问题（静态事实可离线维护一个 sector/dividend 元数据表），扩大长尾命中。
3. **新增指标表格区块：** 加一张 3–5 行的指标速览表（Close / 52W range / SMA20 / SMA50 / SMA200 / RSI），既提升信息密度又利于精选摘要（featured snippet）抓取。
4. **相关搜索词区块：** 页尾加 "Related searches" 内链模块（如 {SYM} vs peers、{SYM} earnings date），互链同批次 3–4 个页面，改善爬虫发现路径与站内权重传递。
5. **数据日期醒目化：** asof 日期从正文小字提为价格旁的显式标注（"as of YYYY-MM-DD close"），减少用户对数据时效的困惑，也降低因延迟数据产生的投诉/跳出。
