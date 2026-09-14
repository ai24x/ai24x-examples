# -*- coding: utf-8 -*-
import json, sys
sys.stdout.reconfigure(encoding="utf-8")
k = json.load(open(r"E:\AI24X\ai24x-website\ai24x01\p\a1\调研报告\99-模板\_bj_klines.json", encoding="utf-8"))
names = {"920199":"倍益康","920284":"灵鸽科技","920932":"科达自控","920169":"七丰精工","920098":"科隆新材","920592":"华信永道"}
def analyze(code):
    bars = k[code]["bars"]
    rows = [{"date": r[0], "open": float(r[1]), "close": float(r[2]), "high": float(r[3]), "low": float(r[4]), "vol": float(r[5])} for r in bars]
    print("="*72)
    print(names.get(code, code), code, "bars:", len(rows), "last:", rows[-1]["date"])
    for i, r in enumerate(rows[-10:], start=len(rows)-10):
        pct = (r["close"]/rows[i-1]["close"]-1)*100 if i>0 else 0
        print('%s O=%8.2f C=%8.2f H=%8.2f L=%8.2f V=%9.0f  %+5.2f%%' % (r["date"], r["open"], r["close"], r["high"], r["low"], r["vol"], pct))
    closes = [r["close"] for r in rows]
    def ma(p): return sum(closes[-p:])/p
    print("MA5=%.2f MA10=%.2f MA20=%.2f MA50=%.2f" % (ma(5), ma(10), ma(20), ma(50)))
    print("5日: %+.2f%%  10日: %+.2f%%" % ((closes[-1]/closes[-6]-1)*100, (closes[-1]/closes[-11]-1)*100))
    vols = [r["vol"] for r in rows]
    v5 = sum(vols[-5:])/5; v20 = sum(vols[-20:])/20
    print("量5/量20=%.2f" % (v5/v20))
    hi50 = max(r["high"] for r in rows[-50:]); lo50 = min(r["low"] for r in rows[-50:])
    print("50日高=%.2f 50日低=%.2f 位置=%d%%" % (hi50, lo50, (closes[-1]-lo50)/(hi50-lo50)*100))
for code in ["920199","920284","920932","920169","920098","920592"]:
    analyze(code)