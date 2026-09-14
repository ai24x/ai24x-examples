# 副脑03 · OR 默认改为 DeepSeek Flash / V4-Pro

> 发令：2026-07-30  
> 代码：`_OR_DEFAULT_MODELS` L1=`deepseek/deepseek-v4-flash`，L2=`deepseek/deepseek-v4-pro`  
> MiMo：能力向时再设 `OPENROUTER_MODEL_L1=xiaomi/mimo-v2.5`  
> 禁止整文件覆盖 `.env`；NSSM：`AI24X-core`

## 执行

```powershell
Set-Location C:\ai24x01
git pull origin master
git log -1 --oneline

# api\.env 行级确认：
# TOKEN_LLM_UPSTREAM=openrouter
# OPENROUTER_API_KEY=...（有余额）
# 删除或注释掉旧的：
# OPENROUTER_MODEL_L1=xiaomi/mimo-v2.5
# OPENROUTER_MODEL_L2=deepseek/deepseek-r1
# （不写则用代码默认 Flash / V4-Pro）

notepad api\.env
Restart-Service AI24X-core
Start-Sleep -Seconds 3
curl.exe -sS http://127.0.0.1:8002/v1/models
```

## 验收

控制台发送 → `provider=openrouter`，`model=deepseek/deepseek-v4-flash`（或含 v4-flash）。

## 能力向（可选）

```
OPENROUTER_MODEL_L1=xiaomi/mimo-v2.5
```
→ 重启后再测。

## 回滚直连

```
TOKEN_LLM_UPSTREAM=direct
```
→ 重启。
