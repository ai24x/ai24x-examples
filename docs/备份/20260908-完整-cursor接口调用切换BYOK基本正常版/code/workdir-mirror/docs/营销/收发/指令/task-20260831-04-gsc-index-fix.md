# 需求类型：④国际生产/SEO（副脑04）
# 标题：GSC 未编入索引 51 个网页诊断与修复（雷总 08-31 指令）
# 期望：明日完成诊断+可修项修复，回执

## 背景
雷总 08-31 00:30：Google Search Console 显示「网页未被编入索引」**51 个**，需检查修复。

## 任务
1. **拉取诊断**：用 GSC API（google-search-console skill / 已配置的 GSC 权限）查询 51 个未编入索引 URL，按 Google 原因分类（Not found 404 / Redirect error / Noindex / Soft 404 / Discovered - currently not indexed / Crawled - currently not indexed / Page with redirect / Blocked by robots 等），输出分类统计表 + 每类 URL 清单
2. **按原因分流修复**（能 04 直接修的修）：
   - 404/Redirect/路由类 → 定位并修复（或列清单交平台官改代码）
   - noindex/robots 拦截类 → 修正 meta/robots 配置
   - Crawled/Discovered-not-indexed 类 → 检查内容质量/重复/内链，给出优化建议（内容优化交 01 或列清单）
3. **请求编入索引**：修复后对关键 URL 用 GSC URL Inspection + Indexing API 请求重新编入
4. 诊断报告落盘：C:\ai24x01\ops\gsc-index-20260831.md

## 纪律
- GSC 数据只用于本站域名（www/open/markets 对应站点）；不暴露账号凭据
- 不批量提交灌水 URL（Google 规则），只处理真实修复项

## 回执
✅ 分类统计 + 已修复项 + 待代码修复清单（交平台官）+ 报告路径；⚠️ 问题项
