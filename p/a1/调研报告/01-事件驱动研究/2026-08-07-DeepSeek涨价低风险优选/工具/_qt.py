# -*- coding: utf-8 -*-
import sys, urllib.request
sys.stdout.reconfigure(encoding="utf-8")
# 腾讯行情 GBK
def qt(code):
    url = "http://qt.gtimg.cn/q=sz" + code if code.startswith("30") or code.startswith("00") else "http://qt.gtimg.cn/q=sh" + code
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    raw = urllib.request.urlopen(req, timeout=10).read().decode("gbk", errors="ignore")
    # 字段: 1名称 2代码 3现价 4昨收 5今开 6成交量(手) 39 PE 44流通市值 45总市值 (亿)
    parts = raw.split("~")
    name = parts[1]; price = parts[3]; pe = parts[39]; fcap = parts[44]; tcap = parts[45]
    print(name, code, "现价", price, "PE", pe, "流通市值(亿)", fcap, "总市值(亿)", tcap)
for c in ["300603", "300252", "002657"]:
    qt(c)