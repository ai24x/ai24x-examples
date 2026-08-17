# -*- coding: utf-8 -*-
import os, sys, json, time
sys.path.insert(0, os.path.abspath("api"))
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path("api/.env"))
from model_warehouse import resolve_vip_pick
import model_router as mr

# Codex 风格：strict=true 且 parameters 缺 additionalProperties（此前 Requesty/OR 必 400）
TOOLS = [
    {"type": "function", "function": {"name": "list_files", "description": "List files", "strict": True,
     "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Directory path"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "read_file", "description": "Read a file", "strict": True,
     "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "File path"}}, "required": ["path"]}}},
]
MSGS = [
    {"role": "system", "content": "You are the AI24X assistant. You are a helpful coding agent."},
    {"role": "user", "content": "list files and then read main.py"},
    {"role": "assistant", "content": None, "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "list_files", "arguments": "{\"path\":\".\"}"}}]},
    {"role": "tool", "content": "main.py\nutils.py", "tool_call_id": "call_1"},
    {"role": "user", "content": "now read main.py"},
]

pick = resolve_vip_pick("vip-gpt56-luna")
chain = mr._vip_aggregator_chain(pick, "openai/gpt-5.6-luna")
print("chain:", [(c.get("provider"), c.get("model")) for c in chain])
t0 = time.time()
n = 0
last = None
for ev in mr._run_vip_pick_chat_stream(
    pick=pick, prompt="list files", temperature=0.7, max_tokens=200,
    messages=MSGS, tools=TOOLS, tool_choice=None,
):
    n += 1
    last = ev
    if n <= 3:
        print(f"[{time.time()-t0:5.1f}s] ev#{n}", json.dumps(ev, ensure_ascii=False)[:260])
print("events:", n, "| last type:", last and last.get("type"), "| provider:", last and last.get("provider"))
if last and last.get("type") == "error":
    print("ERROR:", json.dumps(last, ensure_ascii=False)[:400])
else:
    tc = last and last.get("tool_calls")
    print("tool_calls:", json.dumps(tc, ensure_ascii=False)[:300] if tc else None)
