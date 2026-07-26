"""
Token 产品套餐目录（与 a1 行情官 VIP 配额套餐完全独立）。

定价口径（2026-07-26）：
- 主数据按国际价（USD 锚定，对标 OpenRouter 中国模型线 +10%～25% 便利溢价）
- 国内站收银台收 CNY（微信/支付宝）；国际站收 USD（PayPal 等）— 同一 SKU
- 前端按语言展示：中文只显示人民币文案；其它语言显示美元文案
- 价格可用环境变量覆盖（分）：TOKEN_PRICE_<PLAN_UPPER>_FEN
"""
from __future__ import annotations

import os
from typing import Any


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


_VIP_DAILY_WAN = 10  # 日赠约 10 万 token（与 VIP_DAILY_BONUS_TOKENS=100_000 对齐）

TOKEN_PLANS: dict[str, dict[str, Any]] = {
    "token_pack_10k": {
        "title_zh": "入门包",
        "title_en": "Starter",
        "price_usd": 5.0,
        "price_fen": _price("TOKEN_PRICE_TOKEN_PACK_10K_FEN", _fen_from_usd(5.0)),
        "credit_tokens": 100_000,
        "set_vip": False,
        "enabled": True,
        "note_zh": "国内外同一套餐；本站使用微信/支付宝支付人民币。",
        "note_en": "Same SKU worldwide. Intl checkout: PayPal (USD).",
    },
    "token_pack_100k": {
        "title_zh": "开发包",
        "title_en": "Builder",
        "price_usd": 20.0,
        "price_fen": _price("TOKEN_PRICE_TOKEN_PACK_100K_FEN", _fen_from_usd(20.0)),
        "credit_tokens": 500_000,
        "set_vip": False,
        "enabled": True,
        "note_zh": "主力预充值；单价优于入门包。",
        "note_en": "Best for regular API use; better unit rate than Starter.",
    },
    "token_vip_month": {
        "title_zh": "Pro 月卡",
        "title_en": "Pro Pass",
        "price_usd": 15.0,
        "price_fen": _price("TOKEN_PRICE_TOKEN_VIP_MONTH_FEN", _fen_from_usd(15.0)),
        "credit_tokens": 0,
        "set_vip": True,
        "vip_days": 30,
        "enabled": True,
        "note_zh": (
            f"开通 Token VIP 30 天；有效期内每日额外赠送约 {_VIP_DAILY_WAN} 万 token。"
        ),
        "note_en": (
            f"Token VIP for 30 days; about {_VIP_DAILY_WAN * 10_000:,} bonus tokens/day."
        ),
    },
    "token_vip_month_50w": {
        "title_zh": "Scale 组合包",
        "title_en": "Scale",
        "price_usd": 100.0,
        "price_fen": _price("TOKEN_PRICE_TOKEN_VIP_MONTH_50W_FEN", _fen_from_usd(100.0)),
        "credit_tokens": 2_500_000,
        "set_vip": True,
        "vip_days": 30,
        "enabled": True,
        "note_zh": (
            f"立即到账 250 万 token，并开通 Pro 月卡 30 天；日赠约 {_VIP_DAILY_WAN} 万 token。"
        ),
        "note_en": (
            f"2.5M tokens credited + Pro Pass 30 days; ~{_VIP_DAILY_WAN * 10_000:,} bonus/day."
        ),
    },
}


def list_public_plans() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    fx = _usd_cny()
    for plan_id, p in TOKEN_PLANS.items():
        if not p.get("enabled", True):
            continue
        usd = float(p.get("price_usd") or 0)
        fen = int(p["price_fen"])
        title_zh = str(p.get("title_zh") or p.get("title") or plan_id)
        title_en = str(p.get("title_en") or title_zh)
        note_zh = str(p.get("note_zh") or p.get("note") or "")
        note_en = str(p.get("note_en") or note_zh)
        out.append(
            {
                "plan": plan_id,
                "title": title_zh,
                "title_zh": title_zh,
                "title_en": title_en,
                "price_fen": fen,
                "price_yuan": f"{fen / 100:.2f}",
                "price_usd": f"{usd:.2f}" if usd else None,
                "usd_cny": fx,
                "credit_tokens": int(p.get("credit_tokens") or 0),
                "set_vip": bool(p.get("set_vip")),
                "vip_days": int(p.get("vip_days") or 0) or None,
                "note": note_zh,
                "note_zh": note_zh,
                "note_en": note_en,
                "settle_hint_zh": "本站：微信 / 支付宝，人民币结算",
                "settle_hint_en": "Intl site: PayPal (USD). Same SKUs as CN site.",
            }
        )
    return out


def get_plan(plan_id: str) -> dict[str, Any] | None:
    pid = (plan_id or "").strip()
    p = TOKEN_PLANS.get(pid)
    if not p or not p.get("enabled", True):
        return None
    title = str(p.get("title_zh") or p.get("title") or pid)
    return {"plan": pid, "title": title, **p}


def normalize_plan(plan_id: str) -> tuple[str, int]:
    """返回 (plan_id, price_fen)；非法则抛 ValueError。"""
    p = get_plan(plan_id)
    if not p:
        raise ValueError(f"unknown_or_disabled_plan:{plan_id}")
    return str(p["plan"]), int(p["price_fen"])
