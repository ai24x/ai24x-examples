# -*- coding: utf-8 -*-
import json, os, urllib.request
BASE = "http://127.0.0.1:18011"
D = os.path.dirname(os.path.abspath(__file__))
tok = open(os.path.join(D, "token.txt"), encoding="utf-8-sig").read().strip()
def get(url):
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + tok})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))
d = get(BASE + "/api/kline?secid=0.300252&period=day")
dd = d["data"]["sz300252"]
print("keys:", list(dd.keys()))
for k, v in dd.items():
    print(k, type(v), (len(v) if isinstance(v, list) else v))
    if isinstance(v, list) and v:
        print("   first:", v[0])
        print("   last:", v[-1])