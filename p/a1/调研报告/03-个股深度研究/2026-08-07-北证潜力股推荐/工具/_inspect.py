# -*- coding: utf-8 -*-
import json, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
base = r"E:\AI24X\ai24x-website\ai24x01\p\a1\调研报告\03-个股深度研究\2026-08-07-北证潜力股推荐"
with open(base + r"\数据\klines_20260807.json", "r", encoding="utf-8") as f:
    K = json.load(f)
print("codes:", list(K.keys()))
for code in ["920932", "920098", "920284"]:
    d = K[code]
    print(code, list(d.keys()))
    bars = d["bars"]
    print("  n_bars:", len(bars))
    print("  first:", bars[0])
    print("  last3:", bars[-3:])