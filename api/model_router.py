"""
L0–L3 模型路由（MVP）。

默认上游模式：OpenRouter 等 OpenAI 兼容**聚合平台**（转售友好、一 Key 多模型）。
TOKEN_LLM_UPSTREAM=direct 时回退直连 DeepSeek / 硅基流动 / Qwen 国际。

未配置 Key 时走本地 stub；配置后走真实调用，单层失败则 fallback 下一档。
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

# 逻辑模型名 → 层级
MODEL_LAYER: dict[str, str] = {
    "auto": "auto",
    "free": "auto",
    "flash": "L1",
    "pro": "L2",
    "ultra": "L3",
    "glm-4-flash": "L0",
    "siliconflow-free": "L0",
    "deepseek-flash": "L1",
    "deepseek-chat": "L1",
    "deepseek-pro": "L2",
    "deepseek-reasoner": "L2",
    "kimi-k3": "L3",
    "minimax": "L3",
    "qwen-plus": "L3",
    "doubao-pro": "L3",
    "gpt-3.5-turbo": "L1",
}

# 聚合模式：各层都打同一 OpenRouter，用不同 model id 区分档位
CHAIN_FREE = ["L1", "L0"]
CHAIN_VIP = ["L1", "L2", "L3"]
# 欧盟：优先「国际向」聚合模型（仍经 OpenRouter），再兜底
CHAIN_FREE_EU = ["QI", "L1", "L0"]
CHAIN_VIP_EU = ["QI", "L1", "L2", "L3"]

LAYER_DEFAULT_MODEL = {
    "L0": "or-fallback",
    "L1": "or-flash",
    "L2": "or-pro",
    "L3": "or-ultra",
    "QI": "or-eu",
}

# 聚合默认 model id（OpenRouter；可用 OPENROUTER_MODEL_* 覆盖）
# 成本优先：L1=DS Flash；能力向可改 OPENROUTER_MODEL_L1=xiaomi/mimo-v2.5
_OR_DEFAULT_MODELS = {
    "L0": "openrouter/auto",
    "L1": "deepseek/deepseek-v4-flash",
    "L2": "deepseek/deepseek-v4-pro",
    "L3": "openai/gpt-4o-mini",
    "QI": "qwen/qwen-2.5-72b-instruct",
}

# 直连模式逻辑名 → upstream model id
LOGICAL_TO_UPSTREAM_MODEL_DIRECT = {
    "glm-4-flash": "THUDM/glm-4-9b-chat",
    "siliconflow-free": "Qwen/Qwen2.5-7B-Instruct",
    "flash": "deepseek-v4-flash",
    "deepseek-flash": "deepseek-v4-flash",
    "deepseek-chat": "deepseek-v4-flash",
    "deepseek-v4-flash": "deepseek-v4-flash",
    "pro": "deepseek-v4-pro",
    "deepseek-pro": "deepseek-v4-pro",
    "deepseek-reasoner": "deepseek-v4-pro",
    "deepseek-v4-pro": "deepseek-v4-pro",
    "ultra": "deepseek-v4-pro",
    "gpt-3.5-turbo": "deepseek-v4-flash",
    "auto": "deepseek-v4-flash",
    "free": "deepseek-v4-flash",
    "qwen-intl-turbo": "qwen-turbo",
    "qwen-intl-plus": "qwen-plus",
    "qwen-plus": "qwen-plus",
}

# 聚合模式：品牌档 → OpenRouter model（可被 env 覆盖后的层默认再映射）
LOGICAL_TO_UPSTREAM_MODEL_OR = {
    "flash": "L1",
    "deepseek-flash": "L1",
    "deepseek-chat": "L1",
    "or-flash": "L1",
    "pro": "L2",
    "deepseek-pro": "L2",
    "deepseek-reasoner": "L2",
    "or-pro": "L2",
    "ultra": "L3",
    "or-ultra": "L3",
    "kimi-k3": "L3",
    "auto": "L1",
    "free": "L1",
    "or-fallback": "L0",
    "siliconflow-free": "L0",
    "glm-4-flash": "L0",
    "or-eu": "QI",
    "qwen-intl-turbo": "QI",
    "qwen-intl-plus": "QI",
    "qwen-plus": "QI",
}

LAYER_COST_MULT = {"L0": 1, "L1": 1, "L2": 5, "L3": 8, "QI": 1}

_EU_COUNTRY_CODES = frozenset(
    {
        "AT",
        "BE",
        "BG",
        "HR",
        "CY",
        "CZ",
        "DK",
        "EE",
        "FI",
        "FR",
        "DE",
        "GR",
        "HU",
        "IE",
        "IT",
        "LV",
        "LT",
        "LU",
        "MT",
        "NL",
        "PL",
        "PT",
        "RO",
        "SK",
        "SI",
        "ES",
        "SE",
        "EU",
    }
)


@dataclass
class RouteResult:
    ok: bool
    text: str
    model: str
    layer: str
    provider: str
    token_count: int
    attempts: list[dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None


def list_models_public(*, is_vip: bool) -> dict[str, Any]:
    mode = _upstream_mode()
    l0 = _layer_upstream("L0")
    l1 = _layer_upstream("L1")
    l2 = _layer_upstream("L2")
    l3 = _layer_upstream("L3")
    qi = _layer_upstream("QI")
    any_key = bool(l0.get("key") or l1.get("key") or qi.get("key"))
    return {
        "layers": {
            "L0": {
                "title": "兜底（聚合自动路由 / 直连硅基）",
                "models": ["or-fallback", "siliconflow-free", "glm-4-flash"],
                "free": True,
                "ready": bool(l0.get("key")),
                "provider": l0.get("provider"),
            },
            "L1": {
                "title": "主打 flash（聚合 · 默认 DeepSeek V4 Flash）",
                "models": ["flash", "deepseek-chat", "or-flash", "auto"],
                "free": True,
                "ready": bool(l1.get("key")),
                "provider": l1.get("provider"),
                "upstream_model": l1.get("model") or None,
            },
            "QI": {
                "title": "欧盟向聚合模型（需 TOKEN_REGION_ROUTING=1）",
                "models": ["or-eu", "qwen-intl-turbo"],
                "free": True,
                "ready": bool(qi.get("key")),
                "provider": qi.get("provider"),
                "upstream_model": qi.get("model") or None,
            },
            "L2": {
                "title": "VIP pro",
                "models": ["pro", "or-pro", "deepseek-pro"],
                "vip_only": True,
                "ready": bool(l2.get("key")),
                "upstream_model": l2.get("model") or None,
            },
            "L3": {
                "title": "VIP ultra",
                "models": ["ultra", "or-ultra"],
                "vip_only": True,
                "ready": bool(l3.get("key")),
                "upstream_model": l3.get("model") or None,
            },
        },
        "brand": {
            "free": "auto → 聚合 L1→L0",
            "flash": "L1",
            "pro": "L2（VIP）",
            "ultra": "L3（VIP）",
        },
        "default": "auto",
        "chain": CHAIN_VIP if is_vip else CHAIN_FREE,
        "region_routing": _region_routing_enabled(),
        "upstream_mode": mode,
        "upstream": {
            "mode": "live" if any_key else "stub",
            "openrouter_ready": mode == "openrouter" and bool(l1.get("key")),
            "direct_ready": mode == "direct" and bool(l1.get("key")),
            "l0_ready": bool(l0.get("key")),
            "l1_ready": bool(l1.get("key")),
            "qi_ready": bool(qi.get("key")),
            "l0_base": l0.get("base") or None,
            "l1_base": l1.get("base") or None,
            "qi_base": qi.get("base") or None,
            "l1_model": l1.get("model") or None,
            "l2_model": l2.get("model") or None,
            "l3_model": l3.get("model") or None,
        },
        "note": (
            "聚合默认 L1=deepseek/deepseek-v4-flash、L2=deepseek/deepseek-v4-pro；"
            "能力向可 OPENROUTER_MODEL_L1=xiaomi/mimo-v2.5。"
            "TOKEN_LLM_UPSTREAM=direct 回退官方 DeepSeek。"
        ),
    }


def _env(name: str, default: str = "") -> str:
    v = (os.getenv(name) or "").strip()
    if v:
        return v
    try:
        from config import settings as _s

        alias_map = {
            "DEEPSEEK_API_KEY": "deepseek_api_key",
            "DEEPSEEK_BASE_URL": "deepseek_base_url",
            "DEEPSEEK_MODEL": "deepseek_model",
            "SILICONFLOW_API_KEY": "siliconflow_api_key",
            "SILICONFLOW_BASE_URL": "siliconflow_base_url",
            "SILICONFLOW_MODEL": "siliconflow_model",
            "TOKEN_LLM_TIMEOUT_S": "token_llm_timeout_s",
            "OPENROUTER_API_KEY": "openrouter_api_key",
            "OPENROUTER_BASE_URL": "openrouter_base_url",
            "TOKEN_LLM_UPSTREAM": "token_llm_upstream",
        }
        attr = alias_map.get(name)
        if attr and hasattr(_s, attr):
            return str(getattr(_s, attr) or "").strip() or default
    except Exception:
        pass
    return default


def _upstream_mode() -> str:
    """
    direct | openrouter

    现阶段默认直连 DeepSeek（国内可充值跑通）。
    显式 TOKEN_LLM_UPSTREAM=openrouter 且 Key 有余额后再切聚合。
    """
    raw = (_env("TOKEN_LLM_UPSTREAM", "") or "").strip().lower()
    if raw in ("openrouter", "aggregator", "or"):
        return "openrouter"
    if raw in ("direct", "official", "legacy"):
        return "direct"
    # 未写 TOKEN_LLM_UPSTREAM：有 DeepSeek 则直连（先跑通）；否则才用 OR
    if _env("DEEPSEEK_API_KEY") or _env("TOKEN_LLM_L1_KEY"):
        return "direct"
    if _env("OPENROUTER_API_KEY"):
        return "openrouter"
    return "direct"


def _normalize_openai_base(base: str) -> str:
    base = (base or "").rstrip("/")
    if base in ("https://api.deepseek.com", "http://api.deepseek.com"):
        return base + "/v1"
    if base.endswith("api.deepseek.com"):
        return base + "/v1"
    if base in ("https://api.siliconflow.cn", "http://api.siliconflow.cn"):
        return base + "/v1"
    if base in ("https://openrouter.ai/api", "http://openrouter.ai/api"):
        return base + "/v1"
    return base


def _openrouter_model_for_layer(layer: str) -> str:
    layer = (layer or "").upper()
    env_key = {
        "L0": "OPENROUTER_MODEL_L0",
        "L1": "OPENROUTER_MODEL_L1",
        "L2": "OPENROUTER_MODEL_L2",
        "L3": "OPENROUTER_MODEL_L3",
        "QI": "OPENROUTER_MODEL_EU",
    }.get(layer, "")
    if env_key:
        v = _env(env_key)
        if v:
            return v
    return _OR_DEFAULT_MODELS.get(layer, _OR_DEFAULT_MODELS["L1"])


def _layer_upstream(layer: str) -> dict[str, str]:
    """
    openrouter：各层共用 OpenRouter Key，按层选不同 model。
    direct：L0 硅基 / L1 DeepSeek / QI DashScope 国际。
    """
    layer = (layer or "").upper()
    if _upstream_mode() == "openrouter":
        base = (
            _env("OPENROUTER_BASE_URL")
            or _env("TOKEN_LLM_BASE")
            or "https://openrouter.ai/api/v1"
        )
        key = _env("OPENROUTER_API_KEY") or _env("TOKEN_LLM_KEY")
        model = _openrouter_model_for_layer(layer)
        return {
            "base": _normalize_openai_base(base),
            "key": key,
            "model": model,
            "provider": "openrouter",
        }

    if layer == "L0":
        base = (
            _env("TOKEN_LLM_L0_BASE")
            or _env("SILICONFLOW_BASE_URL")
            or "https://api.siliconflow.cn/v1"
        )
        key = _env("TOKEN_LLM_L0_KEY") or _env("SILICONFLOW_API_KEY")
        model = (
            _env("TOKEN_LLM_L0_MODEL")
            or _env("SILICONFLOW_MODEL")
            or "Qwen/Qwen2.5-7B-Instruct"
        )
        provider = "siliconflow"
    elif layer == "L1":
        base = (
            _env("TOKEN_LLM_L1_BASE")
            or _env("DEEPSEEK_BASE_URL")
            or _env("TOKEN_LLM_BASE")
            or "https://api.deepseek.com/v1"
        )
        key = _env("TOKEN_LLM_L1_KEY") or _env("DEEPSEEK_API_KEY") or _env("TOKEN_LLM_KEY")
        model = (
            _env("TOKEN_LLM_L1_MODEL")
            or _env("DEEPSEEK_MODEL")
            or _env("TOKEN_LLM_MODEL")
            or "deepseek-v4-flash"
        )
        provider = "deepseek"
    elif layer == "QI":
        base = (
            _env("TOKEN_LLM_QI_BASE")
            or _env("QWEN_INTL_BASE_URL")
            or "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
        )
        key = _env("TOKEN_LLM_QI_KEY") or _env("QWEN_INTL_API_KEY") or _env("DASHSCOPE_API_KEY")
        model = _env("TOKEN_LLM_QI_MODEL") or _env("QWEN_INTL_MODEL") or "qwen-turbo"
        provider = "qwen_intl"
    elif layer in ("L2", "L3"):
        # 直连阶段：VIP 档暂共用 DeepSeek（pro 模型）；OR 充值后再切回聚合档
        base = (
            _env(f"TOKEN_LLM_{layer}_BASE")
            or _env("DEEPSEEK_BASE_URL")
            or _env("TOKEN_LLM_BASE")
            or "https://api.deepseek.com/v1"
        )
        key = (
            _env(f"TOKEN_LLM_{layer}_KEY")
            or _env("DEEPSEEK_API_KEY")
            or _env("TOKEN_LLM_KEY")
        )
        default_model = "deepseek-v4-pro" if layer == "L2" else "deepseek-v4-pro"
        model = (
            _env(f"TOKEN_LLM_{layer}_MODEL")
            or _env("DEEPSEEK_MODEL_PRO")
            or default_model
        )
        provider = "deepseek"
    else:
        base = _env(f"TOKEN_LLM_{layer}_BASE") or _env("TOKEN_LLM_BASE") or ""
        key = _env(f"TOKEN_LLM_{layer}_KEY") or _env("TOKEN_LLM_KEY") or ""
        model = _env(f"TOKEN_LLM_{layer}_MODEL") or LAYER_DEFAULT_MODEL.get(layer, "")
        provider = "openai_compatible"

    return {
        "base": _normalize_openai_base(base),
        "key": key,
        "model": model,
        "provider": provider,
    }


def _timeout_s() -> float:
    try:
        return max(2.0, float(_env("TOKEN_LLM_TIMEOUT_S", "15") or "15"))
    except ValueError:
        return 15.0


def _upstream_model_id(logical: str, layer_default: str) -> str:
    logical = (logical or "").strip()
    if _upstream_mode() == "openrouter":
        if "/" in logical and not logical.startswith("or-"):
            return logical
        mapped_layer = LOGICAL_TO_UPSTREAM_MODEL_OR.get(logical)
        if mapped_layer:
            return _openrouter_model_for_layer(mapped_layer)
        return layer_default or _openrouter_model_for_layer("L1")
    return LOGICAL_TO_UPSTREAM_MODEL_DIRECT.get(logical, layer_default or logical)

def _region_routing_enabled() -> bool:
    v = (_env("TOKEN_REGION_ROUTING", "0") or "0").strip().lower()
    return v in ("1", "true", "yes", "on")


def normalize_region(region_hint: Optional[str]) -> str:
    """
    返回 'EU' | 'DEFAULT'。
    支持：EU / EEA 字样，或 ISO 国家码（CF-IPCountry）。
    """
    raw = (region_hint or "").strip().upper()
    if not raw:
        return "DEFAULT"
    if raw in ("EU", "EEA", "EUROPE"):
        return "EU"
    if len(raw) == 2 and raw in _EU_COUNTRY_CODES:
        return "EU"
    return "DEFAULT"


def resolve_chain(
    *,
    requested_model: Optional[str],
    is_vip: bool,
    region_hint: Optional[str] = None,
) -> list[tuple[str, str]]:
    """
    返回 [(layer, logical_model), ...] 尝试序列。
    TOKEN_REGION_ROUTING=0（默认）：行为与改前一致（非欧盟链）。
    =1 且 region=EU：优先 QI（Qwen 国际）。
    """
    req = (requested_model or "auto").strip().lower() or "auto"
    use_eu = _region_routing_enabled() and normalize_region(region_hint) == "EU"
    if use_eu:
        # 无 QI Key 时仍给出 EU 链；run_routed_chat 会 skip no_key 并 fallback
        free_chain = CHAIN_FREE_EU
        vip_chain = CHAIN_VIP_EU
    else:
        free_chain = CHAIN_FREE
        vip_chain = CHAIN_VIP

    if req in ("auto", "free"):
        layers = vip_chain if is_vip else free_chain
        return [(ly, LAYER_DEFAULT_MODEL[ly]) for ly in layers]

    layer = MODEL_LAYER.get(req, "L1")
    if layer == "auto":
        layers = vip_chain if is_vip else free_chain
        return [(ly, LAYER_DEFAULT_MODEL[ly]) for ly in layers]

    # 品牌档映射到默认逻辑模型
    if _upstream_mode() == "openrouter":
        brand_logical = {
            "flash": "or-flash",
            "pro": "or-pro",
            "ultra": "or-ultra",
        }
        if use_eu:
            brand_logical["flash"] = "or-eu"
    else:
        brand_logical = {
            "flash": "deepseek-chat" if not use_eu else "qwen-intl-turbo",
            "pro": "deepseek-pro" if not use_eu else "qwen-intl-plus",
            "ultra": "deepseek-pro",
        }
    logical = brand_logical.get(req, req)

    # VIP 限定层：FREE 用户降到默认 FREE 链，禁止静默按 VIP 价升档
    if layer in ("L2", "L3") and not is_vip:
        return [(ly, LAYER_DEFAULT_MODEL[ly]) for ly in free_chain]

    chain_layers = vip_chain if is_vip else free_chain
    # 从指定层开始，再 fallback 同链后续
    out: list[tuple[str, str]] = [(layer, logical)]
    started = False
    for ly in chain_layers:
        if ly == layer:
            started = True
            continue
        if started:
            out.append((ly, LAYER_DEFAULT_MODEL[ly]))
    if not started:
        # 指定层不在链上时，追加链
        for ly in chain_layers:
            if ly != layer:
                out.append((ly, LAYER_DEFAULT_MODEL[ly]))
    return out


def run_routed_chat(
    *,
    prompt: str,
    requested_model: Optional[str],
    is_vip: bool,
    temperature: float = 0.7,
    max_tokens: int = 1000,
    region_hint: Optional[str] = None,
) -> RouteResult:
    attempts: list[dict[str, Any]] = []
    chain = resolve_chain(
        requested_model=requested_model, is_vip=is_vip, region_hint=region_hint
    )
    timeout_s = _timeout_s()
    any_live = any(bool(_layer_upstream(ly)["key"]) for ly, _ in chain)

    for layer, logical_model in chain:
        up = _layer_upstream(layer)
        api_model = _upstream_model_id(logical_model, up["model"])
        t0 = time.time()
        try:
            if up["base"] and up["key"]:
                out = _call_openai_compatible(
                    base=up["base"],
                    key=up["key"],
                    model=api_model,
                    prompt=prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout_s=timeout_s,
                    provider=str(up.get("provider") or ""),
                )
                provider = str(up.get("provider") or "openai_compatible")
                if "openrouter.ai" in up["base"]:
                    provider = "openrouter"
                elif "deepseek.com" in up["base"]:
                    provider = "deepseek"
                elif "siliconflow" in up["base"]:
                    provider = "siliconflow"
                elif "dashscope" in up["base"] or provider == "qwen_intl":
                    provider = "qwen_intl"
                used_model = str(out.get("raw_model") or api_model)
            else:
                # 已配置其它层真 Key 时：跳过无 Key 层，避免 L0 stub 挡住 DeepSeek
                if any_live:
                    attempts.append(
                        {
                            "layer": layer,
                            "model": logical_model,
                            "ok": False,
                            "skipped": "no_key",
                            "ms": 0,
                        }
                    )
                    continue
                out = _stub_response(prompt, layer=layer, model=logical_model)
                provider = "stub"
                used_model = logical_model

            elapsed = time.time() - t0
            attempts.append(
                {
                    "layer": layer,
                    "model": used_model,
                    "provider": provider,
                    "ok": True,
                    "ms": int(elapsed * 1000),
                }
            )
            raw_tokens = int(out["tokens"])
            mult = int(LAYER_COST_MULT.get(layer, 1))
            bill_tokens = max(1, raw_tokens * mult)
            return RouteResult(
                ok=True,
                text=str(out["text"]),
                model=used_model,
                layer=layer,
                provider=provider,
                token_count=bill_tokens,
                attempts=attempts,
            )
        except Exception as e:
            elapsed = time.time() - t0
            logger.warning("route layer=%s model=%s failed: %s", layer, logical_model, e)
            attempts.append(
                {
                    "layer": layer,
                    "model": logical_model,
                    "ok": False,
                    "error": str(e)[:200],
                    "ms": int(elapsed * 1000),
                }
            )
            continue

    # 所有 live 失败时：测试环境回落 stub，避免无效 Key 把整条链打死
    layer0, logical0 = chain[0] if chain else ("L0", "siliconflow-free")
    stub = _stub_response(prompt, layer=layer0, model=logical0)
    attempts.append(
        {
            "layer": layer0,
            "model": logical0,
            "provider": "stub",
            "ok": True,
            "fallback": "all_live_failed",
        }
    )
    return RouteResult(
        ok=True,
        text=str(stub["text"]),
        model=logical0,
        layer=layer0,
        provider="stub",
        token_count=max(1, int(stub["tokens"])),
        attempts=attempts,
        error="all_live_failed_used_stub",
    )


def public_tier_name(
    requested_model: Optional[str],
    *,
    layer: str = "",
    upstream_model: str = "",
) -> str:
    """对外只返回品牌档，不暴露上游型号。"""
    req = (requested_model or "").strip().lower()
    if req in ("flash", "pro", "ultra", "auto"):
        return req
    if req in ("free",):
        return "auto"
    ly = (layer or "").upper()
    if ly == "L1":
        return "flash"
    if ly == "L2":
        return "pro"
    if ly == "L3":
        return "ultra"
    if ly in ("L0", "QI"):
        return "auto"
    m = (upstream_model or "").lower()
    if "v4-pro" in m or "deepseek-r1" in m or "reasoner" in m or "mimo-v2.5-pro" in m:
        return "pro"
    if m:
        return "flash"
    return "auto"


def _system_prompt() -> str:
    """对外身份：AI24X；不主动报上游厂商。可用 TOKEN_LLM_SYSTEM_PROMPT 覆盖全文。"""
    custom = (_env("TOKEN_LLM_SYSTEM_PROMPT") or "").strip()
    if custom:
        return custom
    return (
        "You are the AI24X assistant on the AI24X API platform. "
        "When users ask which model or company you are, say you are the AI24X assistant "
        "(tiers: auto / flash / pro / ultra). "
        "Do not name upstream providers or model brands such as DeepSeek, Xiaomi, MiMo, "
        "Qwen, OpenAI, OpenRouter, or SiliconFlow, unless the user is clearly an internal "
        "operator debugging with an explicit admin instruction. "
        "Answer helpfully in the user's language."
    )


def _call_openai_compatible(
    *,
    base: str,
    key: str,
    model: str,
    prompt: str,
    temperature: float,
    max_tokens: int,
    timeout_s: float,
    provider: str = "",
) -> dict[str, Any]:
    url = f"{base}/chat/completions"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    # OpenRouter 推荐带上站点头（排行榜 / 风控识别）
    if provider == "openrouter" or "openrouter.ai" in (base or ""):
        headers["HTTP-Referer"] = (
            _env("OPENROUTER_SITE_URL") or "https://www.ai24x.com"
        )
        headers["X-Title"] = _env("OPENROUTER_APP_NAME") or "AI24X"
    body: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": _system_prompt()},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    # DeepSeek v4 直连时默认关 thinking
    if str(model).startswith("deepseek-v4") and (_env("DEEPSEEK_THINKING", "0") or "0").strip() not in (
        "1",
        "true",
        "TRUE",
        "yes",
    ):
        body["thinking"] = {"type": "disabled"}
    with httpx.Client(timeout=timeout_s) as client:
        r = client.post(url, headers=headers, json=body)
    r.raise_for_status()
    data = r.json()
    choices = data.get("choices") or []
    text = ""
    if choices:
        msg = (choices[0] or {}).get("message") or {}
        text = str(msg.get("content") or "").strip()
        if not text:
            text = str(msg.get("reasoning_content") or "").strip()
    usage = data.get("usage") or {}
    total = int(usage.get("total_tokens") or 0)
    if total <= 0:
        total = max(1, int(len(text.split()) * 1.3))
    return {"text": text, "tokens": total, "raw_model": model}


def _stub_response(prompt: str, *, layer: str, model: str) -> dict[str, Any]:
    preview = (prompt or "")[:80]
    text = (
        f"[AI24X {layer}/{model} stub] 已收到：{preview}"
        f"{'…' if len(prompt or '') > 80 else ''}。"
        "当前未配置 TOKEN_LLM_* upstream，返回联调占位回复。"
    )
    return {"text": text, "tokens": max(1, int(len(text.split()) * 1.3))}
