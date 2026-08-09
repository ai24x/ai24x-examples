# -*- coding: utf-8 -*-
import json, os, sys
sys.stdout.reconfigure(encoding="utf-8")
D = r"E:\AI24X\ai24x-website\ai24x01\p\a1\调研报告\03-个股深度研究\2026-08-07-煤炭潜力龙头调研"
with open(os.path.join(D, "数据", "klines_20260807.json"), "r", encoding="utf-8") as f:
    k = json.load(f)
def analyze(code):
    bars = k[code]["bars"]
    rows = [{"date": r[0], "open": float(r[1]), "close": float(r[2]), "high": float(r[3]), "low": float(r[4]), "vol": float(r[5])} for r in bars]
    print("="*72)
    print(code, "last:", rows[-1]["date"])
    for i, r in enumerate(rows[-10:], start=len(rows)-10):
        pct = (r["close"]/rows[i-1]["close"]-1)*100 if i>0 else 0
        print('%s O=%6.2f C=%6.2f H=%6.2f L=%6.2f V=%9.0f  %+5.2f%%' % (r["date"], r["open"], r["close"], r["high"], r["low"], r["vol"], pct))
    closes = [r["close"] for r in rows]
    print("5日: %+.2f%%  10日: %+.2f%%" % ((closes[-1]/closes[-6]-1)*100, (closes[-1]/closes[-11]-1)*100))
for code in ["600758","601011"]:
    analyze(code)