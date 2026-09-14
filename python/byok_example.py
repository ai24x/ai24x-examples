#!/usr/bin/env python3
"""BYOK (Bring Your Own Key) example using AI24X Gateway."""

from openai import OpenAI

# Step 1: Add your provider key on https://open.ai24x.com
# Step 2: Use the gateway with BYOK routing enabled
client = OpenAI(
    base_url="https://api.ai24x.com/v1",
    api_key="sk-your-gateway-key"
)

# The gateway routes to your provider key automatically
response = client.chat.completions.create(
    model="vip-claude-opus",  # Your own Claude key will be used
    messages=[{"role": "user", "content": "What models can I access with BYOK?"}],
    max_tokens=200
)
print(response.choices[0].message.content)