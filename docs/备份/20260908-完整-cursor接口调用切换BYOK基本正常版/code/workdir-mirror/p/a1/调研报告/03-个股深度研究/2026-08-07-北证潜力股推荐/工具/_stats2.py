# -*- coding: utf-8 -*-
import json, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
base = r"E:\AI24X\ai24x-website\ai24x01\p\a1\调研报告\03-个股深度研究\2026-08-07-北证潜力股推荐"
with open(base + r"\数据\klines_20260807.json", "r", encoding="utf-8") as f:
    K = json.load(f)

def brief(code):
    bars = K[code]["bars"]
    rows = [{"date": r[0], "o": float(r[1]), "c": float(r[2]), "h": float(r[3]), "l": float(r[4]), "v": float(r[5])} for r in bars]
    n = len(rows)
    closes = [r["c"] for r in rows]
    c0 = closes[-1]
    def pct(k):
        return (c0 / closes[-1-k] - 1) * 100 if n > k else None
    print(code, "close", c0, "| 5d", f"{pct(5):.1f}%" if pct(5) else "-", "| 10d", f"{pct(10):.1f}%" if pct(10) else "-")
    # 7/27 + 7/28 moves
    for r in rows[-12:]:
        idx = rows.index(r)
        chg = (r["c"] / closes[idx-1] - 1) * 100 if idx > 0 else 0
        print("   ", r["date"], f"chg {chg:+.1f}%", "close", r["c"])

for c in ["920169", "920592", "920199"]:
    brief(c)