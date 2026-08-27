"""
Dodo Payments 产品自动同步（2026-08-23 司令落地）。

后台「产品运营」一键把 markets / token 套餐同步到 Dodo 后台产品，改价后
无需再手工去 Dodo 后台维护，保证「管理台价格 = Dodo 收银台价格」一致：

- markets：pay_products.resolve_market_plans()（含管理台覆盖）；product_id 默认取
  env DODO_PRODUCT_MARKETS_*，新建/改名后回写 markets_plans_override.json 持久化
- token：token_plans.resolved_plans()；新建/改名后回写 token_plans_override.json

匹配规则（按序）：
1. Dodo 产品 metadata {ai24x_product, ai24x_plan} 精确匹配（本模块创建的产品带标记）
2. 已配置 dodo_product_id（env / 覆盖文件）在 Dodo 商品列表命中
3. 都不中 → POST 新建并回写 product_id

商品列表拉取 active + archived 全量（Dodo 分页参数为 page_size / page_number，
status 用 archived 布尔过滤）；命中已归档商品时先 POST /products/{id}/unarchive
再按需 PATCH，避免重复建档。

价格差异（美分）或名称差异 → PATCH 更新；无差异 → unchanged；单套餐失败不中断。
仅 dodo_api_key_ready 时启用；DODO_MODE 决定 test / live（默认 test）。
"""
from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from pay_dodo import dodo_api_base, dodo_api_key_ready

logger = logging.getLogger(__name__)

_TIMEOUT = 30.0
_MD_PRODUCT = "ai24x_product"
_MD_PLAN = "ai24x_plan"


def _pay_cfg() -> Any:
    from token_pay_service import pay_settings_ns

    return pay_settings_ns()


