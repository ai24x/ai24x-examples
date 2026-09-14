# OpenAI Responses API（`/v1/responses`）兼容 · P1 排期

> 登记：2026-08-02 · 来源：LobeChat / LobeHub 实测（关「Responses 规范」可走 completions 验收）  
> **不阻塞**当前网关验收与投流；验收路径继续用 `POST /v1/chat/completions`。

## 为何做

主流客户端（LobeChat 等）默认开「Responses 规范」时请求 `POST /v1/responses`。  
现网只有 `/v1/chat/completions` 与 `/v1/chat/run` → 开开关会 **405**。  
关开关可立刻通；补兼容后「开/关都能通」，接入体验与 SEO 案例更稳。

## 合适开工时机（满足任一即可排进迭代）

1. LobeChat / Open WebUI 接入案例上线后，客服或文档 FAQ 里 **405 + Responses** 咨询变多  
2. 投流落地「自定义 API」转化受阻（用户不会关开关）  
3. 下一轮兼容网关冲刺（与 Cursor / Open WebUI 案例同批）  
4. **明确不做时机**：PayPal Live 首单未定、支付/限购 P0 未清时，先别并行开这刀

## MVP 范围（首版）

| 做 | 不做（首版） |
|----|----------------|
| `POST /v1/responses` 非流式 | 完整 stateful `previous_response_id` 持久化 |
| 鉴权与 completions 一致 | OpenAI 托管 tools / web_search 等 |
| `input` / `instructions` → 内部 chat | 完整 agent 循环 |
| 标准 `object:response` + `output_text` | 复杂多模态 output |
| OpenAI 风格错误 JSON | — |
| 复用现有计费/路由 | 旁路计费 |
| 流式：可标 TODO 或第二刀 | 首版可不做 SSE |

## 验收（开工后）

1. `curl` → `object=response` 且 `output` 有文本  
2. LobeChat **开启** Responses 规范可对话  
3. `/v1/chat/completions`、`/v1/chat/run` 回归 200  
4. 无 key → 401

## 现状依赖

- 已有：`api/openai_compat.py` + `POST /v1/chat/completions`  
- 文档：`web/guides/lobechat.html`（关开关说明）；本排期落地后改文案为「开关可开」
