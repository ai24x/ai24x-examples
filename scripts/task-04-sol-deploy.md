# 04 部署任务：vip-gpt56-sol 上线（commit 3140453）

> 发送：总司令 → 04 国际生产 ｜ 时间：2026-09-03 15:40
> 性质：生产部署（GPT-5.6 Sol 接入，雷总 15:18 拍板）

## 背景
平台官补丁规格已完成，主脑代落盘并已 commit+push（master 3140453，含 model_warehouse.py + model_router.py 改动）。请你执行生产部署 + 核价 + 自测。

## 改动内容（已入库）
1. `api/model_warehouse.py`：新增 `vip-gpt56-sol` 条目（openrouter_id=openai/gpt-5.6-sol，cost 2.0/10.0，billing_mult 26 / in_mult 11 / out_mult 35，quality 标准旗舰·平衡，failover→luna/ds-pro）+ 别名 gpt56-sol/gpt-5.6-sol/sol
2. `api/model_router.py`：_TOKENLAB_MODEL_MAP 加 `vip-gpt56-sol→gpt-5.6-sol`；_REQUESTY_MODELS 加 openai/gpt-5.6-sol

## 任务清单
1. **git 同步**：生产仓库更新到 3140453（标准流程）
2. **核价（关键）**：查 TL/QR 是否有 `openai/gpt-5.6-sol` 同款且更便宜（terra/luna 均拿过 50% off 先例）——若有：把 cost_in/out 换成实价并按毛利公式调低 mult（参照 gpt54/gpt5-mini 先例，防倒挂下限 6×1.5）再部署；若无：维持 OR 价 mult 26/11/35
3. **部署重启**：core 服务重启（AI24X-core 标准流程）
4. **自测**：点名 vip-gpt56-sol 请求通 + 记账正常；/v1/models vip_picks 含 vip-gpt56-sol 且 enabled
5. **回执 ✅/⚠️**：核价结论（TL/QR 有无更低价）、最终 cost/mult、部署 commit、自测结果

## 纪律
- 不动 price_usd 对外套餐价 / .env / 生产 key / 其他模型条目
- 毛利核算防倒挂（地板 = blended_cost×1.5）
