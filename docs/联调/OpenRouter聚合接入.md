# OpenRouter 聚合接入（默认上游）

> 2026-07-28 · 拍板：对外售卖 Token **默认走聚合** → 直连 DeepSeek/Qwen 作兜底。  
> 规划唯一口径：`docs/规划/主脑副脑岗位与国际Token供给-1.0.md` §四（v1.0.2）

## 为什么

- OpenRouter 面向开发者，一 Key 多模型，换档改 env 即可  
- 平台卖 **AI24X Token**，不宣称官方代理  
- token 价≈透传；充值约 +5.5% 平台费，换合规与运维自由度  

## 默认三档（代码已写死，可 env 覆盖）

| 对外 | env | 默认 id |
|------|-----|---------|
| flash / auto | `OPENROUTER_MODEL_L1` | `qwen/qwen3.7-flash` |
| pro | `OPENROUTER_MODEL_L2` | `deepseek/deepseek-r1` |
| ultra | `OPENROUTER_MODEL_L3` | `openai/gpt-4o-mini` |
| 兜底 | `OPENROUTER_MODEL_L0` | `openrouter/auto` |
| 欧盟 | `OPENROUTER_MODEL_EU` | `qwen/qwen-2.5-72b-instruct` |

## 本机 env（行级追加，禁止整文件覆盖）

```
TOKEN_LLM_UPSTREAM=openrouter
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_SITE_URL=https://www.ai24x.com
OPENROUTER_APP_NAME=AI24X
```

```powershell
pm2 restart core-8000 --update-env
# 或生产：pm2 restart core-api-8002 --update-env
```

## 验收

```powershell
# 1) 模式
curl.exe -sS http://127.0.0.1:8000/v1/models
# 期望 upstream_mode=openrouter，openrouter_ready=true

# 2) 烟测（需登录 JWT 或按你们现有 chat 鉴权）
python api/scripts_openrouter_smoke.py
```

期望：`auto` / `flash` / `pro` 均有非 stub 回复（有余额时）。

## 回退直连

```
TOKEN_LLM_UPSTREAM=direct
DEEPSEEK_API_KEY=...
```

## 雷总待办（人工）

1. [openrouter.ai](https://openrouter.ai/) 注册并充值小额  
2. 创建 API Key，写入本机（及以后生产）`api/.env`  
3. 重启 API 后跑烟测  
4. 看 OR 账单，确认 L1/L2/L3 单价与平台售价毛利  
5. （P1）PayPal 审核状态；Webhook 另开任务  
