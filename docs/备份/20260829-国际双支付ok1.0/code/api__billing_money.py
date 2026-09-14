"""
Billing amount & currency — single source of truth.

Rules:
- User wallet credits are always USD cents (amount_usd on fulfill).
- Order amount_fen semantics depend on channel:
  - wechat/alipay: CNY fen (domestic checkout only)
  - paypal/dodo/creem/crypto: USD cents
- International site (TOKEN_PAY_CN_CHANNELS_ENABLED=false): UI/API expose USD only;
  WeChat/Alipay hidden (they cannot charge USD).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

_ADMIN_TZ = ZoneInfo("Asia/Shanghai")

ADMIN_PRODUCT_LABELS: dict[str, str] = {
    "token": "Gateway 托管额度",
    "markets": "行情官 Pro",
    "byok": "BYOK Pro",
}


def admin_product_label(product: str) -> str:
    pid = str(product or "token").strip().lower() or "token"
    return ADMIN_PRODUCT_LABELS.get(pid, pid)


def parse_admin_date_bound(raw: Optional[str], *, end_of_day: bool = False) -> Optional[datetime]:
    """管理端日期筛选：YYYY-MM-DD 按东八区日界；也接受 ISO datetime。"""
    s = str(raw or "").strip()
    if not s:
        return None
    try:
        if len(s) == 10 and s[4] == "-" and s[7] == "-":
            y, m, d = (int(s[0:4]), int(s[5:7]), int(s[8:10]))
            if end_of_day:
                local = datetime(y, m, d, 23, 59, 59, 999000, tzinfo=_ADMIN_TZ)
            else:
                local = datetime(y, m, d, 0, 0, 0, tzinfo=_ADMIN_TZ)
            return local.astimezone(timezone.utc)
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


USD_CHANNELS = frozenset({"paypal", "creem", "crypto", "dodo"})


def cn_pay_channels_enabled() -> bool:
    try:
        from config import settings

        return bool(getattr(settings, "token_pay_cn_channels_enabled", True))
    except Exception:
        return True


def international_billing_profile() -> bool:
    """True when site targets international users (USD checkout, hide CN rails)."""
    return not cn_pay_channels_enabled()


def order_currency(channel: str) -> str:
    return "USD" if str(channel or "").lower() in USD_CHANNELS else "CNY"


def order_credit_usd_cents(row: Any) -> int:
    """Wallet credit in USD cents — always from plan USD anchor for token products."""
    product = str(getattr(row, "product", "") or "token")
    if product == "markets":
        ch = str(getattr(row, "channel", "") or "").lower()
        if ch in USD_CHANNELS:
            return max(1, int(getattr(row, "amount_fen", 0) or 0))
        from token_plans import _usd_cny

        fx = _usd_cny()
        return max(1, int(round(int(getattr(row, "amount_fen", 0) or 0) / fx)))
    from token_plans import _resolve_plan

    plan = _resolve_plan(str(getattr(row, "plan", "") or ""))
    if plan:
        try:
            usd = float(plan.get("price_usd") or 0)
        except (TypeError, ValueError):
            usd = 0.0
        if usd > 0:
            return max(1, int(round(usd * 100)))
    ch = str(getattr(row, "channel", "") or "").lower()
    if ch in USD_CHANNELS:
        return max(1, int(getattr(row, "amount_fen", 0) or 0))
    from token_plans import _usd_cny

    fx = _usd_cny()
    return max(1, int(round(int(getattr(row, "amount_fen", 0) or 0) / fx)))


def order_settle_amount_fen(row: Any) -> int:
    """Checkout/display minor units: USD cents or CNY fen by channel."""
    ch = str(getattr(row, "channel", "") or "").lower()
    if ch in USD_CHANNELS:
        if str(getattr(row, "product", "") or "token") == "markets":
            return max(1, int(getattr(row, "amount_fen", 0) or 0))
        from token_plans import _resolve_plan

        plan = _resolve_plan(str(getattr(row, "plan", "") or ""))
        if plan:
            try:
                usd = float(plan.get("price_usd") or 0)
            except (TypeError, ValueError):
                usd = 0.0
            if usd > 0:
                return max(1, int(round(usd * 100)))
        return max(1, int(getattr(row, "amount_fen", 0) or 0))
    return max(1, int(getattr(row, "amount_fen", 0) or 0))


def format_money_label(amount_minor: int, currency: str) -> str:
    v = (int(amount_minor) or 0) / 100.0
    if str(currency).upper() == "USD":
        return f"${v:.2f}"
    return f"CNY {v:.2f}"


def order_money_fields(row: Any) -> dict[str, Any]:
    settle = order_settle_amount_fen(row)
    currency = order_currency(str(getattr(row, "channel", "") or ""))
    stored = int(getattr(row, "amount_fen", 0) or 0)
    credit_usd = order_credit_usd_cents(row)
    return {
        "amount_fen": settle,
        "amount_stored_fen": stored,
        "currency": currency,
        "amount_label": format_money_label(settle, currency),
        "amount_usd_cents": credit_usd,
        "amount_usd_label": format_money_label(credit_usd, "USD"),
        "amount_mismatch": stored != settle,
    }


def format_admin_datetime(iso: Optional[str], *, now: Optional[datetime] = None) -> str:
    """Admin UI: 今天→21:57；昨天→昨天 21:57；7天内/更早→08-27 21:57（东八区）。"""
    if not iso:
        return "—"
    try:
        raw = str(iso).strip()
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        local = dt.astimezone(_ADMIN_TZ)
    except Exception:
        return str(iso)[:16]

    now = now or datetime.now(_ADMIN_TZ)
    if now.tzinfo is None:
        now = now.replace(tzinfo=_ADMIN_TZ)
    else:
        now = now.astimezone(_ADMIN_TZ)

    hm = f"{local.hour:02d}:{local.minute:02d}"
    if local.date() == now.date():
        return hm
    if local.date() == (now.date() - timedelta(days=1)):
        return f"昨天 {hm}"
    return f"{local.month:02d}-{local.day:02d} {hm}"


def admin_order_row_extras(row: Any) -> dict[str, Any]:
    money = order_money_fields(row)
    created = getattr(row, "created_at", None)
    paid = getattr(row, "paid_at", None)
    created_iso = created.isoformat() if created else None
    paid_iso = paid.isoformat() if paid else None
    return {
        **money,
        "created_at": created_iso,
        "paid_at": paid_iso,
        "created_at_display": format_admin_datetime(created_iso),
        "paid_at_display": format_admin_datetime(paid_iso),
    }
