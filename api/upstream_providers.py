"""
上游通道注册表（主 OR / 硅基 / Together 开源备用 / 国际厂直连）。

启用方式：填对应 *_API_KEY（或管理台覆盖）且 ENABLED 不为 0。
国际旗舰（GPT/Claude/Gemini）OR 挂了 → 优先厂直连，勿指望 Together/硅基同名顶上。
Together：开源/中国开源模备用（与 OR 开源侧类似），不是 OR 的完整替代。
"""
from __future__ import annotations

from typing import Any, Optional

# 通道 id → 配置
PROVIDERS: dict[str, dict[str, Any]] = {
    "openrouter": {
        "title": "OpenRouter（主聚合）",
        "role": "primary_aggregator",
        "openai_compatible": True,
        "key_env": "OPENROUTER_API_KEY",
        "base_env": "OPENROUTER_BASE_URL",
        "default_base": "https://openrouter.ai/api/v1",
        "enabled_env": "TOKEN_UPSTREAM_OPENROUTER_ENABLED",
        "covers": ["china_named", "intl_named", "tiers"],
    },
    "siliconflow": {
        "title": "硅基流动（L0/共享/中国模备用）",
        "role": "china_backup",
        "openai_compatible": True,
        "key_env": "SILICONFLOW_API_KEY",
        "free_key_env": "SILICONFLOW_API_KEY_FREE",
        "base_env": "SILICONFLOW_BASE_URL",
        "default_base": "https://api.siliconflow.cn/v1",
        "enabled_env": "TOKEN_UPSTREAM_SILICON_ENABLED",
        "covers": ["china_open", "shared", "l0"],
    },
    "deepseek": {
        "title": "DeepSeek 官方（Flash/Pro 兜底）",
        "role": "official_failover",
        "openai_compatible": True,
        "key_env": "DEEPSEEK_API_KEY",
        "base_env": "DEEPSEEK_BASE_URL",
        "default_base": "https://api.deepseek.com/v1",
        "enabled_env": "TOKEN_LLM_DS_FAILOVER",
        "covers": ["flash", "vip-ds-flash", "vip-ds-pro", "or_failover"],
        "note": "OR 为主时建议常驻；失败自动直连，无需整站切 direct。",
    },
    "together": {
        "title": "Together AI（开源模国际备用）",
        "role": "open_weight_backup",
        "openai_compatible": True,
        "key_env": "TOGETHER_API_KEY",
        "base_env": "TOGETHER_BASE_URL",
        "default_base": "https://api.together.xyz/v1",
        "enabled_env": "TOKEN_UPSTREAM_TOGETHER_ENABLED",
        "covers": ["open_weight", "china_open_mirror"],
        "note": "无 GPT/Claude 原厂；作 OR 开源侧与中国开源模备用。推荐优先于 Fireworks（目录更全）。",
    },
    "openai_direct": {
        "title": "OpenAI 直连",
        "role": "intl_direct",
        "openai_compatible": True,
        "key_env": "OPENAI_API_KEY",
        "base_env": "OPENAI_BASE_URL",
        "default_base": "https://api.openai.com/v1",
        "enabled_env": "TOKEN_UPSTREAM_OPENAI_DIRECT_ENABLED",
        "covers": ["vip-gpt54", "vip-gpt5", "vip-gpt5-mini", "vip-gpt4o", "vip-gpt4o-mini"],
        "models": {
            "vip-gpt54": "gpt-5.4",
            "vip-gpt5": "gpt-5",
            "vip-gpt5-mini": "gpt-5-mini",
            "vip-gpt4o": "gpt-4o",
            "vip-gpt4o-mini": "gpt-4o-mini",
        },
    },
    "anthropic_direct": {
        "title": "Anthropic 直连",
        "role": "intl_direct",
        "openai_compatible": False,
        "key_env": "ANTHROPIC_API_KEY",
        "base_env": "ANTHROPIC_BASE_URL",
        "default_base": "https://api.anthropic.com/v1",
        "enabled_env": "TOKEN_UPSTREAM_ANTHROPIC_DIRECT_ENABLED",
        "covers": ["vip-claude-opus", "vip-claude-sonnet", "vip-claude-haiku"],
        "models": {
            "vip-claude-opus": "claude-opus-5-0",
            "vip-claude-sonnet": "claude-sonnet-5-0",
            "vip-claude-haiku": "claude-haiku-4-5",
        },
        "note": "Messages API；当前骨架以 OpenAI 兼容探测为主，启用前需接 anthropic 调用适配。",
    },
    "google_direct": {
        "title": "Google AI / Gemini 直连",
        "role": "intl_direct",
        "openai_compatible": True,
        "key_env": "GOOGLE_AI_API_KEY",
        "base_env": "GOOGLE_AI_BASE_URL",
        "default_base": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "enabled_env": "TOKEN_UPSTREAM_GOOGLE_DIRECT_ENABLED",
        "covers": ["vip-gemini-pro", "vip-gemini-flash"],
        "models": {
            "vip-gemini-pro": "gemini-3.1-pro-preview",
            "vip-gemini-flash": "gemini-3.6-flash",
        },
        "note": "兼容端点随 Google 文档调整；以官方为准。",
    },
}


