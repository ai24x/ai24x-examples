# -*- coding: utf-8 -*-
"""烟测：/v1/chat/completions tools ↔ tool_calls ↔ role=tool 闭环。

用法（api 目录、已起 core）：
  python scripts_tools_smoke.py
  python scripts_tools_smoke.py --base http://127.0.0.1:8000 --model flash
  python scripts_tools_smoke.py --model pro
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

import httpx

from database import SessionLocal
from token_mvp_service import create_api_key

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_time",
            "description": "Return the current local time as ISO string.",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    }
]


def _msg_tool_calls(j: dict) -> list:
    ch = (j.get("choices") or [{}])[0]
    return (ch.get("message") or {}).get("tool_calls") or []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    ap.add_argument("--auth-user-id", type=int, default=27)
    ap.add_argument("--model", default="flash")
    ap.add_argument("--stream", action="store_true")
    args = ap.parse_args()
    base = args.base.rstrip("/")
    model = args.model

    db = SessionLocal()
    try:
        created = create_api_key(db, args.auth_user_id, name="tools-smoke")
        api_key = created["api_key"]
    finally:
        db.close()

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    rows = []

    with httpx.Client(timeout=180.0) as client:
        # A) 无 tools 短聊回归
        r0 = client.post(
            f"{base}/v1/chat/completions",
            headers=headers,
            json={
                "model": model,
                "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
                "stream": False,
                "max_tokens": 32,
            },
        )
        j0 = r0.json() if r0.headers.get("content-type", "").startswith("application/json") else {}
        content0 = ((j0.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        rows.append(
            {
                "name": "no_tools_chat",
                "ok": r0.status_code == 200 and bool(content0),
                "status": r0.status_code,
                "preview": str(content0)[:60],
            }
        )

        # B) 带 tools → 期望 tool_calls
        body1 = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": "Call the get_time tool now. Do not answer in plain text first.",
                }
            ],
            "tools": TOOLS,
            "tool_choice": "required",
            "stream": False,
            "max_tokens": 256,
        }
        r1 = client.post(f"{base}/v1/chat/completions", headers=headers, json=body1)
        try:
            j1 = r1.json()
        except Exception:
            j1 = {}
        tcs = _msg_tool_calls(j1)
        fr = ((j1.get("choices") or [{}])[0]).get("finish_reason")
        rows.append(
            {
                "name": "tools_round1_tool_calls",
                "ok": r1.status_code == 200 and bool(tcs),
                "status": r1.status_code,
                "finish_reason": fr,
                "tool_names": [
                    (t.get("function") or {}).get("name") for t in tcs if isinstance(t, dict)
                ],
                "n_tool_calls": len(tcs),
            }
        )

        # C) 第二轮 role=tool
        if tcs:
            tc0 = tcs[0]
            tid = str(tc0.get("id") or "call_smoke")
            body2 = {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": "Call the get_time tool now. Do not answer in plain text first.",
                    },
                    {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": tcs,
                    },
                    {
                        "role": "tool",
                        "tool_call_id": tid,
                        "content": "2026-08-02T23:50:00+08:00",
                    },
                ],
                "tools": TOOLS,
                "tool_choice": "auto",
                "stream": False,
                "max_tokens": 256,
            }
            r2 = client.post(f"{base}/v1/chat/completions", headers=headers, json=body2)
            try:
                j2 = r2.json()
            except Exception:
                j2 = {}
            content2 = ((j2.get("choices") or [{}])[0].get("message") or {}).get(
                "content"
            ) or ""
            rows.append(
                {
                    "name": "tools_round2_role_tool",
                    "ok": r2.status_code == 200 and bool(content2 or _msg_tool_calls(j2)),
                    "status": r2.status_code,
                    "preview": str(content2)[:80],
                }
            )
        else:
            rows.append(
                {
                    "name": "tools_round2_role_tool",
                    "ok": False,
                    "status": None,
                    "skip": "no tool_calls from round1",
                }
            )

        # D) 可选流式：是否出现 tool_calls 增量
        if args.stream:
            saw_tc = False
            with client.stream(
                "POST",
                f"{base}/v1/chat/completions",
                headers=headers,
                json={
                    "model": model,
                    "messages": [
                        {
                            "role": "user",
                            "content": "Call get_time tool now.",
                        }
                    ],
                    "tools": TOOLS,
                    "tool_choice": "required",
                    "stream": True,
                    "max_tokens": 256,
                },
            ) as rs:
                for line in rs.iter_lines():
                    if not line or not str(line).startswith("data:"):
                        continue
                    data = str(line)[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        obj = json.loads(data)
                    except Exception:
                        continue
                    delta = ((obj.get("choices") or [{}])[0].get("delta") or {})
                    if delta.get("tool_calls"):
                        saw_tc = True
                        break
            rows.append(
                {
                    "name": "tools_stream_tool_calls",
                    "ok": saw_tc,
                    "status": rs.status_code,
                }
            )

    print(json.dumps({"model": model, "rows": rows}, ensure_ascii=False, indent=2))
    return 0 if all(r.get("ok") for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
