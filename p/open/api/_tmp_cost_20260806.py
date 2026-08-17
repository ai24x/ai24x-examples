# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, ".")
import model_warehouse as mw

REF = 0.35
rows = []
for row in mw.CATALOG:
    mid = row.get("id") or ""
    if not str(mid).startswith("vip-"):
        continue
    mult = int(row.get("billing_mult") or 1)
    cin = float(row.get("cost_in") or 0)
    cout = float(row.get("cost_out") or 0)
    sell = REF * mult
    gm_out = (sell - cout) / sell * 100 if sell else 0
    gm_in = (sell - cin) / sell * 100 if sell else 0
    cost_mix = (cin * 1 + cout * 4) / 5.0
    gm_mix = (sell - cost_mix) / sell * 100 if sell else 0
    rows.append((mid, mult, sell, cin, cout, gm_out, gm_in, gm_mix))

rows.sort(key=lambda r: -r[2])
print("%-20s %5s %7s %7s %7s %8s %8s %8s" % ("id", "mult", "sell", "in", "out", "GM_out", "GM_in", "GM_1:4"))
for r in rows:
    print("%-20s %5d %7.2f %7.2f %7.2f %7.1f%% %7.1f%% %7.1f%%" % (r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7]))
