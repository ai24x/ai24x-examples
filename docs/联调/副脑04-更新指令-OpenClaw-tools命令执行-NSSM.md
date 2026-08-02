# 副脑04 · 更新指令（OpenClaw tools / 命令执行 · 生产）

> 发令：2026-08-02 夜 · **副脑04 = 对外生产**（www / api）  
> 目标提交：`afd61a6`（`feat(api): OpenClaw tools/tool_calls passthrough for flash and pro`）  
> 进程：NSSM `AI24X-core`（**必须重启**）  
> 静态：`web/` 拉码即生效（硬刷新指南）  
> **禁止**整文件 Write 覆盖 `api/.env`  
> 远端：`git pull origin master`（失败再 `git pull gitee master`）

配套：`docs/联调/OpenClaw真流式与超时-设计-2026-08-02.md` §P1-B

---

## 根因（对齐口径）

不是 flash「不够聪明」。AI24X flash 上游本就是 DeepSeek 系；缺口在兼容网关曾掐断  
`tools[] → tool_calls → role=tool` 环，OpenClaw 只能闲聊、不执行本机命令。

---

## 本包内容

| 项 | 说明 |
|----|------|
| Completions | 透传 `tools` / `tool_choice`；回传 `tool_calls`；保留 `role=tool` |
| 流式 | 真流式 SSE 透传 `tool_calls` 增量 |
| 档位 | flash / pro / VIP 点名（上游支持 tools 时） |
| 开关 | `TOKEN_LLM_TOOLS` 默认开（可不改 env） |
| 指南 | OpenClaw 页写明支持工具调用；`baseUrl` 仍须 `/v1` |
| Responses | `/v1/responses` **仍不支持** tools（与 Completions 区分） |

nginx：沿用真流式包（`proxy_buffering off` + `proxy_read_timeout 360s`）。本包**无新 nginx 键**。

---

## 执行（PowerShell · 整段复制）

```powershell
Set-Location C:\ai24x01

git status
git checkout master
git pull origin master
# 若失败：git pull gitee master
git log -1 --oneline
# 期望：afd61a6 feat(api): OpenClaw tools/tool_calls ...（或更新的 pin 提交）

# 可选显式（默认已开）：TOKEN_LLM_TOOLS=1
# 不要动 DATABASE_URL / 支付密钥；禁止整文件覆盖 .env

Get-Service AI24X-core | Format-Table Name, Status
Restart-Service AI24X-core
Start-Sleep -Seconds 8
Get-Service AI24X-core | Format-Table Name, Status

$ports = @(8002, 8000)
foreach ($p in $ports) {
  try {
    $c = (Invoke-WebRequest "http://127.0.0.1:$p/v1/billing/plans" -UseBasicParsing -TimeoutSec 12).StatusCode
    "plans :$p -> $c"
  } catch { "plans :$p -> $($_.Exception.Message)" }
}
```

---

## 验收（回报主脑）

1. `git log -1` 为本包；`AI24X-core` Running；plans **200**  
2. **tools 非流式**（有效 sk，脱敏回报）：

```powershell
# $key = "sk-..."
curl.exe -sS -X POST "https://api.ai24x.com/v1/chat/completions" `
  -H "Authorization: Bearer $key" -H "Content-Type: application/json" `
  -d "{\"model\":\"flash\",\"tool_choice\":\"required\",\"tools\":[{\"type\":\"function\",\"function\":{\"name\":\"get_time\",\"description\":\"now\",\"parameters\":{\"type\":\"object\",\"properties\":{}}}}],\"messages\":[{\"role\":\"user\",\"content\":\"Call get_time now\"}]}"
```

期望：`choices[0].message.tool_calls` 非空，`finish_reason=tool_calls`。  
`pro` 再测一条同类。

3. 硬刷新：`https://www.ai24x.com/guides/openclaw.html` 见「工具 / 命令执行」说明  
4. （主脑侧）干净 OpenClaw 会话 `ai24x/flash`：要求用工具执行命令 → 轨迹有 exec/read，非口头「已执行」

---

## 回滚

1. `.env` 行级：`TOKEN_LLM_TOOLS=0` + `Restart-Service AI24X-core`（关 tools 透传）  
2. 或代码回退上一稳定 SHA + 重启 core  

## 不要做

- 不要整文件覆盖 `.env`  
- 不要改雷总本机 OpenClaw 默认 primary 为 AI24X  
- 不要宣称 `/v1/responses` 已支持 tools  
