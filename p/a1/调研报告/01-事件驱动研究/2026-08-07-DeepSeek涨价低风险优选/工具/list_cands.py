# -*- coding: utf-8 -*-
import json, os
D = os.path.dirname(os.path.abspath(__file__))
cands = json.load(open(os.path.join(D, "..", "数据", "candidates_prescreen_20260807.json"), encoding="utf-8"))
plates = {"BK1134":"算力","BK1064":"东数","BK0579":"云","BK0922":"IDC","BK1188":"DS","BK1138":"液冷"}
for it in cands:
    ps = ",".join(plates[b] for b in it["plates"])
    print("%s %s  %s亿 %+5.1f%%  [%s] 主力%+.0f万" % (it["code"], it["name"], it["mcap"], it["chg"], ps, (it.get("f62") or 0)/1e4))