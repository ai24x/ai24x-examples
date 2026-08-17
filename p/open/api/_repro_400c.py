# -*- coding: utf-8 -*-
import os, httpx
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path("api/.env"))

KEYS = {
    "tokenlab": ("https://api.tokenlab.sh/v1", os.environ.get("TOKENLAB_API_KEY")),
    "requesty": ("https://router.requesty.ai/v1", os.environ.get("REQUESTY_API_KEY")),
}
MODELS = {"tokenlab": "gpt-5.6-luna", "requesty": "openai/gpt-5.6-luna"}
MSGS = [{"role": "user", "content": "list files and then read main.py"}]

def make_tools(strict):
    return [
        {"type": "function", "function": {"name": "list_files", "description": "List files", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}, **({"strict": strict} if strict else {})}},
        {"type": "function", "function": {"name": "read_file", "description": "Read a file", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}, **({"strict": strict} if strict else {})}},
    ]

def call(prov, body):
    base, key = KEYS[prov]
    try:
        with httpx.Client(timeout=25) as c:
            r = c.post(f"{base}/chat/completions", headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, json=body)
        print(f"== {prov} -> {r.status_code}")
        print(r.text[:600].replace("\n", " "))
    except Exception as e:
        print(f"== {prov} EXC {type(e).__name__}: {str(e)[:300]}")

print("#### C1: strict true in tools")
for p in KEYS:
    call(p, {"model": MODELS[p], "messages": MSGS, "tools": make_tools(True), "max_tokens": 100, "stream": False})

print("\n#### C2: tool_choice {type:function,function:{name}}")
for p in KEYS:
    call(p, {"model": MODELS[p], "messages": MSGS, "tools": make_tools(True), "tool_choice": {"type": "function", "function": {"name": "list_files"}}, "max_tokens": 100, "stream": False})

print("\n#### C3: stream true + strict tools")
for p in KEYS:
    call(p, {"model": MODELS[p], "messages": MSGS, "tools": make_tools(True), "max_tokens": 100, "stream": True, "stream_options": {"include_usage": True}})

print("\n#### C4: bare Responses-shape tools (WRONG shape) to confirm 400")
for p in KEYS:
    call(p, {"model": MODELS[p], "messages": MSGS, "tools": [{"type": "function", "name": "list_files", "description": "List files", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}], "max_tokens": 100, "stream": False})
