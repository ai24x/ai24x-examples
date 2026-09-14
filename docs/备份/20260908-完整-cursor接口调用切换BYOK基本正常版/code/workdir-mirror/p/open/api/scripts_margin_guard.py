#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""毛利守卫：监控全站按模型的估算毛利与国际旗舰占比，超阈值推飞书。

用法（api/ 目录）：
  python scripts_margin_guard.py [--days 7] [--json]

阈值（环境变量，默认值）：
  MARGIN_GUARD_INTL_YELLOW=10  国际旗舰 credits 占比黄线 %
  MARGIN_GUARD_INTL_RED=20     红线 %
  MARGIN_GUARD_GM_YELLOW=25    全站混合毛利黄线 %
  MARGIN_GUARD_GM_RED=20       红线 %
  FEISHU_WEBHOOK_URL           飞书机器人 webhook（未配则只打印）

口径说明：
- 收入 = credits × flash 锚 $0.35/M；成本按 OR 目录价 in/out 1:1 混合（保守），
  中国模实际走硅基批发更低 → 真实毛利只高不低。
- 数据源 BillingLedger.consume（model 列），统计最近 N 天；无数据返回 OK 不告警。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import func

from database import SessionLocal
from models import BillingLedger

FLASH_USD_PER_M = 0.35

# 历史/别名 model 值 -> catalog id（宽容匹配）
_ALIAS = {
    "deepseek-v4-flash": "vip-ds-flash",
    "deepseek-v4-pro": "vip-ds-pro",
    "or-pro": "vip-ds-pro",
    "or-flash": "vip-ds-flash",
}


def _env_float(key: str, default: float) -> float:
    try:
        return float(os.getenv(key) or default)
    except (TypeError, ValueError):
        return float(default)


def _catalog_map():
    """catalog id -> {mult, cost_in, cost_out, is_intl, role}；加载失败返回空（不阻断）。"""
    try:
        import model_warehouse as mw

        out = {}
        for c in mw.catalog_merged():
            cid = str(c.get("id") or "")
            if not cid:
                continue
            is_intl = cid.startswith("vip-gpt") or "claude" in cid or "gemini" in cid
            out[cid] = {
                "mult": max(1, int(c.get("billing_mult") or 1)),
                "cost_in": float(c.get("cost_in") or 0),
                "cost_out": float(c.get("cost_out") or 0),
                "is_intl": is_intl,
                "role": str(c.get("role") or ""),
            }
        return out
    except Exception as e:  # pragma: no cover
        print(f"[warn] catalog load failed: {e}", file=sys.stderr)
        return {}


def _classify(model_key: str, catalog: dict):
    """返回 (kind, mult, cost_in, cost_out, is_intl)。kind: brand|china|intl|unknown"""
    m = str(model_key or "").strip().lower()
    for prefix in ("vip:", "named:", "pick:"):
        if m.startswith(prefix):
            m = m[len(prefix):]
    if m in catalog:
        c = catalog[m]
        kind = "intl" if c["is_intl"] else ("brand" if c["role"] != "vip_pick" else "china")
        return kind, c["mult"], c["cost_in"], c["cost_out"], c["is_intl"]
    if m in _ALIAS and _ALIAS[m] in catalog:
        c = catalog[_ALIAS[m]]
        kind = "intl" if c["is_intl"] else "china"
        return kind, c["mult"], c["cost_in"], c["cost_out"], c["is_intl"]
    if m in ("flash", "auto", "pro", "ultra", "shared", "or-fallback"):
        try:
            from model_warehouse import layer_cost_mult_for

            layer = {"pro": "L2", "ultra": "L3", "shared": "L0", "or-fallback": "L0"}.get(m, "L1")
            mult = max(1, int(layer_cost_mult_for(layer)))
        except Exception:
            layer = "L1"
            mult = 1
        _bc = {"L1": (0.14, 0.28), "L2": (0.435, 0.87), "L3": (0.25, 2.0), "L0": (0.0, 0.0)}
        cin, cout = _bc.get(layer, _bc["L1"])
        return "brand", mult, cin, cout, False
    if any(k in m for k in ("gpt", "claude", "gemini")):
        return "intl", 1, 0.0, 0.0, True
    return "unknown", 1, 0.0, 0.0, False


