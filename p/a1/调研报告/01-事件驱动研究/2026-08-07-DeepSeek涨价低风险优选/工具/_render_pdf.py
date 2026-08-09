# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")
import pypdfium2 as pdfium
pdf = r"E:\AI24X\ai24x-website\ai24x01\p\a1\调研报告\01-事件驱动研究\2026-08-07-DeepSeek涨价低风险优选\分享版\DeepSeek涨价受益链调研_低风险优选版_立昂技术_金信诺_2026-08-07.pdf"
doc = pdfium.PdfDocument(pdf)
print("pages:", len(doc))
outdir = r"E:\AI24X\ai24x-website\ai24x01\p\a1\调研报告\01-事件驱动研究\2026-08-07-DeepSeek涨价低风险优选\工具"
import os
for i in [0, 4, 5, 6, 8]:
    page = doc[i]
    bmp = page.render(scale=1.2)
    img = bmp.to_pil()
    fp = os.path.join(outdir, f"_pg{i+1}.png")
    img.save(fp)
    print("saved", fp, img.size)