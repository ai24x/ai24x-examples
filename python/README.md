# Python Example: AI24X Gateway API

Example code for using AI24X Gateway with the OpenAI Python SDK.

## Prerequisites

```bash
pip install openai
```

## Chat Completion

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://api.ai24x.com/v1",
    api_key="sk-..."  # Replace with your AI24X API key
)

# DeepSeek Flash — best value for general tasks
response = client.chat.completions.create(
    model="flash",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Explain what an AI gateway is in one sentence."}
    ]
)

print(response.choices[0].message.content)
```

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

## Switch Models

```python
# DeepSeek Pro — stronger reasoning
client.chat.completions.create(model="pro", messages=[...])

# GPT-5 — hardest tasks
client.chat.completions.create(model="gpt-5", messages=[...])

# Qwen — long context (1M tokens)
client.chat.completions.create(model="qwen", messages=[...])
```

## BYOK (Bring Your Own Key)

```python
client = OpenAI(
    base_url="https://open.ai24x.com/v1",
    api_key="sk-byok-..."  # Your own provider key via AI24X BYOK
)
```

See full docs at [open.ai24x.com](https://open.ai24x.com)
