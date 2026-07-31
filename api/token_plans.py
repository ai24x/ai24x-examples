"""
Token 产品套餐目录（与 a1 行情官 VIP 配额套餐完全独立）。

定价口径（2026-07-30）：
- 主数据按国际价（USD 锚定）；国内收银台 CNY（微信/支付宝），国际 PayPal USD
- 入门包默认保持体验价 ¥1 / 1 万 token（正式规模获客前再抬）
- 改价优先级：管理台覆盖文件 > env TOKEN_PRICE_*_FEN > 代码默认
- 前台 /v1/billing/plans 与后台同源 list_public_plans / get_plan
"""
from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

_OVERRIDE_PATH = Path(__file__).resolve().parent / "data" / "token_plans_override.json"

_VIP_DAILY_WAN = 10  # 日赠约 10 万 token（与 VIP_DAILY_BONUS_TOKENS=100_000 对齐）

# plan_id → 覆盖 CNY 分的环境变量名
PLAN_PRICE_ENV: dict[str, str] = {
    "token_pack_10k": "TOKEN_PRICE_TOKEN_PACK_10K_FEN",
    "token_pack_100k": "TOKEN_PRICE_TOKEN_PACK_100K_FEN",
    "token_vip_month": "TOKEN_PRICE_TOKEN_VIP_MONTH_FEN",
    "token_vip_month_50w": "TOKEN_PRICE_TOKEN_VIP_MONTH_50W_FEN",
}

# 代码默认（不含运行时价）；价由 _resolve_price_fen 计算
_PLAN_DEFAULTS: dict[str, dict[str, Any]] = {
    "token_pack_10k": {
        "title_zh": "入门包",
        "title_en": "Starter",
        "price_usd": round(1.0 / 7.2, 2),
        "default_fen": 100,
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
        "default_fen": None,  # 由 USD×汇率推算
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
        "default_fen": None,
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
        "default_fen": None,
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


def _load_overrides() -> dict[str, dict[str, Any]]:
    try:
        if not _OVERRIDE_PATH.is_file():
            return {}
        raw = json.loads(_OVERRIDE_PATH.read_text(encoding="utf-8"))
        plans = raw.get("plans") if isinstance(raw, dict) else None
        if not isinstance(plans, dict):
            return {}
        out: dict[str, dict[str, Any]] = {}
        for k, v in plans.items():
            if isinstance(v, dict):
                out[str(k)] = v
        return out
    except Exception:
        return {}


def _save_overrides(plans: dict[str, dict[str, Any]]) -> None:
    _OVERRIDE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {"plans": plans, "updated_note": "admin_ui"}
    _OVERRIDE_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _default_fen_for(plan_id: str, base: dict[str, Any]) -> int:
    df = base.get("default_fen")
    if df is not None:
        return int(df)
    usd = float(base.get("price_usd") or 0)
    return _fen_from_usd(usd) if usd > 0 else 1


def _resolve_plan(plan_id: str) -> dict[str, Any] | None:
    base = _PLAN_DEFAULTS.get(plan_id)
    if not base:
        return None
    ov = _load_overrides().get(plan_id) or {}
    p = deepcopy(base)
    env_key = PLAN_PRICE_ENV.get(plan_id, "")
    default_fen = _default_fen_for(plan_id, base)

    # 可覆盖字段
    for key in (
        "title_zh",
        "title_en",
        "note_zh",
        "note_en",
        "promo",
        "enabled",
        "set_vip",
        "credit_tokens",
        "validity_days",
        "vip_days",
        "price_usd",
    ):
        if key in ov and ov[key] is not None:
            p[key] = ov[key]

    if "price_fen" in ov and ov["price_fen"] is not None:
        try:
            fen = int(ov["price_fen"])
            p["price_fen"] = fen if fen > 0 else _price(env_key, default_fen) if env_key else default_fen
            p["_price_source"] = "admin"
        except (TypeError, ValueError):
            p["price_fen"] = _price(env_key, default_fen) if env_key else default_fen
            p["_price_source"] = "env" if env_key and _env_override_set(env_key) else "default"
    elif env_key:
        p["price_fen"] = _price(env_key, default_fen)
        p["_price_source"] = "env" if _env_override_set(env_key) else "default"
    else:
        p["price_fen"] = default_fen
        p["_price_source"] = "default"

    if "price_usd" in ov and ov["price_usd"] is not None:
        try:
            p["price_usd"] = float(ov["price_usd"])
        except (TypeError, ValueError):
            pass

    p.pop("default_fen", None)
    return p


def resolved_plans() -> dict[str, dict[str, Any]]:
    return {pid: p for pid in _PLAN_DEFAULTS if (p := _resolve_plan(pid))}


# 兼容旧 import：TOKEN_PLANS 为解析后快照（启动时）；运行时请用 resolved_plans/get_plan
TOKEN_PLANS: dict[str, dict[str, Any]] = resolved_plans()


def list_public_plans() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    fx = _usd_cny()
    for plan_id, p in resolved_plans().items():
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
    """运维价表：可编辑字段 + 来源标记。"""
    fx = _usd_cny()
    rows: list[dict[str, Any]] = []
    overrides = _load_overrides()
    for plan_id in _PLAN_DEFAULTS:
        p = _resolve_plan(plan_id) or {}
        env_key = PLAN_PRICE_ENV.get(plan_id, "")
        fen = int(p.get("price_fen") or 0)
        usd = float(p.get("price_usd") or 0)
        src = str(p.get("_price_source") or "default")
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
                "price_source": src,
                "has_admin_override": plan_id in overrides,
                "note_zh": str(p.get("note_zh") or ""),
            }
        )
    return {
        "ok": True,
        "usd_cny": fx,
        "plans": rows,
        "editable": True,
        "ops_note": (
            "价表前后台同源。本页可改 CNY 分 / USD / 到账 token / 启停；"
            "保存后立即对前台生效（写入 api/data/token_plans_override.json）。"
            "优先级：管理台覆盖 > env TOKEN_PRICE_*_FEN > 代码默认。"
            "入门包体验价可继续使用；国际 USD 主路径为 PayPal。"
        ),
    }


