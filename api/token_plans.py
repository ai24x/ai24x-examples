"""
Token 产品套餐目录（与 a1 行情官 VIP 配额套餐完全独立）。

价格可用环境变量覆盖（分）：TOKEN_PRICE_<PLAN_UPPER>_FEN
"""
from __future__ import annotations

import os
from typing import Any


def _price(env_key: str, default_fen: int) -> int:
    raw = (os.getenv(env_key) or "").strip()
    if not raw:
        return int(default_fen)
    try:
        v = int(raw)
        return v if v > 0 else int(default_fen)
    except ValueError:
        return int(default_fen)


# plan_id -> definition
# credit_tokens: 到账 token；set_vip: 是否升级钱包 plan=VIP（享受日赠额度）
TOKEN_PLANS: dict[str, dict[str, Any]] = {
    "token_pack_10k": {
        "title": "Token 加油包 1万",
        "price_fen": _price("TOKEN_PRICE_TOKEN_PACK_10K_FEN", 990),
        "credit_tokens": 10_000,
        "set_vip": False,
        "enabled": True,
    },
    "token_pack_100k": {
        "title": "Token 加油包 10万",
        "price_fen": _price("TOKEN_PRICE_TOKEN_PACK_100K_FEN", 6900),
        "credit_tokens": 100_000,
        "set_vip": False,
        "enabled": True,
    },
    "token_vip_month": {
        "title": "Token VIP 月卡",
        "price_fen": _price("TOKEN_PRICE_TOKEN_VIP_MONTH_FEN", 1990),
        "credit_tokens": 0,
        "set_vip": True,
        "vip_days": 30,
        "enabled": True,
        "note": "开通 VIP 30 天：每日赠送额度见 vip_daily_bonus（默认 50 万）",
    },
    "token_vip_month_50w": {
        "title": "Token VIP 月卡 + 50万到账",
        "price_fen": _price("TOKEN_PRICE_TOKEN_VIP_MONTH_50W_FEN", 4990),
        "credit_tokens": 500_000,
        "set_vip": True,
        "vip_days": 30,
        "enabled": True,
    },
}


def list_public_plans() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for plan_id, p in TOKEN_PLANS.items():
        if not p.get("enabled", True):
            continue
        out.append(
            {
                "plan": plan_id,
                "title": p["title"],
                "price_fen": int(p["price_fen"]),
                "price_yuan": f"{int(p['price_fen']) / 100:.2f}",
                "credit_tokens": int(p.get("credit_tokens") or 0),
                "set_vip": bool(p.get("set_vip")),
                "vip_days": int(p.get("vip_days") or 0) or None,
                "note": p.get("note") or "",
            }
        )
    return out


def get_plan(plan_id: str) -> dict[str, Any] | None:
    pid = (plan_id or "").strip()
    p = TOKEN_PLANS.get(pid)
    if not p or not p.get("enabled", True):
        return None
    return {"plan": pid, **p}


def normalize_plan(plan_id: str) -> tuple[str, int]:
    """返回 (plan_id, price_fen)；非法则抛 ValueError。"""
    p = get_plan(plan_id)
    if not p:
        raise ValueError(f"unknown_or_disabled_plan:{plan_id}")
    return str(p["plan"]), int(p["price_fen"])
