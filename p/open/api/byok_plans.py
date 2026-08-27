"""
BYOK 网关服务费套餐（Bring Your Own Key）。

计费口径：平台只收「网关服务费」，不赚上游 token 差价；用户 key 直接消耗其
自有上游额度。套餐履约（支付成功）后由 token_pay_service 调 byok.activate_subscription
写入 byok_subscriptions 表。

Phase 1 为统计展示；支付链路（PayPal/微信/支付宝/Creem/Mock）复用 token_pay_service。
"""

from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

_OVERRIDE_PATH = Path(
    os.environ.get("BYOK_PLANS_OVERRIDE") or str(Path(__file__).resolve().parent / "data" / "byok_plans_override.json")
)

# 管理台可覆盖字段（p/open/api/data/byok_plans_override.json）
_BYOK_EDITABLE = (
    "title_zh", "title_en", "price_usd", "days", "recommended", "enabled",
    "one_liner_zh", "one_liner_en", "features_zh", "features_en",
    "dodo_product_id",
)


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
            "智能路由 / 故障切换 / 请求缓存 / 用量看板（添加 Key 即可用）",
            "免费档每月 1000 次 BYOK 请求；超出需开通 Pro",
            "Pro 状态标识；长期使用更省心",
            "平台只收网关服务费，不赚上游 token 差价",
        ],
        "features_en": [
            "Smart routing, failover, request cache and usage view (available once you add keys)",
            "Free tier: 1000 BYOK requests/month; Pro removes the cap",
            "Pro status in Console for ongoing use",
            "Gateway service fee only — no markup on your provider spend",
        ],
        "one_liner_zh": "月度服务费 · 解除免费请求上限",
        "one_liner_en": "Monthly service fee · removes free request cap",
    },
    "byok_pro_year": {
        "title_zh": "BYOK Pro 年付",
        "title_en": "BYOK Pro · Yearly",
        "price_usd": 99.0,
        "days": 365,
        "recommended": True,
        "features_zh": [
            "包含月付全部能力（不限每月 BYOK 请求次数）",
            "年付立省 17%（$9.9×12 → $99）",
            "开发者文档与社群支持",
            "后续额度与支持升级时优先保障",
        ],
        "features_en": [
            "Everything in monthly Pro (unlimited BYOK requests)",
            "Save 17% vs monthly ($9.9×12 → $99)",
            "Developer docs and community support",
            "Priority when we add higher support tiers",
        ],
        "one_liner_zh": "年度订阅 · 立省 17% · 推荐",
        "one_liner_en": "Yearly · save 17% · recommended",
    },
}


def _load_overrides() -> dict[str, dict[str, Any]]:
    try:
        if not _OVERRIDE_PATH.is_file():
            return {}
        raw = json.loads(_OVERRIDE_PATH.read_text(encoding="utf-8"))
        plans = raw.get("plans") if isinstance(raw, dict) else None
        if not isinstance(plans, dict):
            return {}
        return {str(k): (v if isinstance(v, dict) else {}) for k, v in plans.items()}
    except Exception:
        return {}


