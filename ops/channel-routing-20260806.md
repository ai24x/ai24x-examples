# 通道路由决策：旗舰点名按评测+实价切主通道 · 2026-08-06

> 依据：副脑04 两轮质量评测（value 档 1457 / flagship 档 1715）+ 本地实拉 TokenLab/OpenRouter 实时价目。
> 决策原则：不亏钱 + 有利润；质量不倒退；供应链信息不进公开接口。

## 一、数据来源
- 评测：https://www.ai24x.com/quality-eval.html 、https://www.ai24x.com/quality-eval-flagship.html
- 原始 JSON：ops/quality-eval-20260806-1457.json 、ops/quality-eval-20260806-1715.json
- 价目：TokenLab /v1/models 详情接口（tokenlab.pricing）、OpenRouter /v1/models（pricing）
- 说明：评测 JSON 里 cost_usd 是按脚本预设价估算（非实拉账单）；本次路由以「质量分」+「实拉价目」双依据。

## 二、逐模型决策表（聚合通道顺序）
| 点名模 | 主通道 | 备选 | 依据（评测 + 实价） | 混合毛利 |
|---|---|---|---|---|
| GPT-5.4 | TokenLab | OR → Requesty | TL 24/24 vs OR 23/24；TL $0.75/$4.5 ≈ OR($2.5/$15) 70% off | 75% |
| GPT-5.6 Terra | TokenLab | OR → Requesty | TL 24/24 vs OR 22/24；TL $0.6/$3.6 < OR($1/$6) | 60% |
| Gemini 3.6 Flash | TokenLab | OR → Requesty | TL 22/24 vs OR 23/24（差1题）；TL $0.75/$3.75 为 OR($1.5/$7.5) 50%，延迟 2.6s < OR 3.5s | 68% |
| Grok 4.20（新增） | TokenLab | OR | TL 22/24·6.3s vs OR 21/24·1.8s；TL $0.625/$1.25 为 OR($1.25/$2.5) 50% | 89% |
| Claude Sonnet 5 | OpenRouter | TL → Requesty | 质量持平 92%；OR 延迟 4.4s vs TL 7.8s | 34% |
| Claude Opus 5 | OpenRouter | TL → Requesty | OR 92% vs TL 77%（TL 有 400 上下文错误）；OR 延迟 9.7s | 34% |
| GPT-5 mini | OpenRouter | TL → Requesty | OR 96% vs TL 92% | 36% |
| GPT-5.6 Luna / GPT-5 / GPT-4o 系 / Haiku / Gemini Pro | OpenRouter | TL → Requesty | 本轮未测或未分胜负，维持 OR 主 | 33-57% |
| Kimi K3 | 硅基→OR（屏蔽 TL） | — | TL 的 kimi-k3 全挂（400/503，0/24） | — |
| DeepSeek Flash/Pro、GLM/Qwen/MiniMax/MiMo 等 | 维持现状（硅基/OR/TL） | — | 价值档已定，本轮不动 | — |

## 三、毛利测算（按主通道实价，售价=flash 锚 0.35×mult）
- GPT-5.4：成本 blended $2.625/M，售价 $10.5/M → 75%
- Terra：成本 $2.1/M，售价 $5.25/M → 60%
- Gemini Flash：成本 $2.25/M，售价 $7.0/M → 68%
- Grok：成本 $0.94/M，售价 $8.4/M → 89%（临时定价，待雷总确认）
- OR 备选兜底时全部 ≥16%（仅 GPT-5.4 走 OR 兜底时 16.7%，可接受）

## 四、代码变更清单
- api/model_warehouse.py
  - vip-gpt54 / vip-gpt56-terra / vip-gemini-flash：channels 字段（TL 首选）+ cost 更新为 TL 实价
  - vip-kimi：channels=["openrouter"]（屏蔽 TL）
  - 新增 vip-grok（Grok 4.20，OR id=x-ai/grok-4.20，channels=[tokenlab,openrouter]，临时定价 mult 24 / in 10 / out 36）
  - merge_catalog_row 支持 channels override（后台可改）
  - 新增 vip_channel_order()；resolve_vip_pick 增加 grok 别名；列表接口 grok 归 intl 组
- api/model_router.py
  - _TOKENLAB_MODEL_MAP 增加 vip-grok
  - 新增 _vip_aggregator_chain()：默认 OR→TL→Requesty，channels 为严格白名单顺序
  - _run_vip_pick_chat / _run_vip_pick_chat_stream 改用聚合链；grok 纳入国际旗舰识别（禁硅基顶替）
- 备份：api/model_warehouse.py.bak.20260806 / api/model_router.py.bak.20260806

## 五、本地验证
- 语法 + 全模块导入 OK；vip_named_guard ALL PASS；map_model_smoke RESULT OK
- 离线断言：5 个 TL 首选 + Kimi 屏蔽 + Grok 无 Requesty 全部 PASS
- 真实调用：gpt54→tokenlab ✓（非流式+流式）；gemini-flash→tokenlab ✓；gpt5-mini OR 403（本地中国区地区限制）→ 自动落 TL ✓（fallback 正常）
- 注：本地 OpenRouter 403「model not available in your region」是中国区限制，生产新加坡节点不受影响（副脑04 评测时 OR 正常）

## 六、待办 / 补测清单
1. 待雷总确认：Grok 4.20 定价（mult 24/in 10/out 36 临时）
2. 补测（副脑04）：GPT-5.6 Luna、Gemini 3.1 Pro、Claude Haiku、GPT-5 / GPT-4o 系在 TL 的质量与延迟 → 达标后评估是否切 TL（成本更低）
3. Llama 4 Maverick（OR $0.2/$0.8，评测 88%）是否上架为「开源旗舰」——待雷总决定
4. Requesty 无 grok-4.20（404 整批），已在白名单外自动跳过
5. 后续可让副脑04 从 TL/OR 控制台导出真实账单，核对毛利（当前毛利按实拉价目估算）
6. 生产验收：拉起后抽查 /v1/models（vip_picks 应含 Grok 且不泄露 channels 字段）

## 七、定价/上架补丁（2026-08-06 晚 · 主脑授权按最优策略定案，待补测后统一推送）
- Grok 4.20 定价定案：billing_mult 24→20、in_mult 10→8、out_mult 36→30（前沿旗舰档：Terra 15 < Grok 20 < GPT-5.4 30；TL 实价 in $0.625/out $1.25 → 毛利约 87%）
- 新增 vip-llama4（Llama 4 Maverick）：OR 实价 in $0.2/out $0.8，评测 21/24·2.7s；定价 mult 3/in 2/out 3（开源旗舰引流款，毛利约 52%）；channels=["openrouter"]（仅 OR 有货）
- 别名：llama / llama-4 / llama-4-maverick / llama4 → vip-llama4；grok/llama 均归 intl 组与国际旗舰降级识别（禁硅基顶替）
- 待办：补测结果回来后做最终路由定案（Luna/Gemini Pro/Haiku/GPT-5/4o 是否切 TL）+ 一并推送
