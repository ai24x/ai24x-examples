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
import ipaddress
import json
import logging
import secrets
import socket
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Iterator, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# 请求缓存：优先 Redis（多 worker / 多实例共享）；不可用时回落进程内存
_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_CACHE_LOCK = threading.Lock()
_CACHE_MAX_ITEMS = 20000
_REDIS: Any = None
_REDIS_INIT = False
_REDIS_PREFIX = "byok:rc:"


class ByokEntitlementError(Exception):
    """免费档门控：勿回落平台路由，应由 API 层直接返回给用户。"""

    def __init__(self, code: str, message: str):
        self.code = str(code or "byok_entitlement")
        self.message = str(message or "BYOK entitlement required")
        super().__init__(self.message)


# ---------------------------------------------------------------------------
# Provider 注册表（OpenAI 兼容直连；Anthropic 走 Messages 适配器）
# group: china=中国名模 | world=世界名模 | other=自定义
# 排序 = 知名度 × 性价比（BYOK 官方 Key 场景）；聚合平台不下拉展示（防引流），ID 仍保留兼容旧 Key
BYOK_PROVIDERS: dict[str, dict[str, Any]] = {
    # —— 中国名模（下拉顺序）——
    "deepseek": {
        "title": "DeepSeek",
        "group": "china",
        "rank": 10,
        "key_hint": "填写 DeepSeek 官方 API Key（platform.deepseek.com）",
        "base": "https://api.deepseek.com/v1",
        "openai_compatible": True,
        "tiers": {
            "auto": "deepseek-chat",
            "flash": "deepseek-chat",
            "pro": "deepseek-reasoner",
            "ultra": "deepseek-reasoner",
        },
    },
    "qwen": {
        "title": "Qwen（通义千问）",
        "group": "china",
        "rank": 20,
        "key_hint": "填写阿里云百炼 / DashScope API Key（Qwen）",
        "base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "openai_compatible": True,
        "tiers": {"auto": "qwen-plus", "flash": "qwen-turbo", "pro": "qwen-plus", "ultra": "qwen-max"},
    },
    "moonshot": {
        "title": "Kimi（月之暗面）",
        "group": "china",
        "rank": 30,
        "key_hint": "填写 Moonshot / Kimi 官方 API Key",
        "base": "https://api.moonshot.cn/v1",
        "openai_compatible": True,
        "tiers": {"auto": "moonshot-v1-8k", "flash": "moonshot-v1-8k", "pro": "moonshot-v1-32k", "ultra": "moonshot-v1-128k"},
    },
    "zhipu": {
        "title": "智谱 GLM",
        "group": "china",
        "rank": 40,
        "key_hint": "填写智谱开放平台 API Key（bigmodel.cn）",
        "base": "https://open.bigmodel.cn/api/paas/v4",
        "openai_compatible": True,
        "tiers": {"auto": "glm-4-flash", "flash": "glm-4-flash", "pro": "glm-4-plus", "ultra": "glm-4-plus"},
    },
    "minimax": {
        "title": "MiniMax",
        "group": "china",
        "rank": 50,
        "key_hint": "填写 MiniMax 官方 API Key（OpenAI 兼容端点）",
        "base": "https://api.minimaxi.com/v1",
        "openai_compatible": True,
        "tiers": {
            "auto": "MiniMax-M2.5",
            "flash": "MiniMax-M2.5",
            "pro": "MiniMax-M2.5",
            "ultra": "MiniMax-M2.5",
        },
    },
    "mimo": {
        "title": "小米 MiMo",
        "group": "china",
        "rank": 60,
        "key_hint": "填写小米 MiMo 官方 API Key（api.xiaomimimo.com）",
        "base": "https://api.xiaomimimo.com/v1",
        "openai_compatible": True,
        "tiers": {
            "auto": "mimo-v2.5",
            "flash": "mimo-v2.5",
            "pro": "mimo-v2.5-pro",
            "ultra": "mimo-v2.5-pro",
        },
    },
    # —— 世界名模 ——
    "openai": {
        "title": "OpenAI（GPT）",
        "group": "world",
        "rank": 10,
        "key_hint": "填写 OpenAI 官方 API Key（platform.openai.com）",
        "base": "https://api.openai.com/v1",
        "openai_compatible": True,
        "tiers": {"auto": "gpt-4o-mini", "flash": "gpt-4o-mini", "pro": "gpt-4o", "ultra": "gpt-4o"},
    },
    "anthropic": {
        "title": "Anthropic（Claude）",
        "group": "world",
        "rank": 20,
        "key_hint": "填写 Anthropic 官方 API Key（Messages API）",
        "base": "https://api.anthropic.com",
        "openai_compatible": False,
        "tiers": {
            "auto": "claude-haiku-4-5",
            "flash": "claude-haiku-4-5",
            "pro": "claude-sonnet-5-0",
            "ultra": "claude-opus-5-0",
        },
    },
    "gemini": {
        "title": "Google Gemini",
        "group": "world",
        "rank": 30,
        "key_hint": "填写 Google AI Studio / Gemini API Key（OpenAI 兼容端点）",
        "base": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "openai_compatible": True,
        "tiers": {
            "auto": "gemini-2.0-flash",
            "flash": "gemini-2.0-flash",
            "pro": "gemini-2.0-flash",
            "ultra": "gemini-2.5-pro",
        },
    },
    "xai": {
        "title": "xAI（Grok）",
        "group": "world",
        "rank": 40,
        "key_hint": "填写 xAI 官方 API Key",
        "base": "https://api.x.ai/v1",
        "openai_compatible": True,
        "tiers": {"auto": "grok-2-latest", "flash": "grok-2-latest", "pro": "grok-2-latest", "ultra": "grok-3"},
    },
    "mistral": {
        "title": "Mistral",
        "group": "world",
        "rank": 50,
        "key_hint": "填写 Mistral 官方 API Key",
        "base": "https://api.mistral.ai/v1",
        "openai_compatible": True,
        "tiers": {"auto": "mistral-small-latest", "flash": "mistral-small-latest", "pro": "mistral-medium-latest", "ultra": "mistral-large-latest"},
    },
    # —— 聚合：不下拉（ui_hidden），仅兼容历史 Key ——
    "openrouter": {
        "title": "OpenRouter（多模聚合）",
        "group": "legacy",
        "rank": 900,
        "ui_hidden": True,
        "key_hint": "历史兼容：OpenRouter 平台 Key",
        "base": "https://openrouter.ai/api/v1",
        "openai_compatible": True,
        "tiers": {"auto": "openrouter/auto", "flash": "openrouter/auto", "pro": "openrouter/auto", "ultra": "openrouter/auto"},
    },
    "siliconflow": {
        "title": "SiliconFlow（多模聚合）",
        "group": "legacy",
        "rank": 910,
        "ui_hidden": True,
        "key_hint": "历史兼容：SiliconFlow 平台 Key",
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
        "title": "Together AI（多模聚合）",
        "group": "legacy",
        "rank": 920,
        "ui_hidden": True,
        "key_hint": "历史兼容：Together AI 平台 Key",
        "base": "https://api.together.xyz/v1",
        "openai_compatible": True,
        "tiers": {"auto": "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo", "flash": "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo", "pro": "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo", "ultra": "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo"},
    },
    "groq": {
        "title": "Groq（推理加速）",
        "group": "legacy",
        "rank": 930,
        "ui_hidden": True,
        "key_hint": "历史兼容：Groq 平台 Key",
        "base": "https://api.groq.com/openai/v1",
        "openai_compatible": True,
        "tiers": {"auto": "llama-3.3-70b-versatile", "flash": "llama-3.1-8b-instant", "pro": "llama-3.3-70b-versatile", "ultra": "llama-3.3-70b-versatile"},
    },
    "custom": {
        "title": "自定义 OpenAI 兼容端点",
        "group": "other",
        "rank": 100,
        "key_hint": "填写兼容端点的 API Key，并填写下方 Base URL（可用此接入其它官方/私有端点）",
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
        "service_fee_note": "Gateway service fee only — no markup on your keys. You are billed by your provider at their rates.",
        "fallback_to_platform": _fallback_to_platform(),
        "cache_ttl_s": _cache_ttl_s(),
        "cache_backend": cache_stats().get("backend"),
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
            "days_left": None,
        }
    now = datetime.now(timezone.utc)
    active = str(row.status) == "active" and row.expires_at is not None and row.expires_at > now
    if str(row.status) == "active" and not active and row.expires_at is not None:
        row.status = "expired"
        try:
            db.commit()
        except Exception:
            db.rollback()
    days_left = None
    if active and row.expires_at is not None:
        days_left = max(0, int((row.expires_at - now).total_seconds() // 86400))
    return {
        "plan": str(row.plan or ""),
        "tier": "pro" if active else "free",
        "status": str(row.status or "active"),
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        "active": active,
        "days_left": days_left,
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
    if not meta or not meta.get("enabled", True):
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


# ---------------------------------------------------------------------------
# BYOK base_url SSRF 防护（上线前 S1）：禁止指向本机 / 内网 / 链路本地 / 云元数据
# ---------------------------------------------------------------------------
_BYOK_BLOCKED_HOSTS = frozenset(
    {
        "localhost",
        "localhost.localdomain",
        "metadata",
        "metadata.google.internal",
        "metadata.goog",
        "kubernetes.default",
        "kubernetes.default.svc",
    }
)
_BYOK_BLOCKED_HOST_SUFFIXES = (".local", ".internal", ".localhost", ".lan", ".corp")


def _byok_ip_blocked(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    ):
        return True
    if isinstance(ip, ipaddress.IPv4Address):
        # CGNAT / 常见云元数据网段
        if ip in ipaddress.ip_network("100.64.0.0/10"):
            return True
        if ip in ipaddress.ip_network("169.254.0.0/16"):
            return True
    return False


def assert_safe_byok_base_url(raw: str) -> str:
    """校验用户自定义 BYOK base_url。通过则返回 strip 后的原文；否则 ValueError。"""
    s = str(raw or "").strip()
    if not s:
        raise ValueError("empty base_url")
    if len(s) > 512:
        raise ValueError("base_url too long")
    if any(ch.isspace() for ch in s):
        raise ValueError("base_url contains whitespace")
    parsed = urlparse(s)
    scheme = (parsed.scheme or "").lower()
    if scheme != "https":
        raise ValueError("base_url must use https")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("base_url must not contain credentials")
    host = (parsed.hostname or "").strip().lower().rstrip(".")
    if not host:
        raise ValueError("base_url missing host")
    if host in _BYOK_BLOCKED_HOSTS or any(host.endswith(suf) for suf in _BYOK_BLOCKED_HOST_SUFFIXES):
        raise ValueError("base_url host is not allowed")
    # 字面量 IP
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None and _byok_ip_blocked(literal):
        raise ValueError("base_url points to a non-public IP")
    # DNS 解析：任一解析结果落内网即拒（防 DNS rebinding 至本机）
    try:
        infos = socket.getaddrinfo(host, parsed.port or 443, type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise ValueError(f"base_url host resolve failed: {e}") from e
    if not infos:
        raise ValueError("base_url host resolve failed")
    for info in infos:
        sockaddr = info[4]
        if not sockaddr:
            continue
        try:
            ip = ipaddress.ip_address(sockaddr[0])
        except ValueError:
            continue
        if _byok_ip_blocked(ip):
            raise ValueError("base_url resolves to a non-public IP")
    return s


def sanitize_byok_base_url(raw: Optional[str]) -> Optional[str]:
    """空 → None；非空则 assert_safe，失败抛 ValueError。"""
    s = str(raw or "").strip()
    if not s:
        return None
    return assert_safe_byok_base_url(s)


def resolve_upstream_model(requested: str, provider: str, key_models: list[str]) -> Optional[str]:
    """把请求模型解析为「该 key 实际要调的上游模型名」。解析不到返回 None。"""
    req = str(requested or "").strip()
    if not req:
        return None
    req_l = req.lower()
    # 2026-09-04 司令修复：vip-* 平台托管专属模型（vip-gpt56-luna/sol/terra/gpt54/kimi/claude/gemini 等）
    # 一律不归 BYOK——用户自带 key 无权顶替平台托管档，命中即回退平台（扣充值余额走 OR/官方上游）。
    # 否则 deepseek key models='[]' 会把 vip-gpt56-luna 原样透传 DeepSeek → 400。
    if req_l.startswith("vip-"):
        return None
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
    # 5) 直接透传仅限 openrouter 类 key（其 key 确实可调任意 openrouter 模型名）。
    #    其余 provider（deepseek/openai/anthropic/siliconflow）key 空 models 时对未知裸模型名一律不覆盖
    #    （回退平台），避免把 vip-* / ds-* 等平台模型原样透传上游 → 400。
    if provider == "openrouter":
        return req
    return None


# ---------------------------------------------------------------------------
# 请求缓存（用户隔离；仅非流式、无 tools；Redis 优先）
# ---------------------------------------------------------------------------
def _redis_url() -> str:
    try:
        from config import settings

        return str(getattr(settings, "redis_url", "") or "").strip()
    except Exception:
        return ""


def _redis_client() -> Any:
    """Lazy Redis；连不上则永久回落内存（本进程内不再重试，避免热路径抖动）。"""
    global _REDIS, _REDIS_INIT
    if _REDIS_INIT:
        return _REDIS
    _REDIS_INIT = True
    url = _redis_url()
    if not url:
        _REDIS = None
        return None
    try:
        import redis as _redis_mod  # type: ignore

        client = _redis_mod.from_url(url, socket_connect_timeout=1.5, socket_timeout=1.5)
        client.ping()
        _REDIS = client
        logger.info("BYOK request cache: Redis connected")
        return _REDIS
    except Exception as e:
        logger.warning("BYOK request cache: Redis unavailable, using memory (%s)", str(e)[:120])
        _REDIS = None
        return None


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


def _mem_get(k: str) -> Optional[dict[str, Any]]:
    with _CACHE_LOCK:
        item = _CACHE.get(k)
        if item and item[0] > time.time():
            return item[1]
        _CACHE.pop(k, None)
    return None


def _mem_put(k: str, data: dict[str, Any], ttl: int) -> None:
    with _CACHE_LOCK:
        now = time.time()
        _CACHE[k] = (now + ttl, data)
        if len(_CACHE) > _CACHE_MAX_ITEMS:
            expired = [kk for kk, v in _CACHE.items() if v[0] < now]
            for kk in expired:
                _CACHE.pop(kk, None)
            if len(_CACHE) > _CACHE_MAX_ITEMS:
                for kk in list(_CACHE.keys())[: _CACHE_MAX_ITEMS // 4]:
                    _CACHE.pop(kk, None)


def _cache_get(k: str) -> Optional[dict[str, Any]]:
    r = _redis_client()
    if r is not None:
        try:
            raw = r.get(_REDIS_PREFIX + k)
            if raw:
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8")
                data = json.loads(raw)
                if isinstance(data, dict):
                    return data
        except Exception as e:
            logger.debug("BYOK Redis get failed: %s", str(e)[:120])
    return _mem_get(k)


def _cache_put(k: str, data: dict[str, Any]) -> None:
    ttl = _cache_ttl_s()
    if ttl <= 0:
        return
    r = _redis_client()
    if r is not None:
        try:
            r.setex(_REDIS_PREFIX + k, int(ttl), json.dumps(data, ensure_ascii=False, default=str))
            return
        except Exception as e:
            logger.debug("BYOK Redis set failed: %s", str(e)[:120])
    _mem_put(k, data, ttl)


def cache_stats() -> dict[str, Any]:
    backend = "memory"
    items: Any = 0
    r = _redis_client()
    if r is not None:
        backend = "redis"
        try:
            # 粗略计数；大 key 空间时 SCAN 过贵，仅返回本前缀近似
            n = 0
            for _ in r.scan_iter(match=_REDIS_PREFIX + "*", count=200):
                n += 1
                if n >= 5000:
                    break
            items = n if n < 5000 else f"{n}+"
        except Exception:
            items = None
    else:
        with _CACHE_LOCK:
            items = len(_CACHE)
    return {"items": items, "ttl_s": _cache_ttl_s(), "backend": backend}


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
    """当月 BYOK 用量；免费档在 enforce 开启且超限时硬拦（Pro 订阅不限）。"""
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
    sub = subscription_status(db, auth_user_id)
    pro = bool(sub.get("active"))
    enforce = _enforce_free_cap()
    over = bool((not pro) and limit and used >= limit)
    return {
        "month_used_requests": used,
        "month_used_tokens": tokens,
        "month_limit_requests": None if pro else limit,
        "over_cap": over,
        "tier": "pro" if pro else "free",
        "unlimited": pro,
        "enforce": enforce,
        "remaining_requests": None if pro else max(0, int(limit) - int(used)),
    }


def assert_byok_entitlement(db, auth_user_id: int) -> dict[str, Any]:
    """Pro 放行；免费档在 enforce 开启且当月请求达上限时抛 ByokEntitlementError。"""
    usage = free_month_usage(db, auth_user_id)
    if usage.get("unlimited") or not usage.get("enforce"):
        return usage
    if not usage.get("over_cap"):
        return usage
    limit = int(usage.get("month_limit_requests") or 0)
    raise ByokEntitlementError(
        "byok_free_cap",
        (
            f"This month's free BYOK allowance ({limit} requests) is used up. "
            "Subscribe to BYOK Pro to continue, or try again next month."
        ),
    )


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
    assert_byok_entitlement(db, int(auth_user_id))
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
            base = assert_safe_byok_base_url(base)
        except ValueError as e:
            last_err = f"{provider}: unsafe base_url ({e})"
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
    assert_byok_entitlement(db, int(auth_user_id))
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
            try:
                base = assert_safe_byok_base_url(base)
            except ValueError as e:
                last_err = f"{provider}: unsafe base_url ({e})"
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
    safe_base = sanitize_byok_base_url(base_url)
    key = ByokKey(
        auth_user_id=int(auth_user_id),
        provider=p,
        name=str(name or "").strip()[:64],
        key_cipher=encrypt_key(raw),
        key_prefix=key_prefix(raw),
        base_url=safe_base,
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
        row.base_url = sanitize_byok_base_url(patch.get("base_url"))
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
    try:
        base = sanitize_byok_base_url(base_url) or provider_default_base(p)
        if base:
            base = assert_safe_byok_base_url(base)
    except ValueError as e:
        return {"ok": False, "error": str(e)}
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


def usage_daily(db, *, auth_user_id: int, days: int = 7) -> dict[str, Any]:
    """BYOK 每日趋势（UTC 日口径，缺天补零）：请求 / tokens / 估算成本。"""
    from datetime import datetime, timedelta, timezone

    from models import ByokUsage

    try:
        days = max(1, min(90, int(days)))
    except (TypeError, ValueError):
        days = 7
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    until = today + timedelta(days=1)
    since = today - timedelta(days=days - 1)
    rows = (
        db.query(ByokUsage)
        .filter(
            ByokUsage.auth_user_id == int(auth_user_id),
            ByokUsage.created_at >= since,
            ByokUsage.created_at < until,
        )
        .all()
    )
    by_day: dict[str, dict[str, Any]] = {}
    for r in rows:
        if not r.created_at:
            continue
        ts = r.created_at
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        d = ts.astimezone(timezone.utc).date().isoformat()
        g = by_day.setdefault(
            d,
            {"requests": 0, "success": 0, "cached": 0, "tokens": 0, "cost_usd_micro": 0, "lat_sum": 0, "lat_n": 0},
        )
        g["requests"] += 1
        if r.success:
            g["success"] += 1
            if r.latency_ms:
                g["lat_sum"] += int(r.latency_ms)
                g["lat_n"] += 1
        if r.cached:
            g["cached"] += 1
        g["tokens"] += int(r.total_tokens or 0)
        g["cost_usd_micro"] += int(r.cost_usd_micro or 0)

    out = []
    for i in range(days):
        d = (since + timedelta(days=i)).date().isoformat()
        g = by_day.get(d)
        if not g:
            out.append(
                {
                    "date": d,
                    "requests": 0,
                    "success": 0,
                    "cached": 0,
                    "tokens": 0,
                    "cost_usd": 0.0,
                    "avg_latency_ms": None,
                }
            )
            continue
        avg_lat = round(g["lat_sum"] / g["lat_n"], 1) if g["lat_n"] else None
        out.append(
            {
                "date": d,
                "requests": int(g["requests"]),
                "success": int(g["success"]),
                "cached": int(g["cached"]),
                "tokens": int(g["tokens"]),
                "cost_usd": round(int(g["cost_usd_micro"]) / 1e6, 6),
                "avg_latency_ms": avg_lat,
            }
        )
    return {"days": days, "rows": out}


def models_catalog() -> dict[str, Any]:
    """控制台「可服务模型」清单：provider + 平台目录推荐。"""
    group_order = ("china", "world", "other", "legacy")
    providers = []
    for pid, p in BYOK_PROVIDERS.items():
        providers.append(
            {
                "id": pid,
                "title": p.get("title", pid),
                "group": p.get("group") or "other",
                "rank": int(p.get("rank") or 999),
                "ui_hidden": bool(p.get("ui_hidden")),
                "key_hint": p.get("key_hint") or "",
                "base": p.get("base", ""),
                "openai_compatible": bool(p.get("openai_compatible")),
                "tiers": p.get("tiers") or {},
            }
        )
    providers.sort(
        key=lambda x: (
            group_order.index(x["group"]) if x["group"] in group_order else 99,
            int(x.get("rank") or 999),
            str(x.get("title") or x.get("id") or ""),
        )
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
    return {
        "providers": providers,
        "providers_ui": [p for p in providers if not p.get("ui_hidden")],
        "groups": [
            {"id": "china", "title": "中国名模"},
            {"id": "world", "title": "世界名模"},
            {"id": "other", "title": "其它"},
        ],
        "catalog": catalog_rows,
        "note": "聚合平台不在下拉展示；已保存的历史 Key 仍可用。其它端点请用「自定义」。",
    }
