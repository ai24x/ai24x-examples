# AI24X Examples

Example code for using AI24X Gateway — one OpenAI-compatible key for DeepSeek, Qwen, GLM, Kimi, GPT-5, and Claude.

## Quick Start

```python
from openai import OpenAI
client = OpenAI(base_url="https://api.ai24x.com/v1", api_key="sk-...")
response = client.chat.completions.create(model="flash", messages=[{"role": "user", "content": "Hello!"}])
print(response.choices[0].message.content)
```

## Directory

| Directory | Description |
|-----------|-------------|
| [python/](python/) | OpenAI Python SDK examples |
| [node/](node/) | Node.js / openai npm package examples |
| [curl/](curl/) | curl command-line examples |

## Features

- **One API key** for 29+ models (DeepSeek, Qwen, GLM, Kimi, GPT-5, Claude, MiMo)
- **OpenAI-compatible** — use existing SDKs, just change `base_url`
- **BYOK** — bring your own provider keys via [open.ai24x.com](https://open.ai24x.com)
- **PayPal / Card** — no Chinese phone number needed

## Docs

- [AI24X Gateway](https://open.ai24x.com)
- [Pricing](https://www.ai24x.com/pricing.html)
- [BYOK Setup](https://open.ai24x.com)

*Educational purposes only. Not investment advice.*
