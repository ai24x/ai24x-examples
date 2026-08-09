# -*- coding: utf-8 -*-
import json, os, sys
sys.stdout.reconfigure(encoding="utf-8")
D = r"E:\AI24X\ai24x-website\ai24x01\p\a1\调研报告\03-个股深度研究\2026-08-07-煤炭潜力龙头调研"
with open(os.path.join(D, "数据", "klines_20260807.json"), "r", encoding="utf-8") as f:
    k = json.load(f)
plates = json.load(open(os.path.join(D, "数据", "plate_members_20260807.json"), encoding="utf-8"))
nm = {}
for bk, blob in plates.items():
    for m in blob["members"]:
        c = str(m.get("f12",""))
        if len(c)==6: nm[c] = m.get("f14")
def analyze(code):
    bars = k[code]["bars"]
    rows = []
    for r in bars:
        rows.append({"date": r[0], "open": float(r[1]), "close": float(r[2]), "high": float(r[3]), "low": float(r[4]), "vol": float(r[5])})
    print("="*72)
    print(nm.get(code, code), code, "bars:", len(rows), "last:", rows[-1]["date"])
    for r in rows[-16:]:
        idx = rows.index(r)
        pct = (r["close"]/rows[idx-1]["close"]-1)*100 if idx>0 else 0
        print('%s O=%6.2f C=%6.2f H=%6.2f L=%6.2f V=%9.0f  %+5.2f%%' % (r["date"], r["open"], r["close"], r["high"], r["low"], r["vol"], pct))
    closes = [r["close"] for r in rows]
    def ma(p): return sum(closes[-p:])/p
    print("MA5=%.2f MA10=%.2f MA20=%.2f MA50=%.2f" % (ma(5), ma(10), ma(20), ma(50)))
    print("5日涨幅: %+.2f%%  10日: %+.2f%%" % ((closes[-1]/closes[-6]-1)*100, (closes[-1]/closes[-11]-1)*100))
    vols = [r["vol"] for r in rows]
    v5 = sum(vols[-5:])/5; v20 = sum(vols[-20:])/20
    print("量5/量20=%.2f" % (v5/v20))
    hi50 = max(r["high"] for r in rows[-50:]); lo50 = min(r["low"] for r in rows[-50:])
    print("50日高=%.2f 50日低=%.2f 位置=%d%%" % (hi50, lo50, (closes[-1]-lo50)/(hi50-lo50)*100))
for code in ["600740","600395","000723","601011","600758","600121","600792","600508","600408"]:
    analyze(code)