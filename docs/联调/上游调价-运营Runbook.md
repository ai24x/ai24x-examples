# 上游 / 直连调价 · 运营 Runbook

> 适用：OpenAI / 硅基 / DeepSeek / OpenRouter 等上游变价，或供货价调整。  
> 原则：**只热更系数，不改扣费公式**；**人审保存，无自动跟价**；已购额度不追溯。

## 两根杠杆（先分清）

| 杠杆 | 改什么 | 何时用 |
|------|--------|--------|
| A 降本 | 模型仓库「层 Model id」切更便宜上游 | 上游涨价或有更优通道 |
| B 跟价/让利 | VIP「成本 in/out + 计费倍率」 | 上游降价想让利，或涨价要守毛利 |

两件事不要混成一次「自动同步」。

## 调价步骤（约 10 分钟）

1. 打开 **Token 管理台 → 模型仓库**。
2. 在 **VIP 名模费率** 表登记新的 **成本 in / out**（USD / 1M，公开价或批发价即可）。
3. 点该行 **填入建议**，或顶部 **全部填入建议倍率**  
   （公式：`ceil(混合成本 / flash锚 × TOKEN_MIN_MARKUP)`，默认加成 2.0）。
4. 人工微调倍率（可略高于建议以留利润，或略低以促销——但不得低于护栏）。
5. 看 **估售$/M** 与 **估毛利%**：红色表示低于地板，保存会被拒。
6. 核对 L2 / L3 品牌层倍率（一般不动；大调 flash 锚时再议）。
7. 点 **保存仓库与费率** → 立即生效（写 `api/data/model_warehouse_override.json`）。
8. 前台硬刷新：`models/vip-picks.html`、控制台试调下拉，确认预估 `$/M` 已变。
9. 用一把测试 Key 打 1 次对应 `vip-*`，核对流水扣费 ≈ 上游用量 × 新倍率。
10. 必要时：**关** 单模开关，或改层 upstream model（杠杆 A）。

## 护栏与环境变量

| 项 | 说明 |
|----|------|
| `TOKEN_FLASH_REF_USD_PER_M` | flash 售价锚（默认 0.35）；估售价 = 锚 × 倍率 |
| `TOKEN_MIN_MARKUP` | 最低加成（默认 2.0）；估售价 ≥ 混合成本 × 加成 |
| 审计 | `api/data/pricing_audit.jsonl`（每次费率变更追加） |

## 回滚（5 步）

1. 打开 `api/data/model_warehouse_override.json`。
2. 对照 `pricing_audit.jsonl` 最近一条的 `old` 字段。
3. 将对应 `vip_rates.<id>`（或整段 `vip_rates` / `layer_mult`）改回旧值。  
   或在管理台重新填入旧成本/倍率后保存。
4. 保存后无需重启 API（覆盖文件即时读取）。
5. 再打 1 次调用确认扣费回到旧倍率。

> 若误删整个 override：仅丢失层 model 覆盖与费率覆盖，代码内 CATALOG 默认仍可用。

## 明确不做

- 新闻/爬虫自动改价（无人审）。
- 追溯改写用户历史流水。
- 因单个 GPT 降价去改 Builder/Scale 包内 token 数（那是 flash 锚；大调锚时另开价表任务）。

## 相关代码

- `api/model_warehouse.py` — 合并读取、护栏、审计、`update_warehouse`
- `api/model_router.py` — VIP 与品牌层扣费读合并倍率
- `web/token-admin.html` — 仓库费率编辑
- `web/models/vip-picks.html` — 前台估价同源 API
