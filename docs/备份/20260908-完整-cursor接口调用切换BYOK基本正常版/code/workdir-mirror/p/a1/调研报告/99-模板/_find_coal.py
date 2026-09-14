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
            print("  retry", i, e)
            time.sleep(4 + i*2)
    return None
# 行业板块列表（煤炭行业 BK0437）
url = "https://push2delay.eastmoney.com/api/qt/clist/get?pn=1&pz=200&po=1&np=1&fltt=2&invt=2&fid=f3&fs=m:90+t:2&fields=f12,f14,f3,f20"
d = get(url)
if d and d.get("data") and d["data"].get("diff"):
    rows = d["data"]["diff"]
    hits = [r for r in rows if "煤" in str(r.get("f14",""))]
    print("行业板块煤相关:", [(r["f12"], r["f14"], r.get("f3")) for r in hits])
else:
    print("no data", d)