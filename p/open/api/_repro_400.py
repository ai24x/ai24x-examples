# -*- coding: utf-8 -*-
"""Reproduce 400 from gateway-style payload against OR/TokenLab/Requesty."""
import json, httpx, os

KEYS = {
    "openrouter": ("https://openrouter.ai/api/v1", os.environ.get("OPENROUTER_API_KEY") or "sk-or-v1-13e"),
    "tokenlab": ("https://api.tokenlab.sh/v1", os.environ.get("TOKENLAB_API_KEY") or "sk-3Y9mo6XSN"),
    "requesty": ("https://router.requesty.ai/v1", os.environ.get("REQUESTY_API_KEY") or "rqsty-sk-2oE"),
}

MODELS = {
    "openrouter": "openai/gpt-5.6-luna",
    "tokenlab": "gpt-5.6-luna",
    "requesty": "openai/gpt-5.6-luna",
}

def call(prov, body):
    base, key = KEYS[prov]
    url = f"{base}/chat/completions"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    try:
        with httpx.Client(timeout=30) as c:
            r = c.post(url, headers=headers, json=body)
        print(f"== {prov} -> {r.status_code}")
        print(r.text[:1500])
    except Exception as e:
        print(f"== {prov} EXC {type(e).__name__}: {str(e)[:500]}")

TOOLS = [
    {"type": "function", "function": {"name": "list_files", "description": "List files in a directory", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "read_file", "description": "Read a file", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
]
MSG = [{"role": "user", "content": "hi"}]

print("===== T1: simple chat, no tools =====")
for prov in ("openrouter", "tokenlab", "requesty"):
    call(prov, {"model": MODELS[prov], "messages": MSG, "max_tokens": 16, "stream": False})

print("\n===== T2: with tools (chat shape), no tool history =====")
for prov in ("openrouter", "tokenlab", "requesty"):
    call(prov, {"model": MODELS[prov], "messages": MSG, "tools": TOOLS, "max_tokens": 16, "stream": False})

print("\n===== T3: multi-round tool history =====")
msgs = [
    {"role": "user", "content": "list files"},
    {"role": "assistant", "content": None, "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "list_files", "arguments": "{\"path\": \".\"}"}}]},
    {"role": "tool", "content": "main.py", "tool_call_id": "call_1"},
    {"role": "user", "content": "now read it"},
]
for prov in ("openrouter", "tokenlab", "requesty"):
    call(prov, {"model": MODELS[prov], "messages": msgs, "tools": TOOLS, "max_tokens": 16, "stream": False})
