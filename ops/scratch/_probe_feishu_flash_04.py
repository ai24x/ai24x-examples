# -*- coding: utf-8 -*-
"""Probe 04: health, flash lane, recent openclaw/core errors."""
import json
import os
import re
import urllib.request
from pathlib import Path

def get(url, timeout=15):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "ignore")
    except Exception as e:
        return None, str(e)

print("=== health 8002 ===")
code, body = get("http://127.0.0.1:8002/health")
print(code, body[:500] if body else body)

print("=== flash lanes ===")
# admin may need key; try public-ish paths
for url in (
    "http://127.0.0.1:8002/v1/models",
):
    c, b = get(url)
    print(url, c, (b or "")[:200])

# warehouse override
ov = Path(r"C:\ai24x01\api\data\model_warehouse_override.json")
print("=== override L1 ===")
print(ov.read_text(encoding="utf-8")[:800])

# openclaw / nssm logs
cands = [
    Path(r"C:\Users\Administrator\.openclaw"),
    Path(r"C:\openclaw"),
    Path(r"C:\ai24x01\ops"),
]
print("=== search openclaw dirs ===")
for d in cands:
    print(d, "exists" if d.exists() else "missing")

# NSSM logs for core
for p in Path(r"C:\ai24x01").rglob("*openclaw*"):
    if p.is_dir() and "node_modules" not in str(p):
        print("dir", p)
        break

# recent ERROR lines in common log locations
log_globs = list(Path(r"C:\ai24x01\ops").glob("*.log"))[-5:]
print("ops logs", [x.name for x in log_globs])

# Try find openclaw gateway log
home = Path(os.path.expanduser("~"))
for pat in ["**/openclaw*.log", "**/gateway*.log", "**/*feishu*.log"]:
    found = list(home.glob(pat))[:8]
    if found:
        print("home", pat, found)

# Check upstream health file if any
for p in [
    Path(r"C:\ai24x01\api\data\upstream_health.json"),
    Path(r"C:\ai24x01\api\data\hero_channel_state.json"),
]:
    if p.exists():
        print("===", p.name, "===")
        print(p.read_text(encoding="utf-8", errors="ignore")[:1200])
