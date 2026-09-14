# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")
from pypdf import PdfReader
pdf = r"E:\AI24X\ai24x-website\ai24x01\p\a1\调研报告\01-事件驱动研究\2026-08-07-DeepSeek涨价低风险优选\分享版\DeepSeek涨价受益链调研_低风险优选版_立昂技术_金信诺_2026-08-07.pdf"
r = PdfReader(pdf)
print("pages:", len(r.pages))
txt = ""
for p in r.pages:
    txt += (p.extract_text() or "") + "\n"
for kw in ["立昂技术", "金信诺", "300603", "300252", "中科金财", "支撑", "止损", "不构成任何投资建议", "BWPX3Z8B"]:
    print(kw, "->", kw in txt)