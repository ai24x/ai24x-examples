# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")
from pypdf import PdfReader
pdf = r"E:\AI24X\ai24x-website\ai24x01\p\a1\调研报告\03-个股深度研究\2026-08-07-煤炭潜力龙头调研\分享版\煤炭板块潜力龙头调研_低风险优选版_盘江股份_山西焦化_2026-08-07.pdf"
r = PdfReader(pdf)
print("pages:", len(r.pages))
txt = ""
for p in r.pages:
    txt += (p.extract_text() or "") + "\n"
for kw in ["盘江股份", "山西焦化", "600395", "600740", "云煤能源", "支撑", "止损", "不构成任何投资建议"]:
    print(kw, "->", kw in txt)