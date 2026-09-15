#!/usr/bin/env python3
"""Vision example using GPT-5."""
from openai import OpenAI

client = OpenAI(base_url="https://api.ai24x.com/v1", api_key="sk-your-key")

response = client.chat.completions.create(
    model="vip-gpt5",
    messages=[{
        "role": "user",
        "content": [
            {"type": "text", "text": "Describe what you see in this image."},
            {"type": "image_url", "image_url": {"url": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/47/PNG_transparency_demonstration_1.png/300px-PNG_transparency_demonstration_1.png"}}
        ]
    }],
    max_tokens=300
)
print(response.choices[0].message.content)
