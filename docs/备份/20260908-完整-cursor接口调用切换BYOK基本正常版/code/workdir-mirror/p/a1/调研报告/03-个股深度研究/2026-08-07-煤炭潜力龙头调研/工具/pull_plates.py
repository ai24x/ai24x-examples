# -*- coding: utf-8 -*-
import json, os, time, urllib.request, urllib.parse, sys
sys.stdout.reconfigure(encoding="utf-8")
D = r"E:\AI24X\ai24x-website\ai24x01\p\a1\调研报告\03-个股深度研究\2026-08-07-煤炭潜力龙头调研"
OUT = os.path.join(D, "数据", "plate_members_20260807.json")
PLATES = {
    "BK0437": "煤炭",
    "BK1250": "煤炭开采",
    "BK1493": "动力煤",
    "BK1494": "焦煤",
}
FIELDS = "f12,f14,f2,f3,f4,f5,f6,f8,f20,f21,f62,f184"
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
    time.sleep(3)
json.dump(result, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("saved:", OUT)
# 打印市值分布概览
small = []
for bk, blob in result.items():
    for m in blob["members"]:
        mc = (m.get("f20") or 0)/1e8
        if 20 <= mc <= 200:
            small.append((m.get("f14"), str(m.get("f12")), mc, m.get("f3"), m.get("f62")))
seen = set(); uniq = []
for s in small:
    if s[1] not in seen:
        seen.add(s[1]); uniq.append(s)
uniq.sort(key=lambda x: x[2])
print("20~200亿候选:", len(uniq))
for u in uniq:
    print(u)