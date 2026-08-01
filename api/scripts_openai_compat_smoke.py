# -*- coding: utf-8 -*-
"""本机验收：/v1/chat/completions 非流式 + 流式 + /v1/chat/run 回归。

用法（api 目录、已起服务）：
  python scripts_openai_compat_smoke.py
  python scripts_openai_compat_smoke.py --base http://127.0.0.1:8000
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    ap.add_argument("--auth-user-id", type=int, default=27)
    args = ap.parse_args()
    base = args.base.rstrip("/")

    db = SessionLocal()
    try:
        created = create_api_key(db, args.auth_user_id, name="openai-compat-smoke")
        api_key = created["api_key"]
    finally:
        db.close()

    rows = []
    with httpx.Client(timeout=120.0) as client:
        # 1) 非流式 completions
        r = client.post(
            f"{base}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "flash",
                "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
                "stream": False,
                "max_tokens": 64,
            },
        )
        try:
            j = r.json()
        except Exception:
            j = {}
        ok = (
            r.status_code == 200
            and j.get("object") == "chat.completion"
            and (j.get("choices") or [{}])[0].get("message", {}).get("content")
        )
        rows.append(
            {
                "name": "completions_non_stream",
                "ok": bool(ok),
                "status": r.status_code,
                "model": j.get("model"),
                "usage": j.get("usage"),
                "preview": ((j.get("choices") or [{}])[0].get("message") or {}).get("content", "")[:80],
            }
        )

        # 2) 流式 SSE
        with client.stream(
            "POST",
            f"{base}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "flash",
                "messages": [{"role": "user", "content": "Say hi"}],
                "stream": True,
                "max_tokens": 64,
            },
        ) as rs:
            text = "".join(rs.iter_text())
            ok2 = rs.status_code == 200 and "data: [DONE]" in text and "chat.completion.chunk" in text
            rows.append(
                {
                    "name": "completions_stream",
                    "ok": bool(ok2),
                    "status": rs.status_code,
                    "has_done": "data: [DONE]" in text,
                    "preview": text[:160].replace("\n", "\\n"),
                }
            )

        # 3) chat/run 回归
        r3 = client.post(
            f"{base}/v1/chat/run",
            headers={"X-API-Key": api_key, "Content-Type": "application/json"},
            json={"prompt": "Reply with exactly: RUN_OK", "model": "flash", "max_tokens": 64},
        )
        try:
            j3 = r3.json()
        except Exception:
            j3 = {}
        ok3 = r3.status_code == 200 and bool(j3.get("response"))
        rows.append(
            {
                "name": "chat_run_regression",
                "ok": bool(ok3),
                "status": r3.status_code,
                "model": j3.get("model"),
                "preview": (j3.get("response") or "")[:80],
            }
        )

        # 4) 无效 key → OpenAI error 形
        r4 = client.post(
            f"{base}/v1/chat/completions",
            headers={"Authorization": "Bearer sk-invalid-smoke", "Content-Type": "application/json"},
            json={"model": "flash", "messages": [{"role": "user", "content": "x"}]},
        )
        try:
            j4 = r4.json()
        except Exception:
            j4 = {}
        ok4 = r4.status_code == 401 and isinstance(j4.get("error"), dict)
        rows.append(
            {
                "name": "invalid_key_openai_error",
                "ok": bool(ok4),
                "status": r4.status_code,
                "error": j4.get("error"),
            }
        )

    passed = sum(1 for x in rows if x.get("ok"))
    failed = len(rows) - passed
    print(json.dumps({"passed": passed, "failed": failed, "rows": rows}, ensure_ascii=False, indent=2))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
