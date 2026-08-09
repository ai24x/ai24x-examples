# -*- coding: utf-8 -*-
import json, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
base = r"E:\AI24X\ai24x-website\ai24x01\p\a1\调研报告\03-个股深度研究\2026-08-07-北证潜力股推荐"
with open(base + r"\数据\klines_20260807.json", "r", encoding="utf-8") as f:
    K = json.load(f)

def stats(code, name):
    bars = K[code]["bars"]
    rows = [{"date": r[0], "o": float(r[1]), "c": float(r[2]), "h": float(r[3]), "l": float(r[4]), "v": float(r[5])} for r in bars]
    n = len(rows)
    closes = [r["c"] for r in rows]
    vols = [r["v"] for r in rows]
    def ma(p, i):
        if i + 1 < p: return None
        return sum(closes[i+1-p:i+1]) / p
    last = rows[-1]
    i = n - 1
    print("=" * 70)
    print(name, code, "last:", last["date"], "close", last["c"])
    for p in [5, 10, 20, 50, 60]:
        print(f"  MA{p} = {ma(p, i):.2f}")
    print("  MA20 prev-day:", f"{ma(20, i-1):.2f}")
    # 5d / 10d pct
    c0 = closes[i]; c5 = closes[i-5] if n > 5 else closes[0]; c10 = closes[i-10] if n > 10 else closes[0]
    print(f"  5日涨幅 = {(c0/c5-1)*100:.2f}%  10日涨幅 = {(c0/c10-1)*100:.2f}%")
    # vol ratios
    v5 = sum(vols[i-4:i+1]) / 5
    v20 = sum(vols[i-19:i+1]) / 20
    v10 = sum(vols[i-9:i+1]) / 10
    print(f"  8/6量 = {vols[i]:.0f}手 = {vols[i]/1e4:.2f}万手  vol5/vol20 = {v5/v20:.2f}  vol10/vol20 = {v10/v20:.2f}")
    # recent lows/highs
    lows20 = min(r["l"] for r in rows[-20:])
    highs20 = max(r["h"] for r in rows[-20:])
    print(f"  近20日低 = {lows20:.2f}  近20日高 = {highs20:.2f}")
    # last 8 days
    for r in rows[-8:]:
        chg = (r["c"] / closes[rows.index(r) - 1] - 1) * 100 if rows.index(r) > 0 else 0
        print(f"    {r['date']} O{r['o']:.2f} C{r['c']:.2f} H{r['h']:.2f} L{r['l']:.2f} V{r['v']:.0f}手 chg{chg:+.2f}%")
    # 50-day high for reference
    highs60 = max(r["h"] for r in rows[-60:])
    print(f"  近60日高 = {highs60:.2f}")

for c, nm in [("920932", "科达自控"), ("920098", "科隆新材"), ("920284", "灵鸽科技")]:
    stats(c, nm)