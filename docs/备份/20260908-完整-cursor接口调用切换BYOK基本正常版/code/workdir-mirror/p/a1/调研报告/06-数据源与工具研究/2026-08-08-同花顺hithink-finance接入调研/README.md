# 同花顺 hithink-finance（金融数据API）接入调研

> 调研日期：2026-08-08 ｜ 数据来源：官方文档站 fuyao.aicubes.cn（/llms-full.txt 全文）、GitHub HiThink-Tech/Financial-API（README/SKILL/Issues）、QuantAPI 官方权限说明页

## 一、结论速览

| 问题 | 结论 |
|---|---|
| 是否官方提供接口 | 是。2026-06 上线，同花顺官方维护，官网 fuyao.aicubes.cn，GitHub 官方仓库（MIT License，340+ star） |
| 免费还是付费 | 当前**免费开放**（官方 Issue 回复"无限制次数"），但**无公开价格表**，处于"先养猪后收费"培养期，未来可能转付费 |
| 要钱吗、多少钱 | 暂无定价。参考同花顺其它接口线：QuantAPI 免费版有月度额度；iFinD/QuantAPI 付费约个人 6.8k 元/年起、机构 2~5 万/年（含 500 万条/月） |
| 板块资金流向 | **不提供**。30 个 MCP 工具/34 个 REST 端点里没有主力净流入/板块资金流/北向接口 |
| 如何接入 | 登录同花顺账号 → fuyao.aicubes.cn/admin 创建 API Key（只显示一次）→ REST/MCP/CLI/Python 四选一 |

## 二、能力清单（官方一手文档）

- **A股行情**：单只/多只/全市场快照、历史日/周/月K（前复权/后复权）、全市场 Parquet 导出（10年日K）
- **基本面**：利润表/资产负债表/现金流量表、五类财务指标（成长/盈利/偿债/营运/现金流）、估值快照（PE_TTM/PB/PS/PCF）、复权因子事件流
- **指数与板块**：同花顺指数列表（概念/行业 886xxx/881xxx .TI）、成分股、行情快照、历史K线
- **特色数据**：涨停池、连板天梯、个股异动原因、同花顺热榜（飙升榜/热股/历史排行）、龙虎榜（全部/机构/游资）
- **基金**：资料、重仓股、净值、区间收益、持有人结构、场内 ETF/LOF 快照与日线
- **明确不含**：分钟K、tick、海外行情、宏观数据、新闻公告原文、研报原文、**板块/个股资金流向（主力净流入）**、北向南向

## 三、免费 or 付费（证据链）

1. 官方文档站/README 无任何"收费/套餐/额度"页面（sitemap 67 页已全查）；
2. GitHub Issue #10「请问API是否有调用次数限制」→ 官方账号 curtisyang1228-oss 回复 **"无限制次数"**；社区评论"先养猪 后收费"；
3. 代码层已预留商业化伏笔：错误码 4001=频率超限（有 QPS 软限流）、2003=capability 权限分级（"请联系管理员开通对应权限"）；
4. 获取 Key 免费：同花顺账号登录即可，无付费门槛。

**风险提示**：免费期随时可能结束；"无限制次数"是社区口径非书面 SLA；不要把它当生产唯一数据源，只做增强/交叉验证通道。

## 四、同花顺其它接口收费参考（对照）

| 产品 | 免费额度 | 付费参考 |
|---|---|---|
| QuantAPI 免费版（官方页） | 实时行情 300万/月、高频 150万/月、日内快照 200万/月、历史行情 100万/月、基本面 60万/月、智能选股 4000/月（1条=1个Excel单元格，每月1号清零） | 免费版仅需 iFinD 账号，无需申请 |
| iFinD / QuantAPI 付费（行业公开信息） | — | 个人年费约 6,800 元起；机构 2~5 万元/年（含 500 万条/月）；采购公示参考 iFinD 终端 1.45万/套/年、同花顺全数据接口 3.1万/套/年 |

## 五、接入方式（6 种，统一 Key）

```bash
# 1) REST（最通用，服务端集成首选）
curl 'https://fuyao.aicubes.cn/api/a-share/prices/snapshot?thscodes=600519.SH' -H 'X-api-key: <KEY>'
# 响应信封：code=0 成功；2001 Key无效；2003 无权限；4001 频率超限；数据在 data.item

# 2) 托管 MCP（4 个端点，HTTP MCP，headers 带 X-api-key）
#    https://fuyao.aicubes.cn/mcp/a-share          （A股17工具）
#    https://fuyao.aicubes.cn/mcp/a-share-index    （指数/板块4工具）
#    https://fuyao.aicubes.cn/mcp/meta             （标的检索2工具）
#    https://fuyao.aicubes.cn/mcp/fund             （基金7工具）

# 3) CLI
npm i -g @hithink-tech/hithink-finance-cli
hithink-finance auth login
hithink-finance capabilities --format json

# 4) Python SDK / toolkit    5) marketdb（本地 DuckDB）  6) Agent Skill
npx skills add HiThink-Tech/Financial-API --skill hithink-finance
```

**拿 Key 三步**：① fuyao.aicubes.cn 用同花顺账号登录 → ② admin 页「创建 API Key」填别名 → ③ 提交后**立即复制保存（只显示一次）**。

## 六、对 AI行情官 的落地建议

- 值得接：免费期内接入成本约等于 0。高价值点=同花顺特色数据——涨停池/连板天梯/个股异动原因/热榜/龙虎榜（含游资净买入），可交叉验证「掘金」板块热点、「复盘」主线、以及标的**利空/异动排查**（此前依赖东财板块页，抓取受限）。
- 接不了资金流向：板块/大盘主力净流入仍只能走东财 push2delay（现方案），hithink 无此能力——"板块资金流向付费源"这里没有，别抱期望。
- 口径不可混：同花顺板块指数（886xxx/881xxx .TI）与东财板块（BKxxxx）是**不同编制，K线不等**（AGENTS.md 十八节已记录）——只用于"热点/异动/情绪"校验，不用于板块K线替换。
- 接入姿势：18011 后端新增 ths_fuyao provider（REST 通道）→ 复用 _RateGate 限流 + 按日缓存（当日命中不重抓）→ 先本地小流量实测稳定性/延迟/限流 → 收费后再评估成本。生产不做唯一数据源，与东财/腾讯并行。

## 七、行动项

- [ ] 老板本人登录 fuyao.aicubes.cn 创建 API Key（Key 只显示一次，别发群里）
- [ ] 后端加 ths_fuyao provider + 特色数据缓存，先接 涨停池/异动原因/龙虎榜 三个端点做「掘金/复盘」交叉验证
- [ ] 观察免费期稳定性，记录 4001 限流频率
