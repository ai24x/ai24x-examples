# -*- coding: utf-8 -*-
# 用途：OCR 校验图表中文是否渲染正常（防乱码）。用法：python ocr_check.py
import os
from rapidocr_onnxruntime import RapidOCR

engine = RapidOCR()
TOOL_DIR = os.path.dirname(os.path.abspath(__file__))   # 工具/
REPORT_DIR = os.path.dirname(TOOL_DIR)                  # 报告文件夹
for f in ["chart_litong.png", "chart_ucloud.png"]:
    res, _ = engine(os.path.join(REPORT_DIR, f))
    txt = "\n".join(r[1] for r in (res or []))
    print("=====", f)
    print(txt[:600])
