# DeepSeek 直连跑通（现阶段默认上游）

> 2026-07-30 · 因 OpenRouter 国内充值不便，**先 `direct` 跑通 chat**；OR 有国际卡/加密余额后再切回。  
> 规划：`docs/规划/主脑副脑岗位与国际Token供给-1.0.md` §四（v1.0.4）

## 本机 / 生产 env（行级，禁止整文件覆盖）

```
TOKEN_LLM_UPSTREAM=direct
DEEPSEEK_API_KEY=sk-...
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
# 可选 VIP pro：
# DEEPSEEK_MODEL_PRO=deepseek-v4-pro
# 可选 L0 兜底（国内也可充）：
# SILICONFLOW_API_KEY=
# SILICONFLOW_MODEL=Qwen/Qwen2.5-7B-Instruct
```

OpenRouter Key **可保留不删**，只要 `TOKEN_LLM_UPSTREAM=direct` 就不会走 OR。

```powershell
# 本机
# 重启监听 8000 的 uvicorn / 或 pm2 restart core-8000 --update-env
# 生产 NSSM：
Restart-Service AI24X-core
```

## 验收

```powershell
python api/scripts_openrouter_smoke.py
# 期望：TOKEN_LLM_UPSTREAM mode = direct
# L1 provider=deepseek key=yes

# 真调（需 DeepSeek 有余额）
$env:OPENROUTER_SMOKE_LIVE="1"
python api/scripts_openrouter_smoke.py
# 期望 live ok、provider=deepseek（非 stub）
```

控制台 / `chat/run`：`flash`/`auto` 有真实回复。

## 以后切回 OpenRouter

```
TOKEN_LLM_UPSTREAM=openrouter
# OPENROUTER_API_KEY=...（已充值）
```

重启 API。详见 `docs/联调/OpenRouter聚合接入.md`。

## 副脑03 最短指令

```
行级：TOKEN_LLM_UPSTREAM=direct + 确认 DEEPSEEK_API_KEY 已配
Restart-Service AI24X-core
curl /v1/models → upstream_mode=direct，l1_ready=true
回报脱敏：mode + deepseek key set/len
```
