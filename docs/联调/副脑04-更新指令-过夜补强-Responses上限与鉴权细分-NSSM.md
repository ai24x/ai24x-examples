# 副脑04 · 更新指令（过夜补强 · Responses 上限 + 鉴权细分）

> 发令：2026-08-03 凌晨 · **副脑04 = 对外生产**  
> 目标提交：`7c2c92c`（`fix(api): align Responses max_tokens and refine OpenAI auth error codes`）  
> 进程：NSSM `AI24X-core`（**必须重启**）  
> 静态：指南 locales 拉码即生效  
> **禁止**整文件 Write 覆盖 `api/.env`  
> 配套总说明：`docs/联调/主脑副脑统一说明-OpenClaw与AI24X现状-2026-08-03.md`

## 本包

| 项 | 说明 |
|----|------|
| Responses | `max_output_tokens` / `max_tokens` 上限与 Completions 对齐（16384） |
| 401 | 无效 key → `invalid_api_key`；已吊销 → `key_disabled`（勿再统一糊成一句） |
| 402 | OpenAI 错误体透出业务 `code`（如 `insufficient_balance`） |
| 指南 | OpenClaw maxTokens/平台上限说明 |
| env 自检（只读） | 确认有 `DEEPSEEK_API_KEY`；`TOKEN_LLM_DS_PREFER_PAID` 默认开（可不写）；`TOKEN_LLM_TOOLS`/`TOKEN_LLM_TRUE_STREAM` 默认开 |

## 执行

```powershell
Set-Location C:\ai24x01
git checkout master
git pull origin master
# 失败：git pull gitee master
git log -1 --oneline

# 只读自检（不要改写整个 .env）
Select-String -Path api\.env -Pattern "^DEEPSEEK_API_KEY=|^TOKEN_LLM_UPSTREAM=|^TOKEN_LLM_DS_PREFER|^TOKEN_LLM_TOOLS=|^TOKEN_LLM_TRUE_STREAM="

Restart-Service AI24X-core
Start-Sleep -Seconds 8
Get-Service AI24X-core

# 健康
Invoke-WebRequest http://127.0.0.1:8002/v1/billing/plans -UseBasicParsing
# 若 8002 不通试 8000
```

## 验收回报

1. `git log -1`  
2. core Running；plans 200  
3. （可选）假 key → 401 且 `error.code=invalid_api_key`  
4. 确认上一包 tools 仍可用（flash + tools → tool_calls）  

## 不要做

- 不要整文件覆盖 `.env`  
- 不要关 `TOKEN_LLM_TOOLS` / `TOKEN_LLM_TRUE_STREAM`（除非回滚）  
