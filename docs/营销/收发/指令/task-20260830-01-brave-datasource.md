# 需求类型：①获客/内容（副脑01）
# 标题：web_search Brave API key + 财经数据源被墙处理（雷总 08-30 确认）
# 期望：今日/明日完成，回执

## 背景
18:30 验收：01 提示 web_search 缺 Brave API key；财经站抓取被墙、数据标 illustrative。雷总 08-30 20:36 确认处理。

## 任务
1. **Brave API key**：申请免费版 Brave Search API key（https://brave.com/search/api/ 免费档即可，不花钱），配置到 01 的 OpenClaw（web_search provider），验证搜索可用
2. **财经数据被墙**：被墙的源（具体哪些域名列出）→ 换成可访问的授权源（如 yfinance/Stooq/alpha vantage 免费档等）；标注 illustrative 的数据**发布前必须回传主脑核验真实性**，未经核验不得上线
3. 更新内容生产管线文档：数据源清单（可用/被墙）+ 数据真实性核验流程

## 纪律
- 免费 key 申请用自己的邮箱；不暴露 key 到公共平台/回执
- 发布类内容数据必须真实，illustrative 仅限内部演示，上生产前核验

## 回执
✅ 完成项 + Brave key 配置状态 + 数据源清单；⚠️ 问题项
