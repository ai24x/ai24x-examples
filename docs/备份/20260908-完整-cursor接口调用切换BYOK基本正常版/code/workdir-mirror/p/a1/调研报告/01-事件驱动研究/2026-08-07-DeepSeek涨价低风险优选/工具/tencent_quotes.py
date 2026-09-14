# -*- coding: utf-8 -*-
import os, time, urllib.request
D = os.path.dirname(os.path.abspath(__file__))
codes = ["300252","002657","301085","603881","300603","300895","600602","688158",
         "688418","002418","300065","603339","002965","301070","688168","300494",
         "300442","300738","002197","301157","002733","002881","300324","002902"]
def pref(c):
    return ("sh" if c.startswith(("60","68","90")) else "sz") + c
rows = []
for c in codes:
    try:
        req = urllib.request.Request("https://qt.gtimg.cn/q=" + pref(c), headers={"User-Agent":"Mozilla/5.0"})
        raw = urllib.request.urlopen(req, timeout=10).read()
        txt = raw.decode("gbk", errors="replace")
        parts = txt.split("~")
        if len(parts) > 45:
            name=parts[1]; price=parts[3]; chg=parts[32]; turnover=parts[38]; pe=parts[39]; floatmc=parts[44]; totalmc=parts[45]
            print("%s %s price=%s chg=%s%% turnover=%s%% PE=%s 流通=%.1f亿 总市值=%.1f亿" % (c,name,price,chg,turnover,pe,float(floatmc),float(totalmc)))
    except Exception as e:
        print(c, "ERR", e)
    time.sleep(0.6)