"""
Token 产品套餐目录（与 a1 行情官 VIP 配额套餐完全独立）。

定价口径（2026-07-30）：
- 主数据按国际价（USD 锚定）；国内收银台 CNY（微信/支付宝），国际 PayPal USD
- 入门包默认保持体验价 ¥1 / 1 万 token（正式规模获客前再抬）；可用 env 覆盖
- 改价：行级改 TOKEN_PRICE_*_FEN 后重启；管理台只读展示，禁止网页写 .env
- 国际支付主路径 = PayPal；国内微信/支付宝不按「国际收单」改造（另签产品再立项）
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


def _env_override_set(env_key: str) -> bool:
    return bool((os.getenv(env_key) or "").strip())


def _fen_from_usd(usd: float) -> int:
    return max(1, int(round(float(usd) * _usd_cny() * 100)))


_VIP_DAILY_WAN = 10  # 日赠约 10 万 token（与 VIP_DAILY_BONUS_TOKENS=100_000 对齐）

# plan_id → 覆盖 CNY 分的环境变量名
PLAN_PRICE_ENV: dict[str, str] = {
    "token_pack_10k": "TOKEN_PRICE_TOKEN_PACK_10K_FEN",
    "token_pack_100k": "TOKEN_PRICE_TOKEN_PACK_100K_FEN",
    "token_vip_month": "TOKEN_PRICE_TOKEN_VIP_MONTH_FEN",
    "token_vip_month_50w": "TOKEN_PRICE_TOKEN_VIP_MONTH_50W_FEN",
}

TOKEN_PLANS: dict[str, dict[str, Any]] = {
    "token_pack_10k": {
        "title_zh": "入门包",
        "title_en": "Starter",
        # 体验价：默认 ¥1（100 分）；正式获客前可继续保留
        "price_usd": round(1.0 / _usd_cny(), 2),
        "price_fen": _price("TOKEN_PRICE_TOKEN_PACK_10K_FEN", 100),
        "credit_tokens": 10_000,
        "set_vip": False,
        "validity_days": 365,
        "enabled": True,
        "promo": True,
        "note_zh": "体验价：¥1 到账 1 万 token；额度自到账起 12 个月有效。支持微信、支付宝。",
        "note_en": "Promo: about $0.14 for 10k credits (valid 12 months from credit). PayPal on the international site.",
    },
    "token_pack_100k": {
        "title_zh": "开发包",
        "title_en": "Builder",
        "price_usd": 20.0,
        "price_fen": _price("TOKEN_PRICE_TOKEN_PACK_100K_FEN", _fen_from_usd(20.0)),
        "credit_tokens": 500_000,
        "set_vip": False,
        "validity_days": 365,
        "enabled": True,
        "promo": False,
        "note_zh": "适合日常调用，单价更优；额度自到账起 12 个月有效。",
        "note_en": "Better unit rate for regular API use. Credits valid 12 months from top-up.",
    },
    "token_vip_month": {
        "title_zh": "Pro 月卡",
        "title_en": "Pro Pass",
        "price_usd": 15.0,
        "price_fen": _price("TOKEN_PRICE_TOKEN_VIP_MONTH_FEN", _fen_from_usd(15.0)),
        "credit_tokens": 0,
        "set_vip": True,
        "vip_days": 30,
        "validity_days": 0,
        "enabled": True,
        "promo": False,
        "note_zh": (
            f"开通 Token VIP 30 天；有效期内每日额外赠送约 {_VIP_DAILY_WAN} 万 token（日赠额度另计有效期）。"
        ),
        "note_en": (
            f"Token VIP for 30 days; about {_VIP_DAILY_WAN * 10_000:,} bonus tokens/day (bonus lots expire separately)."
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
        "validity_days": 730,
        "enabled": True,
        "promo": False,
        "note_zh": (
            f"立即到账 250 万 token（24 个月有效），并开通 Pro 月卡 30 天；日赠约 {_VIP_DAILY_WAN} 万 token。"
        ),
        "note_en": (
            f"2.5M tokens credited (valid 24 months) + Pro Pass 30 days; ~{_VIP_DAILY_WAN * 10_000:,} bonus/day."
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
                "validity_days": int(p.get("validity_days") or 0) or None,
                "note": note_zh,
                "note_zh": note_zh,
                "note_en": note_en,
                "settle_hint_zh": "支持微信支付、支付宝",
                "settle_hint_en": "Pay with PayPal (USD) on the international site",
            }
        )
    return out


def list_admin_plans() -> dict[str, Any]:
    """运维只读价表：含 env 覆盖键；不含密钥。"""
    fx = _usd_cny()
    rows: list[dict[str, Any]] = []
    for plan_id, p in TOKEN_PLANS.items():
        env_key = PLAN_PRICE_ENV.get(plan_id, "")
        fen = int(p.get("price_fen") or 0)
        usd = float(p.get("price_usd") or 0)
        rows.append(
            {
                "plan": plan_id,
                "title_zh": str(p.get("title_zh") or plan_id),
                "title_en": str(p.get("title_en") or ""),
                "enabled": bool(p.get("enabled", True)),
                "promo": bool(p.get("promo")),
                "price_fen": fen,
                "price_yuan": f"{fen / 100:.2f}",
                "price_usd": round(usd, 2) if usd else None,
                "credit_tokens": int(p.get("credit_tokens") or 0),
                "set_vip": bool(p.get("set_vip")),
                "vip_days": int(p.get("vip_days") or 0) or None,
                "validity_days": int(p.get("validity_days") or 0) or None,
                "price_env_key": env_key or None,
                "price_env_override": bool(env_key and _env_override_set(env_key)),
                "note_zh": str(p.get("note_zh") or ""),
            }
        )
    return {
        "ok": True,
        "usd_cny": fx,
        "plans": rows,
        "ops_note": (
            "入门包默认体验价可继续使用。改价：服务器行级改对应 TOKEN_PRICE_*_FEN 后重启 API；"
            "本页不可写密钥或 .env。"
            "国际 USD 主路径为 PayPal；国内微信/支付宝保持 CNY 国内商户。"
            "PayPal Webhook 为回跳失败时的履约兜底（P1），主路径 Capture 已够用。"
        ),
    }


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
