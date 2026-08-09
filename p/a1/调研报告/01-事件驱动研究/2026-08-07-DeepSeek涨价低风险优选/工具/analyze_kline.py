# -*- coding: utf-8 -*-
import json, os
D = os.path.dirname(os.path.abspath(__file__))
data = json.load(open(os.path.join(D, "..", "数据", "klines_20260807.json"), encoding="utf-8"))
names = {"300252":"金信诺","002657":"中科金财","301085":"亚康股份","300603":"立昂技术","300608":"思特奇","300895":"铜牛信息","002733":"雄韬股份","301157":"华塑科技"}
def ma(arr, p, i):
    if i+1 < p: return None
    return sum(arr[i+1-p:i+1])/p
for code in ["300252","002657","301085","300603","300608","300895"]:
    bars = data[code]["bars"]
    print("="*90)
    print(names[code], code, "bars:", len(bars))
    n = len(bars)
    closes = [float(b[2]) for b in bars]
    highs = [float(b[3]) for b in bars]
    lows = [float(b[4]) for b in bars]
    vols = [float(b[5]) for b in bars]
    c5 = ma(closes,5,n-1); c10 = ma(closes,10,n-1); c20 = ma(closes,20,n-1)
    last = closes[-1]
    lo60 = min(lows[-60:]); hi60 = max(highs[-60:])
    pos60 = (last-lo60)/(hi60-lo60)*100 if hi60>lo60 else 0
    chg5 = (last/closes[-6]-1)*100
    chg10 = (last/closes[-11]-1)*100
    chg20 = (last/closes[-21]-1)*100
    v5 = sum(vols[-5:])/5
    v20 = sum(vols[-20:])/20
    print("last=%.2f MA5=%.2f MA10=%.2f MA20=%.2f" % (last, c5, c10, c20))
    print("60日低=%.2f 高=%.2f 位置=%.0f%% | 5日%+.1f%% 10日%+.1f%% 20日%+.1f%% | 量5/量20=%.2f" % (lo60, hi60, pos60, chg5, chg10, chg20, v5/v20))
    print("近8日:")
    for b in bars[-8:]:
        d,o,c,h,l,v = b[0], float(b[1]), float(b[2]), float(b[3]), float(b[4]), float(b[5])
        chg = (c/float(bars[bars.index(b)-1][2])-1)*100 if bars.index(b)>0 else 0
        print("   %s O=%.2f C=%.2f H=%.2f L=%.2f V=%8.0f  %+5.1f%%" % (d,o,c,h,l,v,chg))