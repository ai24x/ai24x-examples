# AI24X

**One API. Every AI. Pay Less.**

AI24X is an AI Gateway that gives you a single OpenAI-compatible endpoint for 29+ models — DeepSeek, Qwen, GLM, Kimi, GPT-5, Claude, MiMo, and more.

## What We Offer

- **AI Gateway** — One API key, one base URL, 29+ models. Switch between providers without changing code.
- **BYOK (Bring Your Own Key)** — Use your existing provider keys through our smart routing layer. Get failover, caching, and usage analytics.
- **Global Payment** — PayPal and international cards accepted. No Chinese phone number needed.

## Quick Start

```python
from openai import OpenAI
client = OpenAI(base_url="https://api.ai24x.com/v1", api_key="sk-...")
response = client.chat.completions.create(model="flash", messages=[{"role": "user", "content": "Hello!"}])
print(response.choices[0].message.content)
```

## Models

| Category | Models |
|----------|--------|
| Frontier | GPT-5, Claude, DeepSeek V4 Pro |
| Value | DeepSeek Flash, Qwen, GLM, Kimi, MiMo |
| Open Source | Qwen, DeepSeek, Yi, MiniMax, Hunyuan |
| Long Context | Kimi (1M tokens), Qwen (1M tokens) |

## Links

- [Gateway Console](https://open.ai24x.com)
- [Pricing](https://www.ai24x.com/pricing.html)
- [BYOK Setup](https://open.ai24x.com)
- [GitHub Examples](https://github.com/ai24x/ai24x-examples)

*Educational purposes only.*
