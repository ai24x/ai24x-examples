# -*- coding: utf-8 -*-
import json, os, urllib.request

BASE = "http://127.0.0.1:18011"
tok_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "token.txt")
tok = open(tok_path, encoding="utf-8-sig").read().strip()
out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "数据", "score_20260806.json")

codes = [
    ("1.603629", "利通电子", "603629"),
    ("1.688158", "优刻得", "688158"),
    ("0.301396", "宏景科技", "301396"),
]

def get(url):
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + tok})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))

result = {}
for secid, name, code in codes:
    snap = get(f"{BASE}/api/quote/snapshot?secid={secid}")
    sig = None
    try:
        sig = get(f"{BASE}/api/signals?secid={secid}&period=day")
    except Exception as e:
        sig = {"error": str(e)}
    result[code] = {"name": name, "secid": secid, "snapshot": snap, "signals": sig}
    print(name, code, "score=", snap.get("score"))

with open(out_path, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print("saved:", out_path)
