#!/usr/bin/env python3
"""Test multiple models on the same prompt for comparison."""

from openai import OpenAI
import time

client = OpenAI(
    base_url="https://api.ai24x.com/v1",
    api_key="sk-your-key-here"
)

prompt = "Explain what an AI gateway is in two sentences."

models = [
    ("flash", "Fast everyday tier"),
    ("pro", "High-value tier"),
    ("vip-gpt5", "GPT-5"),
    ("vip-claude-sonnet", "Claude Sonnet"),
    ("vip-gemini-flash", "Gemini Flash"),
    ("vip-ds-flash", "DeepSeek Flash"),
    ("vip-qwen-max", "Qwen Max"),
]

print(f"Prompt: {prompt}\n")
print(f"{'Model':<25} {'Type':<20} {'Time':<8} {'Response'}")
print("-" * 80)

for model_id, label in models:
    start = time.time()
    try:
        response = client.chat.completions.create(
            model=model_id,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150
        )
        elapsed = time.time() - start
        text = response.choices[0].message.content[:60].replace("\n", " ")
        print(f"{model_id:<25} {label:<20} {elapsed:<8.2f}s {text}...")
    except Exception as e:
        print(f"{model_id:<25} {label:<20} {'ERROR':<8} {str(e)[:50]}")