def _env(name: str, default: str = "") -> str:
    from llm_keys import get_key

    if name in (
        "OPENROUTER_API_KEY",
        "OPENROUTER_API_KEY_FREE",
        "SILICONFLOW_API_KEY",
        "SILICONFLOW_API_KEY_FREE",
        "DEEPSEEK_API_KEY",
        "TOGETHER_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GOOGLE_AI_API_KEY",
    ):
        return get_key(name, default)
    import os

    return (os.environ.get(name) or default).strip()


def _enabled(flag_env: str) -> bool:
    # 默认开：有 Key 即视为可启用；显式 0 关闭
    raw = _env(flag_env, "1").lower()
    return raw not in ("0", "false", "no", "off")


def resolve_provider(pid: str) -> Optional[dict[str, Any]]:
    meta = PROVIDERS.get(pid)
    if not meta:
        return None
    key = _env(str(meta.get("key_env") or ""))
    if meta.get("free_key_env"):
        # 硅基：解析时仍返回主 key；调用方按场景选 free
        pass
    if not key:
        return None
    if not _enabled(str(meta.get("enabled_env") or "")):
        return None
    base = _env(str(meta.get("base_env") or ""), str(meta.get("default_base") or ""))
    return {
        "id": pid,
        "title": meta.get("title"),
        "role": meta.get("role"),
        "base": base,
        "key": key,
        "openai_compatible": bool(meta.get("openai_compatible")),
        "models": dict(meta.get("models") or {}),
        "note": meta.get("note") or "",
    }


def list_providers_admin() -> dict[str, Any]:
    from llm_keys import mask

    rows = []
    for pid, meta in PROVIDERS.items():
        key = _env(str(meta.get("key_env") or ""))
        free_k = _env(str(meta.get("free_key_env") or "")) if meta.get("free_key_env") else ""
        en = _enabled(str(meta.get("enabled_env") or ""))
        rows.append(
            {
                "id": pid,
                "title": meta.get("title"),
                "role": meta.get("role"),
                "enabled_flag": en,
                "key_set": bool(key),
                "key_masked": mask(key) if key else "",
                "free_key_set": bool(free_k),
                "free_key_masked": mask(free_k) if free_k else "",
                "ready": bool(key) and en,
                "covers": list(meta.get("covers") or []),
                "note": meta.get("note") or "",
                "default_base": meta.get("default_base") or "",
            }
        )
    return {
        "ok": True,
        "providers": rows,
        "recommendation": {
            "open_weight_backup": "together",
            "intl_flagship_backup": ["openai_direct", "anthropic_direct", "google_direct"],
            "why_not_fireworks_first": (
                "Together 开源目录通常更全，更接近「OR 开源侧」备用；"
                "Fireworks 偏延迟。GPT/Claude 二者都没有，必须厂直连或第二聚合。"
            ),
        },
        "ops_note": (
            "填 Key 且未关闭 ENABLED 即 ready。"
            "国际旗舰备用请配 OpenAI/Anthropic/Google 直连；"
            "Together 只作开源模备用。"
        ),
    }


def direct_model_for_vip(public_id: str) -> Optional[dict[str, Any]]:
    """VIP 点名 → 直连通道（若已配 Key）。"""
    for pid, meta in PROVIDERS.items():
        if meta.get("role") != "intl_direct":
            continue
        models = meta.get("models") or {}
        if public_id not in models:
            continue
        up = resolve_provider(pid)
        if not up or not up.get("openai_compatible"):
            # anthropic 非兼容：骨架返回信息，调用层暂跳过
            if not up:
                return None
            return {**up, "model": models[public_id], "skip_call": not up.get("openai_compatible")}
        return {**up, "model": models[public_id], "skip_call": False}
    return None
