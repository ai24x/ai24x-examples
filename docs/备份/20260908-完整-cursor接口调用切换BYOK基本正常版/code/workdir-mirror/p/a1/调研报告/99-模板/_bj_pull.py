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
    url = "https://push2delay.eastmoney.com/api/qt/clist/get?pn=%d&pz=500&po=1&np=1&fltt=2&invt=2&fid=f3&fs=m:0+t:81+s:2048&fields=%s" % (pn, FIELDS)
    d = get(url)
    if not d or not d.get("data") or not d["data"].get("diff"):
        break
    rows = d["data"]["diff"]
    allrows.extend(rows)
    print("pn", pn, "got", len(rows), "total", len(allrows))
    if len(rows) < 500:
        break
    pn += 1
    time.sleep(2)
print("TOTAL BSE stocks:", len(allrows))
# 过滤 ST/退
clean = [r for r in allrows if "ST" not in str(r.get("f14","")).upper() and "退" not in str(r.get("f14",""))]
print("clean:", len(clean))
# 小市值 + 今日涨幅温和
cands = []
for r in clean:
    mc = (r.get("f20") or 0)/1e8
    chg = r.get("f3")
    if 5 <= mc <= 40 and chg is not None and -2 <= chg <= 8:
        cands.append((r.get("f12"), r.get("f14"), round(mc,1), chg, r.get("f62")))
cands.sort(key=lambda x: x[2])
print("5-40亿候选:", len(cands))
for c in cands:
    print(c)
import os
out = r"E:\AI24X\ai24x-website\ai24x01\p\a1\调研报告\99-模板\_bj_members.json"
json.dump(clean, open(out, "w", encoding="utf-8"), ensure_ascii=False)
print("saved", out)