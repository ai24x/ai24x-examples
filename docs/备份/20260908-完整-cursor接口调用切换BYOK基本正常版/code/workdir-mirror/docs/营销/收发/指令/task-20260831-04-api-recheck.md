# 需求类型：④国际生产/复测（副脑04）
# 标题：AI24X 接口 + Bench 上游复测（雷总 08-31 拍板：确认 524/503 是否持续）
# 期望：8/31 谷段执行（晨 7:00-8:30 或 18:30 后），回执

## 背景
8/30 23:51 Bench FULL 报告出现上游异常（flash/pro/ultra/shared、vip-kimi、vip-qwen-max、vip-glm 报 524；vip-claude-sonnet、vip-llama4 报 503），疑似深夜上游高峰负载抖动。雷总拍板：安排 04 复测确认是否持续。

## 任务
1. 谷段重跑完整 Bench（scripts_bench_weekly.py），对比 8/30 23:51 报告：524/503 是否消失
2. 复测核心接口（A 块）：api /health、/v1/models、chat completions 非流式+流式
3. 若异常持续 → 排查上游路由/熔断配置（哪些上游、错误分布），定位根因后修复或上报
4. 复测报告落盘：C:\ai24x01\ops\bench-recheck-20260831.md

## 纪律
- 谷段执行（避开 DeepSeek 高峰 9-12/14-18）；用测试 key；不暴露凭据

## 回执
✅ 复测结论（异常消失/持续+根因）+ 报告路径；⚠️ 问题项
