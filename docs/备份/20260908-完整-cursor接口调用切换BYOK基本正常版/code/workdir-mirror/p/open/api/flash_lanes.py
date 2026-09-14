# -*- coding: utf-8 -*-
"""Flash / Auto（L1）候选通道价表与一键切换。

管理台：供应链监控 → Flash 通道价表（成本从低到高）→ 一键切主通道。
写回：system_flags.token_llm_l1_lane + warehouse layers.L1.model（立即生效）。
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import model_warehouse as mw

_HERO_AUDIT_PATH = Path(__file__).resolve().parent / "data" / "hero_apply_audit.jsonl"

_FLASH_LANE_META: dict[str, dict[str, Any]] = {
    "mimo_official": {
        "label": "MiMo 官方",
        "family": "MiMo",
        "via": "官方直连",
        "health_pid": "mimo",
        "or_id": "xiaomi/mimo-v2.5",
        "model": "mimo-v2.5",
        "warehouse_model": "xiaomi/mimo-v2.5",
        "quality_note": "同价档主力；官方直连延迟通常优于聚合",
    },
    "or_mimo": {
        "label": "MiMo · OpenRouter",
        "family": "MiMo",
        "via": "OpenRouter",
        "health_pid": "openrouter",
        "or_id": "xiaomi/mimo-v2.5",
        "model": "xiaomi/mimo-v2.5",
        "warehouse_model": "xiaomi/mimo-v2.5",
        "quality_note": "同模型经聚合；作官方不可用时的备选",
    },
    "or_deepseek": {
        "label": "DeepSeek · OpenRouter",
        "family": "DeepSeek",
        "via": "OpenRouter",
        "health_pid": "openrouter",
        "or_id": "deepseek/deepseek-v4-flash",
        "model": "deepseek/deepseek-v4-flash",
        "warehouse_model": "deepseek/deepseek-v4-flash",
        "quality_note": "能力向备选；看实拉价是否低于 MiMo",
    },
    "deepseek_official": {
        "label": "DeepSeek 官方",
        "family": "DeepSeek",
        "via": "官方直连",
        "health_pid": "deepseek",
        "or_id": "deepseek/deepseek-v4-flash",
        "model": "deepseek-v4-flash",
        "warehouse_model": "deepseek/deepseek-v4-flash",
        "quality_note": "官方涨价后通常更贵；稳但是成本压力大",
    },
}


def _catalog_cost(cid: str) -> tuple[float, float]:
    for c in mw.catalog_merged():
        if str(c.get("id") or "") == cid:
            return float(c.get("cost_in") or 0), float(c.get("cost_out") or 0)
    return 0.0, 0.0


def _or_live_pair(pp: dict[str, Any], or_id: str) -> Optional[tuple[float, float]]:
    for x in pp.get("openrouter") or []:
        if x.get("id") == or_id and x.get("pricing"):
            p = x["pricing"]
            try:
                return float(p["in"]), float(p["out"])
            except Exception:
                return None
    return None


def _flash_lane_cost(lane_id: str, pp: dict[str, Any]) -> tuple[float, float, str]:
    from price_monitor import _hike_applied

    meta = _FLASH_LANE_META[lane_id]
    or_id = str(meta["or_id"])
    if lane_id in ("or_mimo", "or_deepseek"):
        live = _or_live_pair(pp, or_id)
        if live:
            return live[0], live[1], "openrouter_live"
        if lane_id == "or_mimo":
            cin, cout = _catalog_cost("mimo-v25")
            return (cin or 0.14), (cout or 0.28), "catalog_mimo"
        cin, cout = _catalog_cost("ds-v4-flash")
        return (cin or 0.14), (cout or 0.28), "catalog_ds"
    if lane_id == "mimo_official":
        cin, cout = _catalog_cost("mimo-v25")
        return (cin or 0.14), (cout or 0.28), "catalog_mimo"
    hike = _hike_applied("vip-ds-flash")
    if hike:
        try:
            from model_router import current_period

            period = current_period()
        except Exception:
            period = "offpeak"
        if period == "peak" and hike.get("peak_in") is not None:
            return float(hike["peak_in"]), float(hike["peak_out"]), "official_peak"
        return float(hike["in"]), float(hike["out"]), "official_offpeak"
    cin, cout = _catalog_cost("ds-v4-flash")
    return (cin or 0.14), (cout or 0.28), "catalog_ds"


def _flash_lane_ready(lane_id: str) -> tuple[bool, str]:
    try:
        from model_router import _upstream_from_flash_lane

        up = _upstream_from_flash_lane(lane_id)
        if up and up.get("key"):
            return True, ""
    except Exception as e:
        return False, str(e)[:80]
    labels = {
        "mimo_official": "未配置 MiMo 密钥",
        "or_mimo": "未配置 OpenRouter 密钥",
        "or_deepseek": "未配置 OpenRouter 密钥",
        "deepseek_official": "未配置 DeepSeek 密钥",
    }
    return False, labels.get(lane_id, "通道未就绪")


def build_flash_lanes(health: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """flash/auto 候选通道：成本从低到高 + 当前生效 + 可否一键。"""
    from price_monitor import _load, _provider_health

    health = health or {"circuit": {}, "recs": {}}
    pp = _load()
    try:
        from model_router import detect_active_flash_lane

        active = detect_active_flash_lane()
    except Exception:
        active = "mimo_official"
    try:
        from system_flags import effective_l1_lane

        admin_lane = effective_l1_lane()
    except Exception:
        admin_lane = None

    ref = float(mw.flash_ref_usd_per_m() or 0.35)
    rows: list[dict[str, Any]] = []
    for lane_id, meta in _FLASH_LANE_META.items():
        cin, cout, src = _flash_lane_cost(lane_id, pp)
        blend = round((cin + cout) / 2.0, 4) if (cin or cout) else None
        sum_io = round(cin + cout, 4)
        cost_1to4 = round(cin + 4 * cout, 4)
        sell_in = sell_out = ref
        gm_1to4 = (
            round((1 - (cin + 4 * cout) / (sell_in + 4 * sell_out)) * 100, 1)
            if (sell_in + 4 * sell_out) > 0
            else None
        )
        pid = str(meta["health_pid"])
        ph = _provider_health(health, pid)
        ready, ready_reason = _flash_lane_ready(lane_id)
        circuit = bool(ph.get("circuit_open"))
        applyable = ready and not circuit and lane_id != active
        if not ready:
            reason = ready_reason
        elif circuit:
            reason = f"{meta['label']} 上游熔断中"
        elif lane_id == active:
            reason = "当前已是该通道"
        else:
            reason = f"将 flash/auto 主通道切至 {meta['label']}（立即生效）"
        rows.append(
            {
                "id": lane_id,
                "label": meta["label"],
                "family": meta["family"],
                "via": meta["via"],
                "model": meta["model"],
                "quality_note": meta["quality_note"],
                "cost_in": round(cin, 4),
                "cost_out": round(cout, 4),
                "cost_sum": sum_io,
                "cost_blend": blend,
                "cost_1to4": cost_1to4,
                "cost_source": src,
                "gm_1to4": gm_1to4,
                "sell_ref": ref,
                "ready": ready,
                "circuit_open": circuit,
                "stability": {
                    "score": ph.get("score"),
                    "sample": ph.get("sample"),
                    "fail_rate": ph.get("fail_rate"),
                },
                "active": lane_id == active,
                "applyable": applyable,
                "apply_reason": reason,
            }
        )
    rows.sort(
        key=lambda r: (
            float(r["cost_1to4"]) if r.get("cost_1to4") is not None else 1e9,
            float(r["cost_sum"]) if r.get("cost_sum") is not None else 1e9,
            str(r["id"]),
        )
    )
    cheapest = next((r for r in rows if r.get("ready") and not r.get("circuit_open")), None)
    return {
        "note": (
            "对外仍显示 flash / auto；本表按上游成本（1 入 + 4 出加权）从低到高排列。"
            "一键切换立即写回并生效，不改用户可见文案。"
        ),
        "active": active,
        "admin_override": admin_lane,
        "cheapest_ready": (cheapest or {}).get("id"),
        "lanes": rows,
    }


def apply_flash_lane(*, lane_id: str, actor: str = "admin") -> dict[str, Any]:
    """一键切换 flash/auto（L1）主通道。"""
    from price_monitor import _provider_health, snapshot

    lid = str(lane_id or "").strip().lower()
    aliases = {
        "mimo": "mimo_official",
        "or-mimo": "or_mimo",
        "or-deepseek": "or_deepseek",
        "deepseek": "deepseek_official",
        "ds": "deepseek_official",
    }
    lid = aliases.get(lid, lid)
    if lid not in _FLASH_LANE_META:
        raise ValueError(
            "未知通道，仅支持 mimo_official / or_mimo / or_deepseek / deepseek_official"
        )
    meta = _FLASH_LANE_META[lid]
    ready, ready_reason = _flash_lane_ready(lid)
    if not ready:
        raise ValueError(ready_reason or "通道未就绪")

    try:
        from upstream_health import snapshot as _uh_snapshot

        uh = _uh_snapshot() or {}
    except Exception:
        uh = {}
    pid = str(meta["health_pid"])
    if (_provider_health(uh, pid) or {}).get("circuit_open"):
        raise ValueError(f"{meta['label']} 当前熔断中，禁止切换")

    from system_flags import update_system_flags

    update_system_flags({"token_llm_l1_lane": lid})
    try:
        mw.update_warehouse(
            {
                "layers": [
                    {
                        "layer": "L1",
                        "model": str(meta.get("warehouse_model") or meta.get("model") or ""),
                    }
                ],
                "note": f"flash_lane:{lid}",
            },
            actor=str(actor or "admin")[:64],
        )
    except Exception:
        pass

    try:
        from model_router import _layer_upstream, detect_active_flash_lane

        active = detect_active_flash_lane()
        live = _layer_upstream("L1")
    except Exception:
        active = lid
        live = {}

    audit = {
        "ts": int(time.time()),
        "cst": datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S"),
        "actor": str(actor or "admin")[:64],
        "kind": "flash_lane",
        "lane": lid,
        "label": meta["label"],
        "active_after": active,
        "provider": live.get("provider"),
        "model": live.get("model"),
    }
    try:
        _HERO_AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _HERO_AUDIT_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(audit, ensure_ascii=False) + "\n")
    except Exception:
        pass

    snap = snapshot()
    return {
        "ok": True,
        "message": f"已将 flash/auto 主通道切至 {meta['label']}",
        "lane": lid,
        "label": meta["label"],
        "active": active,
        "runtime": {
            "provider": live.get("provider"),
            "model": live.get("model"),
            "key_set": bool(live.get("key")),
        },
        **{k: snap.get(k) for k in (
            "flash_lanes",
            "hero_picks",
            "summary",
            "rows",
            "generated_cst",
            "provider_prices_time",
            "flash_ref",
            "thresholds",
        )},
    }
