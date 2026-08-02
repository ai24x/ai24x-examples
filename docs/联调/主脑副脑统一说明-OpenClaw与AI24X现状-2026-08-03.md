# 主脑 / 副脑统一说明 · OpenClaw × AI24X（2026-08-03）

> 口径：给主脑、副脑01–04、Cursor 会话共用。勿再按「无 tools / 假流式 / 平台死卡 4000」旧叙事推进。  
> 生产：副脑04 = www / api。远端：`origin` / `gitee` master。

---

## 一句话现状

OpenClaw 接 AI24X（`baseUrl=https://api.ai24x.com/v1` + `flash`/`pro`）**能聊天、能工具调用执行本机命令**；flash/pro 路由为 **DeepSeek 官方直连优先 + OpenRouter 兜底**（非「纯聚合劣质替身」）。

---

## 根因对齐（勿再归因「Flash 不够聪明」）

| 层 | 事实 |
|----|------|
| 模型 | flash/pro ≈ DS 系同档；智商接近直连 |
| 曾断裂 | 兼容层未跑通 `tools → tool_calls → role=tool`；假流式拉长等待感 |
| 已修 | 真流式 + tools 闭环（生产已验 OpenClaw `exec`） |
| 客户端坑 | baseUrl 缺 `/v1`→405；key 被省略号截断→401；主会话超大上下文→卡顿感 |

---

## 架构口径（已落地，不是待建设空想）

```
OpenClaw / 客户端
  → https://api.ai24x.com/v1/chat/completions
  → AI24X 鉴权 / 计费 / 路由
       ├─ flash(L1) / pro(L2)：TOKEN_LLM_DS_PREFER_PAID=1（默认）→ DeepSeek 官方优先
       └─ 失败 / 限流 → OpenRouter 等同层回退
  → 真流式 SSE + tools 透传（TOKEN_LLM_TRUE_STREAM / TOKEN_LLM_TOOLS 默认开）
```

| 相对 DS 直连 | 说明 |
|--------------|------|
| 多一跳 | 平台计费与多上游，偶发首包稍慢 |
| 能力 | Completions：tools / 真流式 / max_tokens≤16384 |
| Responses | 文本最小兼容；**勿宣传 Responses 已支持 tools** |
| 上下文声明 | OpenClaw 示例 contextWindow=128000、maxTokens=8192（客户端默认；平台允许更高 max_tokens） |

---

## 已发版要点（仓库）

| 包 | SHA（参考） | 说明 |
|----|-------------|------|
| 真流式 | `056af39` 一带 | SSE 透传 + nginx 超时清单 |
| tools | `afd61a6` | tools / tool_calls / role=tool |
| 侧栏可读 | `6d1c227` | 控制台当前项非白字 |
| 过夜补强 | `7c2c92c` | Responses 上限对齐 Completions；401 区分 invalid / key_disabled；402 透出业务 code |

副脑04 跑书：

- `docs/联调/副脑04-更新指令-OpenClaw真流式nginx超时.md`
- `docs/联调/副脑04-更新指令-OpenClaw-tools命令执行-NSSM.md`
- `docs/联调/副脑04-更新指令-过夜补强-Responses上限与鉴权细分-NSSM.md`（本过夜包）

---

## 主脑建议对照（何者已过时）

| 主脑 P0 旧说法 | 现况 |
|----------------|------|
| 要做真流式 | **已做**（确认 04 nginx） |
| 要做原生 tools | **已做**（公网 + OpenClaw exec 已验） |
| 平台死卡 max_tokens=4000 | Completions **已 16384**；Responses 过夜对齐；OpenClaw 客户端可配 8192+ |
| 全 OR、无直连 | **默认 DS prefer + OR 兜底**（需 04 有 `DEEPSEEK_API_KEY`） |

**下一刀（P1，非连夜大改）**：Responses tools（可选）、错误文案/多语言细化、docs 各客户端 baseUrl 表、多 Key 控制台体验。

---

## 分工

| 角色 | 做什么 |
|------|--------|
| **副脑04** | `git pull` → 重启 `AI24X-core` → 核 env（勿整文件写 `.env`）→ curl tools / plans → 回报 SHA |
| **主脑** | 更新记忆：勿再发「无 tools / 假流式」任务包；OpenClaw 验收用**干净会话**；默认 primary 可仍 DeepSeek，会话切 `ai24x/flash` 即可 |
| **Cursor/开发** | 过夜补强已合入；雷总验收清单见下 |
| **雷总** | 回来按「验收」三节点头即可 |

---

## 验收（雷总回来）

1. 公网：带 `tools` 的 flash → 有 `tool_calls`  
2. 干净 OpenClaw：`ai24x/flash` 要求 exec 出年份 → 轨迹有 `exec`  
3. 指南：`/guides/openclaw.html` 写明 tools + maxTokens 说明  
4. 无效 key → `invalid_api_key`；已吊销 key → `key_disabled`（若已部署过夜包）

---

## 对外话术（可复制）

> OpenClaw 推荐 `baseUrl=https://api.ai24x.com/v1`，模型填 `flash` 或 `pro`。支持流式与工具调用，可执行本机命令；flash/pro 以高质量上游为主并自动容灾。Key 须完整粘贴，勿截断。

---

## 禁止

- 整文件覆盖生产/本机 `api/.env`  
- 把主脑默认 primary **永久**钉死 AI24X（验收用干净会话）  
- 用户可见文案写 SMTP / 副脑 / env / 上游厂商名  
