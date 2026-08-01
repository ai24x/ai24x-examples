"""
免费共享通道（独立运营域）。

与付费 flash/pro/ultra 分离：余额用尽后可选继续走 L0 共享池（限日帽），
主路径仍引导充值。配置写入 api/data/free_shared_override.json。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

_OVERRIDE_PATH = Path(__file__).resolve().parent / "data" / "free_shared_override.json"

# 共享池目录（仓库式；用户对外仍只见 shared）
SHARED_CATALOG: list[dict[str, Any]] = [
    {
        "id": "silicon-qwen",
        "title": "硅基 Qwen2.5-7B",
        "provider": "siliconflow",
        "model_id": "Qwen/Qwen2.5-7B-Instruct",
        "cost": "免费/极低",
        "quality": "国内稳 · 推荐主力",
        "access": "live",
        "scale_note": "靠硅基免费额度 + 日帽；人多时加第二硅基账号或切 OR free",
    },
    {
        "id": "or-auto",
        "title": "OpenRouter Auto",
        "provider": "openrouter",
        "model_id": "openrouter/auto",
        "cost": "免费池/低价",
        "quality": "自动选便宜端点",
        "access": "live",
        "scale_note": "OR 免费约 50 次/日/账号；可多 Key 轮询（P1）",
    },
    {
        "id": "or-free-router",
        "title": "OpenRouter Free Router",
        "provider": "openrouter",
        "model_id": "openrouter/free",
        "cost": "$0",
        "quality": "纯免费模型路由",
        "access": "ready",
        "scale_note": "质量浮动大；作第三梯队",
    },
    {
        "id": "sf-glm-flash",
        "title": "硅基 GLM-4-Flash",
        "provider": "siliconflow",
        "model_id": "THUDM/glm-4-9b-chat",
        "cost": "低价/活动",
        "quality": "中文备选",
        "access": "planned",
        "scale_note": "以硅基控制台实际免费列表为准再启用",
    },
    {
        "id": "byok-user",
        "title": "用户自带 Key（BYOK）",
        "provider": "byok",
        "model_id": "user-provided",
        "cost": "用户侧承担",
        "quality": "不降平台质量成本",
        "access": "planned",
        "scale_note": "后期：用户填 OR/硅基 Key，走其额度；平台只收薄网关费",
    },
]

_DEFAULTS: dict[str, Any] = {
    "enabled": True,
    "daily_req_cap": 30,
    "daily_token_cap": 30_000,
    "prefer": "silicon-qwen",  # 主力：容灾链起点 / 轮询起点（单选）
    "pool_enabled": ["silicon-qwen", "or-auto"],  # 启用成员（多选）→ 容灾或轮询
    "dispatch_mode": "failover",  # failover=挂了自动顶上；rotate=多条轮询
    "brand_model": "shared",
    "upgrade_first": True,
    "ops_title": "免费共享通道",
}

_PREFER_ALIASES = {
    "siliconflow": "silicon-qwen",
    "openrouter_auto": "or-auto",
    "or-auto": "or-auto",
    "silicon-qwen": "silicon-qwen",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _load() -> dict[str, Any]:
    try:
        if not _OVERRIDE_PATH.is_file():
            return {}
        raw = json.loads(_OVERRIDE_PATH.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def _save(data: dict[str, Any]) -> None:
    _OVERRIDE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _OVERRIDE_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def effective_config() -> dict[str, Any]:
    ov = _load()
    out = dict(_DEFAULTS)
    for k in _DEFAULTS:
        if k in ov and ov[k] is not None:
            out[k] = ov[k]
    out["enabled"] = bool(out["enabled"])
    out["upgrade_first"] = bool(out.get("upgrade_first", True))
    try:
        out["daily_req_cap"] = max(1, min(500, int(out["daily_req_cap"])))
    except (TypeError, ValueError):
        out["daily_req_cap"] = _DEFAULTS["daily_req_cap"]
    try:
        out["daily_token_cap"] = max(1000, min(2_000_000, int(out["daily_token_cap"])))
    except (TypeError, ValueError):
        out["daily_token_cap"] = _DEFAULTS["daily_token_cap"]

    prefer = str(out.get("prefer") or "silicon-qwen").strip().lower()
    prefer = _PREFER_ALIASES.get(prefer, prefer)
    valid_ids = {c["id"] for c in SHARED_CATALOG}
    if prefer not in valid_ids:
        prefer = "silicon-qwen"
    out["prefer"] = prefer

    pe = out.get("pool_enabled")
    if not isinstance(pe, list) or not pe:
        pe = list(_DEFAULTS["pool_enabled"])
    pe2 = []
    for x in pe:
        xid = _PREFER_ALIASES.get(str(x).strip().lower(), str(x).strip())
        if xid in valid_ids and xid not in pe2:
            pe2.append(xid)
    if prefer not in pe2:
        pe2.insert(0, prefer)
    out["pool_enabled"] = pe2
    dm = str(out.get("dispatch_mode") or "failover").strip().lower()
    if dm not in ("failover", "rotate"):
        dm = "failover"
    out["dispatch_mode"] = dm
    out["brand_model"] = str(out.get("brand_model") or "shared")[:32]
    return out


_rotate_seq = 0


def ordered_pool_ids(cfg: Optional[dict[str, Any]] = None) -> list[str]:
    """返回本次尝试顺序：failover=主力优先；rotate=轮转起点后接其余。"""
    global _rotate_seq
    cfg = cfg or effective_config()
    ids = list(cfg.get("pool_enabled") or [])
    prefer = str(cfg.get("prefer") or "")
    if prefer in ids:
        ids = [prefer] + [x for x in ids if x != prefer]
    if not ids:
        return ["silicon-qwen", "or-auto"]
    if cfg.get("dispatch_mode") == "rotate" and len(ids) > 1:
        _rotate_seq = (_rotate_seq + 1) % len(ids)
        start = _rotate_seq
        return ids[start:] + ids[:start]
    return ids


def resolve_catalog_upstream(cid: str) -> Optional[dict[str, Any]]:
    """把目录 id 解析成可调用的上游（base/key/model/provider）。不可用返回 None。"""
    from model_router import _env, _normalize_openai_base, _upstream_mode

    row = next((c for c in SHARED_CATALOG if c["id"] == cid), None)
    if not row or row.get("access") == "planned" or row.get("provider") == "byok":
        return None
    prov = str(row.get("provider") or "")
    model_id = str(row.get("model_id") or "")

    if prov == "siliconflow":
        key = ""
        try:
            from llm_keys import silicon_free_key

            key = silicon_free_key()
        except Exception:
            key = _env("SILICONFLOW_API_KEY") or _env("TOKEN_LLM_L0_KEY")
        if not key:
            return None
        base = _env("SILICONFLOW_BASE_URL") or _env("TOKEN_LLM_L0_BASE") or "https://api.siliconflow.cn/v1"
        model = _env("SILICONFLOW_MODEL") or _env("TOKEN_LLM_L0_MODEL") or model_id
        return {
            "catalog_id": cid,
            "base": _normalize_openai_base(base),
            "key": key,
            "model": model,
            "provider": "siliconflow",
            "title": row.get("title"),
        }

    if prov == "openrouter":
        if _upstream_mode() != "openrouter":
            # 仍可用 OR Key 直打共享备，不强制整站 mode
            pass
        key = ""
        try:
            from llm_keys import openrouter_free_key

            key = openrouter_free_key()
        except Exception:
            key = _env("OPENROUTER_API_KEY") or _env("TOKEN_LLM_KEY")
        if not key:
            return None
        base = _env("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1"
        return {
            "catalog_id": cid,
            "base": _normalize_openai_base(base),
            "key": key,
            "model": model_id or "openrouter/auto",
            "provider": "openrouter",
            "title": row.get("title"),
        }
    return None


def build_shared_attempt_chain() -> list[dict[str, Any]]:
    """启用池按策略排序，过滤不可用项 → 实际调用链。"""
    cfg = effective_config()
    out: list[dict[str, Any]] = []
    for cid in ordered_pool_ids(cfg):
        up = resolve_catalog_upstream(cid)
        if up:
            out.append(up)
    return out


def run_shared_pool_chat(
    *,
    prompt: str,
    temperature: float = 0.7,
    max_tokens: int = 1000,
) -> Any:
    """共享池专用路由：按 failover/rotate 依次尝试启用成员。"""
    import time

    from model_router import RouteResult, _call_openai_compatible, _timeout_s

    chain = build_shared_attempt_chain()
    attempts: list[dict[str, Any]] = []
    timeout_s = _timeout_s()
    if not chain:
        return RouteResult(
            ok=False,
            text="",
            model="",
            layer="L0",
            provider="",
            token_count=0,
            attempts=[{"ok": False, "error": "shared_pool_empty"}],
            error="shared_pool_empty",
        )

    for up in chain:
        t0 = time.time()
        try:
            out = _call_openai_compatible(
                base=up["base"],
                key=up["key"],
                model=up["model"],
                prompt=prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout_s=timeout_s,
                provider=str(up.get("provider") or ""),
            )
            elapsed = time.time() - t0
            used = str(out.get("raw_model") or up["model"])
            attempts.append(
                {
                    "catalog_id": up.get("catalog_id"),
                    "layer": "L0",
                    "model": used,
                    "provider": up.get("provider"),
                    "ok": True,
                    "ms": int(elapsed * 1000),
                }
            )
            return RouteResult(
                ok=True,
                text=str(out["text"]),
                model=used,
                layer="L0",
                provider=str(up.get("provider") or "shared"),
                token_count=max(1, int(out["tokens"])),
                attempts=attempts,
            )
        except Exception as e:
            elapsed = time.time() - t0
            attempts.append(
                {
                    "catalog_id": up.get("catalog_id"),
                    "layer": "L0",
                    "model": up.get("model"),
                    "provider": up.get("provider"),
                    "ok": False,
                    "error": str(e)[:200],
                    "ms": int(elapsed * 1000),
                }
            )
            continue

    return RouteResult(
        ok=False,
        text="",
        model="",
        layer="L0",
        provider="",
        token_count=0,
        attempts=attempts,
        error="all_shared_failed",
    )


def is_enabled() -> bool:
    return bool(effective_config()["enabled"])

def _catalog_runtime(cid: str, *, l0: dict, mode: str, or_key: bool) -> dict[str, Any]:
    row = next((c for c in SHARED_CATALOG if c["id"] == cid), None)
    if not row:
        return {"id": cid, "ready": False, "runtime": "unknown"}
    access = str(row.get("access") or "planned")
    ready = False
    runtime = "planned"
    if access == "planned":
        runtime = "planned"
    elif row["provider"] == "siliconflow":
        ready = bool(l0.get("key")) and (
            str(l0.get("provider") or "") == "siliconflow" or bool(l0.get("key"))
        )
        runtime = "active" if ready else "need_key"
    elif row["provider"] == "openrouter":
        ready = bool(or_key)
        runtime = "active" if ready else "need_key"
    elif row["provider"] == "byok":
        runtime = "planned"
        ready = False
    return {
        **row,
        "ready": ready,
        "runtime": runtime,
    }


def admin_snapshot(db: Optional[Session] = None) -> dict[str, Any]:
    from model_router import _env, _layer_upstream, _upstream_mode

    cfg = effective_config()
    l0 = _layer_upstream("L0")
    mode = _upstream_mode()
    or_key = False
    try:
        from llm_keys import openrouter_main_key, openrouter_free_key

        or_key = bool(openrouter_main_key() or openrouter_free_key())
    except Exception:
        or_key = bool(_env("OPENROUTER_API_KEY") or _env("TOKEN_LLM_KEY"))

    catalog_out = []
    for c in SHARED_CATALOG:
        rt = _catalog_runtime(c["id"], l0=l0, mode=mode, or_key=or_key)
        enabled = c["id"] in cfg["pool_enabled"]
        is_primary = c["id"] == cfg["prefer"]
        role = "primary" if is_primary else ("enabled" if enabled else "standby")
        if not enabled:
            role = "off"
        catalog_out.append({**rt, "enabled": enabled, "role": role})

    # 兼容旧 UI：当前启用链（按 prefer 优先）
    pool = []
    ordered = [cfg["prefer"]] + [x for x in cfg["pool_enabled"] if x != cfg["prefer"]]
    for i, cid in enumerate(ordered):
        rt = _catalog_runtime(cid, l0=l0, mode=mode, or_key=or_key)
        pool.append(
            {
                **rt,
                "role": "primary" if i == 0 else "backup",
                "enabled": True,
            }
        )

    today_users = 0
    today_reqs = 0
    if db is not None:
        try:
            from models import BillingLedger
            from sqlalchemy import func

            day = _utcnow().strftime("%Y-%m-%d")
            q = (
                db.query(
                    func.count(BillingLedger.id),
                    func.count(func.distinct(BillingLedger.auth_user_id)),
                )
                .filter(
                    BillingLedger.entry_type == "shared",
                    BillingLedger.note.like(f"free_shared {day}%"),
                )
                .first()
            )
            if q:
                today_reqs = int(q[0] or 0)
                today_users = int(q[1] or 0)
        except Exception:
            pass

    live_n = sum(1 for x in catalog_out if x.get("runtime") == "active" and x.get("enabled"))
    return {
        "ok": True,
        "config": cfg,
        "pool": pool,
        "catalog": catalog_out,
        "l0": {
            "provider": l0.get("provider"),
            "model": l0.get("model"),
            "key_set": bool(l0.get("key")),
            "upstream_mode": mode,
        },
        "connectivity": {
            "primary_ready": bool(pool and pool[0].get("ready")),
            "backup_ready": bool(len(pool) > 1 and pool[1].get("ready")),
            "live_enabled_count": live_n,
            "dispatch_mode": cfg["dispatch_mode"],
            "attempt_order": [x.get("catalog_id") for x in build_shared_attempt_chain()],
            "note": (
                "当前 L0 实际命中："
                + str(l0.get("provider") or "-")
                + " / "
                + str(l0.get("model") or "-")
                + ("（Key 已配）" if l0.get("key") else "（无 Key）")
            ),
        },
        "scale_tips": [
            "主力=单选：failover 先打谁；rotate 轮询起点",
            "启用=多选：挂了自动顶上，或参与轮询分摊风控",
            "人多：多启用 live + 选轮询",
            "质量敏感：主力保持硅基 Qwen",
            "规模期再上 BYOK；勿把 Flash/Pro 塞进共享池",
        ],
        "today": {"requests": today_reqs, "users": today_users},
        "funnel": {
            "steps": [
                "注册小礼包试用",
                "用尽 → 主推付费套餐",
                "或选「免费共享」→ 仅共享池 · 日帽限流",
            ],
            "upgrade_first": cfg["upgrade_first"],
        },
        "ops_note": (
            "启用可多选；主力单选。"
            "调度：挂了自动顶上=主力→其余依次试；多条轮询=每次换起点。"
            "用户对外只见 shared。"
        ),
    }


def update_config(patch: dict[str, Any]) -> dict[str, Any]:
    cur = _load()
    if "enabled" in patch and patch["enabled"] is not None:
        cur["enabled"] = bool(patch["enabled"])
    if "daily_req_cap" in patch and patch["daily_req_cap"] is not None:
        cur["daily_req_cap"] = int(patch["daily_req_cap"])
    if "daily_token_cap" in patch and patch["daily_token_cap"] is not None:
        cur["daily_token_cap"] = int(patch["daily_token_cap"])
    if "prefer" in patch and patch["prefer"] is not None:
        cur["prefer"] = str(patch["prefer"]).strip().lower()
    if "upgrade_first" in patch and patch["upgrade_first"] is not None:
        cur["upgrade_first"] = bool(patch["upgrade_first"])
    if "brand_model" in patch and patch["brand_model"] is not None:
        cur["brand_model"] = str(patch["brand_model"]).strip()[:32] or "shared"
    if "dispatch_mode" in patch and patch["dispatch_mode"] is not None:
        cur["dispatch_mode"] = str(patch["dispatch_mode"]).strip().lower()
    if "pool_enabled" in patch and patch["pool_enabled"] is not None:
        if isinstance(patch["pool_enabled"], list):
            cur["pool_enabled"] = [str(x).strip() for x in patch["pool_enabled"] if str(x).strip()]
    _save(cur)
    return admin_snapshot()


def _shared_counts_today(db: Session, auth_user_id: int) -> tuple[int, int]:
    from models import BillingLedger

    day = _utcnow().strftime("%Y-%m-%d")
    rows = (
        db.query(BillingLedger)
        .filter(
            BillingLedger.auth_user_id == int(auth_user_id),
            BillingLedger.entry_type == "shared",
            BillingLedger.note.like(f"free_shared {day}%"),
        )
        .all()
    )
    reqs = len(rows)
    toks = sum(int(r.tokens or 0) for r in rows)
    return reqs, toks


def assert_shared_allowed(db: Session, auth_user_id: int) -> dict[str, Any]:
    """余额用尽后走共享：校验开关与日帽。"""
    cfg = effective_config()
    if not cfg["enabled"]:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "message_zh": "余额不足，请充值后再试",
                "message_en": "Insufficient balance. Please top up and try again.",
                "message": "余额不足，请充值后再试",
                "code": "insufficient_balance",
            },
        )
    reqs, toks = _shared_counts_today(db, int(auth_user_id))
    _quota_detail = {
        "message_zh": "今日免费额度已用完，请充值继续使用，或明日再试。",
        "message_en": "Today’s free quota is used up. Top up to continue, or try again tomorrow.",
        "message": "今日免费额度已用完，请充值继续使用，或明日再试。",
        "code": "free_quota_exhausted",
    }
    if reqs >= int(cfg["daily_req_cap"]):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=_quota_detail,
        )
    if toks >= int(cfg["daily_token_cap"]):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=_quota_detail,
        )
    return {
        "mode": "shared",
        "remain_req": int(cfg["daily_req_cap"]) - reqs,
        "remain_tokens": int(cfg["daily_token_cap"]) - toks,
        "brand_model": cfg["brand_model"],
        "prefer": cfg["prefer"],
    }


def record_shared_usage(
    db: Session,
    *,
    auth_user_id: int,
    tokens: int,
    model: Optional[str],
    request_id: Optional[str],
) -> None:
    from models import BillingLedger

    day = _utcnow().strftime("%Y-%m-%d")
    db.add(
        BillingLedger(
            auth_user_id=int(auth_user_id),
            entry_type="shared",
            amount=0,
            model=(model or "")[:64] or None,
            tokens=max(0, int(tokens)),
            request_id=request_id,
            note=f"free_shared {day}",
        )
    )
    db.commit()


def resolve_chat_billing_mode(
    db: Session,
    *,
    auth_user_id: int,
    requested_model: Optional[str],
    force_shared: bool = False,
) -> dict[str, Any]:
    """
    返回 {mode: paid|shared, wallet?, shared?}。
    - 有余额：付费
    - 无余额且（force_shared 或 model=shared）且通道开启：共享
    - 否则 402（detail 可含可转共享提示，由调用方组文案）
    """
    from token_mvp_service import ensure_period_bonus, get_or_create_wallet
    from auth_user_service import raise_if_frozen
    from models import AuthUser

    u = db.query(AuthUser).filter(AuthUser.id == int(auth_user_id)).first()
    raise_if_frozen(u)
    w = ensure_period_bonus(db, get_or_create_wallet(db, int(auth_user_id)))
    bal = int(w.balance_tokens or 0)
    req = (requested_model or "").strip().lower()
    cfg = effective_config()
    want_shared = force_shared or req in ("shared", "free-shared", "free_shared")

    if bal > 0 and not want_shared:
        return {"mode": "paid", "wallet": w, "balance": bal}

    if bal > 0 and want_shared:
        # 有余额仍选共享：允许（体验共享档），不扣余额
        shared = assert_shared_allowed(db, int(auth_user_id))
        return {"mode": "shared", "wallet": w, "balance": bal, "shared": shared}

    if bal <= 0:
        if want_shared or (cfg["enabled"] and not cfg.get("upgrade_first")):
            shared = assert_shared_allowed(db, int(auth_user_id))
            return {"mode": "shared", "wallet": w, "balance": 0, "shared": shared}
        # 默认：余额不足先 402，前端展示充值 + 「继续免费」按钮
        extra = ""
        if cfg["enabled"]:
            extra = "也可选择免费共享通道继续体验。"
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=("余额不足，请充值后再试。" + extra).strip(),
        )

    return {"mode": "paid", "wallet": w, "balance": bal}
