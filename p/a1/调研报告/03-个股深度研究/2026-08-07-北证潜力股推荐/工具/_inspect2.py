# -*- coding: utf-8 -*-
import json, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
base = r"E:\AI24X\ai24x-website\ai24x01\p\a1\调研报告\03-个股深度研究\2026-08-07-北证潜力股推荐"
with open(base + r"\数据\snap_batch_20260807.json", "r", encoding="utf-8") as f:
    S = json.load(f)
print(type(S), len(S) if hasattr(S, "__len__") else "")
if isinstance(S, list):
    for x in S[:2]:
        print(json.dumps(x, ensure_ascii=False)[:600])
elif isinstance(S, dict):
    for k in list(S.keys())[:3]:
        print(k, json.dumps(S[k], ensure_ascii=False)[:600])