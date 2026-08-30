# 需求类型：④国际生产/发布（副脑04）
# 标题：推广前全量检查——AI24X 接口 + BYOK 调用（雷总 08-30 指令 · 推广前必检）
# 期望：今日 12:00 前回执（推广前必须完成）

## 背景
雷总 08-30 09:53 指令：马上要推广，派 04 检查 AI24X 接口与 BYOK 调用是否全部正常。主脑全程监督，检查结果必须闭环（发现问题→修复→验收→汇报雷总），不许查完就放那里。

## 检查项（逐项给证据：HTTP 状态/响应时间/结论 ✅⚠️❌）

### 1. AI24X 核心接口（api.ai24x.com）
- [ ] /health（含 commit 版本号）
- [ ] /v1/models（模型列表可拉取）
- [ ] /v1/chat/completions 非流式（真实 key 调 DeepSeek 模型，验证响应）
- [ ] /v1/chat/completions 流式（SSE [DONE] 正常）
- [ ] 账单/用量接口（今日订单、credits 查询）
- [ ] 支付链路（Dodo/PayPal 下单接口 + 回调日志近 24h 无异常；待履约订单积压处置）
- [ ] markets 接口（markets.ai24x.com 页面 + 数据接口 + Pro 订阅校验）

### 2. BYOK 调用（open.ai24x.com）
- [ ] open.ai24x.com /v1 调用（BYOK 用户 key 验证 + chat completions 正常）
- [ ] BYOK key 创建/校验/用量接口
- [ ] 智能路由（上游通道健康：OpenRouter/DeepSeek/SiliconFlow/MiMo 等；近 1h 失败率）
- [ ] 余额/用量 daily 接口（含 Redis 缓存）
- [ ] www 引导「Buy on AI Gateway」跳转链路

### 3. 异常处置
- 发现 ❌ → 立即定位修复（或标注阻塞+原因），修复后复测
- P0（生产不可用/支付异常）→ 立即飞书私信雷总，不等回执

## 输出
- 检查报告落盘：C:\ai24x01\ops\pre-launch-api-check-20260830.md（每项：命令/URL + 结果 + 结论）
- 回执：✅ 全绿 或 ⚠️ 异常清单（已修复/待修复）+ 报告路径

## 纪律
- 用生产 key 测试时用测试账号 key，不暴露真实凭据；不在回执/报告写密钥
- 公网验证用新加坡出口
