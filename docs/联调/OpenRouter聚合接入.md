# OpenRouter 聚合接入（默认上游）

> 2026-07-28 · 拍板：对外售卖 Token **默认走聚合**，降低官方直连转售封禁风险。

## 为什么

- OpenRouter 等面向开发者，一 Key 多模型，换模型不换代码  
- 平台卖的是 **AI24X Token**，不宣称官方代理  
- 直连 DeepSeek/Qwen 仍保留：`TOKEN_LLM_UPSTREAM=direct`

## 本机 / 生产 env（行级）

```
TOKEN_LLM_UPSTREAM=openrouter
OPENROUTER_API_KEY=<你的 key>
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_SITE_URL=https://www.ai24x.com
OPENROUTER_APP_NAME=AI24X
# 可选改模型（OpenRouter 控制台复制 id）
# OPENROUTER_MODEL_L1=deepseek/deepseek-chat
# OPENROUTER_MODEL_L2=deepseek/deepseek-r1
# OPENROUTER_MODEL_L3=openai/gpt-4o-mini
# OPENROUTER_MODEL_L0=openrouter/auto
# OPENROUTER_MODEL_EU=qwen/qwen-2.5-72b-instruct
```

然后：`pm2 restart core-8000 --update-env`（本机）或生产 `core-api-8002`。

## 验收

1. `GET /v1/models` → `upstream_mode=openrouter`，`openrouter_ready=true`  
2. 登录后 `POST /v1/chat/run`，`model=auto` 有正常回复  
3. 管理/日志里 provider 可见 `openrouter`

## 回退直连

```
TOKEN_LLM_UPSTREAM=direct
DEEPSEEK_API_KEY=...
```

重启 API 即可。

## 第二聚合商（以后）

任意 OpenAI 兼容：把 `OPENROUTER_BASE_URL` + Key 换成另一家，或再加一层 env（待扩展）。当前先跑通一家。