def update_admin_plans(updates: list[dict[str, Any]]) -> dict[str, Any]:
    """合并写入管理台覆盖；仅允许已有 plan_id。"""
    cur = _load_overrides()
    for item in updates or []:
        if not isinstance(item, dict):
            continue
        pid = str(item.get("plan") or "").strip()
        if pid not in _PLAN_DEFAULTS:
            continue
        row = dict(cur.get(pid) or {})
        if "price_fen" in item and item["price_fen"] is not None:
            try:
                fen = int(item["price_fen"])
                if fen > 0:
                    row["price_fen"] = fen
            except (TypeError, ValueError):
                pass
        if "price_usd" in item and item["price_usd"] is not None:
            try:
                usd = float(item["price_usd"])
                if usd >= 0:
                    row["price_usd"] = usd
            except (TypeError, ValueError):
                pass
        if "credit_tokens" in item and item["credit_tokens"] is not None:
            try:
                ct = int(item["credit_tokens"])
                if ct >= 0:
                    row["credit_tokens"] = ct
            except (TypeError, ValueError):
                pass
        if "enabled" in item and item["enabled"] is not None:
            row["enabled"] = bool(item["enabled"])
        if "promo" in item and item["promo"] is not None:
            row["promo"] = bool(item["promo"])
        if "title_zh" in item and item["title_zh"] is not None:
            row["title_zh"] = str(item["title_zh"])[:64]
        if "note_zh" in item and item["note_zh"] is not None:
            row["note_zh"] = str(item["note_zh"])[:500]
        cur[pid] = row
    _save_overrides(cur)
    global TOKEN_PLANS
    TOKEN_PLANS = resolved_plans()
    return list_admin_plans()


def get_plan(plan_id: str) -> dict[str, Any] | None:
    pid = (plan_id or "").strip()
    p = _resolve_plan(pid)
    if not p or not p.get("enabled", True):
        return None
    title = str(p.get("title_zh") or p.get("title") or pid)
    clean = {k: v for k, v in p.items() if not str(k).startswith("_")}
    return {"plan": pid, "title": title, **clean}


def normalize_plan(plan_id: str) -> tuple[str, int]:
    """返回 (plan_id, price_fen)；非法则抛 ValueError。"""
    p = get_plan(plan_id)
    if not p:
        raise ValueError(f"unknown_or_disabled_plan:{plan_id}")
    return str(p["plan"]), int(p["price_fen"])
