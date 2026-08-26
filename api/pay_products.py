"""AI24X 统一支付中台 · 产品目录（2026-08-17 建立）。

每个接入子产品在这里登记一份配置：
- out_trade_no 前缀（token=T 兼容旧单；markets=M）
- 套餐定价（USD；微信/支付宝下单时按 _usd_cny 换算成 CNY 分）
- 回跳地址（PayPal/支付宝/Creem 付完回到各自站点）
- 履约方式（token=核心本地入账；markets=签名回调子服务激活订阅）

新增子产品 = 加一个注册项，支付通道/回调/查单层零改动（无限分类扩充）。
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

# 自举加载 api/.env：本模块的 MARKET_PLANS 在导入期读 DODO_PRODUCT_MARKETS_*，
# 不依赖其它模块（如 llm_keys）先被导入触发 dotenv，避免「首次同步重复建产品」。
try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent / ".env", override=False)
except Exception:
    pass

# markets 子服务履约回调（服务端到服务端，同机 18012 / 生产同机）
MARKETS_FULFILL_URL = os.environ.get(
    "MARKETS_FULFILL_URL", "http://127.0.0.1:18012/api/subscribe/fulfill"
)
MARKETS_FULFILL_SECRET = os.environ.get("MARKETS_FULFILL_SECRET", "")
# 运营后台网关 → markets 子服务管理接口基址（同机回环；生产同机 18012）
MARKETS_ADMIN_BASE = os.environ.get("MARKETS_ADMIN_BASE", "http://127.0.0.1:18012").rstrip("/")

MARKETS_RETURN_URL = os.environ.get(
    "MARKETS_PAY_RETURN_URL", "https://markets.ai24x.com/app.html?pay=done"
)

MARKET_PLANS: Dict[str, Dict[str, Any]] = {
    "weekly": {
        "price_usd": 9.9,
        "days": 7,
        "label": "Pro Weekly",
        "title": "AI24X Markets Pro · 1 week",
        "title_zh": "AI24X Markets Pro · 周卡",
        "price_label": "$9.9/week",
        "price_label_zh": "$9.9/周",
        "perk": "All Pro features for 7 days",
        "perk_zh": "7 天完整 Pro 功能（AI 点评不限次、自选 50 只）",
        "creem_product_id": os.environ.get("CREEM_PRODUCT_MARKETS_WEEKLY", "").strip(),
        "dodo_product_id": os.environ.get("DODO_PRODUCT_MARKETS_WEEKLY", "").strip(),
    },
    "monthly": {
        "price_usd": 24.9,
        "days": 30,
        "label": "Pro Monthly",
        "title": "AI24X Markets Pro · 1 month",
        "title_zh": "AI24X Markets Pro · 月卡",
        "price_label": "$24.9/month",
        "price_label_zh": "$24.9/月",
        "perk": "30-day Pro — unlimited AI briefs & 50-symbol watchlist",
        "perk_zh": "30 天 Pro — AI 点评不限次、自选 50 只",
        "creem_product_id": os.environ.get("CREEM_PRODUCT_MARKETS_MONTHLY", "").strip(),
        "dodo_product_id": os.environ.get("DODO_PRODUCT_MARKETS_MONTHLY", "").strip(),
    },
    "yearly": {
        "price_usd": 199.0,
        "days": 365,
        "label": "Pro Yearly",
        "title": "AI24X Markets Pro · 1 year",
        "title_zh": "AI24X Markets Pro · 年卡",
        "price_label": "$199/year",
        "price_label_zh": "$199/年",
        "perk": "Best value — a full year of Pro",
        "perk_zh": "最划算 — 全年 Pro（约省 33%）",
        "creem_product_id": os.environ.get("CREEM_PRODUCT_MARKETS_YEARLY", "").strip(),
        "dodo_product_id": os.environ.get("DODO_PRODUCT_MARKETS_YEARLY", "").strip(),
    },
}

# 与 markets 子服务共享的套餐覆盖文件（管理台保存 → markets 写 → 本文件同源读取）
_MARKET_OVERRIDE_PATH = Path(
    os.environ.get("MARKETS_PLANS_OVERRIDE")
    or str(
        Path(__file__).resolve().parents[1]
        / "p" / "markets" / "api" / "server" / "data" / "markets_plans_override.json"
    )
)
_MARKET_EDITABLE = (
    "label", "usd", "days", "description", "enabled",
    "title_zh", "title_en", "price_label", "price_label_zh", "perk", "perk_zh",
    "dodo_product_id",
)


def _load_market_overrides() -> Dict[str, Dict[str, Any]]:
    try:
        if not _MARKET_OVERRIDE_PATH.is_file():
            return {}
        raw = json.loads(_MARKET_OVERRIDE_PATH.read_text(encoding="utf-8"))
        plans = raw.get("plans") if isinstance(raw, dict) else None
        if not isinstance(plans, dict):
            return {}
        return {str(k): (v if isinstance(v, dict) else {}) for k, v in plans.items()}
    except Exception:
        return {}


def set_market_dodo_product_id(plan_id: str, product_id: str) -> bool:
    """Dodo 同步创建/改名产品后回写 product_id（持久化，优先于 env 默认值）。"""
    pid = str(plan_id or "").strip().lower()
    if pid not in MARKET_PLANS:
        return False
    try:
        cur = _load_market_overrides()
        row = dict(cur.get(pid) or {})
        row["dodo_product_id"] = str(product_id or "").strip()
        cur[pid] = row
        _MARKET_OVERRIDE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _MARKET_OVERRIDE_PATH.write_text(
            json.dumps({"plans": cur, "updated_note": "dodo_sync"}, ensure_ascii=False, indent=2)
            + "\n",
            encoding="utf-8",
        )
        return True
    except Exception:
        return False


def resolve_market_plans() -> Dict[str, Dict[str, Any]]:
    """markets 套餐 = 代码默认 + 管理台覆盖；禁用套餐由 public_products 过滤。"""
    ov = _load_market_overrides()
    out: Dict[str, Dict[str, Any]] = {}
    period = {"weekly": ("week", "周"), "monthly": ("month", "月"), "yearly": ("year", "年")}
    for pid, base in MARKET_PLANS.items():
        p = dict(base)
        o = ov.get(pid) or {}
        for key in _MARKET_EDITABLE:
            if key in o and o[key] is not None:
                p[key] = o[key]
        p.setdefault("enabled", True)
        # 管理台以 usd 改价 → 同步到 price_usd 与价格标签（除非显式覆盖）
        if "usd" in o and o["usd"] is not None:
            usd = float(o["usd"])
            p["price_usd"] = usd
            per = period.get(pid)
            if per:
                if "price_label" not in o or o["price_label"] is None:
                    p["price_label"] = "${:g}/{}".format(usd, per[0])
                if "price_label_zh" not in o or o["price_label_zh"] is None:
                    p["price_label_zh"] = "${:g}/{}".format(usd, per[1])
        out[pid] = p
    return out


# ————— BYOK 网关服务费套餐（Bring Your Own Key）—————
# 平台只收网关服务费，不赚上游 token 差价；价格与 p/open byok_plans 默认一致
# （$9.9/月、$99/年）。支付后端（Dodo 等）商品目录以本登记为同步源。
BYOK_PLANS: Dict[str, Dict[str, Any]] = {
    "byok_pro_month": {
        "price_usd": 9.9,
        "days": 30,
        "label": "Pro Monthly",
        "title": "AI24X BYOK Pro · 1 month",
        "title_zh": "AI24X BYOK Pro · 月付",
        "price_label": "$9.9/month",
        "price_label_zh": "$9.9/月",
        "perk": "BYOK smart gateway service fee — your own keys",
        "perk_zh": "BYOK 智能网关服务费 — 使用自有 key",
        "dodo_product_id": os.environ.get("DODO_PRODUCT_BYOK_MONTH", "").strip(),
    },
    "byok_pro_year": {
        "price_usd": 99.0,
        "days": 365,
        "label": "Pro Yearly",
        "title": "AI24X BYOK Pro · 1 year",
        "title_zh": "AI24X BYOK Pro · 年付",
        "price_label": "$99/year",
        "price_label_zh": "$99/年",
        "perk": "Best value — a full year of BYOK Pro",
        "perk_zh": "最划算 — 全年 BYOK Pro",
        "dodo_product_id": os.environ.get("DODO_PRODUCT_BYOK_YEAR", "").strip(),
    },
}

# core 侧 BYOK 覆盖文件（gitignore）：dodo_product_id 回写等；价格默认即正式价
_BYOK_OVERRIDE_PATH = Path(
    os.environ.get("BYOK_PLANS_OVERRIDE_CORE")
    or str(Path(__file__).resolve().parent / "data" / "byok_plans_override.json")
)
_BYOK_EDITABLE = (
    "label", "usd", "days", "description", "enabled",
    "title_zh", "title_en", "price_label", "price_label_zh", "perk", "perk_zh",
    "dodo_product_id",
)


def _load_byok_overrides() -> Dict[str, Dict[str, Any]]:
    try:
        if not _BYOK_OVERRIDE_PATH.is_file():
            return {}
        raw = json.loads(_BYOK_OVERRIDE_PATH.read_text(encoding="utf-8"))
        plans = raw.get("plans") if isinstance(raw, dict) else None
        if not isinstance(plans, dict):
            return {}
        return {str(k): (v if isinstance(v, dict) else {}) for k, v in plans.items()}
    except Exception:
        return {}


def set_byok_dodo_product_id(plan_id: str, product_id: str) -> bool:
    """Dodo 同步创建/改名 BYOK 产品后回写 product_id（优先于 env 默认值）。"""
    pid = str(plan_id or "").strip().lower()
    if pid not in BYOK_PLANS:
        return False
    try:
        cur = _load_byok_overrides()
        row = dict(cur.get(pid) or {})
        row["dodo_product_id"] = str(product_id or "").strip()
        cur[pid] = row
        _BYOK_OVERRIDE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _BYOK_OVERRIDE_PATH.write_text(
            json.dumps({"plans": cur, "updated_note": "dodo_sync"}, ensure_ascii=False, indent=2)
            + "\n",
            encoding="utf-8",
        )
        return True
    except Exception:
        return False


def resolve_byok_plans() -> Dict[str, Dict[str, Any]]:
    """BYOK 套餐 = 代码默认（正式价）+ core 覆盖；禁用由调用方过滤。"""
    ov = _load_byok_overrides()
    out: Dict[str, Dict[str, Any]] = {}
    period = {"byok_pro_month": ("month", "月"), "byok_pro_year": ("year", "年")}
    for pid, base in BYOK_PLANS.items():
        p = dict(base)
        o = ov.get(pid) or {}
        for key in _BYOK_EDITABLE:
            if key in o and o[key] is not None:
                p[key] = o[key]
        p.setdefault("enabled", True)
        if "usd" in o and o["usd"] is not None:
            usd = float(o["usd"])
            p["price_usd"] = usd
            per = period.get(pid)
            if per:
                if "price_label" not in o or o["price_label"] is None:
                    p["price_label"] = "${:g}/{}".format(usd, per[0])
                if "price_label_zh" not in o or o["price_label_zh"] is None:
                    p["price_label_zh"] = "${:g}/{}".format(usd, per[1])
        out[pid] = p
    return out


PRODUCTS: Dict[str, Dict[str, Any]] = {
    # token：沿用 token_plans 套餐目录 + 核心本地入账（BillingLedger/topup）
    "token": {
        "prefix": "T",
        "plans": None,  # None = 走 token_plans 目录
        "return_url": None,  # None = 用全局 paypal_return_url / alipay_return_url
        "fulfill": {"type": "local"},
    },
    # markets：AI行情官国际版 Pro 订阅，付完签名回调 markets 子服务激活
    "markets": {
        "prefix": "M",
        "plans": MARKET_PLANS,
        "return_url": MARKETS_RETURN_URL,
        "fulfill": {
            "type": "http",
            "url": MARKETS_FULFILL_URL,
            "secret": MARKETS_FULFILL_SECRET,
        },
    },
}


def known_products() -> tuple[str, ...]:
    return tuple(PRODUCTS.keys())


def product_prefix(product: str) -> str:
    meta = PRODUCTS.get(product or "token") or {}
    return str(meta.get("prefix") or "T")


def product_plan(product: str, plan_id: str) -> Optional[Dict[str, Any]]:
    """返回产品内套餐元信息（不含价格换算）；token 委托 token_plans。"""
    product = product or "token"
    meta = PRODUCTS.get(product) or {}
    plans = meta.get("plans")
    if plans is None:
        from token_plans import get_plan

        return get_plan(plan_id)
    pid = str(plan_id or "").strip().lower()
    if product == "markets":
        resolved = resolve_market_plans().get(pid) or {}
        return dict(resolved) if resolved else None
    return dict(plans.get(pid) or {}) if pid else None


def product_return_url(product: str) -> Optional[str]:
    meta = PRODUCTS.get(product or "token") or {}
    return meta.get("return_url")


def is_known_product(product: str) -> bool:
    return (product or "token") in PRODUCTS


def public_products() -> Dict[str, Any]:
    """统一产品套餐目录：前端「选项目 → 选套餐 → 选支付方式」一次拉全。"""
    from token_pay_service import public_plans

    data = public_plans()
    pay = data.get("pay") or {}

    markets_plans: list[Dict[str, Any]] = []
    for pid, p in resolve_market_plans().items():
        if not p.get("enabled", True):
            continue
        markets_plans.append(
            {
                "plan": pid,
                "title": str(p.get("label") or pid),
                "title_zh": str(p.get("title_zh") or p.get("label") or pid),
                "price_usd": p.get("price_usd"),
                "price_label": str(p.get("price_label") or f"${p.get('price_usd', '')}"),
                "price_label_zh": str(p.get("price_label_zh") or f"${p.get('price_usd', '')}"),
                "days": p.get("days"),
                "perk": str(p.get("perk") or ""),
                "perk_zh": str(p.get("perk_zh") or ""),
            }
        )

    byok_plans: list[Dict[str, Any]] = []
    for pid, p in resolve_byok_plans().items():
        if not p.get("enabled", True):
            continue
        byok_plans.append(
            {
                "plan": pid,
                "title": str(p.get("label") or pid),
                "title_zh": str(p.get("title_zh") or p.get("label") or pid),
                "price_usd": p.get("price_usd"),
                "price_label": str(p.get("price_label") or f"${p.get('price_usd', '')}"),
                "price_label_zh": str(p.get("price_label_zh") or f"${p.get('price_usd', '')}"),
                "days": p.get("days"),
                "perk": str(p.get("perk") or ""),
                "perk_zh": str(p.get("perk_zh") or ""),
                "recommended": pid == "byok_pro_year",
            }
        )

    return {
        "ok": True,
        "pay": pay,
        "products": [
            {
                "product": "markets",
                "title": "AI24X Markets Pro",
                "title_zh": "AI24X 行情官 · 国际版 Pro",
                "desc": (
                    "Charts, technical indicators and unlimited AI commentary for "
                    "US stocks, ETFs and indices. Pay with WeChat, Alipay, PayPal or USDT."
                ),
                "desc_zh": (
                    "美股/ETF/指数 K线、技术指标与 AI 点评不限次。"
                    "支持微信、支付宝、PayPal、USDT 支付。"
                ),
                "url": "https://markets.ai24x.com",
                "plans": markets_plans,
            },
            {
                "product": "token",
                "title": "AI Gateway credits",
                "title_zh": "AI Gateway 额度",
                "desc": (
                    "Top up managed credits and named-model access here. "
                    "API keys and docs: open.ai24x.com."
                ),
                "desc_zh": "在此充值托管额度与点名资格；API Key 与文档在 open.ai24x.com。",
                "url": "https://open.ai24x.com",
                "plans": data.get("plans") or [],
            },
            {
                "product": "byok",
                "title": "BYOK Gateway",
                "title_zh": "BYOK 智能网关",
                "desc": (
                    "Bring your own API keys — smart routing, failover, request cache and a "
                    "cost dashboard. Platform charges a gateway service fee only. "
                    "Purchase at open.ai24x.com."
                ),
                "desc_zh": (
                    "自带 API Key：智能路由 + 故障转移 + 请求缓存 + 成本看板，"
                    "平台只收网关服务费。在 open.ai24x.com 开通。"
                ),
                "url": "https://open.ai24x.com/pricing.html",
                "plans": byok_plans,
            },
        ],
    }
