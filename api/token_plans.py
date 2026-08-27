"""
Token 产品套餐目录（与 a1 行情官 VIP 配额套餐完全独立）。

定价口径（2026-08-02 终稿）：
- 钱包 token ≈ flash 当量；对外 flash 锚约 $0.35/M（Builder 约 $0.40/M）
- 主数据按国际价（USD 锚定）；国内收银台 CNY（微信/支付宝），国际 PayPal USD
- 入门包为小额体验档（$2 / 100 万 token）；单位成本高于大包，适合试水
- VIP 日赠仅可用于 flash/auto/共享档（见 token_mvp_service）
- 改价优先级：管理台覆盖文件 > env TOKEN_PRICE_*_FEN > 代码默认
- 前台 /v1/billing/plans 与后台同源 list_public_plans / get_plan
"""
from __future__ import annotations

import json
import logging
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_OVERRIDE_PATH = Path(__file__).resolve().parent / "data" / "token_plans_override.json"
# 管理台保存时镜像同步到 open 子站（同仓库 p/open/api/data），实现一个开关管两端
_OPEN_OVERRIDE_PATH = (
    Path(__file__).resolve().parents[1] / "p" / "open" / "api" / "data" / "token_plans_override.json"
)

_VIP_DAILY_WAN = 10  # 日赠约 10 万 token（与 VIP_DAILY_BONUS_TOKENS=100_000 对齐）

# plan_id → 覆盖 CNY 分的环境变量名
PLAN_PRICE_ENV: dict[str, str] = {
    "token_pack_10k": "TOKEN_PRICE_TOKEN_PACK_10K_FEN",
    "token_pack_100k": "TOKEN_PRICE_TOKEN_PACK_100K_FEN",
    "token_vip_month": "TOKEN_PRICE_TOKEN_VIP_MONTH_FEN",
    "token_vip_month_50w": "TOKEN_PRICE_TOKEN_VIP_MONTH_50W_FEN",
    "token_pack_mid": "TOKEN_PRICE_TOKEN_PACK_MID_FEN",
    "token_value_pack": "TOKEN_PRICE_TOKEN_VALUE_PACK_FEN",
}