def _headers(cfg: Any) -> dict[str, str]:
    return {
        "Authorization": "Bearer " + str(getattr(cfg, "dodo_api_key", "") or "").strip(),
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def _price_obj(usd: float) -> dict[str, Any]:
    """Dodo price 对象：suggested_price 不能低于 price，故普通定价省略该字段。"""
    return {
        "currency": "USD",
        "discount": 0,
        "price": max(1, int(round(float(usd) * 100))),
        "purchasing_power_parity": False,
        "type": "one_time_price",
        "pay_what_you_want": False,
        "tax_inclusive": True,
    }


def _item_price_cents(item: dict[str, Any]) -> int:
    raw = item.get("price")
    if isinstance(raw, dict):
        raw = raw.get("price")
    try:
        return int(float(raw or 0))
    except (TypeError, ValueError):
        return 0


async def _get_products(cfg: Any) -> list[dict[str, Any]]:
    """拉取 Dodo 商品（active + archived 全量，翻页后按 product_id 去重）。

    Dodo API 分页参数为 page_size / page_number（page_number 从 0 起），商品状态
    用 archived 布尔过滤；持续翻页直到不足一页。去重时 active 优先，archived 列表
    项打 _dodo_archived 标记，供同步时复用/反归档（避免重复建商品）。
    """
    url = f"{dodo_api_base(cfg)}/products"
    seen: dict[str, dict[str, Any]] = {}
    async with httpx.AsyncClient(timeout=_TIMEOUT) as ac:
        for archived in ("false", "true"):
            page_number = 0
            while True:
                r = await ac.get(
                    url,
                    params={
                        "page_size": 100,
                        "page_number": page_number,
                        "archived": archived,
                    },
                    headers=_headers(cfg),
                )
                if r.status_code >= 400:
                    try:
                        detail = r.json()
                    except Exception:
                        detail = {"raw": r.text[:300]}
                    raise RuntimeError(f"dodo_list_products {r.status_code}: {detail}")
                try:
                    page = r.json().get("items") or []
                except Exception:
                    page = []
                if not isinstance(page, list):
                    page = []
                for it in page:
                    if not isinstance(it, dict):
                        continue
                    pid = str(it.get("product_id") or "").strip()
                    if not pid:
                        continue
                    if archived == "true":
                        it = dict(it)
                        it["_dodo_archived"] = True
                    if pid not in seen or archived == "false":
                        seen[pid] = it
                if len(page) < 100:
                    break
                page_number += 1
    return list(seen.values())


def _match_product(
    products: list[dict[str, Any]], *, product: str, plan_id: str, configured_id: str
) -> dict[str, Any] | None:
    for it in products:
        md = it.get("metadata")
        if isinstance(md, dict):
            if (
                str(md.get(_MD_PRODUCT) or "").strip() == product
                and str(md.get(_MD_PLAN) or "").strip() == plan_id
            ):
                return it
    cid = str(configured_id or "").strip()
    if cid:
        for it in products:
            if str(it.get("product_id") or "").strip() == cid:
                return it
    return None


def _plan_display(product: str, plan_id: str, plan: dict[str, Any]) -> tuple[str, str]:
    usd = float(plan.get("price_usd") or 0)
    if product == "markets":
        label = {"weekly": "Weekly", "monthly": "Monthly", "yearly": "Yearly"}.get(
            plan_id, str(plan.get("label") or plan_id)
        )
        period = {"weekly": "week", "monthly": "month", "yearly": "year"}.get(plan_id, "")
        name = f"AI24X Markets Pro · {label}"
        desc = (
            f"AI24X Markets Pro {label} plan. ${usd:g}/{period}.\n\n"
            "- Unlimited AI commentary\n"
            "- Watchlist up to 50 symbols\n"
            "- Full charting with technical indicators\n\n"
            "For educational purposes only — not investment advice."
        )
        return name, desc
    if product == "byok":
        label = {"byok_pro_month": "Monthly", "byok_pro_year": "Yearly"}.get(
            plan_id, str(plan.get("label") or plan_id)
        )
        period = {"byok_pro_month": "month", "byok_pro_year": "year"}.get(plan_id, "")
        name = f"AI24X BYOK Pro · {label}"
        desc = (
            f"BYOK smart gateway service fee. ${usd:g}/{period}.\n\n"
            "- Bring your own API keys (smart routing + failover)\n"
            "- Multi-key load balancing and request cache\n"
            "- Cost dashboard by key / model / project\n\n"
            "Platform charges a gateway service fee only; no markup on upstream tokens."
        )
        return name, desc
    title = str(plan.get("title_en") or plan.get("title_zh") or plan_id)
    name = f"AI24X AI Gateway Credits · {title}"
    lines = [f"AI24X AI Gateway credits for the {title} plan. ${usd:g} one-time."]
    credits = int(plan.get("credit_tokens") or 0)
    days = int(plan.get("validity_days") or 0)
    if credits > 0 and days > 0:
        lines.append(f"Includes {credits:,} credits · valid {days} days.")
    elif credits > 0:
        lines.append(f"Includes {credits:,} credits.")
    elif days > 0:
        lines.append(f"Valid {days} days.")
    if plan.get("set_vip"):
        lines.append("Includes named-model VIP access.")
    lines.append("For developers. Educational purposes only.")
    return name, "\n".join(lines)


async def _create_product(
    cfg: Any, *, name: str, description: str, price: float, product: str, plan_id: str
) -> str:
    url = f"{dodo_api_base(cfg)}/products"
    body = {
        "name": str(name)[:100],
        "description": str(description)[:1000],
        "tax_category": "saas" if product == "markets" else "digital_products",
        "price": _price_obj(price),
        "metadata": {_MD_PRODUCT: product, _MD_PLAN: plan_id},
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT) as ac:
        r = await ac.post(url, json=body, headers=_headers(cfg))
    if r.status_code >= 400:
        try:
            detail = r.json()
        except Exception:
            detail = {"raw": r.text[:300]}
        raise RuntimeError(f"dodo_create_product {r.status_code}: {detail}")
    try:
        data = r.json()
    except Exception:
        data = {}
    pid = str(data.get("product_id") or "").strip()
    if not pid:
        raise RuntimeError("dodo_create_no_product_id")
    return pid


async def _update_product(
    cfg: Any, *, product_id: str, name: str, description: str, price: float
) -> None:
    url = f"{dodo_api_base(cfg)}/products/{product_id}"
    body = {
        "name": str(name)[:100],
        "description": str(description)[:1000],
        "price": _price_obj(price),
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT) as ac:
        r = await ac.patch(url, json=body, headers=_headers(cfg))
    if r.status_code >= 400:
        try:
            detail = r.json()
        except Exception:
            detail = {"raw": r.text[:300]}
        raise RuntimeError(f"dodo_update_product {r.status_code}: {detail}")


async def _unarchive_product(cfg: Any, *, product_id: str) -> None:
    url = f"{dodo_api_base(cfg)}/products/{product_id}/unarchive"
    async with httpx.AsyncClient(timeout=_TIMEOUT) as ac:
        r = await ac.post(url, headers=_headers(cfg))
    if r.status_code >= 400:
        try:
            detail = r.json()
        except Exception:
            detail = {"raw": r.text[:300]}
        raise RuntimeError(f"dodo_unarchive_product {r.status_code}: {detail}")


def _persist_dodo_id(product: str, plan_id: str, product_id: str) -> None:
    """新建/改名产品后回写 product_id：markets/byok 写覆盖文件，token 写 override。"""
    try:
        if product == "markets":
            from pay_products import set_market_dodo_product_id

            set_market_dodo_product_id(plan_id, product_id)
        elif product == "byok":
            from pay_products import set_byok_dodo_product_id

            set_byok_dodo_product_id(plan_id, product_id)
        else:
            from token_plans import set_dodo_product_id

            set_dodo_product_id(plan_id, product_id)
    except Exception as e:
        logger.warning("dodo sync persist id failed %s:%s: %r", product, plan_id, e)


async def _sync_one(
    cfg: Any,
    *,
    product: str,
    plan_id: str,
    plan: dict[str, Any],
    products: list[dict[str, Any]],
    report: dict[str, Any],
) -> None:
    item: dict[str, Any] = {
        "product": product,
        "plan": plan_id,
        "action": "error",
        "product_id": "",
        "name": "",
        "price_usd": None,
        "note": "",
    }
    try:
        usd = float(plan.get("price_usd") or 0)
        if usd <= 0:
            raise ValueError("price_usd <= 0")
        name, description = _plan_display(product, plan_id, plan)
        configured_id = str(plan.get("dodo_product_id") or "").strip()
        existing = _match_product(
            products, product=product, plan_id=plan_id, configured_id=configured_id
        )
        cents = int(round(usd * 100))
        item["name"] = name
        item["price_usd"] = round(usd, 2)
        if existing:
            pid = str(existing.get("product_id") or "").strip()
            item["product_id"] = pid
            cur_cents = _item_price_cents(existing)
            cur_name = str(existing.get("name") or "")
            cur_desc = str(existing.get("description") or "")
            if existing.get("_dodo_archived"):
                await _unarchive_product(cfg, product_id=pid)
                item["note"] = "archived→unarchived"
            if cur_cents == cents and cur_name == name and cur_desc == description:
                item["action"] = "unchanged"
            else:
                await _update_product(
                    cfg, product_id=pid, name=name, description=description, price=usd
                )
                item["action"] = "updated"
            # token/byok 套餐命中即回写 product_id，保证收银台可用
            # （markets 以 env DODO_PRODUCT_MARKETS_* 为准，仅新建/改名时回写）
            if product in ("token", "byok"):
                _persist_dodo_id(product, plan_id, pid)
        else:
            pid = await _create_product(
                cfg,
                name=name,
                description=description,
                price=usd,
                product=product,
                plan_id=plan_id,
            )
            item["product_id"] = pid
            item["action"] = "created"
            _persist_dodo_id(product, plan_id, pid)
    except Exception as e:
        logger.warning("dodo sync plan error product=%s plan=%s: %r", product, plan_id, e)
        item["note"] = str(e)[:300]
    report["items"].append(item)


def _empty_report(ok: bool, error: str = "", message: str = "") -> dict[str, Any]:
    return {
        "ok": ok,
        "error": error,
        "message": message,
        "mode": str(getattr(_pay_cfg(), "dodo_mode", "test") or "test"),
        "synced_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "summary": {"created": 0, "updated": 0, "unchanged": 0, "errors": 0},
        "items": [],
    }


async def sync_dodo_products() -> dict[str, Any]:
    """一键同步 markets + token 全部启用套餐到 Dodo 后台产品。"""
    cfg = _pay_cfg()
    if not dodo_api_key_ready(cfg):
        return _empty_report(
            False, "dodo_not_configured", "DODO_API_KEY 未配置，无法同步。"
        )
    report = _empty_report(True)
    report["mode"] = str(getattr(cfg, "dodo_mode", "test") or "test")
    try:
        products = await _get_products(cfg)
    except Exception as e:
        logger.warning("dodo products list failed: %r", e)
        return _empty_report(False, "dodo_list_failed", f"Dodo 商品列表拉取失败：{e}")

    from pay_products import resolve_byok_plans, resolve_market_plans
    from token_plans import resolved_plans

    for plan_id, plan in resolve_market_plans().items():
        if not plan.get("enabled", True):
            continue
        await _sync_one(
            cfg, product="markets", plan_id=plan_id, plan=plan, products=products, report=report
        )
    for plan_id, plan in resolve_byok_plans().items():
        if not plan.get("enabled", True):
            continue
        await _sync_one(
            cfg, product="byok", plan_id=plan_id, plan=plan, products=products, report=report
        )
    for plan_id, plan in resolved_plans().items():
        if not plan.get("enabled", True):
            continue
        await _sync_one(
            cfg, product="token", plan_id=plan_id, plan=plan, products=products, report=report
        )

    summary = {"created": 0, "updated": 0, "unchanged": 0, "errors": 0}
    for it in report["items"]:
        act = str(it.get("action") or "")
        if act in summary:
            summary[act] += 1
        else:
            summary["errors"] += 1
    report["summary"] = summary
    report["ok"] = summary["errors"] == 0
    return report
