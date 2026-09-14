# -*- coding: utf-8 -*-
import json, os, sys
sys.stdout.reconfigure(encoding="utf-8")
D = r"E:\AI24X\ai24x-website\ai24x01\p\a1\调研报告\03-个股深度研究\2026-08-07-煤炭潜力龙头调研"
snap = json.load(open(os.path.join(D, "数据", "snap_batch_20260807.json"), encoding="utf-8"))
plates = json.load(open(os.path.join(D, "数据", "plate_members_20260807.json"), encoding="utf-8"))
# 名称与市值映射
name_mc = {}
for bk, blob in plates.items():
    for m in blob["members"]:
        c = str(m.get("f12",""))
        if c.isdigit() and len(c)==6:
            name_mc[c] = (m.get("f14"), (m.get("f20") or 0)/1e8, m.get("f3"))
def show(code):
    if code not in snap: 
        print(code, "NOT FOUND"); return
    s = snap[code]["snapshot"]
    nm, mc, chg = name_mc.get(code, ("?","?","?"))
    print("="*70)
    print("%s %s | 市值≈%.0f亿 | 今日%+.1f%% | score=%s cpos=%.1f%%" % (code, nm, mc, chg or 0, s.get("score"), (s.get("cpos") or 0)*100))
    print("  tags:", " | ".join(s.get("tags") or []))
    print("  risks:", " | ".join(s.get("risks") or []) if s.get("risks") else "无")
    print("  red_days=%s up=%.1f%% volr=%.2f" % (s.get("red_days"), s.get("up_pct") or 0, s.get("vol_ratio") or 0))
for code in ["600740","600971","600395","000937","600758","600121","600408","600792","601011","600508","600403","601015","000571","600997","600123","000552","000723","601101"]:
    show(code)