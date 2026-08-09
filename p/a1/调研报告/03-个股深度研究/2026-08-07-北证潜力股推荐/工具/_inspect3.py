# -*- coding: utf-8 -*-
import json, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
base = r"E:\AI24X\ai24x-website\ai24x01\p\a1\调研报告\03-个股深度研究\2026-08-07-北证潜力股推荐"
with open(base + r"\数据\snap_batch_20260807.json", "r", encoding="utf-8") as f:
    S = json.load(f)
for code in ["920932", "920098", "920284", "920169", "920592", "920199"]:
    x = S.get(code)
    if not x:
        print(code, "MISSING"); continue
    snap = x.get("snapshot") or {}
    print("=" * 60)
    print(code, x.get("name"), "mcap(总市值/亿):", x.get("mcap"))
    for k in ["score", "tags", "risks", "red_days", "vol_ratio", "up_pct", "cpos", "latest_time"]:
        print(" ", k, "=", snap.get(k))