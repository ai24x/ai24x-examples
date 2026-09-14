# -*- coding: utf-8 -*-
import urllib.request
req = urllib.request.Request("https://qt.gtimg.cn/q=sz300252", headers={"User-Agent":"Mozilla/5.0"})
txt = urllib.request.urlopen(req, timeout=10).read().decode("gbk", errors="replace")
parts = txt.split("~")
for i in range(38, 60):
    print(i, repr(parts[i]) if i < len(parts) else "N/A")