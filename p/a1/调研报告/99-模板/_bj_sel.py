# -*- coding: utf-8 -*-
import json, sys
sys.stdout.reconfigure(encoding="utf-8")
liq = json.load(open(r"E:\AI24X\ai24x-website\ai24x01\p\a1\调研报告\99-模板\_bj_liquid.json", encoding="utf-8"))
sel = [c for c in liq if c["amount"] >= 0.30]
print("体检数量:", len(sel))
print(" ".join(c["code"] for c in sel))
json.dump(sel, open(r"E:\AI24X\ai24x-website\ai24x01\p\a1\调研报告\99-模板\_bj_sel.json","w",encoding="utf-8"), ensure_ascii=False, indent=1)