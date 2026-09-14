# AI24X Examples

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://ai24x-examples-bj26ncdeqstapzeta63ozr.streamlit.app/)

Example code for using [AI24X Gateway](https://open.ai24x.com) — one OpenAI-compatible key for **31+ models**: DeepSeek, Qwen, GLM, Kimi, MiMo, GPT-6, GPT-5, Claude, Gemini, Grok, Llama and more.

## Live Demo

Try the AI24X Gateway interactively — compare model pricing and test API calls directly in your browser.

**[Launch Live Demo →](https://ai24x-examples-bj26ncdeqstapzeta63ozr.streamlit.app/)**

## Quick Start

```python
from openai import OpenAI
client = OpenAI(base_url="https://api.ai24x.com/v1", api_key="sk-...")
response = client.chat.completions.create(model="flash", messages=[{"role": "user", "content": "Hello!"}])
print(response.choices[0].message.content)
```

```bash
curl -X POST "https://api.ai24x.com/v1/chat/completions"   -H "Content-Type: application/json"   -H "Authorization: Bearer sk-your-key"   -d '{"model":"flash","messages":[{"role":"user","content":"Hello!"}]}'
```

## Directory

| Directory | Description |
|-----------|-------------|
| [python/](python/) | OpenAI Python SDK examples (chat, multi-model, BYOK) |
| [node/](node/) | Node.js / openai npm package examples |
| [curl/](curl/) | curl command-line examples |
| [streamlit_app.py](streamlit_app.py) | Interactive Streamlit demo with 31+ models |

## Supported Models (31+)

| Group | Models |
|-------|--------|
| **Managed Tiers** | flash, auto, pro, ultra, shared |
| **DeepSeek** | vip-ds-flash, vip-ds-pro |
| **Qwen** | vip-qwen-max, vip-qwen122b |
| **GPT-6 Series** | vip-gpt6-astra, vip-gpt56-terra, vip-gpt56-sol, vip-gpt56-luna |
| **GPT-5 & GPT-4** | vip-gpt5, vip-gpt5-mini, vip-gpt54, vip-gpt4o, vip-gpt4o-mini |
| **Claude** | vip-claude-opus, vip-claude-sonnet, vip-claude-haiku |
| **Gemini** | vip-gemini-pro, vip-gemini-flash |
| **Others** | vip-kimi, vip-kimi-code, vip-mimo, vip-minimax, vip-glm, vip-hy3, vip-grok, vip-llama4 |

## Features

- **One API key** for 31+ models
- **OpenAI-compatible** — use existing SDKs, just change base_url
- **BYOK** — bring your own provider keys via open.ai24x.com
- **PayPal / Card** — no Chinese phone number needed
- **Streaming** — SSE streaming supported
- **Usage tracking** — per-model token and cost breakdown

## Docs

- [AI24X Gateway](https://open.ai24x.com)
- [Pricing](https://www.ai24x.com/pricing.html)
- [BYOK Setup](https://open.ai24x.com)
- [Live Demo](https://ai24x-examples-bj26ncdeqstapzeta63ozr.streamlit.app/)

*Educational purposes only. Not investment advice.*
