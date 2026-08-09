# -*- coding: utf-8 -*-
import json, os, time, urllib.request, sys
sys.stdout.reconfigure(encoding="utf-8")
BASE = "http://127.0.0.1:18011"
tok = open(r"E:\AI24X\ai24x-website\ai24x01\p\a1\调研报告\03-个股深度研究\2026-08-07-煤炭潜力龙头调研\工具\token.txt", encoding="utf-8-sig").read().strip()
def get(url):
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + tok})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode("utf-8"))
codes = ["920199","920284","920932","920169","920098","920592"]
res = {}
for code in codes:
    for attempt in range(5):
        try:
            d = get(BASE + "/api/kline?secid=1." + code + "&period=day")
            arr = d["data"]["bj" + code]["qfqday"]
            print(code, "bars:", len(arr), "last:", arr[-1][0])
            res[code] = {"secid": "1." + code, "bars": arr}
            break
        except Exception as e:
            print(code, "retry", attempt, e)
            time.sleep(4)
    time.sleep(2.5)
json.dump(res, open(r"E:\AI24X\ai24x-website\ai24x01\p\a1\调研报告\99-模板\_bj_klines.json","w",encoding="utf-8"), ensure_ascii=False)
print("saved")