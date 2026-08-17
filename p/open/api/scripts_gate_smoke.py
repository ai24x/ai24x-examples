#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
投流前闸门只读冒烟（不写库、不真下单）。

用法:
  python scripts_gate_smoke.py
  python scripts_gate_smoke.py --base https://api.ai24x.com

退出码 0=关键项通过；非 0=有失败。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import httpx

OUT = Path(__file__).resolve().parent / "_gate_smoke_last.json"


def _ok(name: str, cond: bool, detail: str = "") -> dict:
    return {"name": name, "ok": bool(cond), "detail": (detail or "")[:500]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    args = ap.parse_args()
    base = args.base.rstrip("/")
    rows: list[dict] = []

    with httpx.Client(base_url=base, timeout=30.0) as client:
        # health
        try:
            r = client.get("/health")
            rows.append(_ok("health", r.status_code == 200, r.text[:200]))
        except Exception as e:
            rows.append(_ok("health", False, str(e)))

        # plans: 公开仅 3 包；无月卡；价不该是 14/144 分
        try:
            j = client.get("/v1/billing/plans").json()
            plans = j.get("plans") or j.get("items") or []
            if isinstance(j, list):
                plans = j
            enabled = [p for p in plans if p.get("enabled", True)]
            ids = [str(p.get("plan") or p.get("id") or p.get("plan_id") or "") for p in enabled]
            fen = [int(p.get("price_fen") or 0) for p in enabled]
            # 2026-08-05: 5 档在售（Starter/VIP Pass/Builder/Advanced/Scale）
            have_mid = "token_pack_mid" in ids
            have_pass = "token_vip_month" in ids
            have_scale = "token_vip_month_50w" in ids
            sane_fen = all(f <= 0 or f >= 100 for f in fen)  # 至少 ¥1 / $1 量级
            rows.append(
                _ok(
                    "plans_public",
                    len(enabled) >= 5 and have_mid and have_pass and have_scale and sane_fen,
                    json.dumps({"ids": ids, "fen": fen, "count": len(enabled)}, ensure_ascii=False),
                )
            )
        except Exception as e:
            rows.append(_ok("plans_public", False, str(e)))

        # pay status
        try:
            j = client.get("/v1/billing/pay/status").json()
            mock = bool(j.get("token_pay_mock_enabled") or j.get("mock_allowed"))
            # 生产应 mock=false；本机可能 true，仅记录
            rows.append(
                _ok(
                    "pay_status",
                    True,
                    json.dumps(
                        {
                            "pay": j.get("token_pay_enabled"),
                            "mock": mock,
                            "paypal_webhook_id_set": (j.get("paypal") or {}).get("webhook_id_set"),
                        },
                        ensure_ascii=False,
                    ),
                )
            )
        except Exception as e:
            rows.append(_ok("pay_status", False, str(e)))

        # login throttle path exists (bad password → 401 not 500)
        try:
            r = client.post(
                "/v1/auth/login",
                json={"email": "gate-smoke-nonexist@example.com", "password": "wrong-pass-xyz"},
            )
            rows.append(
                _ok(
                    "login_endpoint",
                    r.status_code in (401, 429),
                    f"status={r.status_code} body={r.text[:180]}",
                )
            )
        except Exception as e:
            rows.append(_ok("login_endpoint", False, str(e)))

        # models brand flash present
        try:
            j = client.get("/v1/models").json()
            brand = j.get("brand") or {}
            rows.append(_ok("models_brand_flash", bool(brand.get("flash")), str(brand)[:200]))
        except Exception as e:
            rows.append(_ok("models_brand_flash", False, str(e)))

    OUT.write_text(
        json.dumps({"ts": time.time(), "base": base, "rows": rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    failed = [r for r in rows if not r["ok"]]
    for r in rows:
        mark = "OK " if r["ok"] else "FAIL"
        print(f"{mark} {r['name']}: {r['detail']}")
    print(f"\nsummary: {len(rows) - len(failed)}/{len(rows)} ok → {OUT}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
