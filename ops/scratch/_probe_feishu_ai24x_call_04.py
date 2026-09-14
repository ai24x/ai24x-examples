# -*- coding: utf-8 -*-
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

am = json.loads(
    Path(r"C:\Users\Administrator\.openclaw\agents\main\agent\models.json").read_text(
        encoding="utf-8"
    )
)
cfg = json.loads(Path(r"C:\Users\Administrator\.openclaw\openclaw.json").read_text(encoding="utf-8"))
key_root = (((cfg.get("models") or {}).get("providers") or {}).get("ai24x") or {}).get("apiKey") or ""
key = (((am.get("providers") or {}).get("ai24x") or {}).get("apiKey") or key_root).strip()
base = "https://api.ai24x.com/v1"
print("using_agent_models_key=", bool((((am.get("providers") or {}).get("ai24x") or {}).get("apiKey"))))
print("keys_differ=", bool(key_root and key and key_root != key))
print("key_prefix=", key[:14] + "...")

headers = {"Authorization": "Bearer " + key, "Content-Type": "application/json"}


def call(path, payload=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        base + path,
        data=data,
        headers=headers,
        method="GET" if payload is None else "POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        return None, repr(e)


c, b = call("/billing/balance")
print("balance", c, b[:700])

c, b = call(
    "/chat/completions",
    {
        "model": "flash",
        "messages": [{"role": "user", "content": "ping reply ok"}],
        "max_tokens": 16,
    },
)
print("flash16", c, b[:900])

c, b = call(
    "/chat/completions",
    {
        "model": "flash",
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 8192,
    },
)
print("flash8k", c, b[:900])

# openclaw recent log files (no recursive home)
log_dir = Path(r"C:\Users\Administrator\.openclaw\logs")
if log_dir.exists():
    files = [p for p in log_dir.iterdir() if p.is_file()]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    print("log_files", [p.name for p in files[:10]])
    for f in files[:3]:
        text = f.read_text(encoding="utf-8", errors="replace")
        hits = [
            ln
            for ln in text.splitlines()
            if any(
                x in ln.lower()
                for x in (
                    "429",
                    "rate-limited",
                    "rate_limit",
                    "insufficient",
                    "ai24x",
                    "billing",
                    "cooldown",
                    "all models",
                )
            )
        ]
        print("file", f.name, "hits", len(hits))
        for ln in hits[-12:]:
            print(ln.replace(key, "sk-***")[:280])
