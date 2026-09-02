# 04回执 · Codex 断片 max_tokens + 本机 aliases

- **网关**：`c7d41c7fc41d` → health `67e73e0782f6`；默认 max_tokens 无 tools=4096 / 有 tools=8192
- **本机 Codex**：已改 `C:\Users\Admin\.codex\config.toml` 别名回 `ai24x-prod/*`（仅 `ds-flash`/`ds-pro` 直连 DeepSeek）
- **复测**：重启 Codex 桌面端后切 AI24X Flash；长回答不应再半截断开
- **英文 STEPS**：桌面 `conversationDetailMode=STEPS_COMMANDS` 仍会显示英文工具规划独白，与网关 reasoning 不是同一层
