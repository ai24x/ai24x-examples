# 副脑03 · 切回 OpenRouter（已充值）

> 发令：2026-07-30  
> 前提：OpenRouter 已能支付宝充值；本机烟测 L1=`xiaomi/mimo-v2.5` 通过。  
> DeepSeek Key **保留**，作回滚：`TOKEN_LLM_UPSTREAM=direct`。  
> 禁止整文件覆盖 `.env`；NSSM：`AI24X-core`。

## 执行

```powershell
Set-Location C:\ai24x01
# 可选 pull（若只需改 env 可跳过）
git pull origin master

# 行级改 api\.env：
# TOKEN_LLM_UPSTREAM=openrouter
# OPENROUTER_API_KEY=<已有，确认有余额>
# （DEEPSEEK_API_KEY 保留不删）

notepad api\.env

Restart-Service AI24X-core
Start-Sleep -Seconds 3
curl.exe -sS http://127.0.0.1:8002/v1/models
# 期望 upstream_mode=openrouter，openrouter_ready=true
# l1_model 含 mimo 或 xiaomi/mimo-v2.5
```

## 验收

控制台再点发送：`provider` 宜为 `openrouter`，`model` 宜为 `xiaomi/mimo-v2.5`（或 env 覆盖值）。

## 回滚

```
TOKEN_LLM_UPSTREAM=direct
```
→ `Restart-Service AI24X-core`（继续用 DeepSeek）。
