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
codes = ["300252","002657","301085","300603","300608","300895","002733","301157"]
out = os.path.join(D, "..", "数据", "klines_20260807.json")
res = {}
for code in codes:
    sid = secid(code)
    market = "sh" if code.startswith(("60","68")) else "sz"
    for attempt in range(5):
        try:
            d = get(BASE + "/api/kline?secid=" + sid + "&period=day")
            arr = d["data"][market + code]["qfqday"]
            print(code, "bars:", len(arr), "last:", arr[-1])
            res[code] = {"secid": sid, "bars": arr}
            break
        except Exception as e:
            print(code, "retry", attempt, e)
            time.sleep(4)
    time.sleep(2)
json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("saved")