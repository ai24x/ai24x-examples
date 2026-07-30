# OpenRouter 聚合接入

> 2026-07-30 · **成本优先**：L1=`deepseek/deepseek-v4-flash`，L2=`deepseek/deepseek-v4-pro`；MiMo 能力向一键切换。  
> 规划：`docs/规划/主脑副脑岗位与国际Token供给-1.0.md` §四（v1.0.5）

## 为什么

- 一 Key 多模型；OR 上 Flash 标价通常 ≤ MiMo，更贴 flash 毛利  
- MiMo 作 Agent/热度增强，不强制默认  
- 故障回滚：`TOKEN_LLM_UPSTREAM=direct` + 官方 DeepSeek  

## 默认三档（代码默认，可 env 覆盖）

| 对外 | env | 默认 id |
|------|-----|---------|
| flash / auto | `OPENROUTER_MODEL_L1` | `deepseek/deepseek-v4-flash` |
| 能力向 L1 | 同上 | `xiaomi/mimo-v2.5` |
| pro | `OPENROUTER_MODEL_L2` | `deepseek/deepseek-v4-pro` |
| ultra | `OPENROUTER_MODEL_L3` | `openai/gpt-4o-mini` |
| 兜底 | `OPENROUTER_MODEL_L0` | `openrouter/auto` |
| 欧盟 | `OPENROUTER_MODEL_EU` | `qwen/qwen-2.5-72b-instruct` |

## 本机 / 生产 env

```
TOKEN_LLM_UPSTREAM=openrouter
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_SITE_URL=https://www.ai24x.com
OPENROUTER_APP_NAME=AI24X
# 与代码默认一致时可省略：
# OPENROUTER_MODEL_L1=deepseek/deepseek-v4-flash
# OPENROUTER_MODEL_L2=deepseek/deepseek-v4-pro
# 能力向：
# OPENROUTER_MODEL_L1=xiaomi/mimo-v2.5
```

```powershell
# 生产 NSSM：
Restart-Service AI24X-core
```

## 验收

```powershell
python api/scripts_openrouter_smoke.py
# OPENROUTER_SMOKE_LIVE=1 → L1 model=deepseek/deepseek-v4-flash，provider=openrouter
```

## 回退直连

```
TOKEN_LLM_UPSTREAM=direct
DEEPSEEK_API_KEY=...
```
