# -*- coding: utf-8 -*-
import json, os, urllib.request, urllib.parse, time
BASE = "http://127.0.0.1:18011"
D = os.path.dirname(os.path.abspath(__file__))
tok = open(os.path.join(D, "token.txt"), encoding="utf-8-sig").read().strip()
def get(url):
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + tok})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))
kw = ["算力租赁","东数西算","数据中心","云计算","AIGC","液冷","DeepSeek","算力","服务器","AI应用","算力调度","IDC","数据要素","华为昇腾","GPU"]
out = {}
for k in kw:
    try:
        d = get(BASE + "/api/suggest?q=" + urllib.parse.quote(k) + "&include_plates=1")
        out[k] = d
        print("=== ", k, " ===")
        for it in (d.get("QuotationCodeTable") or {}).get("Data") or []:
            print("  ", it.get("QuoteID"), it.get("Name"), it.get("Classify"), it.get("Code"))
    except Exception as e:
        print(k, "ERR", e)
    time.sleep(1.2)
json.dump(out, open(os.path.join(D, "suggest_20260807.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("saved")