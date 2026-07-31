"""
模型仓库（运营统筹）：档位 ↔ 上游、成本、容灾链、套餐毛利、VIP 自选规划。

覆盖文件：api/data/model_warehouse_override.json
优先级：覆盖 > env OPENROUTER_MODEL_* / 直连默认 > 代码目录
"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Optional

_OVERRIDE_PATH = Path(__file__).resolve().parent / "data" / "model_warehouse_override.json"

# 粗算上游价（USD / 1M tokens；以公开挂牌量级，非实时账单）
# in=input out=output；展示用 blended≈ (in+out)/2
CATALOG: list[dict[str, Any]] = [
    {
        "id": "ds-v4-flash",
        "title": "DeepSeek V4 Flash",
        "brand_tiers": ["auto", "flash"],
        "layer": "L1",
        "role": "default_flash",
        "priority": 1,
        "openrouter_id": "deepseek/deepseek-v4-flash",
        "direct_id": "deepseek-v4-flash",
        "cost_in": 0.14,
        "cost_out": 0.28,
        "quality": "高性价比默认",
        "access": "live",  # live | ready | planned
        "failover_to": ["silicon-qwen", "or-auto"],
    },
    {
        "id": "ds-v4-pro",
        "title": "DeepSeek V4 Pro",
        "brand_tiers": ["pro"],
        "layer": "L2",
        "role": "default_pro",
        "priority": 1,
        "openrouter_id": "deepseek/deepseek-v4-pro",
        "direct_id": "deepseek-v4-pro",
        "cost_in": 0.435,
        "cost_out": 0.87,
        "quality": "推理加强",
        "access": "live",
        "failover_to": ["ds-v4-flash"],
    },
    {
        "id": "or-gpt4o-mini",
        "title": "GPT-4o mini",
        "brand_tiers": ["ultra"],
        "layer": "L3",
        "role": "default_ultra",
        "priority": 1,
        "openrouter_id": "openai/gpt-4o-mini",
        "direct_id": None,
        "cost_in": 0.15,
        "cost_out": 0.60,
        "quality": "国际轻量",
        "access": "live",
        "failover_to": ["ds-v4-pro"],
    },
    {
        "id": "silicon-qwen",
        "title": "硅基 Qwen2.5-7B",
        "brand_tiers": ["shared", "auto"],
        "layer": "L0",
        "role": "fallback_l0",
        "priority": 1,
        "openrouter_id": None,
        "direct_id": "Qwen/Qwen2.5-7B-Instruct",
        "provider_hint": "siliconflow",
        "cost_in": 0.0,
        "cost_out": 0.0,
        "quality": "免费/极低价兜底",
        "access": "ready",
        "failover_to": ["or-auto"],
    },
    {
        "id": "or-auto",
        "title": "OpenRouter Auto / Free",
        "brand_tiers": ["shared"],
        "layer": "L0",
        "role": "or_fallback",
        "priority": 2,
        "openrouter_id": "openrouter/auto",
        "direct_id": None,
        "cost_in": 0.0,
        "cost_out": 0.0,
        "quality": "OR 自动/免费池",
        "access": "ready",
        "failover_to": [],
    },
    {
        "id": "mimo-v25",
        "title": "Xiaomi MiMo v2.5",
        "brand_tiers": ["flash"],
        "layer": "L1",
        "role": "capability_alt",
        "priority": 2,
        "openrouter_id": "xiaomi/mimo-v2.5",
        "direct_id": None,
        "cost_in": 0.2,
        "cost_out": 0.4,
        "quality": "能力向备选（非默认）",
        "access": "planned",
        "failover_to": ["ds-v4-flash"],
    },
    {
        "id": "qwen-eu",
        "title": "Qwen 2.5 72B（国际/EU）",
        "brand_tiers": ["auto"],
        "layer": "QI",
        "role": "eu_route",
        "priority": 1,
        "openrouter_id": "qwen/qwen-2.5-72b-instruct",
        "direct_id": None,
        "cost_in": 0.1,
        "cost_out": 0.3,
        "quality": "区域路由",
        "access": "planned",
        "failover_to": ["ds-v4-flash"],
    },
    # —— VIP 自选：中国名模优先（OR 有则走 OR；冲模用户）——
    {
        "id": "vip-ds-flash",
        "title": "DeepSeek V4 Flash（点名）",
        "brand_tiers": ["vip_pick"],
        "layer": "VIP",
        "role": "vip_pick",
        "priority": 1,
        "openrouter_id": "deepseek/deepseek-v4-flash",
        "direct_id": "deepseek-v4-flash",
        "cost_in": 0.14,
        "cost_out": 0.28,
        "billing_mult": 1,
        "quality": "中国名模·省",
        "access": "planned",
        "failover_to": ["ds-v4-flash"],
    },
    {
        "id": "vip-ds-pro",
        "title": "DeepSeek V4 Pro（点名）",
        "brand_tiers": ["vip_pick"],
        "layer": "VIP",
        "role": "vip_pick",
        "priority": 2,
        "openrouter_id": "deepseek/deepseek-v4-pro",
        "direct_id": "deepseek-v4-pro",
        "cost_in": 0.435,
        "cost_out": 0.87,
        "billing_mult": 3,
        "quality": "中国名模·强",
        "access": "planned",
        "failover_to": ["ds-v4-pro"],
    },
    {
        "id": "vip-kimi",
        "title": "Kimi / Moonshot（OR）",
        "brand_tiers": ["vip_pick"],
        "layer": "VIP",
        "role": "vip_pick",
        "priority": 3,
        "openrouter_id": "moonshotai/kimi-k2",
        "direct_id": None,
        "cost_in": 0.5,
        "cost_out": 2.0,
        "billing_mult": 4,
        "quality": "中国名模·Kimi（K2/Kimi3 口头；id 按 OR 挂牌校准）",
        "access": "planned",
        "failover_to": ["ds-v4-pro"],
    },
    {
        "id": "vip-mimo",
        "title": "小米 MiMo（OR）",
        "brand_tiers": ["vip_pick"],
        "layer": "VIP",
        "role": "vip_pick",
        "priority": 4,
        "openrouter_id": "xiaomi/mimo-v2.5",
        "direct_id": None,
        "cost_in": 0.2,
        "cost_out": 0.4,
        "billing_mult": 2,
        "quality": "中国名模·小米 MiMo（id 按 OR 挂牌校准）",
        "access": "planned",
        "failover_to": ["ds-v4-flash"],
    },
    {
        "id": "vip-minimax",
        "title": "MiniMax M2（OR）",
        "brand_tiers": ["vip_pick"],
        "layer": "VIP",
        "role": "vip_pick",
        "priority": 5,
        "openrouter_id": "minimax/minimax-m2",
        "direct_id": None,
        "cost_in": 0.3,
        "cost_out": 1.2,
        "billing_mult": 4,
        "quality": "中国名模·MiniMax（id 按 OR 挂牌校准）",
        "access": "planned",
        "failover_to": ["ds-v4-pro"],
    },
    {
        "id": "vip-qwen-max",
        "title": "Qwen（国际/Max 档）",
        "brand_tiers": ["vip_pick"],
        "layer": "VIP",
        "role": "vip_pick",
        "priority": 6,
        "openrouter_id": "qwen/qwen-2.5-72b-instruct",
        "direct_id": None,
        "cost_in": 0.1,
        "cost_out": 0.3,
        "billing_mult": 2,
        "quality": "中国名模·通义系",
        "access": "planned",
        "failover_to": ["ds-v4-flash"],
    },
    {
        "id": "vip-glm",
        "title": "智谱 GLM（OR）",
        "brand_tiers": ["vip_pick"],
        "layer": "VIP",
        "role": "vip_pick",
        "priority": 7,
        "openrouter_id": "z-ai/glm-4.5",
        "direct_id": None,
        "cost_in": 0.2,
        "cost_out": 0.8,
        "billing_mult": 3,
        "quality": "中国名模·智谱 GLM（id 上线前按 OR 挂牌改）",
        "access": "planned",
        "failover_to": ["ds-v4-flash"],
    },
    # —— VIP 自选：国际旗舰（次优先）——
    {
        "id": "vip-gpt4o",
        "title": "OpenAI GPT-4o",
        "brand_tiers": ["vip_pick"],
        "layer": "VIP",
        "role": "vip_pick",
        "priority": 10,
        "openrouter_id": "openai/gpt-4o",
        "direct_id": None,
        "cost_in": 2.5,
        "cost_out": 10.0,
        # 开发包 $20/50万平台额度 → 约 $40/百万平台 token；×14 覆盖 OR gpt-4o 进出价并留余量
        "billing_mult": 14,
        "quality": "国际旗舰",
        "access": "ready",
        "failover_to": ["vip-gpt4o-mini", "vip-ds-pro"],
    },
    {
        "id": "vip-gpt4o-mini",
        "title": "OpenAI GPT-4o mini",
        "brand_tiers": ["vip_pick"],
        "layer": "VIP",
        "role": "vip_pick",
        "priority": 13,
        "openrouter_id": "openai/gpt-4o-mini",
        "direct_id": None,
        "cost_in": 0.15,
        "cost_out": 0.6,
        "billing_mult": 4,
        "quality": "国际轻量·性价比",
        "access": "ready",
        "failover_to": ["vip-ds-flash", "ds-v4-flash"],
    },
    {
        "id": "vip-claude-sonnet",
        "title": "Anthropic Claude Sonnet",
        "brand_tiers": ["vip_pick"],
        "layer": "VIP",
        "role": "vip_pick",
        "priority": 11,
        "openrouter_id": "anthropic/claude-sonnet-4",
        "direct_id": None,
        "cost_in": 3.0,
        "cost_out": 15.0,
        # 输出向最贵；×18 保证即全输出也不倒挂（相对 $40/M 平台价）
        "billing_mult": 18,
        "quality": "写作/推理优质",
        "access": "ready",
        "failover_to": ["vip-claude-haiku", "vip-ds-pro"],
    },
    {
        "id": "vip-claude-haiku",
        "title": "Anthropic Claude Haiku",
        "brand_tiers": ["vip_pick"],
        "layer": "VIP",
        "role": "vip_pick",
        "priority": 14,
        "openrouter_id": "anthropic/claude-3.5-haiku",
        "direct_id": None,
        "cost_in": 0.8,
        "cost_out": 4.0,
        "billing_mult": 6,
        "quality": "国际轻量·快",
        "access": "ready",
        "failover_to": ["vip-ds-flash", "ds-v4-flash"],
    },
    {
        "id": "vip-gemini-pro",
        "title": "Google Gemini Pro",
        "brand_tiers": ["vip_pick"],
        "layer": "VIP",
        "role": "vip_pick",
        "priority": 12,
        "openrouter_id": "google/gemini-2.5-pro",
        "direct_id": None,
        "cost_in": 1.25,
        "cost_out": 10.0,
        "billing_mult": 12,
        "quality": "长上下文",
        "access": "ready",
        "failover_to": ["vip-gemini-flash", "vip-ds-pro"],
    },
    {
        "id": "vip-gemini-flash",
        "title": "Google Gemini Flash",
        "brand_tiers": ["vip_pick"],
        "layer": "VIP",
        "role": "vip_pick",
        "priority": 15,
        "openrouter_id": "google/gemini-2.5-flash",
        "direct_id": None,
        "cost_in": 0.15,
        "cost_out": 0.6,
        "billing_mult": 4,
        "quality": "国际轻量·长上下文",
        "access": "ready",
        "failover_to": ["vip-ds-flash", "ds-v4-flash"],
    },
]


def _load_ov() -> dict[str, Any]:
    try:
        if not _OVERRIDE_PATH.is_file():
            return {}
        raw = json.loads(_OVERRIDE_PATH.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def _save_ov(data: dict[str, Any]) -> None:
    _OVERRIDE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _OVERRIDE_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def layer_model_override(layer: str) -> Optional[str]:
    ov = _load_ov()
    layers = ov.get("layers") if isinstance(ov.get("layers"), dict) else {}
    row = layers.get(str(layer).upper()) if isinstance(layers, dict) else None
    if not isinstance(row, dict):
        return None
    m = (row.get("model") or "").strip()
    return m or None


def vip_pick_enabled() -> bool:
    ov = _load_ov()
    if "vip_pick_enabled" in ov:
        return bool(ov.get("vip_pick_enabled"))
    return True  # 默认开：高阶 VIP 可点名中国模


def resolve_vip_pick(requested_model: Optional[str]) -> Optional[dict[str, Any]]:
    """若请求是 VIP 点名模，返回目录行（含 openrouter_id / billing_mult）；否则 None。"""
    raw = (requested_model or "").strip()
    if not raw:
        return None
    key = raw.lower()
    # 去掉常见前缀
    for prefix in ("vip:", "vip-", "named:", "pick:"):
        if key.startswith(prefix):
            key = key[len(prefix) :].lstrip("-:")
            break
    aliases = {
        "kimi": "vip-kimi",
        "moonshot": "vip-kimi",
        "kimi-k2": "vip-kimi",
        "kimi3": "vip-kimi",
        "kimi-3": "vip-kimi",
        "mimo": "vip-mimo",
        "xiaomi-mimo": "vip-mimo",
        "xiaomi": "vip-mimo",
        "minimax": "vip-minimax",
        "minimax-m2": "vip-minimax",
        "glm": "vip-glm",
        "zhipu": "vip-glm",
        "zhipu-glm": "vip-glm",
        "qwen": "vip-qwen-max",
        "deepseek": "vip-ds-flash",
        "deepseek-flash": "vip-ds-flash",
        "deepseek-pro": "vip-ds-pro",
        "ds-flash": "vip-ds-flash",
        "ds-pro": "vip-ds-pro",
        "gpt4o": "vip-gpt4o",
        "gpt-4o": "vip-gpt4o",
        "openai": "vip-gpt4o",
        "gpt4o-mini": "vip-gpt4o-mini",
        "gpt-4o-mini": "vip-gpt4o-mini",
        "claude": "vip-claude-sonnet",
        "claude-sonnet": "vip-claude-sonnet",
        "sonnet": "vip-claude-sonnet",
        "claude-haiku": "vip-claude-haiku",
        "haiku": "vip-claude-haiku",
        "gemini": "vip-gemini-pro",
        "gemini-pro": "vip-gemini-pro",
        "gemini-flash": "vip-gemini-flash",
    }
    cid = aliases.get(key, key if key.startswith("vip-") else "")
    if not cid:
        # 直接匹配 catalog id
        cid = key if any(c["id"] == key for c in CATALOG) else ""
    if not cid:
        return None
    for c in CATALOG:
        if c.get("role") != "vip_pick":
            continue
        if str(c.get("id")) != cid:
            continue
        if not c.get("openrouter_id") and not c.get("direct_id"):
            return None
        return dict(c)
    return None


def list_vip_picks_for_user(*, is_vip: bool) -> list[dict[str, Any]]:
    """控制台可选点名列表（中国模优先）。非 VIP 也返回目录但 locked。"""
    enabled = vip_pick_enabled()
    out = []
    for c in sorted(
        [x for x in CATALOG if x.get("role") == "vip_pick"],
        key=lambda x: int(x.get("priority") or 99),
    ):
        # 国际旗舰次优先：仍列出，标注 intl
        is_intl = str(c.get("id") or "").startswith("vip-gpt") or "claude" in str(
            c.get("id")
        ) or "gemini" in str(c.get("id") or "")
        out.append(
            {
                "id": c["id"],
                "title": c.get("title") or c["id"],
                "model": c["id"],
                "billing_mult": int(c.get("billing_mult") or 1),
                "quality": c.get("quality") or "",
                "group": "intl" if is_intl else "china",
                "locked": (not is_vip) or (not enabled),
                "enabled_platform": enabled,
            }
        )
    return out


def vip_pick_models() -> list[str]:
    ov = _load_ov()
    raw = ov.get("vip_pick_models")
    if isinstance(raw, list) and raw:
        return [str(x).strip() for x in raw if str(x).strip()]
    return [
        str(c["openrouter_id"])
        for c in CATALOG
        if c.get("role") == "vip_pick" and c.get("openrouter_id")
    ]


def _blended(c: dict[str, Any]) -> float:
    return round((float(c.get("cost_in") or 0) + float(c.get("cost_out") or 0)) / 2.0, 4)


def warehouse_snapshot() -> dict[str, Any]:
    from model_router import (
        CHAIN_FREE,
        CHAIN_VIP,
        _OR_DEFAULT_MODELS,
        _layer_upstream,
        _upstream_mode,
        list_models_public,
    )
    from token_plans import list_public_plans

    mode = _upstream_mode()
    ov = _load_ov()
    layer_ov = ov.get("layers") if isinstance(ov.get("layers"), dict) else {}

    layers_live: dict[str, Any] = {}
    for ly in ("L0", "L1", "L2", "L3", "QI"):
        info = _layer_upstream(ly)
        ov_model = None
        if isinstance(layer_ov.get(ly), dict):
            ov_model = (layer_ov[ly].get("model") or "").strip() or None
        enabled = True
        if isinstance(layer_ov.get(ly), dict) and "enabled" in layer_ov[ly]:
            enabled = bool(layer_ov[ly]["enabled"])
        layers_live[ly] = {
            "layer": ly,
            "provider": info.get("provider"),
            "model": ov_model or info.get("model"),
            "default_model": _OR_DEFAULT_MODELS.get(ly) if mode == "openrouter" else info.get("model"),
            "key_set": bool(info.get("key")),
            "enabled": enabled,
            "source": "admin" if ov_model else "env/default",
        }

    pub = list_models_public(is_vip=True)
    brand_rows = []
    brand_layer = {"auto": "L1", "flash": "L1", "pro": "L2", "ultra": "L3"}
    for bid, title in (pub.get("brand") or {}).items():
        layer = brand_layer.get(bid, "L1")
        live = layers_live.get(layer) or {}
        brand_rows.append(
            {
                "brand": bid,
                "title": title,
                "maps_to_layer": layer,
                "upstream_model": live.get("model") or "—",
                "chain_free": " → ".join(CHAIN_FREE),
                "chain_vip": " → ".join(CHAIN_VIP),
            }
        )

    catalog_out = []
    for c in CATALOG:
        row = deepcopy(c)
        row["cost_blended_usd_per_m"] = _blended(c)
        ly = str(c.get("layer") or "")
        live = layers_live.get(ly) or {}
        key_ok = bool(live.get("key_set")) if ly in layers_live else False
        # 接入状态：规划 / 缺 Key / 在线路由中
        access = str(c.get("access") or "planned")
        if access == "planned":
            runtime = "planned"
        elif ly == "VIP":
            runtime = "vip_pick_planned" if not vip_pick_enabled() else ("ready" if key_ok else "need_key")
        elif key_ok and live.get("enabled", True):
            # 当前层实际模型是否匹配
            cur = str(live.get("model") or "")
            want = str(c.get("openrouter_id") or c.get("direct_id") or "")
            runtime = "active" if want and want in cur else "standby"
        elif key_ok:
            runtime = "disabled"
        else:
            runtime = "need_key"
        row["runtime"] = runtime
        row["billing_mult"] = int(c.get("billing_mult") or (1 if ly != "VIP" else 10))
        catalog_out.append(row)

    plans = list_public_plans()
    plan_margin = []
    flash_cost = _blended(next(x for x in CATALOG if x["id"] == "ds-v4-flash"))
    for p in plans:
        tokens = int(p.get("credit_tokens") or 0)
        usd = float(p.get("price_usd") or 0) if p.get("price_usd") else None
        if usd is None and p.get("price_fen"):
            usd = round(int(p["price_fen"]) / 100.0 / 7.2, 4)
        est_cost = round((tokens / 1_000_000.0) * flash_cost, 4) if tokens else None
        margin = round((usd or 0) - (est_cost or 0), 4) if usd is not None and est_cost is not None else None
        plan_margin.append(
            {
                "plan": p.get("plan"),
                "title": p.get("title_zh") or p.get("title"),
                "price_usd": usd,
                "price_fen": p.get("price_fen"),
                "credit_tokens": tokens,
                "est_upstream_if_all_flash_usd": est_cost,
                "est_gross_usd": margin,
                "note": "毛利按 Flash 混合成本粗算；实际随档位/用量变",
            }
        )

    failover = {
        "free_chain": CHAIN_FREE,
        "vip_chain": CHAIN_VIP,
        "note": "层内失败自动下一档；OR↔直连不自动切换，须改上游模式。",
        "mode": mode,
        "risks": [
            {
                "if_down": "L1 Flash",
                "then": "FREE→L0（硅基/OR auto）；VIP→L2 Pro",
                "mitigation": "配齐 SILICONFLOW 或 OR L0",
            },
            {
                "if_down": "OpenRouter 整站",
                "then": "改上游模式=direct + DeepSeek Key",
                "mitigation": "管理台一键切 direct（须已配 DeepSeek）",
            },
            {
                "if_down": "DeepSeek 直连",
                "then": "切回 openrouter",
                "mitigation": "保持 OR Key 有余额",
            },
        ],
    }

    return {
        "ok": True,
        "upstream_mode": mode,
        "brand_map": brand_rows,
        "layers": layers_live,
        "catalog": catalog_out,
        "failover": failover,
        "plans_margin": plan_margin,
        "vip_pick": {
            "enabled": vip_pick_enabled(),
            "models": vip_pick_models(),
            "note": (
                "高阶 VIP 自选通道：用户控制台可选 OR 国际优质模型；"
                "扣费按 billing_mult × 平台 token 单价（规划中，开关打开后下期接控制台）。"
            ),
        },
        "ops_note": (
            "付费仓：改层 model 后保存即生效。"
            "容灾已内置 FREE：L1→L0；VIP：L1→L2→L3（挂了自动下一档）。"
            "与免费共享池调度独立。VIP 自选为规划能力。"
        ),
    }


def update_warehouse(patch: dict[str, Any]) -> dict[str, Any]:
    cur = _load_ov()
    layers = dict(cur.get("layers") or {}) if isinstance(cur.get("layers"), dict) else {}

    for item in patch.get("layers") or []:
        if not isinstance(item, dict):
            continue
        ly = str(item.get("layer") or "").strip().upper()
        if ly not in ("L0", "L1", "L2", "L3", "QI"):
            continue
        row = dict(layers.get(ly) or {})
        if item.get("model") is not None:
            m = str(item.get("model") or "").strip()
            if m:
                row["model"] = m
            elif "model" in row:
                del row["model"]
        if item.get("enabled") is not None:
            row["enabled"] = bool(item["enabled"])
        layers[ly] = row

    cur["layers"] = layers
    if patch.get("vip_pick_enabled") is not None:
        cur["vip_pick_enabled"] = bool(patch["vip_pick_enabled"])
    if patch.get("vip_pick_models") is not None:
        cur["vip_pick_models"] = [
            str(x).strip() for x in (patch.get("vip_pick_models") or []) if str(x).strip()
        ][:32]
    if patch.get("note") is not None:
        cur["note"] = str(patch.get("note") or "")[:200]

    _save_ov(cur)
    return warehouse_snapshot()
