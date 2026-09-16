#!/usr/bin/env python3
"""Basic chat completion using AI24X Gateway."""

from openai import OpenAI

client = OpenAI(
    base_url="https://api.ai24x.com/v1",
    api_key="sk-your-key-here"  # Replace with your key
)

# Try different models (flash = best value for general tasks)
models = ["flash", "auto", "pro", "vip-gpt5", "vip-claude-opus-4"]

for model in models:
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "What is the capital of France? Answer in one sentence."}],
        max_tokens=100
    )
    print(f"[{model}] {response.choices[0].message.content}")
    print(f"  Tokens: {response.usage.prompt_tokens} in -> {response.usage.completion_tokens} out")
    print()