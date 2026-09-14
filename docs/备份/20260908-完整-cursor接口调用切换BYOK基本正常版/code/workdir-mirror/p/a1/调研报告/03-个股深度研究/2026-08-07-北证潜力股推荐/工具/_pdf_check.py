# -*- coding: utf-8 -*-
import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
pdf = r"E:\AI24X\ai24x-website\ai24x01\p\a1\调研报告\03-个股深度研究\2026-08-07-北证潜力股推荐\分享版\北证潜力股推荐_低风险优选版_科达自控_科隆新材_灵鸽科技_2026-08-07.pdf"
try:
    from pypdf import PdfReader
except ImportError:
    from PyPDF2 import PdfReader
r = PdfReader(pdf)
print("pages:", len(r.pages))
text = "\n".join((p.extract_text() or "") for p in r.pages)
for kw in ["科达自控", "920932", "科隆新材", "920098", "灵鸽科技", "920284", "止损", "不构成任何投资建议", "BWPX3Z8B", "信号分享卡"]:
    print(kw, "=>", kw in text)