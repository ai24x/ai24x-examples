# -*- coding: utf-8 -*-
import os, sys, json, time
sys.path.insert(0, os.path.abspath("api"))
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path("api/.env"))
from model_warehouse import resolve_vip_pick
import model_router as mr

TOOLS = [
    {"type": "function", "function": {"name": "list_files", "description": "List files in a directory", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "read_file", "description": "Read a file", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
]
MSGS = [
    {"role": "system", "content": "You are the AI24X assistant. You are a helpful coding agent."},
    {"role": "user", "content": "list files and then read main.py"},
    {"role": "assistant", "content": None, "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "list_files", "arguments": "{\"path\":\".\"}"}}]},
    {"role": "tool", "content": "main.py\nutils.py", "tool_call_id": "call_1"},
    {"role": "user", "content": "now read main.py"},
]

print("mode:", mr._upstream_mode())
pick = resolve_vip_pick("vip-gpt56-luna")
print("pick id:", pick and pick.get("id"), "channels:", pick and pick.get("channels"))
chain = mr._vip_aggregator_chain(pick, "openai/gpt-5.6-luna")
print("chain:", [(c.get("provider"), c.get("model")) for c in chain])

t0 = time.time()
try:
    n = 0
    for ev in mr._run_vip_pick_chat_stream(
        pick=pick, prompt="list files", temperature=0.7, max_tokens=200,
        messages=MSGS, tools=TOOLS, tool_choice=None,
    ):
        n += 1
        s = json.dumps(ev, ensure_ascii=False)
        print(f"[{time.time()-t0:6.1f}s] ev#{n}", s[:600])
        if n > 14:
            print("... cap ...")
            break
    print("total events:", n)
except Exception as e:
    print("EXC:", type(e).__name__, str(e)[:800])
