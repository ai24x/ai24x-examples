# -*- coding: utf-8 -*-
"""Probe DeepSeek VIP rates + price monitor rows on 04."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "api"))
# on 04 this script is copied next to api or run from C:\ai24x01\api
for p in (Path(r"C:\ai24x01\api"), Path(__file__).resolve().parent):
    if (p / "model_warehouse.py").exists():
        sys.path.insert(0, str(p))
        break

import model_warehouse as mw  # noqa: E402
import price_monitor as pm  # noqa: E402

ids = ("vip-ds-flash", "vip-ds-pro")
rows = [r for r in mw.catalog_merged() if r.get("id") in ids]
print("=== merged ===")
print(
    json.dumps(
        [
            {
                k: r.get(k)
                for k in (
                    "id",
                    "in_mult",
                    "out_mult",
                    "billing_mult",
                    "cost_in",
                    "cost_out",
                    "rate_source",
                    "channels",
                    "peak_in_mult",
                    "peak_out_mult",
                )
            }
            for r in rows
        ],
        indent=2,
        ensure_ascii=False,
    )
)
print("=== override vip_rates ===")
ov = mw._load_ov()
print(json.dumps({k: (ov.get("vip_rates") or {}).get(k) for k in ids}, indent=2, ensure_ascii=False))
print("=== monitor ===")
snap = pm.snapshot()
for r in snap.get("rows") or []:
    if r.get("id") in ids:
        print(
            json.dumps(
                {
                    "id": r["id"],
                    "sell": [r.get("sell_in"), r.get("sell_out")],
                    "cost": [r.get("cost_in"), r.get("cost_out")],
                    "mult": [r.get("in_mult"), r.get("out_mult")],
                    "gm_out": r.get("gm_out"),
                    "gm_blend": r.get("gm_blend"),
                    "market_min": r.get("market_min"),
                    "or": r.get("or"),
                    "tl": r.get("tl"),
                    "flags": r.get("flags"),
                    "level": r.get("level"),
                    "active_channel": r.get("active_channel"),
                },
                ensure_ascii=False,
            )
        )