# 代码默认（不含运行时价）；价由 _resolve_price_fen 计算
_PLAN_DEFAULTS: dict[str, dict[str, Any]] = {
    "token_pack_10k": {
        "title_zh": "入门包",
        "title_en": "Starter",
        # 国际小额整美元；CNY 按汇率折算（默认 ×7.2 → ¥14.40）
        "price_usd": 2.0,
        "default_fen": None,
        "credit_tokens": 1_000_000,
        "set_vip": False,
        "validity_days": 365,
        "enabled": True,
        "promo": True,
        "promo_max_purchases": 0,
        "note_zh": "小额体验包：$2 试水 100 万 token（≈ 数千次 flash 调用）。仅预充额度，不含名模资格；要点名请选 Scale。额度 12 个月有效。",
        "note_en": "Starter trial: $2 for 1M tokens (~thousands of flash calls). Credits only—no named-model access; choose Scale to name models. Valid 12 months.",
    },
    "token_pack_100k": {
        "title_zh": "开发包",
        "title_en": "Builder",
        "price_usd": 20.0,
        "default_fen": None,  # 由 USD×汇率推算
        "credit_tokens": 60_000_000,
        "set_vip": False,
        "validity_days": 365,
        "enabled": True,
        "promo": False,
        "note_zh": "预充 6,000 万 token（≈$0.333/百万），不含名模资格。日常 flash/auto 够用；pro/ultra 与点名名模需 VIP 资格（选 Scale 或 VIP 资格包）。额度 12 个月有效。",
        "note_en": "60M prepaid tokens (~$0.333/M). No named-model access. Great for everyday flash/auto; pro/ultra and named models need VIP (choose Scale or VIP Pass). Valid 12 months.",
    },
    "token_pack_mid": {
        "title_zh": "进阶包",
        "title_en": "Advanced",
        "price_usd": 49.0,
        "default_fen": None,
        "credit_tokens": 150_000_000,
        "set_vip": False,
        "validity_days": 365,
        "enabled": True,
        "promo": False,
        "note_zh": "大额预充 1.5 亿 token（≈$0.327/百万），不含名模资格。适合跑量/团队共用；要点名请选 Scale 组合包。额度 12 个月有效。",
        "note_en": "150M prepaid tokens (~$0.327/M)—no named-model access. Good for volume/teams; choose Scale to name models. Valid 12 months.",
    },
    "token_vip_month": {
        "title_zh": "VIP 资格包",
        "title_en": "VIP Pass",
        "price_usd": 15.0,
        "default_fen": None,
        "credit_tokens": 0,
        "set_vip": True,
        "vip_days": 30,
        "validity_days": 0,
        "enabled": True,  # 2026-08-05 重新启用为「VIP 资格包」（无额度，30 天资格）
        "promo": False,
        "note_zh": (
            "30 天 VIP 资格包：可点名名模、可用 pro/ultra（消耗预充额度）。不含额度。"
            "适合已有 Builder/Advanced 额度、只差资格的老开发者；新用户建议直接选 Scale（资格+额度一次齐）。"
        ),
        "note_en": (
            "30-day VIP access: name models and use pro/ultra (billed from prepaid credits). No credits included. "
            "Best for developers who already have prepaid credits. New users: choose Scale (access + credits in one)."
        ),
    },
    "token_vip_month_50w": {
        "title_zh": "VIP名模包",
        "title_en": "Scale",
        "price_usd": 99.0,
        "default_fen": None,
        "credit_tokens": 250_000_000,
        "set_vip": True,
        "vip_days": 365,
        "validity_days": 365,
        "enabled": True,
        "promo": False,
        "note_zh": (
            "点名模 + 大额预充一次齐：12 个月 VIP 名模资格 + 2.5 亿预充额度（12 个月有效）。"
            "VIP 有效期跟随套餐年限。"
        ),
        "note_en": (
            "Name models + bulk credits in one: 12-month VIP access + 250M prepaid (valid 12 months). "
            "VIP validity matches the plan term."
        ),
    },
    "token_value_pack": {
        "title_zh": "极致性价比·超值包",
        "title_en": "Value Pack",
        "price_usd": 9.9,
        "default_fen": None,
        "credit_tokens": 30_000_000,
        # 2026-08-08：不开全量 VIP；白名单点名资格由 value_pack 批次单独判定（30 天窗口）
        "set_vip": False,
        "value_pack": True,
        "vip_days": 30,
        "validity_days": 365,
        "enabled": True,
        "promo": True,
        "promo_max_purchases": 2,
        "note_zh": (
            "限时特惠 · 极致性价比：$9.9 得 3000 万 credits（≈$0.33/百万）+ 30 天白名单点名资格。 "
            "可点名超值包专属模型（DeepSeek Flash/Pro、GPT-5.6 Luna/Terra、Llama 4、Hy3、GPT-4o mini、"
            "GLM-5.2、Qwen Max/122B、Kimi K2.7 Code、MiniMax M3、MiMo Pro 等）；不包含国际旗舰点名 "
            "（GPT-5/5.4/4o、Claude、Gemini、Grok、Kimi K3）。限购 2 份；额度 12 个月有效。白名单随质量与成本滚动调整。"
        ),
        "note_en": (
            "Limited-time Value Pack: $9.9 for 30M credits (~$0.33/M) + 30-day named-model access to a curated "
            "whitelist (DeepSeek Flash/Pro, GPT-5.6 Luna/Terra, Llama 4, Hy3, GPT-4o mini, GLM-5.2, "
            "Qwen Max/122B, Kimi K2.7 Code, MiniMax M3, MiMo Pro). Flagship picks (GPT-5/5.4/4o, Claude, "
            "Gemini, Grok, Kimi K3) are not included. Max 2 per account; credits valid 12 months. "
            "The whitelist rotates with quality & cost baselines."
        ),
    },
    "token_test_01": {
        "title_zh": "小额测试包",
        "title_en": "Test Pack",
        # 支付通道小额实测专用：默认开放 $0.6，后台价表管理可随时关闭
        "price_usd": 0.6,
        "default_fen": None,
        "credit_tokens": 1_000_000,
        "set_vip": False,
        "validity_days": 365,
        "enabled": True,
        "promo": False,
        "promo_max_purchases": 0,
        "note_zh": "小额支付测试包：$0.6 试水 100 万 credits（≈ 数千次 flash 调用）。默认开放；管理员可在后台价表关闭。仅用于支付通道小额实测。额度 12 个月有效。",
        "note_en": (
            "Small-amount payment test pack: $0.6 for 1M credits (~thousands of flash calls). "
            "Enabled by default; admins can disable it from the dashboard. For payment-channel testing. "
            "Valid 12 months."
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
    try:
        if _OPEN_OVERRIDE_PATH.is_file():
            _OPEN_OVERRIDE_PATH.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
    except Exception as e:  # open 子站不在同仓库/不可写时仅告警，不影响主站保存
        logger.warning("token plans mirror to open failed: %r", e)


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
        "promo_max_purchases",
        "enabled",
        "set_vip",
        "credit_tokens",
        "validity_days",
        "vip_days",
        "price_usd",
        "creem_product_id",
        "dodo_product_id",
        "value_pack",
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
    # 价格口径：CNY 分 vs USD×汇率；偏差>5% 打标，公共列表可用预期分纠偏展示
    try:
        usd_v = float(p.get("price_usd") or 0)
        fen_v = int(p.get("price_fen") or 0)
        expected = int(round(usd_v * _usd_cny() * 100)) if usd_v > 0 else 0
        if expected > 0 and fen_v > 0:
            drift = abs(fen_v - expected) / float(expected)
            if drift > 0.05:
                p["_price_mismatch"] = True
                p["_price_fen_expected"] = expected
                p["_price_drift"] = round(drift, 4)
            else:
                p["_price_mismatch"] = False
        else:
            p["_price_mismatch"] = False
    except Exception:
        p["_price_mismatch"] = False
    return p


def resolved_plans() -> dict[str, dict[str, Any]]:
    return {pid: p for pid in _PLAN_DEFAULTS if (p := _resolve_plan(pid))}


# 兼容旧 import：TOKEN_PLANS 为解析后快照（启动时）；运行时请用 resolved_plans/get_plan
TOKEN_PLANS: dict[str, dict[str, Any]] = resolved_plans()


def _value_pack_models() -> list[str]:
    """超值包白名单点名模型（catalog id），与 model_warehouse.VALUE_PACK_ALLOWED_IDS 同源。"""
    try:
        from model_warehouse import VALUE_PACK_ALLOWED_IDS

        return sorted(VALUE_PACK_ALLOWED_IDS)
    except Exception:
        return []


def list_public_plans() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    fx = _usd_cny()
    for plan_id, p in resolved_plans().items():
        if not p.get("enabled", True):
            continue
        usd = float(p.get("price_usd") or 0)
        fen = int(p["price_fen"])
        # 公共价：若覆盖残留导致 CNY 与 USD 锚偏差过大，以前台展示用 USD 重算分（不改覆盖文件）
        if p.get("_price_mismatch") and p.get("_price_fen_expected"):
            try:
                import logging

                logging.getLogger("token_plans").warning(
                    "plan %s price_fen=%s drift from usd→%s (source=%s); public uses expected",
                    plan_id,
                    fen,
                    p.get("_price_fen_expected"),
                    p.get("_price_source"),
                )
            except Exception:
                pass
            fen = int(p["_price_fen_expected"])
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
                "value_pack": bool(p.get("value_pack")),
                "value_pack_models": _value_pack_models() if bool(p.get("value_pack")) else None,
                "vip_days": int(p.get("vip_days") or 0) or None,
                "validity_days": int(p.get("validity_days") or 0) or None,
                "note": note_zh,
                "note_zh": note_zh,
                "note_en": note_en,
                "promo": bool(p.get("promo")),
                "promo_max_purchases": int(p.get("promo_max_purchases") or 0) or None,
                "settle_hint_zh": "支持微信支付、支付宝",
                "settle_hint_en": "Pay with PayPal (USD) on the international site",
                # 前台能力标签（避免用户误会）
                "cap_credits": int(p.get("credit_tokens") or 0) > 0,
                "cap_vip": bool(p.get("set_vip")) or bool(p.get("value_pack")),
                "cap_named_ready": (bool(p.get("set_vip")) or bool(p.get("value_pack"))) and int(p.get("credit_tokens") or 0) > 0,
                # 双推荐：Value=入门转化，Scale=名模主力（关闭 $2/$0.6 后更要高亮）
                "recommended": plan_id in ("token_value_pack", "token_vip_month_50w"),
                "recommend_badge_zh": (
                    "入门首选"
                    if plan_id == "token_value_pack"
                    else ("名模首选" if plan_id == "token_vip_month_50w" else "")
                ),
                "recommend_badge_en": (
                    "Best start"
                    if plan_id == "token_value_pack"
                    else ("Best for named models" if plan_id == "token_vip_month_50w" else "")
                ),
            }
        )
    # Value → Scale → 其余（小额靠后；后台关闭后自然不出现）
    _ORDER = {
        "token_value_pack": 0,
        "token_vip_month_50w": 1,
        "token_pack_100k": 2,
        "token_pack_mid": 3,
        "token_vip_month": 4,
        "token_pack_10k": 5,
        "token_test_01": 6,
    }
    out.sort(key=lambda row: _ORDER.get(str(row.get("plan") or ""), 99))
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
                "price_mismatch": bool(p.get("_price_mismatch")),
                "price_fen_expected": int(p["_price_fen_expected"])
                if p.get("_price_fen_expected")
                else None,
                "note_zh": str(p.get("note_zh") or ""),
                "creem_product_id": str(p.get("creem_product_id") or ""),
                "dodo_product_id": str(p.get("dodo_product_id") or ""),
            }
        )
    return {
        "ok": True,
        "usd_cny": fx,
        "plans": rows,
        "editable": True,
        "ops_note": (
            "价表前后台同源。本页可改 CNY 分 / USD / 到账 token / 启停；"
            "若某行 price_mismatch=true，说明 CNY 分与 USD×汇率偏差>5%（常见测试残留），请改正或清覆盖；"
            "前台公开展示已自动用 USD 重算分，但后台仍显示覆盖原值便于排查。"
            "保存写入 api/data/token_plans_override.json，立即生效。"
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
        if "creem_product_id" in item and item["creem_product_id"] is not None:
            row["creem_product_id"] = str(item["creem_product_id"])[:64]
        if "dodo_product_id" in item and item["dodo_product_id"] is not None:
            row["dodo_product_id"] = str(item["dodo_product_id"])[:64]
        cur[pid] = row
    _save_overrides(cur)
    global TOKEN_PLANS
    TOKEN_PLANS = resolved_plans()
    return list_admin_plans()


def set_dodo_product_id(plan_id: str, product_id: str) -> bool:
    """Dodo 同步创建/改名产品后回写 product_id（持久化到 override）。"""
    pid = str(plan_id or "").strip()
    if pid not in _PLAN_DEFAULTS:
        return False
    cur = _load_overrides()
    row = dict(cur.get(pid) or {})
    row["dodo_product_id"] = str(product_id or "").strip()
    cur[pid] = row
    _save_overrides(cur)
    global TOKEN_PLANS
    TOKEN_PLANS = resolved_plans()
    return True


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
