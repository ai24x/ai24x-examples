# -*- coding: utf-8 -*-
import json, os
D = os.path.dirname(os.path.abspath(__file__))
data = json.load(open(os.path.join(D, "..", "数据", "plate_members_20260807.json"), encoding="utf-8"))

def is_a_share(code):
    return (len(code) == 6 and code.isdigit()
            and (code.startswith("60") or code.startswith("68")
                 or code.startswith("00") or code.startswith("30")
                 or code.startswith("002") or code.startswith("301")
                 or code.startswith("688")))

merged = {}
for bk, blob in data.items():
    for m in blob["members"]:
        code = str(m.get("f12", ""))
        name = str(m.get("f14", ""))
        if not is_a_share(code):
            continue
        if "ST" in name.upper() or "退" in name or "*" in name:
            continue
        if code not in merged:
            merged[code] = {"code": code, "name": name, "plates": []}
        merged[code]["plates"].append(bk)
        for k in ["f2","f3","f5","f6","f8","f20","f21","f62","f184"]:
            merged[code][k] = m.get(k)

cands = []
for code, it in merged.items():
    mc = (it.get("f20") or 0) / 1e8
    chg = it.get("f3")
    if not (30 <= mc <= 150):
        continue
    if chg is None or chg < -1 or chg > 7.5:
        continue
    it["mcap"] = round(mc, 1)
    it["chg"] = chg
    cands.append(it)

cands.sort(key=lambda x: (-len(x["plates"]), -x["chg"]))
print("merged A-share:", len(merged), "| candidates(30-150亿, -1~7.5%):", len(cands))
out = os.path.join(D, "..", "数据", "candidates_prescreen_20260807.json")
json.dump(cands, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
for it in cands:
    print(it["code"], it["name"], "mcap=%.0f亿" % it["mcap"], "chg=%+.1f%%" % it["chg"], "plates=" + ",".join(it["plates"]), "main=%s" % it.get("f62"))