# -*- coding: utf-8 -*-
import json, os
p = r"E:\AI24X\ai24x-website\ai24x01\p\a1\调研报告\01-事件驱动研究\2026-08-07-DeepSeek涨价低风险优选\工具\chart_final.py"
s = open(p, encoding="utf-8").read()
s = s.replace("liang = load(\"300603\")", "liang = load(\"300603\")[-60:]")
s = s.replace("jinx = load(\"300252\")", "jinx = load(\"300252\")[-60:]")
open(p, "w", encoding="utf-8").write(s)
print("patched")