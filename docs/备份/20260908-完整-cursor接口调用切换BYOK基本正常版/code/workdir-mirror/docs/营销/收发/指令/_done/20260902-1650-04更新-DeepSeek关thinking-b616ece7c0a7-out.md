# 04回执 · DeepSeek v4 关 thinking

- **状态**: ✅ 已上线
- **EXP**: `b616ece7c0a7` · **HEAD/health**: `e26a35d63195`
- **根因核实**: `TOKEN_LLM_UPSTREAM=openrouter` 时上游 model 为 `deepseek/deepseek-v4-flash`，旧逻辑 `startswith("deepseek-v4")` 未命中
- **修复**: 按上游 basename 识别 DeepSeek v4；默认 `thinking={type:disabled}`；关闭时不透传 `reasoning_content` 流式/回落
- **开关**: `DEEPSEEK_THINKING=1` 仍可恢复思考
- **未改**: GPT/Luna 等非 DS v4 路径

## Codex 复测

切 AI24X `flash` / `vip-ds-flash`：不应再出现英文思考块。  
`VIP-gp-56-luna` 行为应不变。
