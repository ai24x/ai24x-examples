# -*- coding: utf-8 -*-
import json, os, time, urllib.request, sys
sys.stdout.reconfigure(encoding="utf-8")
BASE = "http://127.0.0.1:18011"
tok = open(r"E:\AI24X\ai24x-website\ai24x01\p\a1\调研报告\03-个股深度研究\2026-08-07-煤炭潜力龙头调研\工具\token.txt", encoding="utf-8-sig").read().strip()
def get(url):
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + tok})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode("utf-8"))
sel = json.load(open(r"E:\AI24X\ai24x-website\ai24x01\p\a1\调研报告\99-模板\_bj_sel.json", encoding="utf-8"))
result = {}
for c in sel:
    code = c["code"]
    sid = "1." + code
    for attempt in range(4):
        try:
            snap = get(BASE + "/api/quote/snapshot?secid=" + sid)
            score = snap.get("score"); cpos = snap.get("cpos"); risks = snap.get("risks") or []
            print(code, c["name"], "score=%s cpos=%s risks=%s" % (score, cpos, ",".join(risks) if risks else "-"))
            result[code] = {"secid": sid, "name": c["name"], "mcap": c["mcap"], "snapshot": snap}
            break
        except Exception as e:
            print(code, "retry", attempt, e)
            time.sleep(3.5)
    time.sleep(1.0)
out = r"E:\AI24X\ai24x-website\ai24x01\p\a1\调研报告\99-模板\_bj_snap.json"
json.dump(result, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("saved", len(result))