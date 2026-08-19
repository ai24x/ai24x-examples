"""
BYOK 智能网关核心（Bring Your Own Key）—— 2026-08-18 Phase 1。

定位：用户自带上游 API Key，平台只做技术转发 + 智能路由 + 故障转移 + 缓存 +
用量统计/成本看板，按「平台服务费」收费，不再囤平台 token、不再赚 token 差价。

合规红线（务必长期遵守）：
1. 用户 key 一律 AES-256-GCM 加密落库（encrypt_key / decrypt_key），
   日志 / 响应 / 前端只暴露 key_prefix（明文前 8 位），绝不落明文。
2. 路由目标 = 用户自有 key；任何路径都不向上游发平台聚合 key。
3. 请求缓存按「用户 + 模型 + 载荷」哈希命中，不落 prompt 原文，跨用户隔离。
4. 服务费口径透明：平台收网关服务费，不赚 token 差价（页面/接口明示）。
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import secrets
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Iterator, Optional

logger = logging.getLogger(__name__)

# 进程内请求缓存：{cache_key: (expire_ts, payload)}；跨 worker 不共享（多实例建议后续上 Redis）
_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_CACHE_LOCK = threading.Lock()
_CACHE_MAX_ITEMS = 20000


# ---------------------------------------------------------------------------
# Provider 注册表（OpenAI 兼容直连；Anthropic 走 Messages 适配器）
# ---------------------------------------------------------------------------
BYOK_PROVIDERS: dict[str, dict[str, Any]] = {
    "openai": {
        "title": "OpenAI",
        "base": "https://api.openai.com/v1",
        "openai_compatible": True,
        "tiers": {"auto": "gpt-4o-mini", "flash": "gpt-4o-mini", "pro": "gpt-4o", "ultra": "gpt-4o"},
    },
    "anthropic": {
        "title": "Anthropic (Messages API)",
        "base": "https://api.anthropic.com",
        "openai_compatible": False,
        "tiers": {
            "auto": "claude-haiku-4-5",
            "flash": "claude-haiku-4-5",
            "pro": "claude-sonnet-5-0",
            "ultra": "claude-opus-5-0",
        },
    },
    "deepseek": {
        "title": "DeepSeek",
        "base": "https://api.deepseek.com/v1",
        "openai_compatible": True,
        "tiers": {
            "auto": "deepseek-chat",
            "flash": "deepseek-chat",
            "pro": "deepseek-reasoner",
            "ultra": "deepseek-reasoner",
        },
    },
    "openrouter": {
        "title": "OpenRouter",
        "base": "https://openrouter.ai/api/v1",
        "openai_compatible": True,
        "tiers": {"auto": "openrouter/auto", "flash": "openrouter/auto", "pro": "openrouter/auto", "ultra": "openrouter/auto"},
    },
    "siliconflow": {
        "title": "硅基流动 SiliconFlow",
        "base": "https://api.siliconflow.com/v1",
        "openai_compatible": True,
        "tiers": {
            "auto": "Qwen/Qwen3-30B-A3B-Instruct-2507",
            "flash": "Qwen/Qwen2.5-7B-Instruct",
            "pro": "Qwen/Qwen2.5-72B-Instruct",
            "ultra": "Qwen/Qwen2.5-72B-Instruct",
        },
    },
    "together": {
        "title": "Together AI",
        "base": "https://api.together.xyz/v1",
        "openai_compatible": True,
        "tiers": {"auto": "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo", "flash": "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo", "pro": "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo", "ultra": "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo"},
    },
    "moonshot": {
        "title": "Moonshot Kimi",
        "base": "https://api.moonshot.cn/v1",
        "openai_compatible": True,
        "tiers": {"auto": "moonshot-v1-8k", "flash": "moonshot-v1-8k", "pro": "moonshot-v1-32k", "ultra": "moonshot-v1-128k"},
    },
    "zhipu": {
        "title": "智谱 GLM",
        "base": "https://open.bigmodel.cn/api/paas/v4",
        "openai_compatible": True,
        "tiers": {"auto": "glm-4-flash", "flash": "glm-4-flash", "pro": "glm-4-plus", "ultra": "glm-4-plus"},
    },
    "qwen": {
        "title": "阿里云百炼 DashScope",
        "base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "openai_compatible": True,
        "tiers": {"auto": "qwen-plus", "flash": "qwen-turbo", "pro": "qwen-plus", "ultra": "qwen-max"},
    },
    "xai": {
        "title": "xAI Grok",
        "base": "https://api.x.ai/v1",
        "openai_compatible": True,
        "tiers": {"auto": "grok-2-latest", "flash": "grok-2-latest", "pro": "grok-2-latest", "ultra": "grok-3"},
    },
    "groq": {
        "title": "Groq",
        "base": "https://api.groq.com/openai/v1",
        "openai_compatible": True,
        "tiers": {"auto": "llama-3.3-70b-versatile", "flash": "llama-3.1-8b-instant", "pro": "llama-3.3-70b-versatile", "ultra": "llama-3.3-70b-versatile"},
    },
    "mistral": {
        "title": "Mistral",
        "base": "https://api.mistral.ai/v1",
        "openai_compatible": True,
        "tiers": {"auto": "mistral-small-latest", "flash": "mistral-small-latest", "pro": "mistral-medium-latest", "ultra": "mistral-large-latest"},
    },
    "custom": {
        "title": "自定义 OpenAI 兼容端点",
        "base": "",
        "openai_compatible": True,
        "tiers": {},
    },
}


@dataclass
class ByokRouteResult:
    """与 model_router.RouteResult 字段兼容，另加 BYOK 专属字段。"""

    ok: bool
    text: str = ""
    model: str = ""
    layer: str = "BYOK"
    provider: str = "byok"
    token_count: int = 0
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    attempts: list[dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None
    billing_mult: int = 1
    public_model: Optional[str] = None
    tool_calls: Optional[list[dict[str, Any]]] = None
    finish_reason: Optional[str] = None
    byok_key_id: Optional[int] = None
    cached: bool = False
    upstream_model: str = ""
    project: Optional[str] = None


# ---------------------------------------------------------------------------
# 开关
# ---------------------------------------------------------------------------
def _enabled() -> bool:
    try:
        from config import settings

        return bool(settings.byok_enabled)
    except Exception:
        return False


def _fallback_to_platform() -> bool:
    try:
        from config import settings

        return bool(settings.byok_fallback_to_platform)
    except Exception:
        return True


def _cache_ttl_s() -> int:
    try:
        from config import settings

        return max(0, int(settings.byok_cache_ttl_s))
    except Exception:
        return 300


def _free_monthly_limit() -> int:
    try:
        from config import settings

        return max(0, int(settings.byok_free_monthly_requests))
    except Exception:
        return 1000


def _enforce_free_cap() -> bool:
    try:
        from config import settings

        return bool(settings.byok_enforce_free_cap)
    except Exception:
        return False


def service_status() -> dict[str, Any]:
    """网关状态（控制台展示 + 服务费口径透明）。"""
    try:
        from config import settings

        fee_mode = str(settings.byok_fee_mode or "service_fee")
    except Exception:
        fee_mode = "service_fee"
    return {
        "enabled": _enabled(),
        "fee_mode": fee_mode,
        "service_fee_note": "平台只收取网关服务费，不赚取上游 token 差价；用户 key 直接调用其自有上游额度。",
        "fallback_to_platform": _fallback_to_platform(),
        "cache_ttl_s": _cache_ttl_s(),
        "free_monthly_requests": _free_monthly_limit(),
        "enforce_free_cap": _enforce_free_cap(),
        "providers": sorted(BYOK_PROVIDERS.keys()),
    }


def subscription_status(db, auth_user_id: int) -> dict[str, Any]:
    """当前 BYOK 订阅状态（无订阅返回 free 档；过期自动标记 expired 不硬删）。"""
    from datetime import datetime, timezone

    from models import ByokSubscription

    row = (
        db.query(ByokSubscription)
        .filter(ByokSubscription.auth_user_id == int(auth_user_id))
        .order_by(ByokSubscription.expires_at.desc())
        .first()
    )
    if not row:
        return {
            "plan": None,
            "tier": "free",
            "status": "none",
            "started_at": None,
            "expires_at": None,
            "active": False,
        }
    now = datetime.now(timezone.utc)
    active = str(row.status) == "active" and row.expires_at is not None and row.expires_at > now
    if str(row.status) == "active" and not active and row.expires_at is not None:
        row.status = "expired"
        try:
            db.commit()
        except Exception:
            db.rollback()
    return {
        "plan": str(row.plan or ""),
        "tier": "pro" if active else "free",
        "status": str(row.status or "active"),
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        "active": active,
    }


def activate_subscription(
    db,
    *,
    auth_user_id: int,
    plan: str,
    source_order: str = "",
) -> dict[str, Any]:
    """支付履约：开通/续期 BYOK Pro 订阅（幂等由订单抢占保证，此处续期叠加天数）。"""
    from datetime import datetime, timedelta, timezone

    from byok_plans import resolve_byok_plan
    from models import ByokSubscription

    meta = resolve_byok_plan(plan or "")
    if not meta:
        raise ValueError(f"unknown_byok_plan:{plan}")
    days = int(meta.get("days") or 30)
    now = datetime.now(timezone.utc)
    row = (
        db.query(ByokSubscription)
        .filter(ByokSubscription.auth_user_id == int(auth_user_id))
        .order_by(ByokSubscription.expires_at.desc())
        .first()
    )
    if row and str(row.status) == "active" and row.expires_at and row.expires_at > now:
        base = row.expires_at  # 续期：从当前到期日顺延
        row.plan = plan
        row.expires_at = base + timedelta(days=days)
    else:
        base = now
        row = ByokSubscription(
            auth_user_id=int(auth_user_id),
            plan=plan,
            status="active",
            started_at=now,
            expires_at=now + timedelta(days=days),
        )
        db.add(row)
    row.source_order = str(source_order or "")[:32]
    db.commit()
    db.refresh(row)
    return {
        "ok": True,
        "plan": str(row.plan),
        "tier": "pro",
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        "source_order": str(row.source_order or ""),
    }


# ---------------------------------------------------------------------------
# AES-256-GCM 加解密（明文绝不落盘）
# ---------------------------------------------------------------------------
_ENC_PREFIX = "aesgcm:v1:"


def _crypto_key() -> bytes:
    try:
        from config import settings

        secret = str(settings.secret_key or "ai24x-byok-dev")
    except Exception:
        secret = "ai24x-byok-dev"
    return hashlib.sha256(("byok:" + secret).encode("utf-8")).digest()


def encrypt_key(plain: str) -> str:
    """AES-256-GCM 加密；返回 aesgcm:v1:<nonce_b64>:<ct_b64>。"""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    nonce = secrets.token_bytes(12)
    ct = AESGCM(_crypto_key()).encrypt(nonce, (plain or "").encode("utf-8"), None)
    return (
        _ENC_PREFIX
        + base64.b64encode(nonce).decode("ascii")
        + ":"
        + base64.b64encode(ct).decode("ascii")
    )


def decrypt_key(stored: str) -> str:
    """解密存储的 key；失败抛 ValueError（调用方不得把异常里的明文外泄）。"""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    s = str(stored or "")
    if not s.startswith(_ENC_PREFIX):
        raise ValueError("BYOK key format invalid")
    try:
        _, _, nonce_b64, ct_b64 = s.split(":", 3)
        nonce = base64.b64decode(nonce_b64)
        ct = base64.b64decode(ct_b64)
        return AESGCM(_crypto_key()).decrypt(nonce, ct, None).decode("utf-8")
    except Exception:
        raise ValueError("BYOK key decrypt failed")


def key_prefix(plain: str) -> str:
    raw = str(plain or "").strip()
    return raw[:8] if raw else ""


# ---------------------------------------------------------------------------
# Key 辅助
# ---------------------------------------------------------------------------
def parse_models_json(raw: Optional[str]) -> list[str]:
    if not raw:
        return []
    try:
        v = json.loads(raw)
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
    except Exception:
        pass
    return []


def dump_models_json(models: Optional[list[str]]) -> str:
    return json.dumps([str(m).strip() for m in (models or []) if str(m).strip()], ensure_ascii=False)


def provider_default_base(provider: str) -> str:
    p = BYOK_PROVIDERS.get(provider)
    return str(p.get("base") or "") if p else ""


def resolve_upstream_model(requested: str, provider: str, key_models: list[str]) -> Optional[str]:
    """把请求模型解析为「该 key 实际要调的上游模型名」。解析不到返回 None。"""
    req = str(requested or "").strip()
    if not req:
        return None
    req_l = req.lower()
    # 1) key.models 精确匹配（含 OpenRouter 风格前缀 openai/gpt-4o 的 basename 匹配）
    if key_models:
        for m in key_models:
            ml = m.lower()
            if ml == req_l:
                return m
        # OpenRouter 风格前缀（openai/gpt-4o / deepseek/deepseek-chat）：basename 匹配
        for m in key_models:
            ml = m.lower()
            base_m = ml.split("/", 1)[1] if "/" in ml else ml
            if base_m == req_l:
                return m
        if "/" in req_l:
            base_req = req_l.split("/", 1)[1]
            for m in key_models:
                if m.lower() == base_req or m.lower().endswith("/" + base_req):
                    return m
        return None
    # 2) 品牌档 → provider 档位默认模型
    if req_l in ("auto", "flash", "pro", "ultra", "free", "shared"):
        p = BYOK_PROVIDERS.get(provider) or {}
        tiers = p.get("tiers") or {}
        return tiers.get(req_l) or tiers.get("auto")
    # 3) 平台模型目录映射（provider 感知：openrouter 用 openrouter_id，其余用 direct_id）
    try:
        from model_warehouse import catalog_merged

        for row in catalog_merged():
            if str(row.get("id") or "").lower() == req_l:
                if provider == "openrouter":
                    or_id = row.get("openrouter_id")
                    if or_id:
                        return str(or_id)
                else:
                    d_id = row.get("direct_id")
                    if d_id:
                        return str(d_id)
    except Exception:
        pass
    # 4) OpenRouter 风格 "openai/gpt-4o"：拆掉前缀
    if "/" in req_l and req_l.split("/", 1)[0] in ("openrouter", "openai", "anthropic", "deepseek"):
        return req
    # 5) 直接透传（key.models 为空 = 该 key 可服务任意模型）
    return req


# ---------------------------------------------------------------------------
# 请求缓存（用户隔离；仅非流式、无 tools）
# ---------------------------------------------------------------------------
def _cacheable(request: Any) -> bool:
    if getattr(request, "stream", False):
        return False
    if getattr(request, "tools", None):
        return False
    return _cache_ttl_s() > 0


def _cache_key(auth_user_id: int, provider: str, model: str, request: Any) -> str:
    payload = {
        "u": int(auth_user_id),
        "p": provider,
        "m": model,
        "msgs": getattr(request, "messages", None),
        "prompt": getattr(request, "prompt", ""),
        "t": float(getattr(request, "temperature", 0.7) or 0.7),
        "mt": int(getattr(request, "max_tokens", 1000) or 1000),
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _cache_get(k: str) -> Optional[dict[str, Any]]:
    with _CACHE_LOCK:
        item = _CACHE.get(k)
        if item and item[0] > time.time():
            return item[1]
        _CACHE.pop(k, None)
    return None


def _cache_put(k: str, data: dict[str, Any]) -> None:
    ttl = _cache_ttl_s()
    if ttl <= 0:
        return
    with _CACHE_LOCK:
        now = time.time()
        _CACHE[k] = (now + ttl, data)
        if len(_CACHE) > _CACHE_MAX_ITEMS:
            expired = [kk for kk, v in _CACHE.items() if v[0] < now]
            for kk in expired:
                _CACHE.pop(kk, None)
            # 仍超限：按插入序清最老的一半
            if len(_CACHE) > _CACHE_MAX_ITEMS:
                for kk in list(_CACHE.keys())[: _CACHE_MAX_ITEMS // 4]:
                    _CACHE.pop(kk, None)


def cache_stats() -> dict[str, Any]:
    with _CACHE_LOCK:
        n = len(_CACHE)
    return {"items": n, "ttl_s": _cache_ttl_s()}


# ---------------------------------------------------------------------------
# 成本估算（目录参考价，仅看板展示；不代表上游真实账单）
# ---------------------------------------------------------------------------
def estimate_cost_usd_micro(model: str, prompt_tokens: int, completion_tokens: int) -> int:
    cost_in = 0.0
    cost_out = 0.0
    m = str(model or "").lower()
    # 平台目录外的常用别名 → 目录参考价（口径与平台一致，非上游真实账单）
    _COST_ALIASES = {
        "deepseek-chat": "ds-v4-flash",
        "deepseek-reasoner": "ds-v4-pro",
        "qwen-plus": "silicon-qwen",
        "qwen-turbo": "silicon-qwen",
    }
    m = _COST_ALIASES.get(m, m)
    try:
        from model_warehouse import catalog_merged

        for row in catalog_merged():
            rid = str(row.get("id") or "").lower()
            if rid == m or str(row.get("openrouter_id") or "").lower() == m or str(row.get("direct_id") or "").lower() == m:
                cost_in = float(row.get("cost_in") or 0)
                cost_out = float(row.get("cost_out") or 0)
                break
    except Exception:
        pass
    usd = (max(0, int(prompt_tokens)) * cost_in + max(0, int(completion_tokens)) * cost_out) / 1e6
    return max(0, int(round(usd * 1e6)))


# ---------------------------------------------------------------------------
# 用量记录 + key 健康统计
# ---------------------------------------------------------------------------
def record_usage(
    db,
    *,
    auth_user_id: int,
    byok_key_id: Optional[int],
    provider: str,
    model: str,
    upstream_model: str,
    project: Optional[str],
    request_id: str,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    latency_ms: int,
    success: bool,
    error_code: Optional[str] = None,
    cached: bool = False,
) -> None:
    try:
        from models import ByokUsage

        cost = 0 if cached else estimate_cost_usd_micro(
            upstream_model or model, prompt_tokens, completion_tokens
        )
        db.add(
            ByokUsage(
                auth_user_id=int(auth_user_id),
                byok_key_id=byok_key_id,
                provider=str(provider or ""),
                model=str(model or ""),
                upstream_model=str(upstream_model or ""),
                project=str(project or "")[:64] or None,
                request_id=str(request_id or "")[:64] or None,
                prompt_tokens=max(0, int(prompt_tokens)),
                completion_tokens=max(0, int(completion_tokens)),
                total_tokens=max(0, int(total_tokens)),
                cost_usd_micro=cost,
                latency_ms=max(0, int(latency_ms)),
                success=bool(success),
                error_code=str(error_code or "")[:64] or None,
                cached=bool(cached),
            )
        )
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        logger.exception("record_byok_usage failed")


def _update_key_stats(db, key: Any, *, ok: bool, latency_ms: Optional[int], err: str = "") -> None:
    try:
        from models import ByokKey

        row = db.query(ByokKey).filter(ByokKey.id == int(key.id)).first()
        if row is None:
            return
        from datetime import datetime

        if ok:
            row.success_count = int(row.success_count or 0) + 1
            if latency_ms is not None:
                row.last_latency_ms = int(latency_ms)
            row.last_error = None
        else:
            row.fail_count = int(row.fail_count or 0) + 1
            row.last_error = str(err or "")[:200]
        row.last_used_at = datetime.utcnow()
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass


def free_month_usage(db, auth_user_id: int) -> dict[str, Any]:
    """当月 BYOK 用量（免费档统计展示；Phase 1 不硬限，BYOK_ENFORCE_FREE_CAP=1 才限）。"""
    try:
        from datetime import datetime, timezone
        from sqlalchemy import func
        from models import ByokUsage

        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        total = (
            db.query(func.count(ByokUsage.id), func.coalesce(func.sum(ByokUsage.total_tokens), 0))
            .filter(
                ByokUsage.auth_user_id == int(auth_user_id),
                ByokUsage.created_at >= month_start,
            )
            .first()
        )
        used = int(total[0] or 0) if total else 0
        tokens = int(total[1] or 0) if total else 0
    except Exception:
        used, tokens = 0, 0
    limit = _free_monthly_limit()
    return {
        "month_used_requests": used,
        "month_used_tokens": tokens,
        "month_limit_requests": limit,
        "over_cap": bool(limit and used >= limit),
    }


# ---------------------------------------------------------------------------
# Key 选路
# ---------------------------------------------------------------------------
def _score_key(k: Any) -> float:
    """越小越优先：成功率主导，其次最近延迟，其次 priority。"""
    total = max(1, int(k.success_count or 0) + int(k.fail_count or 0))
    success_rate = int(k.success_count or 0) / total
    latency = max(0, int(k.last_latency_ms or 0)) if k.last_latency_ms is not None else 300
    return (1.0 - success_rate) * 1000.0 + latency / 60.0 + int(k.priority or 100) / 100.0


def _ordered_candidates(candidates: list[tuple[Any, str]]) -> list[tuple[Any, str]]:
    return sorted(candidates, key=lambda c: (_score_key(c[0]), int(c[0].id)))


# ---------------------------------------------------------------------------
# 上游调用（OpenAI 兼容直连 + Anthropic Messages 适配）
# ---------------------------------------------------------------------------
def _upstream_error_kind(e: Exception) -> tuple[str, str]:
    try:
        from model_router import _upstream_error_class

        return _upstream_error_class(e)
    except Exception:
        return "network", str(e)[:300]


def _timeout_s(stream: bool = False) -> float:
    try:
        from model_router import _stream_timeout_s, _timeout_s

        return _stream_timeout_s() if stream else _timeout_s()
    except Exception:
        return 60.0


def _shared_client():
    from model_router import _SHARED_CLIENT

    return _SHARED_CLIENT


def _normalize_msgs_for_anthropic(prompt: str, messages: Optional[list[dict[str, Any]]]) -> tuple[str, list[dict[str, str]]]:
    """返回 (system_text, anthropic_messages)。"""
    system_parts: list[str] = []
    out: list[dict[str, str]] = []
    raw = messages if isinstance(messages, list) else (
        [{"role": "user", "content": prompt}] if prompt else []
    )
    for m in raw:
        if not isinstance(m, dict):
            continue
        role = str(m.get("role") or "user")
        content = m.get("content")
        if role == "system":
            system_parts.append(_content_to_text(content))
            continue
        if role not in ("user", "assistant"):
            continue
        out.append({"role": role, "content": _content_to_text(content)})
    if not out and prompt:
        out.append({"role": "user", "content": str(prompt)})
    return "\n\n".join([p for p in system_parts if p]), out


def _content_to_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for it in content:
            if isinstance(it, dict):
                parts.append(str(it.get("text") or ""))
            else:
                parts.append(str(it))
        return "".join(parts)
    return str(content)


def _anthropic_tools(tools: Optional[list[dict[str, Any]]]) -> Optional[list[dict[str, Any]]]:
    if not tools:
        return None
    out = []
    for t in tools:
        if not isinstance(t, dict):
            continue
        fn = t.get("function") or {}
        out.append(
            {
                "name": str(fn.get("name") or "") or None,
                "description": str(fn.get("description") or "") or None,
                "input_schema": fn.get("parameters") or {"type": "object", "properties": {}},
            }
        )
    return [x for x in out if x.get("name")]


def _anthropic_tool_choice(tool_choice: Any) -> Optional[dict[str, Any]]:
    """OpenAI tool_choice → Anthropic tool_choice。"""
    if tool_choice is None:
        return None
    if isinstance(tool_choice, str):
        v = tool_choice.lower()
        if v in ("auto", "none", "required"):
            return {"type": v}
        return {"type": "auto"}
    if isinstance(tool_choice, dict):
        tc = tool_choice.get("type")
        fn = (tool_choice.get("function") or {}) if isinstance(tool_choice.get("function"), dict) else {}
        name = fn.get("name") or tool_choice.get("name")
        if tc == "function" and name:
            return {"type": "tool", "name": str(name)}
        if tc in ("auto", "none", "required"):
            return {"type": tc}
    return {"type": "auto"}


def _call_anthropic_messages(
    *,
    base: str,
    key: str,
    model: str,
    prompt: str,
    temperature: float,
    max_tokens: int,
    messages: Optional[list[dict[str, Any]]],
    tools: Optional[list[dict[str, Any]]] = None,
    tool_choice: Any = None,
    timeout_s: float = 60.0,
) -> dict[str, Any]:
    import httpx

    sys_text, msgs = _normalize_msgs_for_anthropic(prompt, messages)
    url = str(base or "").rstrip("/") + "/v1/messages"
    headers = {
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    body: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": msgs,
    }
    if sys_text:
        body["system"] = sys_text
    atools = _anthropic_tools(tools)
    if atools:
        body["tools"] = atools
        ac = _anthropic_tool_choice(tool_choice)
        if ac:
            body["tool_choice"] = ac
    r = _shared_client().post(
        url,
        headers=headers,
        json=body,
        timeout=httpx.Timeout(timeout_s, connect=min(10.0, timeout_s)),
    )
    r.raise_for_status()
    data = r.json()
    text_parts: list[str] = []
    tool_calls: list[dict[str, Any]] = []
    for block in data.get("content") or []:
        if not isinstance(block, dict):
            continue
        bt = block.get("type")
        if bt == "text":
            text_parts.append(str(block.get("text") or ""))
        elif bt == "tool_use":
            tool_calls.append(
                {
                    "id": str(block.get("id") or ""),
                    "type": "function",
                    "function": {
                        "name": str(block.get("name") or ""),
                        "arguments": json.dumps(block.get("input") or {}, ensure_ascii=False),
                    },
                }
            )
    text = "".join(text_parts).strip()
    usage = data.get("usage") or {}
    prompt_t = int(usage.get("input_tokens") or 0)
    completion_t = int(usage.get("output_tokens") or 0)
    total = max(1, prompt_t + completion_t) if (prompt_t or completion_t) else max(1, int(len(text.split()) * 1.3)) if text else 1
    if prompt_t <= 0 and completion_t <= 0:
        prompt_est = max(1, int(len(prompt) / 4)) if prompt else max(1, total // 2)
        prompt_t = min(prompt_est, max(1, total - 1))
        completion_t = max(1, total - prompt_t)
    stop = str(data.get("stop_reason") or "")
    finish = "stop"
    if stop == "max_tokens":
        finish = "length"
    elif stop == "tool_use":
        finish = "tool_calls"
    return {
        "text": text,
        "tokens": total,
        "prompt_tokens": prompt_t,
        "completion_tokens": completion_t,
        "raw_model": model,
        "tool_calls": tool_calls or None,
        "finish_reason": finish,
    }


def _stream_anthropic_messages(
    *,
    base: str,
    key: str,
    model: str,
    prompt: str,
    temperature: float,
    max_tokens: int,
    messages: Optional[list[dict[str, Any]]],
    tools: Optional[list[dict[str, Any]]] = None,
    tool_choice: Any = None,
    timeout_s: float = 120.0,
) -> Iterator[dict[str, Any]]:
    """Anthropic Messages 流式 → 统一事件：delta / tool_calls_delta / done / error。"""
    import httpx

    sys_text, msgs = _normalize_msgs_for_anthropic(prompt, messages)
    url = str(base or "").rstrip("/") + "/v1/messages"
    headers = {
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    body: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": msgs,
        "stream": True,
    }
    if sys_text:
        body["system"] = sys_text
    atools = _anthropic_tools(tools)
    if atools:
        body["tools"] = atools
        ac = _anthropic_tool_choice(tool_choice)
        if ac:
            body["tool_choice"] = ac

    full_parts: list[str] = []
    input_tokens = 0
    output_tokens = 0
    stop_reason = ""
    tc_acc: dict[int, dict[str, Any]] = {}
    try:
        with _shared_client().stream(
            "POST", url, headers=headers, json=body, timeout=httpx.Timeout(timeout_s, connect=min(10.0, timeout_s))
        ) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if not line:
                    continue
                if isinstance(line, bytes):
                    line = line.decode("utf-8", errors="replace")
                s = str(line).strip()
                if not s.startswith("data:"):
                    continue
                data = s[5:].strip()
                if not data:
                    continue
                try:
                    import json as _json

                    obj = _json.loads(data)
                except Exception:
                    continue
                etype = str(obj.get("type") or "")
                if etype == "message_start":
                    msg = obj.get("message") or {}
                    u = msg.get("usage") or {}
                    input_tokens = max(input_tokens, int(u.get("input_tokens") or 0))
                elif etype == "content_block_start":
                    cb = obj.get("content_block") or {}
                    if cb.get("type") == "tool_use":
                        idx = int(obj.get("index") or 0)
                        tc_acc.setdefault(
                            idx,
                            {
                                "id": str(cb.get("id") or ""),
                                "type": "function",
                                "function": {"name": str(cb.get("name") or ""), "arguments": ""},
                            },
                        )
                elif etype == "content_block_delta":
                    d = obj.get("delta") or {}
                    dt = d.get("type")
                    if dt == "text_delta" and d.get("text"):
                        piece = str(d.get("text"))
                        full_parts.append(piece)
                        yield {"type": "delta", "text": piece, "raw_model": model, "provider": "anthropic"}
                    elif dt == "input_json_delta":
                        idx = int(obj.get("index") or 0)
                        slot = tc_acc.setdefault(
                            idx,
                            {
                                "id": "",
                                "type": "function",
                                "function": {"name": "", "arguments": ""},
                            },
                        )
                        slot["function"]["arguments"] += str(d.get("partial_json") or "")
                        yield {
                            "type": "tool_calls_delta",
                            "tool_calls": [{"index": idx, "id": slot.get("id"), "type": "function", "function": {"name": slot["function"].get("name"), "arguments": slot["function"].get("arguments")}}],
                            "raw_model": model,
                            "provider": "anthropic",
                        }
                elif etype == "message_delta":
                    d = obj.get("delta") or {}
                    if d.get("stop_reason"):
                        stop_reason = str(d.get("stop_reason"))
                    u = obj.get("usage") or {}
                    output_tokens = max(output_tokens, int(u.get("output_tokens") or 0))
                elif etype == "message_stop":
                    break
                elif etype == "error":
                    err = obj.get("error") or {}
                    raise RuntimeError(str(err.get("message") or err))
    except Exception as e:
        kind, detail = _upstream_error_kind(e)
        yield {"type": "error", "error": detail, "raw_model": model, "provider": "anthropic", "error_kind": kind, "partial": "".join(full_parts)}
        return

    full = "".join(full_parts)
    assembled_tcs = None
    if tc_acc:
        assembled_tcs = [tc_acc[i] for i in sorted(tc_acc.keys())]
    total = max(1, input_tokens + output_tokens) if (input_tokens or output_tokens) else max(1, int(len(full.split()) * 1.3)) if full else 1
    if input_tokens <= 0 and output_tokens <= 0:
        prompt_est = max(1, int(len(prompt) / 4)) if prompt else max(1, total // 2)
        input_tokens = min(prompt_est, max(1, total - 1))
        output_tokens = max(1, total - input_tokens)
    finish = "stop"
    if stop_reason == "max_tokens":
        finish = "length"
    elif stop_reason == "tool_use":
        finish = "tool_calls"
    yield {
        "type": "done",
        "text": full,
        "tokens": total,
        "prompt_tokens": input_tokens,
        "completion_tokens": output_tokens,
        "raw_model": model,
        "provider": "anthropic",
        "tool_calls": assembled_tcs,
        "finish_reason": finish,
        "tool_calls_streamed": bool(assembled_tcs),
    }


def _upstream_call(
    *,
    provider: str,
    base: str,
    key: str,
    model: str,
    request: Any,
    timeout_s: float,
    stream: bool = False,
):
    """统一上游调用入口：Anthropic 走 Messages 适配器，其余 OpenAI 兼容直连。"""
    if provider == "anthropic":
        if stream:
            return _stream_anthropic_messages(
                base=base,
                key=key,
                model=model,
                prompt=getattr(request, "prompt", "") or "",
                temperature=float(getattr(request, "temperature", 0.7) or 0.7),
                max_tokens=int(getattr(request, "max_tokens", 1000) or 1000),
                messages=getattr(request, "messages", None),
                tools=getattr(request, "tools", None),
                tool_choice=getattr(request, "tool_choice", None),
                timeout_s=timeout_s,
            )
        return _call_anthropic_messages(
            base=base,
            key=key,
            model=model,
            prompt=getattr(request, "prompt", "") or "",
            temperature=float(getattr(request, "temperature", 0.7) or 0.7),
            max_tokens=int(getattr(request, "max_tokens", 1000) or 1000),
            messages=getattr(request, "messages", None),
            tools=getattr(request, "tools", None),
            tool_choice=getattr(request, "tool_choice", None),
            timeout_s=timeout_s,
        )
    from model_router import _call_openai_compatible, _stream_openai_compatible

    if stream:
        return _stream_openai_compatible(
            base=base,
            key=key,
            model=model,
            prompt=getattr(request, "prompt", "") or "",
            temperature=float(getattr(request, "temperature", 0.7) or 0.7),
            max_tokens=int(getattr(request, "max_tokens", 1000) or 1000),
            timeout_s=timeout_s,
            provider=provider,
            messages=getattr(request, "messages", None),
            tools=getattr(request, "tools", None),
            tool_choice=getattr(request, "tool_choice", None),
        )
    return _call_openai_compatible(
        base=base,
        key=key,
        model=model,
        prompt=getattr(request, "prompt", "") or "",
        temperature=float(getattr(request, "temperature", 0.7) or 0.7),
        max_tokens=int(getattr(request, "max_tokens", 1000) or 1000),
        timeout_s=timeout_s,
        provider=provider,
        messages=getattr(request, "messages", None),
        tools=getattr(request, "tools", None),
        tool_choice=getattr(request, "tool_choice", None),
    )


# ---------------------------------------------------------------------------
# 非流式路由（多 key 故障转移 + 缓存）
# ---------------------------------------------------------------------------
def route_byok_chat(
    db,
    *,
    auth_user_id: int,
    request: Any,
    region_hint: Optional[str] = None,
    project: Optional[str] = None,
) -> Optional[ByokRouteResult]:
    """BYOK 非流式路由；返回 None = 无可用 key 或全部失败且允许回退平台。"""
    if not _enabled():
        return None
    from models import ByokKey

    keys = (
        db.query(ByokKey)
        .filter(ByokKey.auth_user_id == int(auth_user_id), ByokKey.status == "active")
        .all()
    )
    if not keys:
        return None
    requested = str(request.model or "auto").strip() or "auto"
    candidates: list[tuple[Any, str]] = []
    for k in keys:
        km = parse_models_json(k.models)
        up_model = resolve_upstream_model(requested, str(k.provider or ""), km)
        if up_model:
            candidates.append((k, up_model))
    if not candidates:
        return None

    request_id = f"req_{uuid.uuid4().hex[:16]}"
    cacheable = _cacheable(request)
    cache_key = ""
    if cacheable:
        # 同一用户 + 同一 provider/模型/载荷 才命中
        first_k, first_m = _ordered_candidates(candidates)[0]
        cache_key = _cache_key(auth_user_id, str(first_k.provider or ""), first_m, request)
        hit = _cache_get(cache_key)
        if hit:
            record_usage(
                db,
                auth_user_id=auth_user_id,
                byok_key_id=first_k.id,
                provider=str(first_k.provider or ""),
                model=requested,
                upstream_model=first_m,
                project=project,
                request_id=request_id,
                prompt_tokens=int(hit.get("prompt_tokens") or 0),
                completion_tokens=int(hit.get("completion_tokens") or 0),
                total_tokens=int(hit.get("tokens") or 0),
                latency_ms=0,
                success=True,
                cached=True,
            )
            return ByokRouteResult(
                ok=True,
                text=str(hit.get("text") or ""),
                model=str(hit.get("model") or first_m),
                public_model=requested,
                token_count=int(hit.get("tokens") or 0),
                prompt_tokens=int(hit.get("prompt_tokens") or 0),
                completion_tokens=int(hit.get("completion_tokens") or 0),
                provider="byok",
                layer="BYOK",
                tool_calls=hit.get("tool_calls"),
                finish_reason=hit.get("finish_reason") or "stop",
                byok_key_id=first_k.id,
                cached=True,
                upstream_model=first_m,
                project=project,
                attempts=[{"ok": True, "cached": True, "provider": first_k.provider, "model": first_m}],
            )

    last_err = ""
    for k, up_model in _ordered_candidates(candidates):
        provider = str(k.provider or "")
        base = str(k.base_url or "").strip() or provider_default_base(provider)
        if not base:
            last_err = f"{provider}: missing base_url"
            continue
        try:
            plain = decrypt_key(k.key_cipher)
            t0 = time.time()
            out = _upstream_call(
                provider=provider,
                base=base,
                key=plain,
                model=up_model,
                request=request,
                timeout_s=_timeout_s(stream=False),
                stream=False,
            )
            latency_ms = int((time.time() - t0) * 1000)
            _update_key_stats(db, k, ok=True, latency_ms=latency_ms)
            res = ByokRouteResult(
                ok=True,
                text=str(out.get("text") or ""),
                model=str(out.get("raw_model") or up_model),
                public_model=requested,
                token_count=max(1, int(out.get("tokens") or 1)),
                prompt_tokens=max(0, int(out.get("prompt_tokens") or 0)),
                completion_tokens=max(0, int(out.get("completion_tokens") or 0)),
                provider="byok",
                layer="BYOK",
                tool_calls=out.get("tool_calls"),
                finish_reason=out.get("finish_reason") or "stop",
                byok_key_id=k.id,
                cached=False,
                upstream_model=up_model,
                project=project,
                attempts=[{"ok": True, "provider": provider, "model": up_model, "ms": latency_ms, "key_id": k.id}],
            )
            record_usage(
                db,
                auth_user_id=auth_user_id,
                byok_key_id=k.id,
                provider=provider,
                model=requested,
                upstream_model=up_model,
                project=project,
                request_id=request_id,
                prompt_tokens=res.prompt_tokens or 0,
                completion_tokens=res.completion_tokens or 0,
                total_tokens=res.token_count,
                latency_ms=latency_ms,
                success=True,
            )
            if cacheable and cache_key:
                _cache_put(
                    cache_key,
                    {
                        "text": res.text,
                        "tokens": res.token_count,
                        "prompt_tokens": res.prompt_tokens,
                        "completion_tokens": res.completion_tokens,
                        "model": res.model,
                        "tool_calls": res.tool_calls,
                        "finish_reason": res.finish_reason,
                    },
                )
            return res
        except Exception as e:
            kind, detail = _upstream_error_kind(e)
            _update_key_stats(db, k, ok=False, latency_ms=None, err=detail)
            record_usage(
                db,
                auth_user_id=auth_user_id,
                byok_key_id=k.id,
                provider=provider,
                model=requested,
                upstream_model=up_model,
                project=project,
                request_id=request_id,
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                latency_ms=0,
                success=False,
                error_code=kind,
            )
            last_err = f"{provider}/{up_model}: {kind}"
            logger.warning("byok key %s failed provider=%s model=%s kind=%s", k.id, provider, up_model, kind)
            if kind == "format":
                break
    if _fallback_to_platform():
        return None
    return ByokRouteResult(
        ok=False,
        error=f"byok_all_failed: {last_err or 'no candidates'}",
        provider="byok",
        layer="BYOK",
        attempts=[],
        public_model=requested,
        project=project,
    )


# ---------------------------------------------------------------------------
# 流式路由（多 key 故障转移；首包前失败切下一把）
# ---------------------------------------------------------------------------
def stream_byok_chat(
    db,
    *,
    auth_user_id: int,
    request: Any,
    region_hint: Optional[str] = None,
    project: Optional[str] = None,
) -> Optional[Iterator[dict[str, Any]]]:
    """BYOK 流式；返回事件生成器（meta/delta/tool_calls_delta/done/error），
    无可用 key 时返回 None（调用方回退平台路由）。"""
    if not _enabled():
        return None
    from models import ByokKey

    keys = (
        db.query(ByokKey)
        .filter(ByokKey.auth_user_id == int(auth_user_id), ByokKey.status == "active")
        .all()
    )
    if not keys:
        return None
    requested = str(request.model or "auto").strip() or "auto"
    candidates: list[tuple[Any, str]] = []
    for k in keys:
        km = parse_models_json(k.models)
        up_model = resolve_upstream_model(requested, str(k.provider or ""), km)
        if up_model:
            candidates.append((k, up_model))
    if not candidates:
        return None

    request_id = f"req_{uuid.uuid4().hex[:16]}"

    def gen() -> Iterator[dict[str, Any]]:
        last_err = ""
        for k, up_model in _ordered_candidates(candidates):
            provider = str(k.provider or "")
            base = str(k.base_url or "").strip() or provider_default_base(provider)
            if not base:
                last_err = f"{provider}: missing base_url"
                continue
            started = False
            got_done = False
            t0 = time.time()
            try:
                plain = decrypt_key(k.key_cipher)
                stream_iter = _upstream_call(
                    provider=provider,
                    base=base,
                    key=plain,
                    model=up_model,
                    request=request,
                    timeout_s=_timeout_s(stream=True),
                    stream=True,
                )
                for ev in stream_iter:
                    et = ev.get("type")
                    if et == "error":
                        kind = str(ev.get("error_kind") or "network")
                        latency_ms = int((time.time() - t0) * 1000)
                        _update_key_stats(db, k, ok=False, latency_ms=None, err=str(ev.get("error") or "")[:200])
                        record_usage(
                            db,
                            auth_user_id=auth_user_id,
                            byok_key_id=k.id,
                            provider=provider,
                            model=requested,
                            upstream_model=up_model,
                            project=project,
                            request_id=request_id,
                            prompt_tokens=0,
                            completion_tokens=0,
                            total_tokens=0,
                            latency_ms=latency_ms,
                            success=False,
                            error_code=kind,
                        )
                        if kind == "format":
                            yield {"type": "error", "error": f"byok_400: {str(ev.get('error') or '')[:200]}"}
                            return
                        if not started:
                            last_err = f"{provider}/{up_model}: {kind}"
                            break  # 首包前失败：切下一把 key
                        # 已输出部分内容：按既有语义收尾，避免客户端悬空
                        text = str(ev.get("partial") or "")
                        tokens = max(1, int(len(text.split()) * 1.3)) if text else 1
                        yield {
                            "type": "done",
                            "text": text,
                            "tokens": tokens,
                            "raw_model": up_model,
                            "provider": "byok",
                            "layer": "BYOK",
                            "public_model": requested,
                            "byok_key_id": k.id,
                            "degraded_error": str(ev.get("error") or "")[:200],
                        }
                        got_done = True
                        break
                    if et in ("delta", "tool_calls_delta"):
                        if not started:
                            started = True
                            yield {
                                "type": "meta",
                                "layer": "BYOK",
                                "provider": "byok",
                                "raw_model": up_model,
                                "public_model": requested,
                                "byok_key_id": k.id,
                                "project": project,
                            }
                        yield ev
                    elif et == "done":
                        got_done = True
                        latency_ms = int((time.time() - t0) * 1000)
                        _update_key_stats(db, k, ok=True, latency_ms=latency_ms)
                        record_usage(
                            db,
                            auth_user_id=auth_user_id,
                            byok_key_id=k.id,
                            provider=provider,
                            model=requested,
                            upstream_model=up_model,
                            project=project,
                            request_id=request_id,
                            prompt_tokens=max(0, int(ev.get("prompt_tokens") or 0)),
                            completion_tokens=max(0, int(ev.get("completion_tokens") or 0)),
                            total_tokens=max(1, int(ev.get("tokens") or 1)),
                            latency_ms=latency_ms,
                            success=True,
                        )
                        yield {
                            **ev,
                            "provider": "byok",
                            "layer": "BYOK",
                            "public_model": requested,
                            "byok_key_id": k.id,
                            "project": project,
                        }
                        break
                if got_done:
                    return
            except Exception as e:
                kind, detail = _upstream_error_kind(e)
                _update_key_stats(db, k, ok=False, latency_ms=None, err=detail)
                record_usage(
                    db,
                    auth_user_id=auth_user_id,
                    byok_key_id=k.id,
                    provider=provider,
                    model=requested,
                    upstream_model=up_model,
                    project=project,
                    request_id=request_id,
                    prompt_tokens=0,
                    completion_tokens=0,
                    total_tokens=0,
                    latency_ms=int((time.time() - t0) * 1000),
                    success=False,
                    error_code=kind,
                )
                last_err = f"{provider}/{up_model}: {kind}"
                if not started:
                    continue
                yield {"type": "error", "error": detail[:200]}
                return
        yield {"type": "error", "error": last_err or "byok_all_failed"}

    return gen()


def has_byok_coverage(db, auth_user_id: int, requested_model: Optional[str]) -> bool:
    """是否有可用 BYOK key 能服务该模型（供流式预检跳过余额校验）。"""
    if not _enabled() or not auth_user_id:
        return False
    try:
        from models import ByokKey

        keys = (
            db.query(ByokKey)
            .filter(ByokKey.auth_user_id == int(auth_user_id), ByokKey.status == "active")
            .all()
        )
        if not keys:
            return False
        req = str(requested_model or "auto").strip() or "auto"
        for k in keys:
            km = parse_models_json(k.models)
            if resolve_upstream_model(req, str(k.provider or ""), km):
                return True
    except Exception:
        return False
    return False


# ---------------------------------------------------------------------------
# 控制台用辅助（路由层复用）
# ---------------------------------------------------------------------------
def list_keys(db, auth_user_id: int) -> list[dict[str, Any]]:
    from models import ByokKey

    rows = (
        db.query(ByokKey)
        .filter(ByokKey.auth_user_id == int(auth_user_id))
        .order_by(ByokKey.created_at.desc())
        .all()
    )
    out = []
    for k in rows:
        total = max(1, int(k.success_count or 0) + int(k.fail_count or 0))
        out.append(
            {
                "id": k.id,
                "provider": k.provider,
                "name": k.name or "",
                "key_prefix": k.key_prefix or "",
                "base_url": k.base_url or "",
                "models": parse_models_json(k.models),
                "status": k.status,
                "priority": k.priority,
                "last_latency_ms": k.last_latency_ms,
                "success_count": k.success_count,
                "fail_count": k.fail_count,
                "success_rate": round(int(k.success_count or 0) / total, 3),
                "last_error": k.last_error or None,
                "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
                "created_at": k.created_at.isoformat() if k.created_at else None,
                "updated_at": k.updated_at.isoformat() if k.updated_at else None,
            }
        )
    return out


def create_key(
    db,
    *,
    auth_user_id: int,
    provider: str,
    api_key: str,
    name: str = "",
    models: Optional[list[str]] = None,
    base_url: Optional[str] = None,
    priority: int = 100,
) -> dict[str, Any]:
    from models import ByokKey

    p = str(provider or "").strip().lower()
    if p not in BYOK_PROVIDERS:
        raise ValueError(f"unsupported provider: {p}")
    raw = str(api_key or "").strip()
    if len(raw) < 8:
        raise ValueError("api_key too short")
    key = ByokKey(
        auth_user_id=int(auth_user_id),
        provider=p,
        name=str(name or "").strip()[:64],
        key_cipher=encrypt_key(raw),
        key_prefix=key_prefix(raw),
        base_url=str(base_url or "").strip() or None,
        models=dump_models_json(models),
        status="active",
        priority=max(0, min(999, int(priority or 100))),
    )
    db.add(key)
    db.commit()
    db.refresh(key)
    return list_keys(db, auth_user_id) and [x for x in list_keys(db, auth_user_id) if x["id"] == key.id][0]


def update_key(db, *, auth_user_id: int, key_id: int, patch: dict[str, Any]) -> Optional[dict[str, Any]]:
    from models import ByokKey

    row = (
        db.query(ByokKey)
        .filter(ByokKey.id == int(key_id), ByokKey.auth_user_id == int(auth_user_id))
        .first()
    )
    if row is None:
        return None
    if "name" in patch:
        row.name = str(patch.get("name") or "").strip()[:64]
    if "status" in patch:
        st = str(patch.get("status") or "").strip().lower()
        if st in ("active", "disabled"):
            row.status = st
    if "priority" in patch:
        try:
            row.priority = max(0, min(999, int(patch.get("priority"))))
        except (TypeError, ValueError):
            pass
    if "models" in patch:
        row.models = dump_models_json(patch.get("models"))
    if "base_url" in patch:
        row.base_url = str(patch.get("base_url") or "").strip() or None
    if "provider" in patch:
        p = str(patch.get("provider") or "").strip().lower()
        if p in BYOK_PROVIDERS:
            row.provider = p
    if "api_key" in patch:
        raw = str(patch.get("api_key") or "").strip()
        if len(raw) >= 8:
            row.key_cipher = encrypt_key(raw)
            row.key_prefix = key_prefix(raw)
    db.commit()
    db.refresh(row)
    return [x for x in list_keys(db, auth_user_id) if x["id"] == row.id][0]


def delete_key(db, *, auth_user_id: int, key_id: int) -> bool:
    from models import ByokKey

    row = (
        db.query(ByokKey)
        .filter(ByokKey.id == int(key_id), ByokKey.auth_user_id == int(auth_user_id))
        .first()
    )
    if row is None:
        return False
    db.delete(row)
    db.commit()
    return True


def test_key(
    db,
    *,
    auth_user_id: int,
    provider: str,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
    key_id: Optional[int] = None,
) -> dict[str, Any]:
    """校验一把 key（不落库）：发一条最小请求。返回 ok/latency_ms/model/error。"""
    from models import ByokKey

    p = str(provider or "").strip().lower()
    if p not in BYOK_PROVIDERS:
        return {"ok": False, "error": f"unsupported provider: {p}"}
    raw = ""
    if key_id:
        row = (
            db.query(ByokKey)
            .filter(ByokKey.id == int(key_id), ByokKey.auth_user_id == int(auth_user_id))
            .first()
        )
        if row is None:
            return {"ok": False, "error": "key not found"}
        p = row.provider
        base_url = base_url or row.base_url
        try:
            raw = decrypt_key(row.key_cipher)
        except Exception:
            return {"ok": False, "error": "key decrypt failed"}
        model = model or (parse_models_json(row.models) or [None])[0]
    else:
        raw = str(api_key or "").strip()
    if len(raw) < 8:
        return {"ok": False, "error": "api_key too short"}
    base = str(base_url or "").strip() or provider_default_base(p)
    if not base:
        return {"ok": False, "error": "missing base_url"}

    # 构造最小请求：messages 优先，模型给默认档
    class _MiniReq:
        pass

    req = _MiniReq()
    req.prompt = "ping"
    req.messages = [{"role": "user", "content": "ping"}]
    req.temperature = 0.0
    req.max_tokens = 8
    req.tools = None
    req.tool_choice = None
    up_model = model or resolve_upstream_model("auto", p, [])
    if not up_model:
        return {"ok": False, "error": "cannot resolve model"}
    t0 = time.time()
    try:
        out = _upstream_call(
            provider=p,
            base=base,
            key=raw,
            model=up_model,
            request=req,
            timeout_s=min(20.0, _timeout_s(stream=False)),
            stream=False,
        )
        return {
            "ok": True,
            "latency_ms": int((time.time() - t0) * 1000),
            "model": str(out.get("raw_model") or up_model),
            "text": str(out.get("text") or "")[:80],
        }
    except Exception as e:
        kind, detail = _upstream_error_kind(e)
        return {"ok": False, "latency_ms": int((time.time() - t0) * 1000), "error": f"{kind}: {detail[:200]}"}


def usage_summary(
    db,
    *,
    auth_user_id: int,
    days: int = 7,
    group_by: str = "key",
) -> dict[str, Any]:
    """用量/成本看板：按 key / model / project 分组聚合。"""
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import func
    from models import ByokUsage

    try:
        days = max(1, min(365, int(days)))
    except (TypeError, ValueError):
        days = 7
    since = datetime.now(timezone.utc) - timedelta(days=days)
    q = db.query(ByokUsage).filter(
        ByokUsage.auth_user_id == int(auth_user_id),
        ByokUsage.created_at >= since,
    )
    rows = q.all()
    total_req = len(rows)
    ok_rows = [r for r in rows if r.success]
    cached_rows = [r for r in rows if r.cached]
    total_tokens = sum(int(r.total_tokens or 0) for r in rows)
    cost_micro = sum(int(r.cost_usd_micro or 0) for r in rows)
    lat = [int(r.latency_ms or 0) for r in ok_rows if r.latency_ms]
    avg_latency = round(sum(lat) / len(lat), 1) if lat else None

    groups: dict[str, dict[str, Any]] = {}
    for r in rows:
        if group_by == "model":
            gk = str(r.model or "")
        elif group_by == "project":
            gk = str(r.project or "(none)")
        elif group_by == "provider":
            gk = str(r.provider or "")
        else:
            gk = f"key#{r.byok_key_id or '-'}"
        g = groups.setdefault(
            gk,
            {
                "group": gk,
                "requests": 0,
                "success": 0,
                "cached": 0,
                "tokens": 0,
                "cost_usd": 0.0,
                "latency_ms": 0.0,
            },
        )
        g["requests"] += 1
        if r.success:
            g["success"] += 1
        if r.cached:
            g["cached"] += 1
        g["tokens"] += int(r.total_tokens or 0)
        g["cost_usd"] += int(r.cost_usd_micro or 0) / 1e6
        if r.success and r.latency_ms:
            g["latency_ms"] += int(r.latency_ms)
    for g in groups.values():
        if g["success"]:
            g["latency_ms"] = round(g["latency_ms"] / g["success"], 1)
        else:
            g["latency_ms"] = None
        g["cost_usd"] = round(g["cost_usd"], 6)

    return {
        "days": days,
        "group_by": group_by,
        "totals": {
            "requests": total_req,
            "success": len(ok_rows),
            "cached": len(cached_rows),
            "tokens": total_tokens,
            "cost_usd": round(cost_micro / 1e6, 6),
            "avg_latency_ms": avg_latency,
        },
        "groups": sorted(groups.values(), key=lambda x: -x["requests"]),
        "free_month": free_month_usage(db, auth_user_id),
    }


def models_catalog() -> dict[str, Any]:
    """控制台「可服务模型」清单：provider + 平台目录推荐。"""
    providers = []
    for pid, p in BYOK_PROVIDERS.items():
        providers.append(
            {
                "id": pid,
                "title": p.get("title", pid),
                "base": p.get("base", ""),
                "openai_compatible": bool(p.get("openai_compatible")),
                "tiers": p.get("tiers") or {},
            }
        )
    catalog_rows = []
    try:
        from model_warehouse import catalog_merged

        for row in catalog_merged():
            catalog_rows.append(
                {
                    "id": row.get("id"),
                    "title": row.get("title"),
                    "direct_id": row.get("direct_id"),
                    "openrouter_id": row.get("openrouter_id"),
                    "cost_in": row.get("cost_in"),
                    "cost_out": row.get("cost_out"),
                }
            )
    except Exception:
        pass
    return {"providers": providers, "catalog": catalog_rows}
