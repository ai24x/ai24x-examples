# -*- coding: utf-8 -*-
import json, urllib.request, time, sys
sys.stdout.reconfigure(encoding="utf-8")
BASE = "http://127.0.0.1:18011"
tok = open(r"E:\AI24X\ai24x-website\ai24x01\p\a1\调研报告\03-个股深度研究\2026-08-07-煤炭潜力龙头调研\工具\token.txt", encoding="utf-8-sig").read().strip()
def get(url):
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + tok})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))
# 测试北证代码段: 920493(并行科技), 430047(诺思兰德), 832566(梓橦宫), 830799(艾融软件)
tests = ["920493","430047","832566","830799","831010","837006"]
for code in tests:
    sid = "1." + code
    try:
        d = get(BASE + "/api/quote/snapshot?secid=" + sid)
        print(code, "score=%s cpos=%s tags=%s risks=%s" % (d.get("score"), d.get("cpos"), ",".join(d.get("tags") or [])[:60], d.get("risks") or "-"))
    except Exception as e:
        print(code, "ERR", e)
    time.sleep(1.2)