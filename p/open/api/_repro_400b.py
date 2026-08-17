# -*- coding: utf-8 -*-
import json, httpx, os

KEYS = {
    "tokenlab": ("https://api.tokenlab.sh/v1", os.environ.get("TOKENLAB_API_KEY")),
    "requesty": ("https://router.requesty.ai/v1", os.environ.get("REQUESTY_API_KEY")),
}
MODELS = {"tokenlab": "gpt-5.6-luna", "requesty": "openai/gpt-5.6-luna"}

TOOLS = [
    {"type": "function", "function": {"name": "list_files", "description": "List files in a directory", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Directory path"}}, "required": ["path"]}, "strict": True}},
    {"type": "function", "function": {"name": "read_file", "description": "Read a file", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "File path"}}, "required": ["path"]}, "strict": True}},
]
MSGS = [
    {"role": "system", "content": "You are the AI24X assistant. You are a helpful coding agent. You operate a shell and filesystem."},
    {"role": "user", "content": "list files and then read main.py"},
    {"role": "assistant", "content": None, "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "list_files", "arguments": "{\"path\":\".\"}"}}]},
    {"role": "tool", "content": "main.py\nutils.py", "tool_call_id": "call_1"},
    {"role": "user", "content": "now read main.py"},
    {"role": "assistant", "content": None, "tool_calls": [{"id": "call_2", "type": "function", "function": {"name": "read_file", "arguments": "{\"path\":\"main.py\"}"}}]},
    {"role": "tool", "content": "print('hi')", "tool_call_id": "call_2"},
    {"role": "user", "content": "summarize"},
]

def call(prov, body):
    base, key = KEYS[prov]
    url = f"{base}/chat/completions"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    try:
        with httpx.Client(timeout=60) as c:
            r = c.post(url, headers=headers, json=body)
        print(f"== {prov} -> {r.status_code}")
        print(r.text[:2000])
    except Exception as e:
        print(f"== {prov} EXC {type(e).__name__}: {str(e)[:600]}")

print("===== S1: stream=True + stream_options =====")
for prov in KEYS:
    call(prov, {"model": MODELS[prov], "messages": MSGS, "temperature": 0.7, "max_tokens": 512, "tools": TOOLS, "stream": True, "stream_options": {"include_usage": True}})

print("\n===== S2: stream=True, NO stream_options =====")
for prov in KEYS:
    call(prov, {"model": MODELS[prov], "messages": MSGS, "temperature": 0.7, "max_tokens": 512, "tools": TOOLS, "stream": True})

print("\n===== S3: no tools, stream=True + stream_options =====")
for prov in KEYS:
    call(prov, {"model": MODELS[prov], "messages": MSGS, "temperature": 0.7, "max_tokens": 512, "stream": True, "stream_options": {"include_usage": True}})
