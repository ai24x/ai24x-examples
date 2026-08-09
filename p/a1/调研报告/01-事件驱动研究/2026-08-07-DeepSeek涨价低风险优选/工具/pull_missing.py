# -*- coding: utf-8 -*-
import json, os, time, urllib.request
BASE = "http://127.0.0.1:18011"
D = os.path.dirname(os.path.abspath(__file__))
tok = open(os.path.join(D, "token.txt"), encoding="utf-8-sig").read().strip()
def secid(code):
    return ("1." if code.startswith(("60","68")) else "0.") + code
def get(url):
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + tok})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))
codes = ["002418","688418","300065","603339","002965","301070","688168","300494"]
out_path = os.path.join(D, "..", "数据", "snap_batch_20260807.json")
snap = json.load(open(out_path, encoding="utf-8"))
for code in codes:
    sid = secid(code)
    for attempt in range(6):
        try:
            s = get(BASE + "/api/quote/snapshot?secid=" + sid)
            print(code, "score=%s cpos=%s risks=%s" % (s.get("score"), s.get("cpos"), ",".join(s.get("risks") or []) or "-"))
            snap[code] = {"secid": sid, "snapshot": s}
            break
        except Exception as e:
            print(code, "retry", attempt, e)
            time.sleep(6 + attempt * 3)
    time.sleep(3)
json.dump(snap, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("total:", len(snap))