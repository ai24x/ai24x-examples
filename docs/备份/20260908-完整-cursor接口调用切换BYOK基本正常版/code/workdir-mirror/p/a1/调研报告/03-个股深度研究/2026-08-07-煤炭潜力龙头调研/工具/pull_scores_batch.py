# -*- coding: utf-8 -*-
import json, os, time, urllib.request, sys
sys.stdout.reconfigure(encoding="utf-8")
BASE = "http://127.0.0.1:18011"
D = r"E:\AI24X\ai24x-website\ai24x01\p\a1\调研报告\03-个股深度研究\2026-08-07-煤炭潜力龙头调研"
tok = open(os.path.join(D, "工具", "token.txt"), encoding="utf-8-sig").read().strip()
def secid(code):
    if code.startswith(("60", "68", "90", "920", "510", "588")):
        return "1." + code
    return "0." + code
def get(url):
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + tok})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode("utf-8"))
codes = ["600408","600792","600758","601011","600121","000571","601015","600508",
         "600997","600740","600971","600123","600395","000552","600403","000723",
         "601101","000937"]
result = {}
for code in codes:
    sid = secid(code)
    for attempt in range(4):
        try:
            snap = get(BASE + "/api/quote/snapshot?secid=" + sid)
            score = snap.get("score")
            cpos = snap.get("cpos")
            risks = snap.get("risks") or []
            print(code, "score=%s cpos=%s risks=%s" % (score, cpos, ",".join(risks) if risks else "-"))
            result[code] = {"secid": sid, "snapshot": snap}
            break
        except Exception as e:
            print(code, "retry", attempt, e)
            time.sleep(3)
    time.sleep(1.3)
out = os.path.join(D, "数据", "snap_batch_20260807.json")
json.dump(result, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("saved:", out, "| count:", len(result))