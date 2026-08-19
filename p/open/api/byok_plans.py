"""
BYOK 网关服务费套餐（Bring Your Own Key）。

计费口径：平台只收「网关服务费」，不赚上游 token 差价；用户 key 直接消耗其
自有上游额度。套餐履约（支付成功）后由 token_pay_service 调 byok.activate_subscription
写入 byok_subscriptions 表。

Phase 1 为统计展示；支付链路（PayPal/微信/支付宝/Creem/Mock）复用 token_pay_service。
"""

from __future__ import annotations

import os
from copy import deepcopy
from typing import Any


def _usd_cny() -> float:
    raw = (os.getenv("TOKEN_USD_CNY") or "7.2").strip()
    try:
        v = float(raw)
        return v if v > 0 else 7.2
    except ValueError:
        return 7.2


def _fen_from_usd(usd: float) -> int:
    return max(1, int(round(float(usd) * _usd_cny() * 100)))


# BYOK 服务费套餐目录（价格可经 env 覆盖：BYOK_PRICE_PRO_MONTH_USD / BYOK_PRICE_PRO_YEAR_USD）
_BYOK_PLAN_DEFAULTS: dict[str, dict[str, Any]] = {
    "byok_pro_month": {
        "title_zh": "BYOK Pro 月付",
        "title_en": "BYOK Pro · Monthly",
        "price_usd": 9.9,
        "days": 30,
        "recommended": False,
        "features_zh": [
            "无限 BYOK 智能路由（用户自有 key）",
            "同模型多 key 负载均衡 + 故障转移",
            "请求缓存（省自有 key token 成本）",
            "完整成本看板：按 key / 模型 / 项目",
            "多 key 打标签 + 额度监控",
        ],
        "features_en": [
            "Unlimited BYOK smart routing (your own keys)",
            "Multi-key load balancing + failover",
            "Request cache (saves your key tokens)",
            "Full cost dashboard: by key / model / project",
            "Multiple tagged keys + quota monitoring",
        ],
        "one_liner_zh": "月度订阅 · 平台服务费",
        "one_liner_en": "Monthly service fee",
    },
    "byok_pro_year": {
        "title_zh": "BYOK Pro 年付",
        "title_en": "BYOK Pro · Yearly",
        "price_usd": 99.0,
        "days": 365,
        "recommended": True,
        "features_zh": [
            "包含 BYOK Pro 月付全部权益",
            "年付立省 17%（$9.9×12 → $99）",
            "优先故障转移 + 缓存容量提升",
            "开发者文档与社群支持",
        ],
        "features_en": [
            "Everything in BYOK Pro Monthly",
            "Save 17% vs monthly ($9.9×12 → $99)",
            "Priority failover + larger cache",
            "Developer docs & community support",
        ],
        "one_liner_zh": "年度订阅 · 立省 17%",
        "one_liner_en": "Yearly · save 17%",
    },
}


def _price_usd(plan_id: str, base: dict[str, Any]) -> float:
    env_key = {
        "byok_pro_month": "BYOK_PRICE_PRO_MONTH_USD",
        "byok_pro_year": "BYOK_PRICE_PRO_YEAR_USD",
    }.get(plan_id, "")
    raw = (os.getenv(env_key) or "").strip() if env_key else ""
    try:
        v = float(raw)
        return v if v > 0 else float(base.get("price_usd") or 0)
    except (TypeError, ValueError):
        return float(base.get("price_usd") or 0)


def resolve_byok_plan(plan_id: str) -> dict[str, Any] | None:
    """返回 BYOK 套餐快照（含实时价格 / CNY 分），未知 plan 返回 None。"""
    base = _BYOK_PLAN_DEFAULTS.get(plan_id or "")
    if not base:
        return None
    p = deepcopy(base)
    usd = _price_usd(plan_id, base)
    p["price_usd"] = round(usd, 2)
    p["price_fen"] = _fen_from_usd(usd)
    return p


def public_byok_plans() -> list[dict[str, Any]]:
    """公开 BYOK 套餐目录（仅服务费套餐，不含任何 key 信息）。"""
    out: list[dict[str, Any]] = []
    for pid in ("byok_pro_month", "byok_pro_year"):
        p = resolve_byok_plan(pid)
        if not p:
            continue
        out.append(
            {
                "plan": pid,
                "title_zh": p["title_zh"],
                "title_en": p["title_en"],
                "price_usd": p["price_usd"],
                "price_fen": p["price_fen"],
                "days": p["days"],
                "recommended": bool(p.get("recommended")),
                "features_zh": p.get("features_zh") or [],
                "features_en": p.get("features_en") or [],
                "one_liner_zh": p.get("one_liner_zh") or "",
                "one_liner_en": p.get("one_liner_en") or "",
                "product": "byok",
            }
        )
    return out


def is_byok_plan(plan_id: str) -> bool:
    return bool(_BYOK_PLAN_DEFAULTS.get(plan_id or ""))
