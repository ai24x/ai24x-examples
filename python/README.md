# Python Examples: AI24X Gateway API

Example code for using [AI24X Gateway](https://www.ai24x.com) with the OpenAI Python SDK.

## Quick Start

```bash
pip install openai
```

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://api.ai24x.com/v1",
    api_key="sk-your-key"  # Replace with your AI24X API key
)

# flash = best value for general tasks
response = client.chat.completions.create(
    model="flash",
    messages=[{"role": "user", "content": "What is an AI gateway?"}]
)

print(response.choices[0].message.content)
```

## Supported Models (35+)

All models are accessible via the same endpoint — just change the `model` parameter.

| Model Name | Description |
|-----------|-------------|
| `flash` | Best value for general tasks (recommended default) |
| `auto` | Auto-selects optimal model for your prompt |
| `pro` | Stronger reasoning for complex tasks |
| `ultra` | Maximum capability for hardest problems |
| `shared` | Shared pool for cost-sensitive workloads |
| `vip-gpt5` | GPT-5 — hardest tasks, best reasoning |
| `vip-gpt5-mini` | GPT-5 Mini — fast, cost-effective |
| `vip-gpt6-astra` | GPT-6 Astra — latest generation |
| `vip-gpt56-terra` | GPT-5.6 Terra |
| `vip-gpt56-sol` | GPT-5.6 Sol |
| `vip-gpt56-luna` | GPT-5.6 Luna |
| `vip-claude-opus` | Claude Opus |
| `vip-claude-opus-4` | Claude Opus 4 |
| `vip-claude-sonnet` | Claude Sonnet |
| `vip-claude-haiku` | Claude Haiku |
| `vip-ds-flash` | DeepSeek Flash |
| `vip-ds-pro` | DeepSeek Pro |
| `vip-ds-v3` | DeepSeek V3 |
| `vip-qwen-max` | Qwen Max |
| `vip-qwen3` | Qwen 3 |
| `vip-gemini-2.5-pro` | Gemini 2.5 Pro |
| `vip-gemini-2.5-flash` | Gemini 2.5 Flash |
| `vip-kimi` | Kimi |
| `vip-kimi-code` | Kimi Code |
| `vip-mimo` | MiMo |
| `vip-mimo-pro` | MiMo Pro |
| `vip-minimax` | MiniMax |
| `vip-glm` | GLM |
| `vip-grok` | Grok |
| `vip-llama4` | Llama 4 |
| `vip-mistral` | Mistral |
| `vip-hy3` | Hy3 |

## Files

| File | Description |
|------|-------------|
| `chat_completion.py` | Basic chat with multiple models |
| `streaming_example.py` | SSE streaming response |
| `multi_model_test.py` | Compare responses across models |
| `tool_calling_example.py` | Function calling / tools |
| `vision_example.py` | Image analysis with vision models |
| `byok_example.py` | Bring Your Own Key example |
| `price_compare.py` | Compare model pricing |

## Streaming

```python
stream = client.chat.completions.create(
    model="flash",
    messages=[{"role": "user", "content": "Write a haiku about APIs."}],
    stream=True
)

for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
```

## List Available Models

```python
models = client.models.list()
for m in models:
    print(m.id)
```

## BYOK (Bring Your Own Key)

```python
client = OpenAI(
    base_url="https://open.ai24x.com/v1",
    api_key="sk-byok-..."  # Your own provider key via AI24X BYOK
)
```

See full docs at [open.ai24x.com](https://open.ai24x.com)