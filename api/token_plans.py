"""
Token 产品套餐目录（与 a1 行情官 VIP 配额套餐完全独立）。

定价口径（2026-07-26）：
- 主数据按国际价（USD 锚定，对标 OpenRouter 中国模型线 +10%～25% 便利溢价）
- 国内站收银台收 CNY（微信/支付宝）；国际站收 USD（PayPal 等）— 同一 SKU
- 价格可用环境变量覆盖（分）：TOKEN_PRICE_<PLAN_UPPER>_FEN
"""
from __future__ import annotations

import os
from typing import Any

# 展示用汇率（国内 CNY ≈ USD × 此值；可用 TOKEN_USD_CNY 覆盖）
def _usd_cny() -> float:
    raw = (os.getenv("TOKEN_USD_CNY") or "7.2").strip()
    try:
        v = float(raw)
        return v if v > 0 else 7.2
    except ValueError:
        return 7.2


def _price(env_key: str, default_fen: int) -> int:
    raw = (os.getenv(env_key) or "").strip()
    if not raw:
        return int(default_fen)
    try:
        v = int(raw)
        return v if v > 0 else int(default_fen)
    except ValueError:
        return int(default_fen)


def _fen_from_usd(usd: float) -> int:
    return max(1, int(round(float(usd) * _usd_cny() * 100)))


# 与 token_mvp_service.VIP_DAILY_BONUS_TOKENS 对齐（文案用）
_VIP_DAILY_BONUS_HINT = 100_000

# plan_id -> definition（SKU 国内外统一；仅结算通道不同）
TOKEN_PLANS: dict[str, dict[str, Any]] = {
    "token_pack_10k": {
        "title": "Starter 入门包",
        "price_usd": 5.0,
        "price_fen": _price("TOKEN_PRICE_TOKEN_PACK_10K_FEN", _fen_from_usd(5.0)),
        "credit_tokens": 100_000,
        "set_vip": False,
        "enabled": True,
        "note": "约 $5 · 国内外同一套餐；国内站微信/支付宝付人民币。",
    },
    "token_pack_100k": {
        "title": "Builder 开发包",
        "price_usd": 20.0,
        "price_fen": _price("TOKEN_PRICE_TOKEN_PACK_100K_FEN", _fen_from_usd(20.0)),
        "credit_tokens": 500_000,
        "set_vip": False,
        "enabled": True,
        "note": "约 $20 · 主力预充值；单价优于入门包。",
    },
    "token_vip_month": {
        "title": "Pro Pass 月卡",
        "price_usd": 15.0,
        "price_fen": _price("TOKEN_PRICE_TOKEN_VIP_MONTH_FEN", _fen_from_usd(15.0)),
        "credit_tokens": 0,
        "set_vip": True,
        "vip_days": 30,
        "enabled": True,
        "note": (
            f"约 $15 / 30 天 Token VIP；有效期内每日额外赠送约 {_VIP_DAILY_BONUS_HINT // 10000} 万 token。"
            "与「AI 行情官」VIP 无关。"
        ),
    },
    "token_vip_month_50w": {
        "title": "Scale 组合包",
        "price_usd": 100.0,
        "price_fen": _price("TOKEN_PRICE_TOKEN_VIP_MONTH_50W_FEN", _fen_from_usd(100.0)),
        "credit_tokens": 2_500_000,
        "set_vip": True,
        "vip_days": 30,
        "enabled": True,
        "note": (
            f"约 $100 · 立即到账 250 万 token，并开通 Pro Pass 30 天；"
            f"日赠约 {_VIP_DAILY_BONUS_HINT // 10000} 万 token。"
            "与「AI 行情官」VIP 无关。"
        ),
    },
}


def _public_note(p: dict[str, Any]) -> str:
    note = (p.get("note") or "").strip()
    if note:
        return note
    bits: list[str] = []
    credit = int(p.get("credit_tokens") or 0)
    if credit:
        bits.append(f"到账 {credit} token")
    if p.get("set_vip"):
        days = int(p.get("vip_days") or 30)
        bits.append(f"开通 Token VIP {days} 天")
        bits.append(f"每日额外赠送约 {_VIP_DAILY_BONUS_HINT // 10000} 万 token")
    return "；".join(bits)


def list_public_plans() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    fx = _usd_cny()
    for plan_id, p in TOKEN_PLANS.items():
        if not p.get("enabled", True):
            continue
        usd = float(p.get("price_usd") or 0)
        fen = int(p["price_fen"])
        out.append(
            {
                "plan": plan_id,
                "title": p["title"],
                "price_fen": fen,
                "price_yuan": f"{fen / 100:.2f}",
                "price_usd": f"{usd:.2f}" if usd else None,
                "usd_cny": fx,
                "credit_tokens": int(p.get("credit_tokens") or 0),
                "set_vip": bool(p.get("set_vip")),
                "vip_days": int(p.get("vip_days") or 0) or None,
                "note": _public_note(p),
                "settle_hint": "国内站 CNY（微信/支付宝）· 国际站 USD（PayPal 等）· 同一 SKU",
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
