# 04更新回执 · 中国模关 thinking + health 脱敏

- **时间**：2026-09-02 19:55
- **代码**：`3f4560de7e1b`（fix commit）
- **HEAD / health**：`1c58d034bcd3`（含指令文档提交）
- **派发**：`deploy04_direct.ps1` → 成功，群回执已发
- **验收**：
  - markers：`_apply_upstream_thinking_controls` / `_cn_thinking_family` / Qwen `enable_thinking` / `/v1/models` strip
  - 04 本机 gate：`cn_thinking_gate_ok`
  - 公网 `/health`：无 `upstream_mode` / `layers`
- **覆盖**：MiMo / DeepSeek / Kimi / GLM / Qwen（可关型号）；思考专用模仅挡透传
- **可复测**：Codex 切 `flash` / `vip-kimi` / `vip-glm` / `vip-qwen-max`，不应再先出英文 reasoning 块
