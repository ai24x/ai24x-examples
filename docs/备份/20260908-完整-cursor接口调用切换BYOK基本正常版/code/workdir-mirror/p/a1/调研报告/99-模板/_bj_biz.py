# -*- coding: utf-8 -*-
import json, sys
sys.stdout.reconfigure(encoding="utf-8")
rows = json.load(open(r"E:\AI24X\ai24x-website\ai24x01\p\a1\调研报告\99-模板\_bj_all.json", encoding="utf-8"))
by = {str(r.get("f12")): r for r in rows}
snap = json.load(open(r"E:\AI24X\ai24x-website\ai24x01\p\a1\调研报告\99-模板\_bj_snap.json", encoding="utf-8"))
for code in ["920098","920284","920169","920932","920592"]:
    r = by.get(code, {})
    s = snap.get(code, {}).get("snapshot", {})
    mc = float(r.get("f20") or 0)/1e8
    amt = float(r.get("f6") or 0)/1e8
    print("="*70)
    print(code, r.get("f14"), "| 总市值 %.0f亿 | 成交额 %.2f亿" % (mc, amt))
    print("score:", s.get("score"), "| cpos: %.0f%%" % ((s.get("cpos") or 0)*100))
    print("tags:", " | ".join(s.get("tags") or []))
    print("risks:", " | ".join(s.get("risks") or []) if s.get("risks") else "无")