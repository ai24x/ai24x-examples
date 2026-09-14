# -*- coding: utf-8 -*-
import json, os, time, urllib.request, urllib.parse
D = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(D, "..", "数据", "plate_members_20260807.json")

PLATES = {
    "BK1134": "算力概念",
    "BK1064": "东数西算",
    "BK0579": "云计算",
    "BK0922": "数据中心",
    "BK1188": "DeepSeek概念",
    "BK1138": "液冷概念",
}
FIELDS = "f12,f14,f2,f3,f4,f5,f6,f8,f20,f21,f62,f184"

def get(url, tries=6):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"})
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            print("  retry", i, e)
            time.sleep(5 + i * 2)
    return None

def pull(fs):
    allrows = []
    pn = 1
    while True:
        url = "https://push2delay.eastmoney.com/api/qt/clist/get?pn=%d&pz=500&po=1&np=1&fltt=2&invt=2&fid=f3&fs=%s&fields=%s" % (pn, urllib.parse.quote(fs), FIELDS)
        d = get(url)
        if not d or not d.get("data") or not d["data"].get("diff"):
            break
        rows = d["data"]["diff"]
        allrows.extend(rows)
        if len(rows) < 500:
            break
        pn += 1
        time.sleep(1.5)
    return allrows

result = {}
for bk, name in PLATES.items():
    print("=== pull", bk, name, "===")
    rows = pull("b:" + bk)
    print("  members:", len(rows))
    result[bk] = {"name": name, "members": rows}
    time.sleep(4)

json.dump(result, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("saved:", OUT)