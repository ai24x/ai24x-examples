#!/usr/bin/env python3
"""Streaming chat completion example."""
from openai import OpenAI

client = OpenAI(base_url="https://api.ai24x.com/v1", api_key="sk-your-key")

stream = client.chat.completions.create(
    model="flash",
    messages=[{"role": "user", "content": "Count from 1 to 10, one per line."}],
    stream=True, max_tokens=200
)
for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
print()
