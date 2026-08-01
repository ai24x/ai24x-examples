# 副脑04 · 更新指令（OpenAI 兼容 POST /v1/chat/completions）

> 发令：2026-08-02  
> 进程：NSSM `AI24X-core`（**必须重启**以加载新路由）  
> **禁止**整文件覆盖 `api/.env`；本包**无需**改 `.env`  
> 远端：`git pull origin master`（或 `gitee master`）

## 本包内容

| 项 | 说明 |
|----|------|
| 新接口 | `POST /v1/chat/completions`（与 `/v1/chat/run` 并存） |
| 认证 | `Authorization: Bearer <API_KEY>` 或 `X-API-Key`（同一密钥体系） |
| 请求 | OpenAI `messages[]` + `model` + `stream` |
| 计费 | 复用 `ChatService.process_chat_request`（禁止另账） |
| 流式 | `stream=true` → SSE chunk + `data: [DONE]` |
| 错误 | OpenAI `{"error":{"message","type","code"}}` |
| 文件 | `api/openai_compat.py`、`api/main.py`、`api/scripts_openai_compat_smoke.py` |

## 执行（PowerShell · 整段复制）

```powershell
Set-Location C:\ai24x01

git status
git checkout master
git pull origin master
# 若失败：git pull gitee master
git log -1 --oneline
# 期望含：openai / chat/completions / compat

# 勿动 DATABASE_URL；本包无 .env 必改项

Get-Service AI24X-core | Format-Table Name, Status
Restart-Service AI24X-core
Start-Sleep -Seconds 6
Get-Service AI24X-core | Format-Table Name, Status

try { (Invoke-WebRequest "http://127.0.0.1:8002/health" -UseBasicParsing -TimeoutSec 15).StatusCode } catch { $_.Exception.Message }

# openapi 应含 chat/completions
$oa = (Invoke-WebRequest "http://127.0.0.1:8002/openapi.json" -UseBasicParsing -TimeoutSec 20).Content
if ($oa -match "chat/completions") { "openapi: HAS completions" } else { "openapi: MISSING completions" }

# 环回：用一把有效 Key（控制台创建后粘贴到 $key）
# $key = "sk-xxxxxxxx"
# curl.exe -sS "http://127.0.0.1:8002/v1/chat/completions" -H "Authorization: Bearer $key" -H "Content-Type: application/json" -d "{\"model\":\"flash\",\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}],\"stream\":false}"
# curl.exe -sS -N "http://127.0.0.1:8002/v1/chat/completions" -H "Authorization: Bearer $key" -H "Content-Type: application/json" -d "{\"model\":\"flash\",\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}],\"stream\":true}"
# curl.exe -sS "https://api.ai24x.com/v1/chat/completions" ...（公网同测）
```

## 验收（回报主脑）

1. `git log -1` 为本包提交；`AI24X-core` Running；health **200**  
2. openapi 含 `chat/completions`  
3. 本机/公网：非流式 200 + `object=chat.completion`；流式含 `data: [DONE]`  
4. `/v1/chat/run` 仍可用（X-API-Key）  
5. **Open WebUI / LobeChat**（主脑协调实测）：  
   - Base URL：`https://api.ai24x.com/v1`（或文档要求的根；以客户端为准）  
   - API Key：控制台签发的 `sk-…`  
   - Model：`flash` / `pro` / `ultra` / `vip-*`

## 不要做

- 不要 `pm2 restart` core  
- 不要 Write 整份 `.env`  
- 不要改 guides 文案（本期不做）  
