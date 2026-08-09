# -*- coding: utf-8 -*-
import json, sys
sys.stdout.reconfigure(encoding="utf-8")
rows = json.load(open(r"E:\AI24X\ai24x-website\ai24x01\p\a1\调研报告\99-模板\_bj_all.json", encoding="utf-8"))
def num(v):
    try: return float(v)
    except: return 0.0
out = []
for r in rows:
    name = str(r.get("f14",""))
    mc = num(r.get("f20"))/1e8
    chg = num(r.get("f3"))
    amt = num(r.get("f6"))/1e8   # 成交额(亿)
    turn = num(r.get("f8"))       # 换手率
    if "ST" in name.upper() or "退" in name: continue
    if not (8 <= mc <= 40): continue
    if chg < -1 or chg > 7: continue
    if amt < 0.15: continue       # 成交额<1500万 剔除流动性不足
    out.append({"code": str(r.get("f12")), "name": name, "mcap": round(mc,1),
                "chg": chg, "amount": round(amt,2), "turn": turn})
out.sort(key=lambda x: -x["amount"])
print("流动性候选:", len(out))
for c in out:
    print(c["code"], c["name"], "市值%.0f亿" % c["mcap"], "涨%+.1f%%" % c["chg"], "额%.2f亿" % c["amount"], "换手%.1f%%" % c["turn"])
json.dump(out, open(r"E:\AI24X\ai24x-website\ai24x01\p\a1\调研报告\99-模板\_bj_liquid.json","w",encoding="utf-8"), ensure_ascii=False, indent=1)