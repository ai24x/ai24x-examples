# -*- coding: utf-8 -*-
import json, os, time, urllib.request
BASE = "http://127.0.0.1:18011"
D = os.path.dirname(os.path.abspath(__file__))
tok = open(os.path.join(D, "token.txt"), encoding="utf-8-sig").read().strip()

def secid(code):
    if code.startswith(("60", "68", "90", "920", "510", "588")):
        return "1." + code
    return "0." + code

def get(url):
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + tok})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))

codes = [
    # 算力租赁/云厂商（最直接受益）
    "688158","300846","688316","603881","300738","002335","600602","600797",
    "000815","300383","300442","300017","301085","002197","300603","300895",
    "688227","603110","603220","002313","300541","002418","688418","300065",
    # 液冷/温控/电源（次直接受益）
    "603912","301202","300499","300990","300684","300731","301157","002272",
    "301516","002733","603339","002965","002993","603380","301248","002642",
    "002881","300768","688023","002657","002123","300324","301070","688168",
    "300494","002902","300252","301018",
]
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
            time.sleep(2.5)
    time.sleep(1.2)

out = os.path.join(D, "..", "数据", "snap_batch_20260807.json")
json.dump(result, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("saved:", out, "| count:", len(result))