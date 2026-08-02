# 副脑04 · 更新指令（OpenClaw 真流式 + 定价/防刷本包 · 生产）

> 发令：2026-08-02 · **副脑04 = 对外生产**（www / api）  
> 目标提交：拉码后看下方「期望 commit」（推送后填写 / 或 `git log -1`）  
> 进程：NSSM `AI24X-core`（**必须重启**）  
> 静态：`web/` 拉码即生效（硬刷新）  
> **禁止**整文件 Write 覆盖 `api/.env`  
> 远端：`git pull origin master`（失败再 `git pull gitee master`）

配套设计：`docs/联调/OpenClaw真流式与超时-设计-2026-08-02.md`

---

## 本包内容（摘要）

| 项 | 说明 |
|----|------|
| **真流式** | `stream=true` 上游 SSE 透传；流末扣费；`TOKEN_LLM_TRUE_STREAM` 默认开 |
| **超时** | 应用读超时默认 300s；**nginx 必须**关缓冲 + 拉长 `proxy_read_timeout` |
| **上下文** | prompt 上限约 12 万字；messages 透传上游 |
| **OpenClaw** | 指南推荐 `baseUrl=https://api.ai24x.com/v1` |
| 定价 P1 | Starter $2/30万、Builder $20/40M、Scale $99；VIP 日赠仅 flash/auto/shared |
| 中国 VIP | 硅基优先路由（有 siliconflow_id） |
| 邮箱防刷 | 一次性邮箱域名拦截 + 发信频控 |
| 管理台 | 价表 POST、共享默认帽、硅基 id 列 |

---

## 执行（PowerShell · 整段复制）

```powershell
Set-Location C:\ai24x01

git status
git checkout master
git pull origin master
# 若失败：git pull gitee master
git log -1 --oneline
# 期望：含 OpenClaw 真流式 / true_stream / stream_chat 等（见主脑钉死的 SHA）

# —— 可选 env（行级追加；默认已开真流式，可不改）——
# 若需显式：TOKEN_LLM_TRUE_STREAM=1
# TOKEN_LLM_STREAM_TIMEOUT_S=300
# 不要动 DATABASE_URL / 支付密钥

Get-Service AI24X-core | Format-Table Name, Status
Restart-Service AI24X-core
Start-Sleep -Seconds 8
Get-Service AI24X-core | Format-Table Name, Status

# 健康（端口以现网为准：常见 8002 或 8000）
$ports = @(8002, 8000)
foreach ($p in $ports) {
  try {
    $c = (Invoke-WebRequest "http://127.0.0.1:$p/v1/billing/plans" -UseBasicParsing -TimeoutSec 12).StatusCode
    "plans :$p -> $c"
  } catch { "plans :$p -> $($_.Exception.Message)" }
}
```

### Nginx（必做 · 否则 OpenClaw 长会话仍 504）

编辑 `api.ai24x.com` 反代（upstream 端口以现网为准，常见 `127.0.0.1:8002`）：

```nginx
location /v1/chat/completions {
    proxy_pass http://127.0.0.1:8002;   # ← 改成现网 core 端口
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header Connection "";
    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 360s;
    proxy_send_timeout 360s;
}
```

若 completions 走统一 `location /`：至少在该 location 加 `proxy_buffering off;` 且 `proxy_read_timeout` ≥ **300s**。

```powershell
nginx -t
nginx -s reload
# 或现网惯用 reload 脚本
```

---

## 验收（回报主脑）

1. `git log -1` 为本包；`AI24X-core` Running；plans **200**  
2. **流式（公网）**——首包应明显早于整段结束，且不 504：

```powershell
# $key = "sk-..."   # 控制台有效 Key
curl.exe -N -sS -X POST "https://api.ai24x.com/v1/chat/completions" `
  -H "Authorization: Bearer $key" `
  -H "Content-Type: application/json" `
  -d "{\"model\":\"flash\",\"stream\":true,\"messages\":[{\"role\":\"user\",\"content\":\"Count slowly from 1 to 15\"}]}"
```

3. `/v1/chat/run` 仍可用（无回归）  
4. OpenClaw：`baseUrl=https://api.ai24x.com/v1`，`api=openai-completions`，model=`flash`/`pro`；中等多轮不再稳定 Continue/504  
5. 硬刷新：`https://www.ai24x.com/guides/openclaw.html` 见 `/v1` 推荐文案  

---

## 回滚

1. nginx：去掉加长超时 / 恢复 buffering → `nginx -s reload`  
2. 代码：`git checkout <上一稳定 SHA> -- api/model_router.py api/services.py api/openai_compat.py api/main.py`（或整仓回退）+ `Restart-Service AI24X-core`  
3. 或 `.env` 行级：`TOKEN_LLM_TRUE_STREAM=0` + 重启 core（回假流式）  

## 不要做

- 不要整文件覆盖 `.env`  
- 不要用 pm2 代替 NSSM 重启 core（现网以 NSSM 为准）  
- 本期**不做** tools / tool_calls（P1-B 另包）  
