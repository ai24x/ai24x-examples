# -*- coding: utf-8 -*-
import json, urllib.request, time, sys
sys.stdout.reconfigure(encoding="utf-8")
def get(url, tries=6):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0","Referer":"https://quote.eastmoney.com/"})
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            print("  retry", i, e); time.sleep(4+i*2)
    return None
# 概念板块列表找北交所相关
for fs, label in [("m:90+t:3", "概念"), ("m:90+t:2", "行业")]:
    url = "https://push2delay.eastmoney.com/api/qt/clist/get?pn=1&pz=300&po=1&np=1&fltt=2&invt=2&fid=f3&fs=%s&fields=f12,f14,f3,f20" % fs
    d = get(url)
    if d and d.get("data") and d["data"].get("diff"):
        rows = d["data"]["diff"]
        hits = [r for r in rows if any(k in str(r.get("f14","")) for k in ["北证","北交","专精特新"])]
        print(label, "hits:", [(r["f12"], r["f14"], r.get("f3")) for r in hits])
    else:
        print(label, "no data")