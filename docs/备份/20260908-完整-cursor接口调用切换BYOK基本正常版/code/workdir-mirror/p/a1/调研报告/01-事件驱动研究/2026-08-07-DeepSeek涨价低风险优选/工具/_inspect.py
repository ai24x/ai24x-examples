# -*- coding: utf-8 -*-
import json, os, sys
sys.stdout.reconfigure(encoding="utf-8")
base = r"E:\AI24X\ai24x-website\ai24x01\p\a1\调研报告\01-事件驱动研究\2026-08-07-DeepSeek涨价低风险优选"
with open(os.path.join(base, "数据", "klines_20260807.json"), "r", encoding="utf-8") as f:
    k = json.load(f)
d = k["300603"]
print("300603 top-level keys:", list(d.keys()))
for kk, vv in d.items():
    if isinstance(vv, dict):
        print(" sub dict", kk, "keys:", list(vv.keys())[:5])
    elif isinstance(vv, list):
        print(" list", kk, "len:", len(vv), "first:", vv[0] if vv else None)