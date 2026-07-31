# 副脑03 · 更新指令（DeepSeek 官方兜底 + 管理台密钥目录）

> 发令：2026-08-01  
> **进程管理：NSSM / Windows 服务（禁止 pm2 启停本包）**  
> **禁止**整文件覆盖 `api/.env`（只允许行级补 `DEEPSEEK_API_KEY` 等）  
> 远端：`git pull gitee master`（若只有 origin：`git pull origin master`）

## 本包内容（主站 Token）

| 项 | 说明 |
|----|------|
| OR→DS 兜底 | `TOKEN_LLM_UPSTREAM=openrouter` 时，L1（flash）OR 失败自动试官方 DeepSeek Flash（需 Key） |
| 开关 | `TOKEN_LLM_DS_FAILOVER=1`（默认开；`=0` 可关） |
| 管理台 | 「开关与密钥」上游密钥改为**表格目录**（同模型仓库风格）：DeepSeek + Together/OpenAI/Anthropic/Google（待规划）一并列出 |
| 文件 | `api/model_router.py`、`api/llm_keys.py`、`api/schemas.py`、`api/upstream_providers.py`、`web/token-admin.html`、`api/.env.example`、容灾文档 |

## 生产 env（行级核对，勿整文件覆盖）

确认 `C:\ai24x01\api\.env`（或实际挂载路径）**已有且非空**：

```
TOKEN_LLM_UPSTREAM=openrouter
DEEPSEEK_API_KEY=<已有国内 Key，须有余额>
# 可选（默认已是开）：
# TOKEN_LLM_DS_FAILOVER=1
# DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
# DEEPSEEK_MODEL=deepseek-v4-flash
```

- **不要**删 `OPENROUTER_API_KEY`（主路径仍走 OR）  
- **不要** Write 整份 `.env`  
- 若缺 `DEEPSEEK_API_KEY`：记事本行级补上 → 必须 `Restart-Service AI24X-core`

## 执行（PowerShell · 整段复制）

```powershell
Set-Location C:\ai24x01

git status
git checkout master
git pull gitee master
# 若 pull 失败且远端叫 origin：git pull origin master
git log -1 --oneline
# 期望含：DeepSeek failover / llm keys catalog / token-admin 一类说明

Get-Service AI24X-core | Format-Table Name, Status
Restart-Service AI24X-core
Start-Sleep -Seconds 5
Get-Service AI24X-core | Format-Table Name, Status

# 门禁
try { (Invoke-WebRequest "http://127.0.0.1:8002/health" -UseBasicParsing -TimeoutSec 15).StatusCode } catch { $_.Exception.Message }

# 密钥目录：应含 DEEPSEEK_API_KEY；待规划含 TOGETHER / OPENAI / ANTHROPIC / GOOGLE_AI
$k = $env:SMS_INTERNAL_KEY
if (-not $k) { $k = (Select-String -Path C:\ai24x01\api\.env -Pattern '^SMS_INTERNAL_KEY=(.+)$').Matches.Groups[1].Value }
$h = @{ "X-SMS-Internal-Key" = $k.Trim() }
$lk = (Invoke-WebRequest "http://127.0.0.1:8002/v1/admin/token/llm_keys" -Headers $h -UseBasicParsing -TimeoutSec 20).Content | ConvertFrom-Json
$names = @($lk.keys | ForEach-Object { $_.name }) -join ","
"keys=$names"
"deepseek_set=" + [bool](@($lk.keys | Where-Object { $_.name -eq "DEEPSEEK_API_KEY" }).set)
"planned=" + (($lk.keys | Where-Object { $_.status -eq "planned" }).Count)

curl.exe -sS -o NUL -w "api_health=%{http_code}`n" https://api.ai24x.com/health
curl.exe -sS -o NUL -w "token_admin=%{http_code}`n" https://www.ai24x.com/token-admin.html
```

## 验收（回报主脑）

1. `git log -1 --oneline`（本包提交）  
2. `AI24X-core` = **Running**；`8002/health` = **200**  
3. `keys=` 含 **`DEEPSEEK_API_KEY`**，且 `deepseek_set=True`（若 False → 行级补 Key 后重启）  
4. `planned=` ≥ **4**（Together / OpenAI / Anthropic / Google）  
5. 浏览器 **Ctrl+F5**：https://www.ai24x.com/token-admin.html →「开关与密钥」→ 上游密钥为**表格**（非卡片），有 DeepSeek 行与待规划行  

## 回滚

```powershell
Set-Location C:\ai24x01
git log -5 --oneline
# 记下本包 hash 后：
git revert <本包提交hash> --no-edit
Restart-Service AI24X-core
Start-Sleep -Seconds 5
Get-Service AI24X-core | Format-Table Name, Status
try { (Invoke-WebRequest "http://127.0.0.1:8002/health" -UseBasicParsing -TimeoutSec 15).StatusCode } catch { $_.Exception.Message }
```

## 不要做

- 不要 `pm2 restart` 本机 core（生产是 NSSM `AI24X-core`）  
- 不要整文件覆盖 `.env`  
- 不要把密钥贴回飞书/指挥中心  
- 不要为了兜底把整站切成 `TOKEN_LLM_UPSTREAM=direct`（本包是 OR 失败才自动 DS）  
