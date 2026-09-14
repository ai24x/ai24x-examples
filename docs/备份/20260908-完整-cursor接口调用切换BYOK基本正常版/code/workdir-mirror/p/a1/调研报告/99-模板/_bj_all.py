# -*- coding: utf-8 -*-
import json, urllib.request, time, sys
sys.stdout.reconfigure(encoding="utf-8")
def get(url, tries=6):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0","Referer":"https://quote.eastmoney.com/"})
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            print("  retry", i, e); time.sleep(4+i*2)
    return None
FIELDS = "f12,f14,f2,f3,f4,f5,f6,f8,f20,f21,f62,f184"
allrows = []
pn = 1
while True:
    url = "https://push2delay.eastmoney.com/api/qt/clist/get?pn=%d&pz=100&po=1&np=1&fltt=2&invt=2&fid=f12&fs=m:0+t:81+s:2048&fields=%s" % (pn, FIELDS)
    d = get(url)
    if not d or not d.get("data") or not d["data"].get("diff"):
        print("end at pn", pn)
        break
    rows = d["data"]["diff"]
    allrows.extend(rows)
    print("pn", pn, "got", len(rows), "total", len(allrows))
    if len(rows) < 100:
        break
    pn += 1
    time.sleep(1.5)
print("TOTAL:", len(allrows))
import os
out = r"E:\AI24X\ai24x-website\ai24x01\p\a1\调研报告\99-模板\_bj_all.json"
json.dump(allrows, open(out, "w", encoding="utf-8"), ensure_ascii=False)
# 统计市值分布
mcs = sorted([(r.get("f20") or 0)/1e8 for r in allrows])
print("中位数市值(亿):", mcs[len(mcs)//2] if mcs else 0)
print(">100亿:", sum(1 for m in mcs if m>100), " 40-100亿:", sum(1 for m in mcs if 40<=m<=100), " 10-40亿:", sum(1 for m in mcs if 10<=m<40), " <10亿:", sum(1 for m in mcs if m<10))