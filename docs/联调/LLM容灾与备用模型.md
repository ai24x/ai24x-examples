# LLM 容灾与备用模型 Runbook（2026-07-30）

## 现状

| 项 | 口径 |
|----|------|
| 生产默认 | 多为 `TOKEN_LLM_UPSTREAM=openrouter`（以服务器 env 为准） |
| 层内降级 | FREE：`L1→L0`；VIP：`L1→L2→L3` |
| 跨模式 | **不会**自动 OR↔直连；须改 env + 重启 |
| 全 live 失败 | 对用户返回「模型服务暂时繁忙」（不再假 stub 成功） |

## P0 备用（建议配齐）

| 优先级 | 用途 | 模型 / 通道 | 配置 |
|--------|------|-------------|------|
| P0 | 主档 flash | OR `deepseek/deepseek-v4-flash` 或直连同名 | `OPENROUTER_*` / `DEEPSEEK_*` |
| P0 | OR 挂了回滚 | `TOKEN_LLM_UPSTREAM=direct` + DeepSeek Key | 行级改 env → `Restart-Service AI24X-core` |
| P0 | FREE 兜底 L0 | 硅基 `Qwen/Qwen2.5-7B-Instruct`（direct）或 OR `openrouter/auto` | `SILICONFLOW_API_KEY` |
| P0 | pro | OR/直连 `deepseek-v4-pro` | L2 |

## P1 能力 / 区域

| 用途 | 建议 | 备注 |
|------|------|------|
| 能力向 L1 | `OPENROUTER_MODEL_L1=xiaomi/mimo-v2.5` | A/B，看毛利 |
| EU | `TOKEN_REGION_ROUTING=1` + QI Key | 默认关 |
| ultra 降本 | 用中国线替代 `gpt-4o-mini` | 可选 |

## 运维自检

```powershell
curl.exe -sS http://127.0.0.1:8002/health
# 期望含 upstream_mode、layers.*.key_set

# 管理台或：
# GET /v1/admin/token/upstream_probe?live=0
# GET /v1/admin/token/upstream_probe?live=1   # 花钱探 L0/L1
```

可选：`AI24X_BUILD_STAMP=20260730-xxx` 写入 env，便于确认已加载新包。

## OR → 直连一键回滚

```
# api\.env 行级：
TOKEN_LLM_UPSTREAM=direct
# 确认 DEEPSEEK_API_KEY 有效
Restart-Service AI24X-core
```

## 调试通清单（本机 / 03）

1. flash 试调成功（非 stub）  
2. 故意断 L1 Key 时 FREE 能否落到 L0（须先配硅基或 OR L0）  
3. `direct` 回滚一次再切回 `openrouter`  
4. health / upstream_probe 绿  

未配硅基时，L0 兜底无效——**吃饭回来可协助：确认是否开硅基账号或只靠 OR L0。**