def build_report(db, days: int) -> dict:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    start = now - timedelta(days=max(1, int(days)))
    rows = (
        db.query(BillingLedger.model, func.coalesce(func.sum(BillingLedger.tokens), 0))
        .filter(
            BillingLedger.entry_type == "consume",
            BillingLedger.created_at >= start,
            BillingLedger.created_at < now,
        )
        .group_by(BillingLedger.model)
        .all()
    )
    catalog = _catalog_map()
    per_model = []
    total_credits = 0
    intl_credits = 0
    rev_usd = 0.0
    cost_usd = 0.0
    kind_sum: dict = {}
    for model_key, credits in rows:
        credits = int(credits or 0)
        if credits <= 0:
            continue
        kind, mult, cin, cout, is_intl = _classify(model_key, catalog)
        if kind == "smoke" or str(model_key).strip().lower() in ("smoke", "test"):
            continue
        total_credits += credits
        kind_sum[kind] = kind_sum.get(kind, 0) + credits
        if is_intl:
            intl_credits += credits
        raw = credits / max(1, mult)
        revenue = credits / 1_000_000.0 * FLASH_USD_PER_M
        cost = raw / 1_000_000.0 * ((cin + cout) / 2.0)
        rev_usd += revenue
        cost_usd += cost
        gm = (revenue - cost) / revenue * 100 if revenue > 0 else 0.0
        per_model.append(
            {
                "model": str(model_key or ""),
                "kind": kind,
                "mult": mult,
                "credits": credits,
                "pct": 0.0,
                "gm_pct": round(gm, 1),
            }
        )
    for row in per_model:
        row["pct"] = round(row["credits"] / total_credits * 100, 2) if total_credits else 0.0
    per_model.sort(key=lambda r: -r["credits"])
    intl_pct = round(intl_credits / total_credits * 100, 2) if total_credits else 0.0
    gm_pct = round((rev_usd - cost_usd) / rev_usd * 100, 1) if rev_usd > 0 else 0.0
    return {
        "start": start.date().isoformat(),
        "end": now.date().isoformat(),
        "days": int(days),
        "total_credits": total_credits,
        "intl_pct": intl_pct,
        "gm_pct": gm_pct,
        "rev_usd": round(rev_usd, 2),
        "cost_usd_est": round(cost_usd, 2),
        "kind_sum": {
            k: round(v / total_credits * 100, 1) if total_credits else 0.0
            for k, v in sorted(kind_sum.items(), key=lambda x: -x[1])
        },
        "top_models": per_model[:12],
        "thresholds": {
            "intl_yellow": _env_float("MARGIN_GUARD_INTL_YELLOW", 10),
            "intl_red": _env_float("MARGIN_GUARD_INTL_RED", 20),
            "gm_yellow": _env_float("MARGIN_GUARD_GM_YELLOW", 25),
            "gm_red": _env_float("MARGIN_GUARD_GM_RED", 20),
        },
    }


def alarm_level(rep: dict) -> str:
    t = rep["thresholds"]
    red = rep["intl_pct"] >= t["intl_red"] or rep["gm_pct"] <= t["gm_red"]
    yellow = rep["intl_pct"] >= t["intl_yellow"] or rep["gm_pct"] <= t["gm_yellow"]
    if red:
        return "RED"
    if yellow:
        return "YELLOW"
    return "OK"


def maybe_feishu(text: str) -> None:
    url = (os.getenv("FEISHU_WEBHOOK_URL") or "").strip()
    if not url:
        print("[feishu] FEISHU_WEBHOOK_URL 未配置，跳过推送", file=sys.stderr)
        return
    try:
        import httpx

        r = httpx.post(url, json={"msg_type": "text", "content": {"text": text}}, timeout=10.0)
        if r.status_code >= 400:
            print(f"[feishu] HTTP {r.status_code}: {r.text[:200]}", file=sys.stderr)
        else:
            print("[feishu] ok", file=sys.stderr)
    except Exception as e:  # pragma: no cover
        print(f"[feishu skipped] {e}", file=sys.stderr)


def main() -> int:
    ap = argparse.ArgumentParser(description="AI24X 毛利守卫")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    db = SessionLocal()
    try:
        rep = build_report(db, args.days)
    finally:
        db.close()
    level = alarm_level(rep)
    t = rep["thresholds"]
    lines = [
        f"[AI24X 毛利守卫] 最近 {rep['days']} 天 · {rep['start']} ~ {rep['end']}",
        f"等级: {level}",
        f"总消耗 credits: {rep['total_credits']:,}",
        f"国际旗舰占比: {rep['intl_pct']}% (黄 {t['intl_yellow']}% / 红 {t['intl_red']}%)",
        f"估算混合毛利: {rep['gm_pct']}% (黄 {t['gm_yellow']}% / 红 {t['gm_red']}%)",
        f"收入估算: ${rep['rev_usd']:.4f} | 成本估算(1:1保守): ${rep['cost_usd_est']:.4f}",
        "分类占比: " + (" | ".join(f"{k}={v}%" for k, v in rep["kind_sum"].items()) or "无"),
        "Top 模型:",
    ]
    for r in rep["top_models"]:
        lines.append(f"  {r['model']} [{r['kind']}] {r['pct']}% · GM≈{r['gm_pct']}%")
    if level != "OK":
        lines.append(
            "建议: 国际旗舰占比超限→上调对应 mult 或临时限流点名模；"
            "毛利超限→检查上游涨价 / 流量结构 / 双价改造排期。"
        )
    text = "\n".join(lines)
    print(text)
    if args.json:
        print("--- json ---")
        print(json.dumps(rep, ensure_ascii=False, indent=2, default=str))
    if level != "OK":
        maybe_feishu(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