def _save_overrides(plans: dict[str, dict[str, Any]]) -> None:
    _OVERRIDE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _OVERRIDE_PATH.write_text(
        json.dumps({"plans": plans, "updated_note": "admin_ui"}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


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


def _dodo_product_id(plan_id: str, p: dict[str, Any]) -> str:
    """Dodo 商品 ID：管理台覆盖 > env（DODO_PRODUCT_BYOK_*）> 空。"""
    ov_v = str(p.get("dodo_product_id") or "").strip()
    if ov_v:
        return ov_v
    env_key = {
        "byok_pro_month": "DODO_PRODUCT_BYOK_MONTH",
        "byok_pro_year": "DODO_PRODUCT_BYOK_YEAR",
    }.get(plan_id or "", "")
    if env_key:
        return (os.getenv(env_key) or "").strip()
    return ""


def resolve_byok_plan(plan_id: str) -> dict[str, Any] | None:
    """返回 BYOK 套餐快照（默认 + 管理台覆盖 + env 价），未知 plan 返回 None。"""
    base = _BYOK_PLAN_DEFAULTS.get(plan_id or "")
    if not base:
        return None
    p = deepcopy(base)
    ov = _load_overrides().get(plan_id) or {}
    for key in _BYOK_EDITABLE:
        if key in ov and ov[key] is not None:
            p[key] = ov[key]
    p.setdefault("enabled", True)
    if "price_usd" in ov and ov["price_usd"] is not None:
        usd = float(ov["price_usd"])
    else:
        usd = _price_usd(plan_id, base)
    p["price_usd"] = round(usd, 2)
    p["price_fen"] = _fen_from_usd(usd)
    p["dodo_product_id"] = _dodo_product_id(plan_id, p)
    return p


def public_byok_plans() -> list[dict[str, Any]]:
    """公开 BYOK 套餐目录（仅服务费套餐，不含任何 key 信息）。"""
    out: list[dict[str, Any]] = []
    for pid in ("byok_pro_month", "byok_pro_year"):
        p = resolve_byok_plan(pid)
        if not p or not p.get("enabled", True):
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
                "enabled": True,
                "product": "byok",
            }
        )
    return out


def list_admin_byok_plans() -> dict[str, Any]:
    """管理台套餐目录（含覆盖来源标记，供编辑回显）。"""
    ov = _load_overrides()
    out = []
    for pid in ("byok_pro_month", "byok_pro_year"):
        p = resolve_byok_plan(pid)
        if not p:
            continue
        out.append(
            {
                "plan": pid,
                "title_zh": p.get("title_zh"),
                "title_en": p.get("title_en"),
                "price_usd": p.get("price_usd"),
                "price_fen": p.get("price_fen"),
                "days": p.get("days"),
                "recommended": bool(p.get("recommended")),
                "enabled": bool(p.get("enabled", True)),
                "one_liner_zh": p.get("one_liner_zh") or "",
                "one_liner_en": p.get("one_liner_en") or "",
                "features_zh": p.get("features_zh") or [],
                "features_en": p.get("features_en") or [],
                "has_override": bool(ov.get(pid)),
                "dodo_product_id": str(p.get("dodo_product_id") or ""),
            }
        )
    return {"plans": out}


def set_byok_dodo_product_id(plan_id: str, product_id: str) -> bool:
    """Dodo 同步回写：把新建/命中商品的 product_id 持久化到覆盖文件。"""
    pid = (plan_id or "").strip()
    if pid not in _BYOK_PLAN_DEFAULTS:
        return False
    cur = _load_overrides()
    row = dict(cur.get(pid) or {})
    row["dodo_product_id"] = str(product_id or "").strip()
    cur[pid] = row
    _save_overrides(cur)
    return True


def update_admin_byok_plans(plans: list) -> dict[str, Any]:
    """写入管理台覆盖（只允许改已知套餐；等于默认值的字段自动清掉）。"""
    ov = _load_overrides()
    changed: list[str] = []
    for item in plans or []:
        if not isinstance(item, dict):
            continue
        pid = str(item.get("plan") or "").strip().lower()
        base = _BYOK_PLAN_DEFAULTS.get(pid)
        if not base:
            continue
        defaults = dict(base)
        defaults.setdefault("enabled", True)
        cur = dict(ov.get(pid) or {})
        for key in _BYOK_EDITABLE:
            if key in item and item[key] is not None:
                cur[key] = item[key]
        cleaned = {k: v for k, v in cur.items() if v != defaults.get(k)}
        if cleaned:
            ov[pid] = cleaned
        else:
            ov.pop(pid, None)
        changed.append(pid)
    _save_overrides(ov)
    return {"ok": True, "changed": changed, "note": "byok plans saved"}


def is_byok_plan(plan_id: str) -> bool:
    return bool(_BYOK_PLAN_DEFAULTS.get(plan_id or ""))
