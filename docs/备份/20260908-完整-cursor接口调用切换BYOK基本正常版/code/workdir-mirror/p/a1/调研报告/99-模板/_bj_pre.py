# -*- coding: utf-8 -*-
import json, sys
sys.stdout.reconfigure(encoding="utf-8")
rows = json.load(open(r"E:\AI24X\ai24x-website\ai24x01\p\a1\调研报告\99-模板\_bj_all.json", encoding="utf-8"))
def num(v):
    try: return float(v)
    except: return 0.0
mcs = sorted(num(r.get("f20"))/1e8 for r in rows)
print("总数:", len(rows), "中位市值: %.1f亿" % mcs[len(mcs)//2])
print(">100亿:", sum(1 for m in mcs if m>100), "| 40-100亿:", sum(1 for m in mcs if 40<=m<=100), "| 10-40亿:", sum(1 for m in mcs if 10<=m<40), "| <10亿:", sum(1 for m in mcs if m<10))
# 预筛：总市值 5~40亿、非ST、今日涨幅 -2~8%
cands = []
for r in rows:
    name = str(r.get("f14",""))
    mc = num(r.get("f20"))/1e8
    chg = num(r.get("f3"))
    if "ST" in name.upper() or "退" in name: continue
    if not (5 <= mc <= 40): continue
    if chg < -2 or chg > 8: continue
    cands.append({"code": str(r.get("f12")), "name": name, "mcap": round(mc,1), "chg": chg, "main": r.get("f62"), "turnover": r.get("f8")})
cands.sort(key=lambda x: x["mcap"])
print("5-40亿候选:", len(cands))
for c in cands:
    print(c)
json.dump(cands, open(r"E:\AI24X\ai24x-website\ai24x01\p\a1\调研报告\99-模板\_bj_cands.json","w",encoding="utf-8"), ensure_ascii=False, indent=1)