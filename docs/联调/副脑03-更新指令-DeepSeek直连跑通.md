# 副脑03 · LLM 切 DeepSeek 直连（先跑通）

> 发令：2026-07-30  
> 原因：OpenRouter 国内充值不便；先 `direct` + DeepSeek 跑通 chat，OR 有余额再切回。  
> **禁止**整文件覆盖 `.env`；勿贴完整 Key。NSSM：`AI24X-core`。

## 执行

```powershell
Set-Location C:\ai24x01
git pull origin master
git log -1 --oneline

# 行级改 api\.env（notepad）：
# TOKEN_LLM_UPSTREAM=direct
# DEEPSEEK_API_KEY=<已有国内 Key，须有余额>
# DEEPSEEK_MODEL=deepseek-v4-flash
# （OPENROUTER_API_KEY 可保留不删）

notepad api\.env

Restart-Service AI24X-core
Start-Sleep -Seconds 3
curl.exe -sS http://127.0.0.1:8002/v1/models
# 期望 upstream_mode=direct，upstream.direct_ready 或 l1_ready=true，l1_model 含 deepseek

# 可选：控制台或 chat/run 测一句 flash
```

## 回报（脱敏）

- git log -1  
- `upstream_mode`、`l1_model`、deepseek key 的 len  
- chat 是否非 stub  

## 以后切 OR

`TOKEN_LLM_UPSTREAM=openrouter` + OR 已充值 → 重启。见 `docs/联调/OpenRouter聚合接入.md`。
