"""
L0–L3 模型路由（MVP）。

默认上游模式：OpenRouter 等 OpenAI 兼容**聚合平台**（转售友好、一 Key 多模型）。
TOKEN_LLM_UPSTREAM=direct 时回退直连 DeepSeek / 硅基流动 / Qwen 国际。

未配置 Key 时走本地 stub；配置后走真实调用，单层失败则 fallback 下一档。
"""
from __future__ import annotations

import contextvars
import json
import logging
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Iterator, Optional

import httpx
import upstream_health

logger = logging.getLogger(__name__)

# 请求级：是否允许向客户端展示推理（默认 False；由 run_routed_* 注入）
_INCLUDE_REASONING_CV: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "ai24x_include_reasoning", default=False
)

# —— 全局共享 keep-alive 连接池（2026-08-13 优化：避免每请求 TCP+TLS 握手；httpx.Client 线程安全）——
_CONNECT_TIMEOUT_S = 5.0  # 连接建立独立短超时：连接失败 5s 内快速 failover，不再吃满总超时
_SHARED_CLIENT = httpx.Client(
    timeout=httpx.Timeout(60.0, connect=_CONNECT_TIMEOUT_S),
    limits=httpx.Limits(max_connections=256, max_keepalive_connections=64),
    follow_redirects=True,
)

# 逻辑模型名 → 层级
MODEL_LAYER: dict[str, str] = {
    "auto": "auto",
    "free": "auto",
    "shared": "L0",
    "free-shared": "L0",
    "free_shared": "L0",
    "flash": "L1",
    "pro": "L2",
    "ultra": "L3",
    "glm-4-flash": "L0",
    "silicon-qwen": "L0",  # 免费共享池硅基主力（点名直落 L0，勿落 L1）
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

# —— DeepSeek 峰谷计价（2026-08-15 落地，官方 8/17 00:00 生效）——
# 官方峰时：北京 09:00-12:00 / 14:00-18:00；其余谷时（18:00-次日 09:00 整夜 15 小时）
PEAK_WINDOWS: tuple[tuple[int, int], ...] = ((9, 12), (14, 18))


def current_period(*, now: Optional[Any] = None) -> str:
    """返回 DeepSeek 计价时段：'peak' / 'offpeak'（Asia/Shanghai 实时判定，不缓存价格）。"""
    forced = (os.getenv("TOKEN_LLM_PERIOD") or "").strip().lower()
    if forced in ("peak", "offpeak"):
        return forced
    import datetime as _dt

    t = now or _dt.datetime.now(_dt.timezone(_dt.timedelta(hours=8)))
    if getattr(t, "tzinfo", None) is None:
        t = t.replace(tzinfo=_dt.timezone(_dt.timedelta(hours=8)))
    hh = t.hour
    return "peak" if any(s <= hh < e for s, e in PEAK_WINDOWS) else "offpeak"


def _peak_mults(pick: dict[str, Any]) -> Optional[tuple[int, int]]:
    """峰时倍率覆盖（仅配置了 peak_in_mult/peak_out_mult 的模型生效，如 vip-ds-flash/pro）。"""
    import datetime as _dt

    # 官方峰谷 2026-08-17 00:00 生效：生效前保持现行价（前台提前展示，扣费不提前加价）
    try:
        _eff = _dt.date.fromisoformat((os.getenv("TOKEN_LLM_PEAK_EFFECTIVE") or "2026-08-17").strip())
    except ValueError:
        _eff = _dt.date(2026, 8, 17)
    if _dt.date.today() < _eff:
        return None
    if current_period() != "peak":
        return None
    pin = pick.get("peak_in_mult")
    pout = pick.get("peak_out_mult")
    if pin is None and pout is None:
        return None
    in_m = max(
        1,
        int(pin if pin is not None else pick.get("in_mult") or pick.get("billing_mult") or 1),
    )
    out_m = max(
        1,
        int(pout if pout is not None else pick.get("out_mult") or pick.get("billing_mult") or 1),
    )
    return in_m, out_m

# 聚合模式：各层都打同一 OpenRouter，用不同 model id 区分档位
CHAIN_FREE = ["L1", "L0"]
# VIP 档：OR 层失败后落到 L0 硅基（免费 Key），避免整站 OR 挂死
CHAIN_VIP = ["L1", "L2", "L3", "L0"]
# 欧盟：优先「国际向」聚合模型（仍经 OpenRouter），再兜底
CHAIN_FREE_EU = ["QI", "L1", "L0"]
CHAIN_VIP_EU = ["QI", "L1", "L2", "L3", "L0"]

LAYER_DEFAULT_MODEL = {
    "L0": "or-fallback",
    "L1": "or-flash",
    "L2": "or-pro",
    "L3": "or-ultra",
    "QI": "or-eu",
}

# 聚合默认 model id（OpenRouter；可用 OPENROUTER_MODEL_* 覆盖）
# 2026-08-14：成本优先 L1=MiMo v2.5（DS 官方 8/17 涨价后同价档）；可用 OPENROUTER_MODEL_L1 覆盖
_OR_DEFAULT_MODELS = {
    "L0": "openrouter/auto",
    # 2026-08-14: DeepSeek 官方 8/17 涨价（flash 输出 ¥2→¥4.5，高峰 ¥9）
    # → L1/L2 默认换同价 MiMo 档（$0.14/$0.28、$0.435/$0.87，tools ✅），DS 仅留 vip 点名/兜底
    "L1": "xiaomi/mimo-v2.5",
    "L2": "xiaomi/mimo-v2.5-pro",
    "L3": "openai/gpt-5-mini",
    "QI": "qwen/qwen3.7-plus",
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

# 与 S_flash≈$0.35/M 绑定（2026-08-05）：pro≈$1.05、ultra≈$2.10
# 运行时 L2/L3 可被 model_warehouse override.layer_mult 覆盖
LAYER_COST_MULT = {"L0": 1, "L1": 1, "L2": 3, "L3": 7, "QI": 1}  # ⚠️ 主脑 2026-08-08 修改：L3 6→7，同步 model_warehouse 消除 ultra 低毛利告警


def _layer_billing_mult(layer: str) -> int:
    try:
        from model_warehouse import layer_cost_mult_for

        return max(1, int(layer_cost_mult_for(layer)))
    except Exception:
        return max(1, int(LAYER_COST_MULT.get(str(layer or "").upper(), 1) or 1))

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
    prompt_tokens: Optional[int] = None       # 2026-08-15: 上游 usage 输入/输出拆分
    completion_tokens: Optional[int] = None
    attempts: list[dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None
    billing_mult: int = 1
    public_model: Optional[str] = None
    tool_calls: Optional[list[dict[str, Any]]] = None
    finish_reason: Optional[str] = None


def _tools_passthrough_enabled() -> bool:
    """默认开启 tools 透传；TOKEN_LLM_TOOLS=0 可关。"""
    return (_env("TOKEN_LLM_TOOLS") or "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


class _UpstreamFormatError(Exception):
    """上游 400 格式错误：同载荷换聚合上游必然同样 400，直接上报不再 failover。"""


def _ensure_strict_schema(params: Any) -> Any:
    """OpenAI strict 模式要求 object 级 schema 带 additionalProperties: false。

    递归补齐，避免 Requesty/OpenRouter 对 strict=true 但缺 additionalProperties
    的 schema 报 400（2026-08-12 实锤：Codex tools strict=true 触发三家 400）。
    """
    if not isinstance(params, dict):
        return params
    t = str(params.get("type") or "").lower()
    if t == "object" and "additionalProperties" not in params:
        params["additionalProperties"] = False
    props = params.get("properties")
    if isinstance(props, dict):
        for k, v in props.items():
            if isinstance(v, dict):
                params["properties"][k] = _ensure_strict_schema(v)
    items = params.get("items")
    if isinstance(items, dict):
        params["items"] = _ensure_strict_schema(items)
    return params


def _normalize_tools_for_upstream(
    tools: Optional[list[dict[str, Any]]],
) -> Optional[list[dict[str, Any]]]:
    """统一 tools 为 chat/completions 形状并保证 strict 合规（幂等）。

    - Responses 扁平形状（{type,name,parameters}）→ chat 形状（{type,function:{...}}）
    - strict=true 时递归补齐 additionalProperties: false，防上游 400
    """
    if not isinstance(tools, list) or not tools:
        return None
    out: list[dict[str, Any]] = []
    for t in tools:
        if not isinstance(t, dict):
            continue
        if not isinstance(t.get("function"), dict) and t.get("name"):
            fn: dict[str, Any] = {"name": str(t["name"])}
            if t.get("description") is not None:
                fn["description"] = str(t["description"])
            if t.get("parameters") is not None:
                fn["parameters"] = t["parameters"]
            if t.get("strict") is not None:
                fn["strict"] = bool(t["strict"])
            t = {"type": "function", "function": fn}
        fn2 = t.get("function")
        if isinstance(fn2, dict) and fn2.get("strict"):
            fn2["parameters"] = _ensure_strict_schema(fn2.get("parameters"))
        out.append(t)
    return out or None


def _upstream_error_class(e: Exception) -> tuple[str, str]:
    """把上游异常分成 (kind, detail)。400=格式错误；5xx/超时/网络才允许 failover。"""
    resp = getattr(e, "response", None)
    code = getattr(resp, "status_code", None)
    detail = str(e)[:300]
    try:
        body = str(getattr(resp, "text", "") or "")[:600]
        if body:
            detail = f"{detail} | body={body}"
    except Exception:
        pass
    try:
        code = int(code)
    except (TypeError, ValueError):
        code = None
    if code == 400:
        return "format", detail
    if code in (401, 403):
        return "auth", detail
    if code == 404:
        return "notfound", detail
    if code == 429:
        return "ratelimit", detail
    if code is not None and 500 <= code < 600:
        return "server", detail
    return "network", detail


_INVOKE_TAG_RE = re.compile(
    r"<invoke\s+name=[\"']([^\"']+)[\"']\s*>([\s\S]*?)</invoke>", re.I
)
_INVOKE_PARAM_RE = re.compile(
    r"<parameter\s+name=[\"']([^\"']+)[\"']\s*>([\s\S]*?)</parameter>", re.I
)
_COLLAB_LINE_RE = re.compile(r"^\s*collab\s*:\s*([A-Za-z0-9_\-\.]+)\s*$", re.M)


def _is_anthropic_upstream(model: str, provider: str = "") -> bool:
    m = (model or "").lower()
    p = (provider or "").lower()
    return "claude" in m or "anthropic" in m or "anthropic" in p or "claude" in p


def _parse_invoke_tool_calls(text: str) -> Optional[list[dict[str, Any]]]:
    """把 Anthropic 文本工具调用转成 chat tool_calls。

    支持 <invoke name=...><parameter name=...>...</parameter></invoke> XML 与
    collab:tool_name 行两种形态；解析成功才返回，避免误伤普通正文。
    """
    if not text or ("<invoke" not in text and "collab:" not in text):
        return None
    out: list[dict[str, Any]] = []
    for m in _INVOKE_TAG_RE.finditer(text):
        name = (m.group(1) or "").strip() or "tool"
        params: dict[str, Any] = {}
        for pm in _INVOKE_PARAM_RE.finditer(m.group(2)):
            pname = (pm.group(1) or "").strip()
            pval = (pm.group(2) or "").strip()
            try:
                pval = json.loads(pval)
            except Exception:
                pass
            if pname:
                params[pname] = pval
        try:
            args = json.dumps(params, ensure_ascii=False)
        except Exception:
            args = "{}"
        out.append(
            {
                "id": "call_" + uuid.uuid4().hex[:16],
                "type": "function",
                "function": {"name": name, "arguments": args},
            }
        )
    if not out:
        cm = _COLLAB_LINE_RE.search(text)
        if cm:
            out.append(
                {
                    "id": "call_" + uuid.uuid4().hex[:16],
                    "type": "function",
                    "function": {"name": cm.group(1), "arguments": "{}"},
                }
            )
    return out or None


def _route_ok_from_out(
    out: dict[str, Any],
    *,
    model: str,
    layer: str,
    provider: str,
    attempts: list[dict[str, Any]],
    token_count: int,
    billing_mult: int = 1,
    public_model: Optional[str] = None,
) -> RouteResult:
    return RouteResult(
        ok=True,
        text=str(out.get("text") or ""),
        model=str(out.get("raw_model") or model),
        layer=layer,
        provider=provider,
        token_count=max(1, int(token_count)),
        prompt_tokens=out.get("prompt_tokens"),
        completion_tokens=out.get("completion_tokens"),
        attempts=attempts,
        billing_mult=billing_mult,
        public_model=public_model,
        tool_calls=out.get("tool_calls"),
        finish_reason=out.get("finish_reason"),
    )


def list_models_public(*, is_vip: bool, allow_names: Optional[set[str]] = None) -> dict[str, Any]:
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
                "title": "auto 兜底",
                "models": ["auto"],
                "free": True,
                "ready": bool(l0.get("key")),
            },
            "L1": {
                "title": "flash",
                "models": ["flash", "auto"],
                "free": True,
                "ready": bool(l1.get("key")),
            },
            "QI": {
                "title": "区域档（按需）",
                "models": ["auto"],
                "free": True,
                "ready": bool(qi.get("key")),
            },
            "L2": {
                "title": "pro（VIP）",
                "models": ["pro"],
                "vip_only": True,
                "ready": bool(l2.get("key")),
            },
            "L3": {
                "title": "ultra（VIP）",
                "models": ["ultra"],
                "vip_only": True,
                "ready": bool(l3.get("key")),
            },
        },
        "brand": {
            "auto": "自动档",
            "flash": "flash",
            "pro": "pro",
            "ultra": "ultra",
        },
        "default": "auto",
        "chain": CHAIN_VIP if is_vip else CHAIN_FREE,
        "region_routing": _region_routing_enabled(),
        "period": current_period(),
        "upstream_mode": mode,
        "upstream": {
            "mode": "live" if any_key else "stub",
            "openrouter_ready": mode == "openrouter" and bool(l1.get("key")),
            "direct_ready": mode == "direct" and bool(l1.get("key")),
            "l0_ready": bool(l0.get("key")),
            "l1_ready": bool(l1.get("key")),
            "qi_ready": bool(qi.get("key")),
            # 运维自检保留；用户控制台勿展示
            "l1_model": l1.get("model") or None,
            "l2_model": l2.get("model") or None,
            "l3_model": l3.get("model") or None,
        },
        "vip_picks": _public_vip_picks(is_vip=is_vip, allow_names=allow_names),
        "shared": "shared",
        "flash_ref_usd_per_m": _public_flash_ref(),
        "note": "对外档位：auto / flash / pro / ultra / shared；VIP 可点名中国与国际名模（见 vip_picks）。",
    }


def _public_flash_ref() -> float:
    try:
        from model_warehouse import flash_ref_usd_per_m

        return float(flash_ref_usd_per_m())
    except Exception:
        return 0.35


def _public_vip_picks(
    *, is_vip: bool, allow_names: Optional[set[str]] = None
) -> list[dict[str, Any]]:
    try:
        from model_warehouse import list_vip_picks_for_user

        return list_vip_picks_for_user(is_vip=is_vip, allow_names=allow_names)
    except Exception:
        return []


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


def _upstream_model_base(model: str) -> str:
    m = str(model or "").strip().lower()
    if not m:
        return ""
    return m.split("/", 1)[-1]


def _is_deepseek_v4_upstream_model(model: str) -> bool:
    """True when upstream model id is DeepSeek v4 (direct or OpenRouter-prefixed).

    Brand tiers (flash / vip-ds-flash) resolve to deepseek-v4-* or deepseek/deepseek-v4-*;
    the old startswith('deepseek-v4') check missed OpenRouter ids.
    """
    base = _upstream_model_base(model)
    return base.startswith("deepseek-v4")


def _is_mimo_upstream_model(model: str, provider: str = "") -> bool:
    """L1 flash 现网默认走 MiMo（mimo-v2.5 / xiaomi/mimo-*），同样有 thinking+reasoning_content。"""
    return _cn_thinking_family(model, provider) == "mimo"


def _cn_thinking_family(model: str, provider: str = "") -> str:
    """识别会吐 reasoning_content 的中国模家族：deepseek|mimo|kimi|glm|qwen|minimax|''。"""
    p = str(provider or "").strip().lower()
    m = str(model or "").strip().lower()
    base = _upstream_model_base(model)
    vendor = m.split("/", 1)[0] if "/" in m else ""

    if p in ("mimo", "xiaomi", "xiaomimimo") or vendor == "xiaomi" or "mimo" in base:
        return "mimo"
    if (
        p in ("deepseek",)
        or vendor in ("deepseek", "deepseek-ai")
        or base.startswith("deepseek")
        or "deepseek" in base
    ):
        return "deepseek"
    if (
        p in ("moonshot", "kimi")
        or vendor in ("moonshotai", "moonshot")
        or "kimi" in base
        or base.startswith("moonshot")
    ):
        return "kimi"
    if (
        p in ("zhipu", "zai", "glm", "z-ai")
        or vendor in ("z-ai", "zhipu", "thudm")
        or base.startswith("glm")
        or "glm-" in base
        or base.startswith("chatglm")
    ):
        return "glm"
    if (
        p in ("qwen", "qwen_intl", "dashscope")
        or vendor == "qwen"
        or base.startswith("qwen")
        or "qwen2" in base
        or "qwen3" in base
    ):
        return "qwen"
    if p in ("minimax",) or vendor == "minimax" or "minimax" in base:
        return "minimax"
    return ""


def _is_thinking_only_upstream(model: str) -> bool:
    """部分型号强制思考；下发 disabled 会 400，只能挡透传。"""
    base = _upstream_model_base(model)
    m = str(model or "").strip().lower()
    if not base:
        return False
    if "reasoner" in base:
        return True
    if "k2.7-code" in base or "kimi-k2.7-code" in m:
        return True
    if "glm-5.3" in base:
        return True
    if (
        base.endswith("-thinking")
        or "-thinking-" in base
        or base.endswith("_thinking")
        or base.endswith("-think")
    ):
        return True
    return False


def _upstream_thinking_enabled() -> bool:
    """是否允许向上游开启思考（env）；与客户端是否可见无关。"""
    try:
        from reasoning_filter import env_allows_upstream_thinking

        return env_allows_upstream_thinking()
    except Exception:
        for key in ("UPSTREAM_THINKING", "DEEPSEEK_THINKING"):
            if (_env(key, "0") or "0").strip() in ("1", "true", "TRUE", "yes"):
                return True
        return False


def _deepseek_thinking_enabled() -> bool:
    """兼容旧名：等同 _upstream_thinking_enabled。"""
    return _upstream_thinking_enabled()


def _should_forward_reasoning_to_client(*, include_reasoning: bool = False) -> bool:
    """客户端可见推理：仅请求显式开启（不再用全局 env 放开出口）。"""
    try:
        from reasoning_filter import client_may_see_reasoning

        return client_may_see_reasoning(include_reasoning=include_reasoning)
    except Exception:
        return bool(include_reasoning)


def _strip_reasoning_fields_from_messages(messages: Any) -> None:
    try:
        from reasoning_filter import strip_reasoning_fields_from_messages

        strip_reasoning_fields_from_messages(messages)
    except Exception:
        if not isinstance(messages, list):
            return
        for item in messages:
            if isinstance(item, dict):
                item.pop("reasoning_content", None)
                item.pop("reasoning", None)
                item.pop("reasoning_details", None)


def _should_inject_thinking_disable(model: str, provider: str = "") -> bool:
    """仅对明确带 deep-thinking 能力的型号下发关思考参数，避免小模/旧模 400。"""
    if _is_thinking_only_upstream(model):
        return False
    family = _cn_thinking_family(model, provider)
    if not family:
        return False
    base = _upstream_model_base(model)
    m = str(model or "").strip().lower()
    vendor = m.split("/", 1)[0] if "/" in m else ""
    if family == "mimo":
        return True
    if family == "deepseek":
        return (
            _is_deepseek_v4_upstream_model(model)
            or "reasoner" in base
            or "deepseek-r1" in base
            or "deepseek-v3" in base
        )
    if family == "kimi":
        return True
    if family == "glm":
        return (
            vendor in ("z-ai", "zhipu")
            or "glm-5" in base
            or "glm-4.7" in base
            or "glm-4.6" in base
            or "glm-4.5" in base
        )
    if family == "qwen":
        return (
            "qwen3" in base
            or base.startswith("qwen-plus")
            or base.startswith("qwen-max")
            or base.startswith("qwen-turbo")
            or base.startswith("qwen-flash")
            or base.startswith("qwen-long")
        )
    if family == "minimax":
        return "minimax-m" in base or "abab" in base
    return False


def _apply_upstream_thinking_controls(
    body: dict[str, Any], *, model: str, provider: str = ""
) -> None:
    """向上游注入关思考参数（与客户端过滤分离）。

    - env / 请求允许上游思考时：不注入 disabled
    - 思考专用模：保留 history reasoning_content，不下发 disabled
    - 否则：剥 history 推理字段 + 按家族注入 thinking/enable_thinking
    """
    if _upstream_thinking_enabled():
        return
    # 思考专用模：必须保留/回传 reasoning_content，禁用 disabled 参数
    if _is_thinking_only_upstream(model):
        return
    msgs = body.get("messages")
    _strip_reasoning_fields_from_messages(msgs)
    if not _should_inject_thinking_disable(model, provider):
        return
    family = _cn_thinking_family(model, provider)
    if family in ("deepseek", "mimo", "kimi", "glm", "minimax"):
        body["thinking"] = {"type": "disabled"}
    if family == "qwen":
        body["enable_thinking"] = False
        ctk = body.get("chat_template_kwargs")
        if not isinstance(ctk, dict):
            ctk = {}
        else:
            ctk = dict(ctk)
        ctk["enable_thinking"] = False
        body["chat_template_kwargs"] = ctk


def _should_disable_upstream_thinking(model: str, provider: str = "") -> bool:
    """兼容旧名：是否会对请求注入关思考参数。"""
    if _upstream_thinking_enabled():
        return False
    return _should_inject_thinking_disable(model, provider)


def _should_disable_deepseek_thinking(model: str) -> bool:
    """兼容旧调用：仅按 model 判断。"""
    return _should_disable_upstream_thinking(model, "")


def _upstream_mode() -> str:
    """
    direct | openrouter

    管理台覆盖优先；否则看 TOKEN_LLM_UPSTREAM / 已配 Key。
    """
    try:
        from system_flags import effective_llm_upstream_override

        ov = effective_llm_upstream_override()
        if ov:
            return ov
    except Exception:
        pass
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
    if base in ("https://api.siliconflow.com", "http://api.siliconflow.com"):
        return base + "/v1"
    if base in ("https://openrouter.ai/api", "http://openrouter.ai/api"):
        return base + "/v1"
    return base


def _openrouter_model_for_layer(layer: str) -> str:
    layer = (layer or "").upper()
    try:
        from model_warehouse import layer_model_override

        ov = layer_model_override(layer)
        if ov:
            return ov
    except Exception:
        pass
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


# 2026-08-14: DS 官方 8/17 涨价 → L1/L2 默认改走 OR 的 MiMo 同价档。
# 回退官方直连：TOKEN_LLM_L1_UPSTREAM=deepseek（L2 同理）。
_LAYER_OR_MODEL = {
    "L1": "xiaomi/mimo-v2.5",
    "L2": "xiaomi/mimo-v2.5-pro",
}


def _openrouter_upstream_with_model(model: str) -> Optional[dict[str, str]]:
    mid = (model or "").strip()
    if not mid:
        return None
    key = _env("OPENROUTER_API_KEY") or _env("TOKEN_LLM_KEY")
    try:
        from llm_keys import openrouter_main_key

        key = openrouter_main_key() or key
    except Exception:
        pass
    if not key:
        return None
    base = (
        _env("OPENROUTER_BASE_URL")
        or _env("TOKEN_LLM_BASE")
        or "https://openrouter.ai/api/v1"
    )
    return {
        "base": _normalize_openai_base(base),
        "key": key,
        "model": mid,
        "provider": "openrouter",
    }


def _effective_l1_lane() -> Optional[str]:
    try:
        from system_flags import effective_l1_lane

        return effective_l1_lane()
    except Exception:
        return None


def _upstream_from_flash_lane(lane: str) -> Optional[dict[str, str]]:
    lane = (lane or "").strip().lower()
    if lane == "mimo_official":
        return _layer_mimo_upstream("L1")
    if lane == "deepseek_official":
        up = _deepseek_upstream_for_layer("L1")
        return up if up.get("key") else None
    if lane == "or_mimo":
        return _openrouter_upstream_with_model("xiaomi/mimo-v2.5")
    if lane == "or_deepseek":
        return _openrouter_upstream_with_model("deepseek/deepseek-v4-flash")
    return None


def detect_active_flash_lane() -> str:
    ov = _effective_l1_lane()
    if ov:
        return ov
    up = _layer_upstream("L1")
    provider = str(up.get("provider") or "").lower()
    model = str(up.get("model") or "").lower()
    if provider == "mimo":
        return "mimo_official"
    if provider == "deepseek":
        return "deepseek_official"
    if provider == "openrouter":
        if "deepseek" in model:
            return "or_deepseek"
        return "or_mimo"
    if _layer_mimo_upstream("L1"):
        return "mimo_official"
    return "or_mimo"


def _layer_or_upstream_override(layer: str) -> Optional[dict[str, str]]:
    """L1/L2 直连模式下可选的 OR 通道（默认启用）；无 OR Key 或显式回退时返回 None。"""
    layer = (layer or "").upper()
    if layer not in ("L1", "L2"):
        return None
    v = (_env(f"TOKEN_LLM_{layer}_UPSTREAM", "") or "").strip().lower()
    if v in ("deepseek", "direct", "official", "ds"):
        return None
    key = _env("OPENROUTER_API_KEY") or _env("TOKEN_LLM_KEY")
    try:
        from llm_keys import openrouter_main_key

        key = openrouter_main_key() or key
    except Exception:
        pass
    if not key:
        return None
    base = (
        _env("OPENROUTER_BASE_URL")
        or _env("TOKEN_LLM_BASE")
        or "https://openrouter.ai/api/v1"
    )
    model = _openrouter_model_for_layer(layer)
    return {
        "base": _normalize_openai_base(base),
        "key": key,
        "model": model,
        "provider": "openrouter",
    }


def _layer_upstream(layer: str) -> dict[str, str]:
    """
    openrouter：各层共用 OpenRouter Key，按层选不同 model。
    direct：L0 硅基 / L1 DeepSeek / QI DashScope 国际。
    """
    layer = (layer or "").upper()
    if layer == "L1":
        lane = _effective_l1_lane()
        if lane:
            got = _upstream_from_flash_lane(lane)
            if got and got.get("key"):
                return got
    if _upstream_mode() == "openrouter":
        # L0 若已配硅基：用独立通道作 FREE 降级 / 免费共享，避免 OR 整站挂时无兜底
        sf_key = _env("SILICONFLOW_API_KEY") or _env("TOKEN_LLM_L0_KEY")
        try:
            from llm_keys import silicon_free_key

            sf_key = silicon_free_key() or sf_key
        except Exception:
            pass
        use_sf_l0 = (_env("TOKEN_LLM_L0_USE_SILICON") or "1").strip().lower() not in (
            "0",
            "false",
            "no",
            "off",
        )
        l0_up = (_env("TOKEN_LLM_L0_UPSTREAM", "") or "").strip().lower()
        if layer == "L0" and l0_up in ("mimo", "xiaomi", "mimo-direct"):
            mi = _mimo_free_upstream()
            if mi:
                return mi
        if layer == "L0" and sf_key and use_sf_l0:
            base = (
                _env("TOKEN_LLM_L0_BASE")
                or _env("SILICONFLOW_BASE_URL")
                or "https://api.siliconflow.com/v1"
            )
            model = (
                _env("TOKEN_LLM_L0_MODEL")
                or _env("SILICONFLOW_MODEL")
                or "Qwen/Qwen2.5-7B-Instruct"
            )
            return {
                "base": _normalize_openai_base(base),
                "key": sf_key,
                "model": model,
                "provider": "siliconflow",
            }
        base = (
            _env("OPENROUTER_BASE_URL")
            or _env("TOKEN_LLM_BASE")
            or "https://openrouter.ai/api/v1"
        )
        key = _env("OPENROUTER_API_KEY") or _env("TOKEN_LLM_KEY")
        try:
            from llm_keys import openrouter_main_key

            key = openrouter_main_key() or key
        except Exception:
            pass
        model = _openrouter_model_for_layer(layer)
        return {
            "base": _normalize_openai_base(base),
            "key": key,
            "model": model,
            "provider": "openrouter",
        }

    if layer == "L0":
        l0_up = (_env("TOKEN_LLM_L0_UPSTREAM", "") or "").strip().lower()
        if l0_up in ("mimo", "xiaomi", "mimo-direct"):
            mi = _mimo_free_upstream()
            if mi:
                return mi
        base = (
            _env("TOKEN_LLM_L0_BASE")
            or _env("SILICONFLOW_BASE_URL")
            or "https://api.siliconflow.com/v1"
        )
        key = (
            _env("SILICONFLOW_COM_API_KEY")
            or _env("TOKEN_LLM_L0_KEY")
            or _env("SILICONFLOW_API_KEY")
        )
        try:
            from llm_keys import silicon_free_key

            key = silicon_free_key() or key
        except Exception:
            pass
        model = (
            _env("TOKEN_LLM_L0_MODEL")
            or _env("SILICONFLOW_MODEL")
            or "Qwen/Qwen2.5-7B-Instruct"
        )
        provider = "siliconflow"
    elif layer == "L1":
        or_up = _layer_or_upstream_override("L1")
        if or_up:
            return or_up
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
        or_up = _layer_or_upstream_override(layer)
        if or_up:
            return or_up
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


# 2026-08-13: 04 实测 L2/L3 QR 同款 200 稳定且降本（deepseek-v4-pro / gpt-5-mini）；
# L1 flash 同款在 QR 60% 超时 -> 不接。
_LAYER_QR_MODEL: dict[str, str] = {
    "L2": "deepseek-v4-pro",
    "L3": "gpt-5-mini",
}


def _layer_qr_upstream(layer: str) -> Optional[dict[str, str]]:
    """Main-layer L2/L3 QuickRouter fallback; returns None when unmapped or key missing (caller skips)."""
    model = _LAYER_QR_MODEL.get((layer or "").strip().upper())
    if not model:
        return None
    try:
        from upstream_providers import resolve_provider

        up = resolve_provider("quickrouter")
        if not up or not up.get("key") or not up.get("base"):
            return None
        return {
            "base": _normalize_openai_base(str(up["base"])),
            "key": str(up["key"]),
            "model": model,
            "provider": "quickrouter",
        }
    except Exception:
        return None


# 2026-08-15: 小米 MiMo 官方直连兜底（国际 api.xiaomimimo.com；官方价=OR 价，同模型 failover）
_LAYER_MIMO_MODEL: dict[str, str] = {
    "L1": "mimo-v2.5",
    "L2": "mimo-v2.5-pro",
}


def _layer_mimo_upstream(layer: str) -> Optional[dict[str, str]]:
    """L1/L2 OR(MiMo) 失败后的官方直连同模型兜底；无 key / 未启用返回 None。"""
    model = _LAYER_MIMO_MODEL.get((layer or "").strip().upper())
    if not model:
        return None
    try:
        from upstream_providers import resolve_provider

        up = resolve_provider("mimo")
        if not up or not up.get("key") or not up.get("base"):
            return None
        return {
            "base": _normalize_openai_base(str(up["base"])),
            "key": str(up["key"]),
            "model": model,
            "provider": "mimo",
        }
    except Exception:
        return None


def _mimo_failover_enabled() -> bool:
    v = (_env("TOKEN_LLM_MIMO_FAILOVER", "1") or "1").strip().lower()
    return v not in ("0", "false", "no", "off")


def _mimo_free_upstream() -> Optional[dict[str, str]]:
    """免费通道独立付费 key（MIMO_API_KEY_FREE · 单独记账）作 L0 备用/升级源。"""
    if not _mimo_failover_enabled():
        return None
    key = (_env("MIMO_API_KEY_FREE") or _env("MIMO_API_KEY") or "").strip()
    if not key:
        return None
    base = (_env("MIMO_BASE_URL") or "https://api.xiaomimimo.com/v1").strip()
    model = (_env("MIMO_L0_MODEL") or _env("TOKEN_LLM_L0_MODEL") or "mimo-v2.5").strip()
    return {
        "base": _normalize_openai_base(base),
        "key": key,
        "model": model,
        "provider": "mimo",
    }


def _deepseek_official_upstream() -> dict[str, str]:
    """
    官方 DeepSeek 通道（与 TOKEN_LLM_UPSTREAM 无关）。
    生产 OR 为主时：OR 失败后用此作 Flash/Pro 直连兜底（需 DEEPSEEK_API_KEY）。
    """
    key = (_env("DEEPSEEK_API_KEY") or "").strip()
    if not key:
        return {"base": "", "key": "", "model": "", "provider": "deepseek"}
    base = (_env("DEEPSEEK_BASE_URL") or "https://api.deepseek.com/v1").strip()
    model = (_env("DEEPSEEK_MODEL") or "deepseek-v4-flash").strip()
    return {
        "base": _normalize_openai_base(base),
        "key": key,
        "model": model,
        "provider": "deepseek",
    }


def _ds_failover_enabled() -> bool:
    v = (_env("TOKEN_LLM_DS_FAILOVER", "1") or "1").strip().lower()
    return v not in ("0", "false", "no", "off")


def _ds_prefer_paid_enabled() -> bool:
    """OR 模式下付费 L1/L2 是否先直连 DeepSeek。

    2026-08-14: DS 官方 8/17 涨价后默认关闭（L1/L2 走 MiMo）；
    需要 DS 优先可设 TOKEN_LLM_DS_PREFER_PAID=1 恢复。
    """
    v = (_env("TOKEN_LLM_DS_PREFER_PAID", "0") or "0").strip().lower()
    return v not in ("0", "false", "no", "off")


def _deepseek_upstream_for_layer(layer: str) -> dict[str, str]:
    """官方 DeepSeek：L1=Flash，L2/L3=Pro。"""
    key = (_env("DEEPSEEK_API_KEY") or _env("TOKEN_LLM_L1_KEY") or "").strip()
    if not key:
        return {"base": "", "key": "", "model": "", "provider": "deepseek"}
    base = (_env("DEEPSEEK_BASE_URL") or "https://api.deepseek.com/v1").strip()
    if layer in ("L2", "L3"):
        model = (
            _env("TOKEN_LLM_L2_MODEL")
            or _env("DEEPSEEK_MODEL_PRO")
            or "deepseek-v4-pro"
        ).strip()
    else:
        model = (
            _env("DEEPSEEK_MODEL")
            or _env("TOKEN_LLM_L1_MODEL")
            or "deepseek-v4-flash"
        ).strip()
    return {
        "base": _normalize_openai_base(base),
        "key": key,
        "model": model,
        "provider": "deepseek",
    }


def _timeout_s() -> float:
    """非流式整请求超时（秒）。默认 15：卡住时尽快失败并 failover，勿拖死线程。"""
    try:
        return max(2.0, float(_env("TOKEN_LLM_TIMEOUT_S", "15") or "15"))
    except ValueError:
        return 15.0


def _stream_timeout_s() -> float:
    """流式读空闲超时（秒）：两次 SSE chunk 间隔上限。
    默认 180（配合 SSE keepalive，覆盖推理/工具间隙；过长会占满 worker）。
    OpenClaw / Codex 长循环可按需调 TOKEN_LLM_STREAM_TIMEOUT_S。
    """
    try:
        return max(30.0, float(_env("TOKEN_LLM_STREAM_TIMEOUT_S", "180") or "180"))
    except ValueError:
        return 180.0


def _httpx_timeout(timeout_s: float) -> httpx.Timeout:
    """连接短、读写跟 timeout_s；避免把 connect 也拉到上百秒。"""
    t = max(2.0, float(timeout_s))
    return httpx.Timeout(
        connect=min(_CONNECT_TIMEOUT_S, t),
        read=t,
        write=min(60.0, t),
        pool=min(10.0, t),
    )


def true_stream_enabled() -> bool:
    return (_env("TOKEN_LLM_TRUE_STREAM") or "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _content_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for p in content:
            if isinstance(p, str):
                parts.append(p)
            elif isinstance(p, dict):
                if p.get("type") == "text" or "text" in p:
                    parts.append(str(p.get("text") or ""))
        return "\n".join(x for x in parts if x)
    return str(content)


def _content_passthrough(content: Any) -> Any:
    """保留 multipart 结构（含 image_url 图片数据）供上游透传。

    ⚠️ 主脑 2026-08-04 新增 · Vision 修复 · 已部署 04 生产
    科设注意：此函数为 vision 修复核心，Gitee 同步 / 部署时请保留。
    详见 FIX-vision-support.md

    OpenAI Vision 格式 message.content 为 list 时条目形如：
      {"type": "text", "text": "..."}
      {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}
    纯文本仍返回 str；空 content 返回 ""。
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[dict[str, Any]] = []
        for p in content:
            if isinstance(p, str):
                parts.append({"type": "text", "text": p})
            elif isinstance(p, dict):
                tp = str(p.get("type") or "").strip().lower()
                if tp == "image_url":
                    # 原样保留图片数据透传上游
                    parts.append(p)
                elif tp == "text" or "text" in p:
                    parts.append({"type": "text", "text": str(p.get("text") or "")})
                else:
                    parts.append(p)
        return parts if parts else ""
    return str(content)


def _build_chat_messages(
    prompt: str,
    messages: Optional[list[dict[str, Any]]] = None,
    *,
    system_prompt: Optional[str] = None,
) -> list[dict[str, Any]]:
    """组装上游 messages；透传 user/assistant/tool 与 assistant.tool_calls。"""
    sys = system_prompt if system_prompt is not None else _system_prompt()
    if messages and isinstance(messages, list):
        out: list[dict[str, Any]] = [{"role": "system", "content": sys}]
        sys_extra: list[str] = []
        for m in messages:
            if not isinstance(m, dict):
                continue
            role = str(m.get("role") or "").strip().lower()
            if role in ("tool", "function"):
                item: dict[str, Any] = {
                    "role": role,
                    "content": _content_text(m.get("content")),
                }
                if m.get("tool_call_id") is not None:
                    item["tool_call_id"] = str(m.get("tool_call_id"))
                if m.get("name"):
                    item["name"] = str(m.get("name"))
                out.append(item)
                continue
            text = _content_text(m.get("content")).strip()
            tcs = m.get("tool_calls")
            if role == "system":
                if text:
                    sys_extra.append(text)
                continue
            if role == "assistant" and isinstance(tcs, list) and tcs:
                item = {
                    "role": "assistant",
                    "content": text if text else None,
                    "tool_calls": tcs,
                }
                out.append(item)
                continue
            if not text:
                continue
            if role not in ("user", "assistant"):
                role = "user"
            # ⚠️ 主脑 2026-08-04：user 消息保留 multipart（含 image_url）供 vision 透传
            user_content = _content_passthrough(m.get("content"))
            out.append({"role": role, "content": user_content})
        if sys_extra:
            out[0]["content"] = sys + "\n\n" + "\n\n".join(sys_extra)
        if len(out) == 1:
            out.append({"role": "user", "content": (prompt or "Hello").strip() or "Hello"})
        return out
    return [
        {"role": "system", "content": sys},
        {"role": "user", "content": prompt or ""},
    ]


def _upstream_model_id(logical: str, layer_default: str, *, provider: str = "") -> str:
    logical = (logical or "").strip()
    # L0 独立硅基通道（or-fallback/siliconflow-free）：模型名已由 _layer_upstream 解析
    # （TOKEN_LLM_L0_MODEL / SILICONFLOW_MODEL），不得再按 OR 逻辑名映射（or-fallback→openrouter/auto 会 400）
    if str(provider or "").strip() == "siliconflow":
        return layer_default or logical or "Qwen/Qwen2.5-7B-Instruct"
    if str(provider or "").strip() == "openrouter" or _upstream_mode() == "openrouter":
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

    # 免费共享：仅 L0，不爬付费档
    if req in ("shared", "free-shared", "free_shared"):
        return [("L0", LAYER_DEFAULT_MODEL["L0"])]

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
    allow_names: Optional[set[str]] = None,
    temperature: float = 0.7,
    max_tokens: int = 1000,
    region_hint: Optional[str] = None,
    messages: Optional[list[dict[str, Any]]] = None,
    tools: Optional[list[dict[str, Any]]] = None,
    tool_choice: Any = None,
    include_reasoning: bool = False,
) -> RouteResult:
    tok = _INCLUDE_REASONING_CV.set(bool(include_reasoning))
    try:
        return _run_routed_chat_inner(
            prompt=prompt,
            requested_model=requested_model,
            is_vip=is_vip,
            allow_names=allow_names,
            temperature=temperature,
            max_tokens=max_tokens,
            region_hint=region_hint,
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
        )
    finally:
        _INCLUDE_REASONING_CV.reset(tok)


def _run_routed_chat_inner(
    *,
    prompt: str,
    requested_model: Optional[str],
    is_vip: bool,
    allow_names: Optional[set[str]] = None,
    temperature: float = 0.7,
    max_tokens: int = 1000,
    region_hint: Optional[str] = None,
    messages: Optional[list[dict[str, Any]]] = None,
    tools: Optional[list[dict[str, Any]]] = None,
    tool_choice: Any = None,
) -> RouteResult:
    use_tools = tools if (tools and _tools_passthrough_enabled()) else None
    use_choice = tool_choice if use_tools is not None else None

    def _call(**kw: Any) -> dict[str, Any]:
        return _call_openai_compatible(
            messages=messages,
            tools=use_tools,
            tool_choice=use_choice,
            **kw,
        )

    # —— VIP 点名：中国模硅基优先（有 siliconflow_id 时）；国际模仍 OR/厂直连 ——
    pick = None
    pick_gate_on = False
    try:
        from model_warehouse import resolve_vip_pick, vip_pick_enabled

        pick = resolve_vip_pick(requested_model)
        pick_gate_on = bool(vip_pick_enabled())
    except Exception:
        pick = None
        pick_gate_on = False

    if pick:
        pick_allowed = is_vip or (
            allow_names is not None and str(pick.get("id") or "") in allow_names
        )
        if not pick_allowed:
            return RouteResult(
                ok=False,
                text="",
                model="",
                layer="VIP",
                provider="",
                token_count=0,
                attempts=[],
                error="vip_required",
                billing_mult=int(pick.get("billing_mult") or 1),
                public_model=str(pick.get("id") or "vip_pick"),
            )
        if not pick_gate_on:
            return RouteResult(
                ok=False,
                text="",
                model="",
                layer="VIP",
                provider="",
                token_count=0,
                attempts=[],
                error="vip_pick_disabled",
                billing_mult=int(pick.get("billing_mult") or 1),
                public_model=str(pick.get("id") or "vip_pick"),
            )
        try:
            return _run_vip_pick_chat(
                pick=pick,
                prompt=prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                messages=messages,
                tools=use_tools,
                tool_choice=use_choice,
            )
        except _UpstreamFormatError as ufe:
            # 400=格式错误：直接上报，不再走降级链
            return RouteResult(
                ok=False,
                text="",
                model="",
                layer="VIP",
                provider="",
                token_count=0,
                attempts=[],
                error=f"upstream_400: {ufe}",
                billing_mult=int(pick.get("billing_mult") or 1),
                public_model=str(pick.get("id") or "vip_pick"),
            )

    attempts: list[dict[str, Any]] = []
    chain = resolve_chain(
        requested_model=requested_model, is_vip=is_vip, region_hint=region_hint
    )
    timeout_s = _timeout_s()
    any_live = any(bool(_layer_upstream(ly)["key"]) for ly, _ in chain)

    for layer, logical_model in chain:
        up = _layer_upstream(layer)
        api_model = _upstream_model_id(logical_model, up["model"], provider=up.get("provider"))
        t0 = time.time()
        # OR 模式付费档：DeepSeek 直连优先（失败后继续本层 OR）
        if (
            layer in ("L1", "L2")
            and _upstream_mode() == "openrouter"
            and _ds_prefer_paid_enabled()
        ):
            ds = _deepseek_upstream_for_layer(layer)
            if ds.get("key") and ds.get("base"):
                t_ds = time.time()
                try:
                    out = _call(
                        base=ds["base"],
                        key=ds["key"],
                        model=ds["model"],
                        prompt=prompt,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        timeout_s=timeout_s,
                        provider="deepseek",
                    )
                    used_model = str(out.get("raw_model") or ds["model"])
                    attempts.append(
                        {
                            "layer": layer,
                            "model": used_model,
                            "provider": "deepseek",
                            "ok": True,
                            "prefer": "deepseek_official",
                            "ms": int((time.time() - t_ds) * 1000),
                        }
                    )
                    raw_tokens = int(out["tokens"])
                    mult = int(_layer_billing_mult(layer))
                    return _route_ok_from_out(
                        out,
                        model=used_model,
                        layer=layer,
                        provider="deepseek",
                        attempts=attempts,
                        token_count=max(1, raw_tokens * mult),
                        billing_mult=1,
                    )
                except Exception as e_ds:
                    k_ds, d_ds = _upstream_error_class(e_ds)
                    if k_ds == "format":
                        # 400=格式错误：直接上报，不再切本层 OR
                        return RouteResult(
                            ok=False,
                            text="",
                            model="",
                            layer=layer,
                            provider="deepseek",
                            token_count=0,
                            attempts=attempts + [
                                {
                                    "layer": layer,
                                    "model": ds.get("model"),
                                    "provider": "deepseek",
                                    "ok": False,
                                    "prefer": "deepseek_official",
                                    "error": d_ds[:200],
                                }
                            ],
                            error=f"upstream_400: {d_ds}",
                            billing_mult=int(_layer_billing_mult(layer)),
                        )
                    logger.warning(
                        "deepseek prefer layer=%s failed: %s", layer, e_ds
                    )
                    attempts.append(
                        {
                            "layer": layer,
                            "model": ds.get("model"),
                            "provider": "deepseek",
                            "ok": False,
                            "prefer": "deepseek_official",
                            "error": str(e_ds)[:200],
                            "ms": int((time.time() - t_ds) * 1000),
                        }
                    )
        try:
            if up["base"] and up["key"]:
                out = _call(
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
            mult = int(_layer_billing_mult(layer))
            bill_tokens = max(1, raw_tokens * mult)
            return _route_ok_from_out(
                out,
                model=used_model,
                layer=layer,
                provider=provider,
                attempts=attempts,
                token_count=bill_tokens,
                billing_mult=1,
            )
        except Exception as e:
            elapsed = time.time() - t0
            k_e, d_e = _upstream_error_class(e)
            if k_e == "format" and provider in (
                "openrouter",
                "tokenlab",
                "requesty",
                "quickrouter",
            ):
                # 400=格式错误：直接上报，不再 failover
                return RouteResult(
                    ok=False,
                    text="",
                    model="",
                    layer=layer,
                    provider=provider,
                    token_count=0,
                    attempts=attempts
                    + [
                        {
                            "layer": layer,
                            "model": logical_model,
                            "ok": False,
                            "error": d_e[:200],
                            "ms": int(elapsed * 1000),
                        }
                    ],
                    error=f"upstream_400: {d_e}",
                    billing_mult=int(_layer_billing_mult(layer)),
                )
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
            # OR 主档 L1/L2 失败且 OR 模型是 MiMo：先切官方直连（同模型，成本=OR 价）
            if (
                layer in ("L1", "L2")
                and _upstream_mode() == "openrouter"
                and _mimo_failover_enabled()
                and "mimo" in str(api_model).lower()
            ):
                mi = _layer_mimo_upstream(layer)
                if mi:
                    t_mi = time.time()
                    try:
                        out = _call(
                            base=mi["base"],
                            key=mi["key"],
                            model=mi["model"],
                            prompt=prompt,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            timeout_s=timeout_s,
                            provider="mimo",
                        )
                        used_model = str(out.get("raw_model") or mi["model"])
                        attempts.append(
                            {
                                "layer": layer,
                                "model": used_model,
                                "provider": "mimo",
                                "ok": True,
                                "failover": "mimo_official",
                                "ms": int((time.time() - t_mi) * 1000),
                            }
                        )
                        raw_tokens = int(out["tokens"])
                        mult = int(_layer_billing_mult(layer))
                        return _route_ok_from_out(
                            out,
                            model=used_model,
                            layer=layer,
                            provider="mimo",
                            attempts=attempts,
                            token_count=max(1, raw_tokens * mult),
                            billing_mult=1,
                        )
                    except Exception as e_mi:
                        logger.warning("mimo official failover failed: %s", e_mi)
                        attempts.append(
                            {
                                "layer": layer,
                                "model": mi.get("model"),
                                "provider": "mimo",
                                "ok": False,
                                "failover": "mimo_official",
                                "error": str(e_mi)[:200],
                                "ms": int((time.time() - t_mi) * 1000),
                            }
                        )
            # L0 免费通道：硅基免费失败后切 MiMo 独立付费 key（单独记账）
            if layer == "L0" and _mimo_failover_enabled():
                mi = _mimo_free_upstream()
                if mi:
                    t_mi = time.time()
                    try:
                        out = _call(
                            base=mi["base"],
                            key=mi["key"],
                            model=mi["model"],
                            prompt=prompt,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            timeout_s=timeout_s,
                            provider="mimo",
                        )
                        used_model = str(out.get("raw_model") or mi["model"])
                        attempts.append(
                            {
                                "layer": "L0",
                                "model": used_model,
                                "provider": "mimo",
                                "ok": True,
                                "failover": "mimo_free",
                                "ms": int((time.time() - t_mi) * 1000),
                            }
                        )
                        raw_tokens = int(out["tokens"])
                        mult = int(_layer_billing_mult("L0"))
                        return _route_ok_from_out(
                            out,
                            model=used_model,
                            layer="L0",
                            provider="mimo",
                            attempts=attempts,
                            token_count=max(1, raw_tokens * mult),
                            billing_mult=1,
                        )
                    except Exception as e_mi:
                        logger.warning("mimo free failover failed: %s", e_mi)
                        attempts.append(
                            {
                                "layer": "L0",
                                "model": mi.get("model"),
                                "provider": "mimo",
                                "ok": False,
                                "failover": "mimo_free",
                                "error": str(e_mi)[:200],
                                "ms": int((time.time() - t_mi) * 1000),
                            }
                        )
            # OR 主档 L1 失败：自动试官方 DeepSeek Flash（有 Key 才走）
            if (
                layer == "L1"
                and _upstream_mode() == "openrouter"
                and _ds_failover_enabled()
            ):
                ds = _deepseek_official_upstream()
                if ds.get("key") and ds.get("base"):
                    t_ds = time.time()
                    try:
                        out = _call(
                            base=ds["base"],
                            key=ds["key"],
                            model=ds["model"],
                            prompt=prompt,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            timeout_s=timeout_s,
                            provider="deepseek",
                        )
                        used_model = str(out.get("raw_model") or ds["model"])
                        attempts.append(
                            {
                                "layer": "L1",
                                "model": used_model,
                                "provider": "deepseek",
                                "ok": True,
                                "failover": "deepseek_official",
                                "ms": int((time.time() - t_ds) * 1000),
                            }
                        )
                        raw_tokens = int(out["tokens"])
                        mult = int(_layer_billing_mult("L1"))
                        return _route_ok_from_out(
                            out,
                            model=used_model,
                            layer="L1",
                            provider="deepseek",
                            attempts=attempts,
                            token_count=max(1, raw_tokens * mult),
                            billing_mult=1,
                        )
                    except Exception as e2:
                        logger.warning("deepseek official failover failed: %s", e2)
                        attempts.append(
                            {
                                "layer": "L1",
                                "model": ds.get("model"),
                                "provider": "deepseek",
                                "ok": False,
                                "failover": "deepseek_official",
                                "error": str(e2)[:200],
                                "ms": int((time.time() - t_ds) * 1000),
                            }
                        )
            # L2/L3 QR 备用（04 实测 2026-08-13：deepseek-v4-pro / gpt-5-mini 同款 QR 200 稳定且降本）
            if layer in ("L2", "L3") and _upstream_mode() == "openrouter":
                qr = _layer_qr_upstream(layer)
                if qr:
                    try:
                        out = _call(
                            base=qr["base"],
                            key=qr["key"],
                            model=qr["model"],
                            prompt=prompt,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            timeout_s=timeout_s,
                            provider="quickrouter",
                        )
                        used_model = str(out.get("raw_model") or qr["model"])
                        attempts.append(
                            {
                                "layer": layer,
                                "model": used_model,
                                "provider": "quickrouter",
                                "ok": True,
                                "failover": "quickrouter_layer",
                                "ms": int((time.time() - t0) * 1000),
                            }
                        )
                        raw_tokens = int(out["tokens"])
                        mult = int(_layer_billing_mult(layer))
                        return _route_ok_from_out(
                            out,
                            model=used_model,
                            layer=layer,
                            provider="quickrouter",
                            attempts=attempts,
                            token_count=max(1, raw_tokens * mult),
                            billing_mult=1,
                        )
                    except Exception as e_qr:
                        k_qr, d_qr = _upstream_error_class(e_qr)
                        if k_qr == "format" and qr.get("provider") in (
                            "openrouter",
                            "tokenlab",
                            "requesty",
                            "quickrouter",
                        ):
                            return RouteResult(
                                ok=False,
                                text="",
                                model="",
                                layer=layer,
                                provider="quickrouter",
                                token_count=0,
                                attempts=attempts
                                + [
                                    {
                                        "layer": layer,
                                        "model": logical_model,
                                        "ok": False,
                                        "error": d_qr[:200],
                                        "ms": int((time.time() - t0) * 1000),
                                    }
                                ],
                                error=f"upstream_400: {d_qr}",
                                billing_mult=int(_layer_billing_mult(layer)),
                            )
                        logger.warning("layer %s QR failover failed: %s", layer, e_qr)
                        attempts.append(
                            {
                                "layer": layer,
                                "model": qr.get("model"),
                                "provider": "quickrouter",
                                "ok": False,
                                "failover": "quickrouter_layer",
                                "error": str(e_qr)[:200],
                                "ms": int((time.time() - t0) * 1000),
                            }
                        )
            continue

    # 已配置 live Key 但全部失败：对用户硬失败（勿返回假 stub 冒充成功）
    if any_live:
        logger.error("all live routes failed attempts=%s", attempts)
        return RouteResult(
            ok=False,
            text="",
            model="",
            layer="",
            provider="",
            token_count=0,
            attempts=attempts,
            error="all_live_failed",
        )

    # 未配置任何 Key：本机联调 stub
    layer0, logical0 = chain[0] if chain else ("L0", "siliconflow-free")
    stub = _stub_response(prompt, layer=layer0, model=logical0)
    attempts.append(
        {
            "layer": layer0,
            "model": logical0,
            "provider": "stub",
            "ok": True,
            "fallback": "no_keys_stub",
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
        error=None,
    )


def _vip_silicon_first_enabled() -> bool:
    return (_env("TOKEN_LLM_VIP_SILICON_FIRST") or "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _silicon_vip_upstream(model_id: str) -> Optional[dict[str, str]]:
    """付费 VIP 点名用硅基主 Key（勿用免费 L0 Key）。"""
    mid = (model_id or "").strip()
    if not mid:
        return None
    try:
        from llm_keys import silicon_main_key, silicon_com_key, silicon_cn_key

        com_key = silicon_com_key()
        if com_key:
            key = com_key
            base = (
                _env("SILICONFLOW_BASE_URL")
                or _env("TOKEN_LLM_L0_BASE")
                or "https://api.siliconflow.com/v1"
            )
        else:
            key = silicon_cn_key() or silicon_main_key()
            base = (
                _env("SILICONFLOW_BASE_URL")
                or _env("TOKEN_LLM_L0_BASE")
                or "https://api.siliconflow.cn/v1"
            )
    except Exception:
        key = _env("SILICONFLOW_COM_API_KEY") or _env("SILICONFLOW_API_KEY") or _env("TOKEN_LLM_L0_KEY")
        base = (
            _env("SILICONFLOW_BASE_URL")
            or ("https://api.siliconflow.com/v1" if _env("SILICONFLOW_COM_API_KEY") else "https://api.siliconflow.cn/v1")
        )
    if not key:
        return None
    return {"base": base, "key": key, "model": mid, "provider": "siliconflow"}

# —— 国际聚合备用（#2 TokenLab / #3 Requesty）：仅 OR 失败后进入，优先级在厂直连之前 ——
_TOKENLAB_MODEL_MAP: dict[str, str] = {
    "vip-hy3": "hy3",
    "vip-ds-flash": "deepseek-v4-flash",
    "vip-ds-pro": "deepseek-v4-pro",
    "vip-kimi": "kimi-k3",
    "vip-kimi-code": "kimi-k2.7-code",
    "vip-mimo": "mimo-v2.5-pro",
    "vip-minimax": "minimax-m3",
    "vip-qwen-max": "qwen3.7-max",
    "vip-glm": "glm-5.2",
    "vip-gpt5": "gpt-5",
    "vip-gpt5-mini": "gpt-5-mini",
    "vip-gpt54": "gpt-5.4",
    "vip-gpt4o": "gpt-4o",
    "vip-gpt4o-mini": "gpt-4o-mini",
    "vip-claude-sonnet": "claude-sonnet-5",
    "vip-claude-haiku": "claude-haiku-4-5",
    "vip-claude-opus": "claude-opus-5",
    "vip-gemini-pro": "gemini-3.1-pro-preview",
    "vip-gemini-flash": "gemini-3.6-flash",
    "vip-gpt56-terra": "gpt-5.6-terra",
    "vip-gpt56-luna": "gpt-5.6-luna",
    "vip-grok": "grok-4.20",
}

# QuickRouter（#4 国际聚合 · gpt-5 系降本 50%；2026-08-11 接入，分组倍率×1 已账单实测）
_QUICKROUTER_MODEL_MAP: dict[str, str] = {
    "vip-gpt5": "gpt-5",
    "vip-gpt5-mini": "gpt-5-mini",
    # ⚠️ 主脑 2026-08-12：QR 支持 Luna+tools 实测 200，加映射（降本+绕 TokenLab 400）
    "vip-gpt56-luna": "gpt-5.6-luna",
}

_REQUESTY_MODELS: frozenset[str] = frozenset({
    "deepseek/deepseek-v4-flash",
    "deepseek/deepseek-v4-pro",
    "xiaomi/mimo-v2.5-pro",
    "openai/gpt-5",
    "openai/gpt-5-mini",
    "openai/gpt-5.4",
    "openai/gpt-4o",
    "openai/gpt-4o-mini",
    "anthropic/claude-sonnet-5",
    "anthropic/claude-opus-5",
    "google/gemini-3.1-pro-preview",
    "openai/gpt-5.6-terra",
    "openai/gpt-5.6-luna",
})


def _aggregator_upstream(provider_id: str, public_id: str, or_id: str) -> Optional[dict[str, str]]:
    """#2 TokenLab / #3 Requesty 聚合解析；模型不存在则返回 None（由调用链跳过）。"""
    try:
        from upstream_providers import resolve_provider

        up = resolve_provider(provider_id)
        if not up or not up.get("key") or not up.get("base"):
            return None
        if provider_id == "tokenlab":
            model = _TOKENLAB_MODEL_MAP.get(public_id)
        elif provider_id == "quickrouter":
            model = _QUICKROUTER_MODEL_MAP.get(public_id)
        else:
            model = or_id if or_id in _REQUESTY_MODELS else None
        if not model:
            return None
        return {
            "base": _normalize_openai_base(str(up["base"])),
            "key": str(up["key"]),
            "model": model,
            "provider": provider_id,
        }
    except Exception:
        return None


def _aggregator_candidates(public_id: str, or_id: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for pid in ("tokenlab", "requesty"):
        up = _aggregator_upstream(pid, public_id, or_id)
        if up:
            out.append(up)
    return out



def _vip_aggregator_chain(pick: dict[str, Any], or_id: str) -> list[dict[str, str]]:
    """VIP aggregator chain: default OR -> TokenLab -> Requesty; reorder/block via warehouse channels field."""
    public_id = str(pick.get("id") or "")
    try:
        from model_warehouse import vip_channel_order

        order = vip_channel_order(public_id)
    except Exception as e:
        logger.warning("vip_channel_order(%s) fallback default: %s", public_id, e)
        order = None
    default_order = ("openrouter", "tokenlab", "requesty", "quickrouter")
    if isinstance(order, list) and order:
        # channels 为严格白名单顺序：只走列出的通道（未列出的不自动补回，未配置才用默认）
        seen: set[str] = set()
        chain: list[str] = []
        for p in order:
            if p in default_order and p not in seen:
                seen.add(p)
                chain.append(p)
    else:
        chain = list(default_order)
    out: list[dict[str, str]] = []
    for pid in chain:
        # 熔断冷却中的聚合通道自动跳过（默认关闭，不影响现有行为）
        if upstream_health.circuit_open(pid):
            continue
        if pid == "openrouter":
            if not or_id or _upstream_mode() != "openrouter":
                continue
            up = _layer_upstream("L1")
            if not (up.get("key") and up.get("base")):
                continue
            out.append(
                {
                    "provider": "openrouter",
                    "base": str(up["base"]),
                    "key": str(up["key"]),
                    "model": or_id,
                }
            )
        else:
            agg = _aggregator_upstream(pid, public_id, or_id)
            if agg:
                out.append(agg)
    return out


def _run_vip_pick_chat(
    *,
    pick: dict[str, Any],
    prompt: str,
    temperature: float,
    max_tokens: int,
    messages: Optional[list[dict[str, Any]]] = None,
    tools: Optional[list[dict[str, Any]]] = None,
    tool_choice: Any = None,
) -> RouteResult:
    """VIP 点名路由。

    中国模（有 siliconflow_id）：硅基 → OR → 官方 DS/厂直连 → 降级
    DeepSeek 点名：官方 DS → OR → 硅基同族 → 降级
    国际旗舰：OR → TokenLab/Requesty → 厂直连 → DS Flash 降级（禁止硅基顶替）
    """
    billing_mult = max(1, int(pick.get("billing_mult") or 1))
    in_mult = max(1, int(pick.get("in_mult") or pick.get("billing_mult") or 1))
    out_mult = max(1, int(pick.get("out_mult") or pick.get("billing_mult") or 1))
    # 2026-08-15 峰谷：DeepSeek 点名峰时按峰值倍率扣费（实时取时段）
    _pm = _peak_mults(pick)
    if _pm:
        in_mult, out_mult = _pm
    public_id = str(pick.get("id") or "vip_pick")
    or_id = (pick.get("openrouter_id") or "").strip()
    direct_id = (pick.get("direct_id") or "").strip()
    sf_id = (pick.get("siliconflow_id") or "").strip()
    timeout_s = _timeout_s()
    attempts: list[dict[str, Any]] = []
    is_ds_pick = public_id.startswith("vip-ds-")
    is_intl_flagship = (
        public_id.startswith("vip-gpt")
        or "claude" in public_id
        or "gemini" in public_id
        or "grok" in public_id
        or "llama" in public_id
    )

    def _ok_result(out: dict[str, Any], *, model: str, provider: str) -> RouteResult:
        raw = max(1, int(out.get("tokens") or 1))
        p_in = max(1, int(out.get("prompt_tokens") or 0))
        p_out = max(1, int(out.get("completion_tokens") or 0))
        if p_in <= 1 and p_out <= 1:
            half = max(1, raw // 2)
            p_in, p_out = half, max(1, raw - half)
        return _route_ok_from_out(
            out,
            model=model,
            layer="VIP",
            provider=provider,
            attempts=attempts,
            token_count=max(1, p_in * in_mult + p_out * out_mult),
            billing_mult=billing_mult,
            public_model=public_id,
        )

    def _try_call(
        *,
        base: str,
        key: str,
        model: str,
        provider: str,
        note: Optional[str] = None,
    ) -> Optional[RouteResult]:
        t0 = time.time()
        try:
            out = _call_openai_compatible(
                base=base,
                key=key,
                model=model,
                prompt=prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout_s=timeout_s,
                provider=provider,
                messages=messages,
                tools=tools,
                tool_choice=tool_choice,
            )
            row = {
                "layer": "VIP",
                "model": model,
                "provider": provider,
                "ok": True,
                "ms": int((time.time() - t0) * 1000),
            }
            if note:
                row["prefer"] = note
            attempts.append(row)
            return _ok_result(out, model=model, provider=provider)
        except Exception as e:
            row = {
                "layer": "VIP",
                "model": model,
                "provider": provider,
                "ok": False,
                "error": str(e)[:200],
            }
            if note:
                row["prefer"] = note
            attempts.append(row)
            kind, detail = _upstream_error_class(e)
            if kind == "format" and provider in (
                "openrouter",
                "tokenlab",
                "requesty",
                "quickrouter",
            ):
                # 400=格式错误：同载荷换聚合上游必然同样 400，直接上报停止链
                raise _UpstreamFormatError(detail) from e
            logger.warning(
                "vip_pick %s failed id=%s model=%s err=%s",
                provider,
                public_id,
                model,
                e,
            )
            return None

    # —— 通道顺序（2026-08-03：中国模硅基.com 优先(价低) → OR 兜底；国际模 OR 优先）——
    # A) DeepSeek 点名：官方直连最稳最便宜
    if is_ds_pick and direct_id and _ds_failover_enabled():
        ds = _deepseek_official_upstream()
        if ds.get("key") and ds.get("base"):
            got = _try_call(
                base=str(ds["base"]),
                key=str(ds["key"]),
                model=direct_id,
                provider="deepseek",
                note="deepseek_official_first",
            )
            if got:
                return got

    # B) 中国模（非国际旗舰）：硅基 .com 优先（原厂价+国际端点，又快又便宜）
    if (
        (not is_intl_flagship)
        and (not is_ds_pick)
        and sf_id
        and _vip_silicon_first_enabled()
    ):
        sf = _silicon_vip_upstream(sf_id)
        if sf:
            got = _try_call(
                base=_normalize_openai_base(sf["base"]),
                key=sf["key"],
                model=sf["model"],
                provider="siliconflow",
                note="silicon_com_first",
            )
            if got:
                return got

    # C) OpenRouter（国际模主路径；中国模兜底）
    # C+D) aggregator chain: OR -> TokenLab -> Requesty default; flagship prefers channel via channels field
    for cand in _vip_aggregator_chain(pick, or_id):
        got = _try_call(
            base=str(cand["base"]),
            key=str(cand["key"]),
            model=str(cand["model"]),
            provider=str(cand["provider"]),
            note=str(cand["provider"]) + "_chain",
        )
        if got:
            return got
    # C2) MiMo 点名：聚合链失败后切官方直连（同模型 mimo-v2.5-pro；2026-08-15 直连兜底）
    if "mimo" in or_id.lower() and _mimo_failover_enabled():
        mi = _layer_mimo_upstream("L2")
        if mi:
            got = _try_call(
                base=str(mi["base"]),
                key=str(mi["key"]),
                model=str(mi["model"]),
                provider="mimo",
                note="mimo_official",
            )
            if got:
                return got
    # E) 国际旗舰厂直连 / 其它 VIP 厂直连
    try:
        from upstream_providers import direct_model_for_vip

        direct_up = direct_model_for_vip(public_id)
        if direct_up and not direct_up.get("skip_call") and direct_up.get("key"):
            got = _try_call(
                base=_normalize_openai_base(str(direct_up["base"])),
                key=str(direct_up["key"]),
                model=str(direct_up["model"]),
                provider=str(direct_up.get("id") or "direct"),
                note="vendor_direct",
            )
            if got:
                return got
    except Exception as e:
        logger.debug("vip direct resolve skip: %s", e)

    # E) 目录 direct_id → 官方 DeepSeek（非 ds 点名时的兜底）
    if (not is_ds_pick) and direct_id and _ds_failover_enabled():
        ds = _deepseek_official_upstream()
        use_ds = bool(ds.get("key") and ds.get("base")) and (
            str(direct_id).startswith("deepseek")
            or "deepseek" in str(direct_id).lower()
        )
        if use_ds:
            got = _try_call(
                base=str(ds["base"]),
                key=str(ds["key"]),
                model=direct_id,
                provider="deepseek",
                note="deepseek_official",
            )
            if got:
                return got

    # F) DeepSeek 点名失败后：硅基同族
    if is_ds_pick and sf_id and _vip_silicon_first_enabled():
        sf = _silicon_vip_upstream(sf_id)
        if sf:
            got = _try_call(
                base=_normalize_openai_base(sf["base"]),
                key=sf["key"],
                model=sf["model"],
                provider="siliconflow",
                note="silicon_ds_fallback",
            )
            if got:
                return got

    # G) 降级：中国模可走硅基映射/默认小模；国际旗舰禁止静默用硅基顶 GPT/Claude
    degrade_targets: list[tuple[str, str, str, str]] = []

    if _ds_failover_enabled():
        ds = _deepseek_official_upstream()
        if ds.get("key") and ds.get("base"):
            degrade_targets.append(
                (
                    "deepseek",
                    str(ds["base"]),
                    str(ds["key"]),
                    str(ds.get("model") or "deepseek-v4-flash"),
                )
            )

    if not is_intl_flagship:
        try:
            from llm_keys import silicon_degrade_key

            sf_key = silicon_degrade_key()
            sf_base = (
                _env("SILICONFLOW_BASE_URL")
                or _env("TOKEN_LLM_L0_BASE")
                or "https://api.siliconflow.com/v1"
            )
            # 优先用点名映射；没有则回落 L0 默认模（质变，仅最后兜底）
            sf_model = sf_id or (
                _env("SILICONFLOW_MODEL")
                or _env("TOKEN_LLM_L0_MODEL")
                or "Qwen/Qwen2.5-7B-Instruct"
            )
            if sf_key:
                degrade_targets.append(("siliconflow", sf_base, sf_key, sf_model))
        except Exception:
            pass
    else:
        try:
            from upstream_providers import resolve_provider

            tg = resolve_provider("together")
            _ = tg
        except Exception:
            pass

    # 4b) 仍无官方 DS 时：用 OR 主 Key 打 DS Flash（二次机会）
    if not any(p[0] == "deepseek" for p in degrade_targets):
        try:
            from llm_keys import openrouter_main_key

            or_key = openrouter_main_key()
            if or_key:
                degrade_targets.append(
                    (
                        "openrouter",
                        _env("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1",
                        or_key,
                        "deepseek/deepseek-v4-flash",
                    )
                )
        except Exception:
            pass

    for prov, base, key, model in degrade_targets:
        if not key or not base:
            continue
        t0 = time.time()
        try:
            out = _call_openai_compatible(
                base=_normalize_openai_base(base),
                key=key,
                model=model,
                prompt=prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout_s=timeout_s,
                provider=prov,
                messages=messages,
                tools=tools,
                tool_choice=tool_choice,
            )
            elapsed = time.time() - t0
            raw = max(1, int(out.get("tokens") or 1))
            attempts.append(
                {
                    "layer": "VIP",
                    "model": model,
                    "provider": prov,
                    "ok": True,
                    "degraded": True,
                    "ms": int(elapsed * 1000),
                }
            )
            try:
                from llm_keys import note_vip_degrade

                note_vip_degrade(
                    public_id=public_id,
                    to_provider=prov,
                    to_model=model,
                    reason="or_or_direct_unavailable",
                )
            except Exception:
                pass
            return _ok_result(out, model=model, provider=prov)
        except Exception as e:
            attempts.append(
                {
                    "layer": "VIP",
                    "model": model,
                    "provider": prov,
                    "ok": False,
                    "degraded": True,
                    "error": str(e)[:200],
                }
            )

    # 5) 无 Key stub（仅联调）
    if not any(bool(_layer_upstream(ly).get("key")) for ly in ("L1", "L2", "L0")):
        stub = _stub_response(prompt, layer="VIP", model=public_id)
        return RouteResult(
            ok=True,
            text=str(stub["text"]),
            model=public_id,
            layer="VIP",
            provider="stub",
            token_count=max(1, int(stub["tokens"]) * out_mult),
            attempts=attempts + [{"layer": "VIP", "ok": True, "provider": "stub"}],
            billing_mult=billing_mult,
            public_model=public_id,
        )

    return RouteResult(
        ok=False,
        text="",
        model="",
        layer="VIP",
        provider="",
        token_count=0,
        attempts=attempts,
        error="vip_pick_failed",
        billing_mult=billing_mult,
        public_model=public_id,
    )


def public_tier_name(
    requested_model: Optional[str],
    *,
    layer: str = "",
    upstream_model: str = "",
) -> str:
    """对外只返回品牌档，不暴露上游型号。VIP 点名返回 vip-* id。"""
    req = (requested_model or "").strip().lower()
    try:
        from model_warehouse import resolve_vip_pick

        pick = resolve_vip_pick(requested_model)
        if pick:
            return str(pick.get("id") or "vip_pick")
    except Exception:
        pass
    if req in ("flash", "pro", "ultra", "auto", "shared"):
        return req
    if req in ("free", "free-shared", "free_shared"):
        return "shared" if req != "free" else "auto"
    if req.startswith("vip-") or req.startswith("vip:"):
        return req.replace("vip:", "vip-")[:64]
    ly = (layer or "").upper()
    if ly == "VIP":
        return req[:64] if req else "vip_pick"
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
        "Always write the brand as the single token AI24X — never AI on4X, AIon4X, or 24X alone. "
        "When users ask which model or company you are, say you are the AI24X assistant "
        "(tiers: auto / flash / pro / ultra / shared). "
        "Do not name or invent upstream providers, routing layers, env vars, file paths, "
        "or model brands such as DeepSeek, Xiaomi, MiMo, Qwen, OpenAI, OpenRouter, SiliconFlow, "
        "L0/L1/L2/L3, TOKEN_LLM_*, model_warehouse, or .env. "
        "If asked for API keys, secrets, infrastructure, or internal routing, refuse: "
        "you do not have access to operator credentials and cannot disclose gateway internals. "
        "Answer helpfully in the user's language. Use complete sentences; do not repeat filler words."
    )


@upstream_health.wrap
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
    messages: Optional[list[dict[str, Any]]] = None,
    tools: Optional[list[dict[str, Any]]] = None,
    tool_choice: Any = None,
    system_prompt: Optional[str] = None,
    include_reasoning: Optional[bool] = None,
) -> dict[str, Any]:
    from reasoning_filter import extract_client_visible_text

    if include_reasoning is None:
        include_reasoning = bool(_INCLUDE_REASONING_CV.get())
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
        "messages": _build_chat_messages(
            prompt, messages, system_prompt=system_prompt
        ),
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if tools and _tools_passthrough_enabled():
        body["tools"] = _normalize_tools_for_upstream(tools) or tools
        if tool_choice is not None:
            body["tool_choice"] = tool_choice
    # 中国模：默认向上游关 thinking（与客户端出口过滤分离）
    _apply_upstream_thinking_controls(body, model=model, provider=provider)
    from upstream_gate import upstream_slot

    with upstream_slot():
        r = _SHARED_CLIENT.post(
            url,
            headers=headers,
            json=body,
            timeout=_httpx_timeout(timeout_s),
        )
    r.raise_for_status()
    data = r.json()
    choices = data.get("choices") or []
    text = ""
    tool_calls = None
    finish_reason = "stop"
    if choices:
        ch0 = choices[0] or {}
        msg = ch0.get("message") or {}
        # 出口强制过滤：默认不把 reasoning_* 填进正文
        text = extract_client_visible_text(
            msg if isinstance(msg, dict) else {},
            include_reasoning=include_reasoning,
        )
        raw_tcs = msg.get("tool_calls") if isinstance(msg, dict) else None
        if isinstance(raw_tcs, list) and raw_tcs:
            tool_calls = raw_tcs
        finish_reason = str(
            ch0.get("finish_reason") or ("tool_calls" if tool_calls else "stop")
        )
    usage = data.get("usage") or {}
    total = int(usage.get("total_tokens") or 0)
    prompt_t = int(usage.get("prompt_tokens") or 0)
    completion_t = int(usage.get("completion_tokens") or 0)
    # Anthropic 文本工具调用（<invoke> XML / collab:）→ 结构化 tool_calls
    if not tool_calls and _is_anthropic_upstream(model, provider) and text:
        parsed_tcs = _parse_invoke_tool_calls(text)
        if parsed_tcs:
            tool_calls = parsed_tcs
            finish_reason = "tool_calls"
            text = _INVOKE_TAG_RE.sub("", text).strip()
    if total <= 0:
        # tool_calls 无正文时也按最小 1 token 计（避免 0）
        total = max(1, int(len(text.split()) * 1.3)) if text else 1
    if prompt_t <= 0 and completion_t <= 0:
        # 上游未返回 in/out 拆分：按 prompt 长度粗估输入，其余算输出
        prompt_est = max(1, int(len(prompt) / 4)) if prompt else max(1, total // 2)
        prompt_t = min(prompt_est, max(1, total - 1))
        completion_t = max(1, total - prompt_t)
    elif prompt_t <= 0:
        prompt_t = max(0, total - completion_t)
    elif completion_t <= 0:
        completion_t = max(1, total - prompt_t)
    return {
        "text": text,
        "tokens": total,
        "prompt_tokens": prompt_t,
        "completion_tokens": completion_t,
        "raw_model": model,
        "tool_calls": tool_calls,
        "finish_reason": finish_reason,
    }


def _stream_openai_compatible(
    *,
    base: str,
    key: str,
    model: str,
    prompt: str,
    temperature: float,
    max_tokens: int,
    timeout_s: float,
    provider: str = "",
    messages: Optional[list[dict[str, Any]]] = None,
    tools: Optional[list[dict[str, Any]]] = None,
    tool_choice: Any = None,
    include_reasoning: Optional[bool] = None,
):
    """上游真流式。yield dict: delta / tool_calls_delta / done / error。"""
    import json as _json

    from reasoning_filter import ThinkTagStreamScrubber, stream_delta_visible_piece

    if include_reasoning is None:
        include_reasoning = bool(_INCLUDE_REASONING_CV.get())
    url = f"{base}/chat/completions"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    if provider == "openrouter" or "openrouter.ai" in (base or ""):
        headers["HTTP-Referer"] = (
            _env("OPENROUTER_SITE_URL") or "https://www.ai24x.com"
        )
        headers["X-Title"] = _env("OPENROUTER_APP_NAME") or "AI24X"
    body: dict[str, Any] = {
        "model": model,
        "messages": _build_chat_messages(prompt, messages),
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }
    if tools and _tools_passthrough_enabled():
        body["tools"] = _normalize_tools_for_upstream(tools) or tools
        if tool_choice is not None:
            body["tool_choice"] = tool_choice
    _apply_upstream_thinking_controls(body, model=model, provider=provider)
    scrubber = ThinkTagStreamScrubber(include_reasoning=include_reasoning)
    # 部分上游在 stream 时把 usage 放在最后一包
    body["stream_options"] = {"include_usage": True}
    # 上线前 S2：禁止全量 prompt 落日志/落盘（仅保留轻量元数据）
    try:
        logger.debug(
            "upstream stream provider=%s model=%s msgs=%s tools=%s",
            provider,
            model,
            len(body.get("messages") or []),
            len(body.get("tools") or []),
        )
    except Exception:
        pass

    timeout = _httpx_timeout(timeout_s)
    full_parts: list[str] = []
    usage_tokens = 0
    usage_prompt_tokens = 0
    usage_completion_tokens = 0
    finish_reason = "stop"
    tool_calls_streamed = False
    # 拼装流式 tool_calls（按 index）
    tc_acc: dict[int, dict[str, Any]] = {}
    from upstream_gate import release_upstream_slot, try_acquire_upstream_slot

    if not try_acquire_upstream_slot():
        yield {
            "type": "error",
            "error": "upstream_busy",
            "raw_model": model,
            "provider": provider,
            "error_kind": "busy",
        }
        return
    try:
        try:
            with _SHARED_CLIENT.stream(
                "POST", url, headers=headers, json=body, timeout=timeout
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
                        if data == "[DONE]":
                            break
                        try:
                            obj = _json.loads(data)
                        except Exception:
                            continue
                        usage = obj.get("usage") or {}
                        if usage.get("total_tokens"):
                            try:
                                usage_tokens = int(usage.get("total_tokens") or 0)
                            except (TypeError, ValueError):
                                pass
                        try:
                            if usage.get("prompt_tokens") is not None:
                                usage_prompt_tokens = int(usage.get("prompt_tokens") or 0)
                            if usage.get("completion_tokens") is not None:
                                usage_completion_tokens = int(usage.get("completion_tokens") or 0)
                        except (TypeError, ValueError):
                            pass
                        choices = obj.get("choices") or []
                        if not choices:
                            continue
                        ch0 = choices[0] or {}
                        fr = ch0.get("finish_reason")
                        if fr:
                            finish_reason = str(fr)
                        delta = ch0.get("delta") or {}
                        tcs = delta.get("tool_calls")
                        if isinstance(tcs, list) and tcs:
                            tool_calls_streamed = True
                            for piece_tc in tcs:
                                if not isinstance(piece_tc, dict):
                                    continue
                                try:
                                    idx = int(piece_tc.get("index") or 0)
                                except (TypeError, ValueError):
                                    idx = 0
                                slot = tc_acc.setdefault(
                                    idx,
                                    {
                                        "id": "",
                                        "type": "function",
                                        "function": {"name": "", "arguments": ""},
                                    },
                                )
                                if piece_tc.get("id"):
                                    slot["id"] = str(piece_tc.get("id"))
                                if piece_tc.get("type"):
                                    slot["type"] = str(piece_tc.get("type"))
                                fn = piece_tc.get("function") or {}
                                if isinstance(fn, dict):
                                    if fn.get("name"):
                                        slot["function"]["name"] = str(
                                            slot["function"].get("name") or ""
                                        ) + str(fn.get("name"))
                                    if fn.get("arguments") is not None:
                                        slot["function"]["arguments"] = str(
                                            slot["function"].get("arguments") or ""
                                        ) + str(fn.get("arguments"))
                            yield {
                                "type": "tool_calls_delta",
                                "tool_calls": tcs,
                                "raw_model": model,
                                "provider": provider,
                            }
                        piece = stream_delta_visible_piece(
                            delta if isinstance(delta, dict) else {},
                            include_reasoning=include_reasoning,
                        )
                        if piece:
                            text_piece = scrubber.feed(str(piece))
                            if text_piece:
                                full_parts.append(text_piece)
                                yield {
                                    "type": "delta",
                                    "text": text_piece,
                                    "raw_model": model,
                                    "provider": provider,
                                }
        except Exception as e:
            # 附带上游 4xx/5xx 响应体 + 错误分类（format=400 直接上报不再 failover）
            kind, detail = _upstream_error_class(e)
            logger.warning(
                "upstream error kind=%s provider=%s model=%s detail=%s",
                kind,
                provider,
                model,
                str(detail)[:500],
            )
            yield {
                "type": "error",
                "error": detail,
                "raw_model": model,
                "provider": provider,
                "error_kind": kind,
            }
            return

        tail = scrubber.flush()
        if tail:
            full_parts.append(tail)
            yield {
                "type": "delta",
                "text": tail,
                "raw_model": model,
                "provider": provider,
            }
        full = "".join(full_parts)
        assembled_tcs = None
        if tc_acc:
            assembled_tcs = [tc_acc[i] for i in sorted(tc_acc.keys())]
            if finish_reason == "stop":
                finish_reason = "tool_calls"
        # Anthropic 文本工具调用（<invoke> XML / collab:）→ 结构化 tool_calls
        if not assembled_tcs and _is_anthropic_upstream(model, provider) and full:
            parsed_tcs = _parse_invoke_tool_calls(full)
            if parsed_tcs:
                assembled_tcs = parsed_tcs
                finish_reason = "tool_calls"
        if usage_tokens <= 0:
            usage_tokens = max(1, int(len(full.split()) * 1.3)) if full else 1
        if usage_prompt_tokens <= 0 and usage_completion_tokens <= 0:
            prompt_est = max(1, int(len(prompt) / 4)) if prompt else max(1, usage_tokens // 2)
            usage_prompt_tokens = min(prompt_est, max(1, usage_tokens - 1))
            usage_completion_tokens = max(1, usage_tokens - usage_prompt_tokens)
        elif usage_prompt_tokens <= 0:
            usage_prompt_tokens = max(0, usage_tokens - usage_completion_tokens)
        elif usage_completion_tokens <= 0:
            usage_completion_tokens = max(1, usage_tokens - usage_prompt_tokens)
        yield {
            "type": "done",
            "text": full,
            "tokens": usage_tokens,
            "prompt_tokens": usage_prompt_tokens,
            "completion_tokens": usage_completion_tokens,
            "raw_model": model,
            "provider": provider,
            "tool_calls": assembled_tcs,
            "finish_reason": finish_reason,
            "tool_calls_streamed": tool_calls_streamed,
        }
    finally:
        release_upstream_slot()




def _stub_response(prompt: str, *, layer: str, model: str) -> dict[str, Any]:
    preview = (prompt or "")[:80]
    text = (
        f"[AI24X {layer}/{model} stub] 已收到：{preview}"
        f"{'…' if len(prompt or '') > 80 else ''}。"
        "当前未配置 TOKEN_LLM_* upstream，返回联调占位回复。"
    )
    return {"text": text, "tokens": max(1, int(len(text.split()) * 1.3))}


def _try_upstream_stream(
    *,
    base: str,
    key: str,
    model: str,
    prompt: str,
    temperature: float,
    max_tokens: int,
    provider: str,
    layer: str,
    billing_mult: int,
    public_model: str,
    messages: Optional[list[dict[str, Any]]],
    tools: Optional[list[dict[str, Any]]] = None,
    tool_choice: Any = None,
    billing_in: Optional[int] = None,
    billing_out: Optional[int] = None,
) -> Iterator[dict[str, Any]]:
    """对单一上游做真流式；成功结束 yield done；首包前失败 yield 空并 return。

    双价计费：billing_in/billing_out 缺省回落 billing_mult（品牌层单费率不变）。
    """
    timeout_s = _stream_timeout_s()
    started = False
    recorded = False
    t0 = time.time()
    in_mult = max(1, int(billing_in if billing_in is not None else billing_mult or 1))
    out_mult = max(1, int(billing_out if billing_out is not None else billing_mult or 1))
    for ev in _stream_openai_compatible(
        base=_normalize_openai_base(base),
        key=key,
        model=model,
        prompt=prompt,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout_s=timeout_s,
        provider=provider,
        messages=messages,
        tools=tools,
        tool_choice=tool_choice,
    ):
        et = ev.get("type")
        if et == "error":
            err_kind = str(ev.get("error_kind") or "network")
            if not recorded:
                # 400 格式错误属载荷问题，不是上游故障：不记健康失败（不触发熔断/误判）
                if err_kind != "format":
                    upstream_health.record_attempt(
                        provider,
                        model,
                        ok=False,
                        ms=int((time.time() - t0) * 1000),
                        err=str(ev.get("error") or "")[:160],
                    )
                recorded = True
            if started:
                # 已写出部分内容：按已有文本收尾，避免客户端悬空
                text = str(ev.get("partial") or "")
                raw = max(1, int(len(text.split()) * 1.3)) if text else 1
                half = max(1, raw // 2)
                billed = max(1, half * in_mult + max(1, raw - half) * out_mult)
                yield {
                    "type": "done",
                    "text": text,
                    "tokens": billed,
                    "raw_model": model,
                    "provider": provider,
                    "layer": layer,
                    "billing_mult": billing_mult,
                    "public_model": public_model,
                    "degraded_error": str(ev.get("error") or "")[:200],
                }
            elif err_kind == "format":
                # 400=格式错误：同载荷换聚合上游必然同样 400，直接上报停止链
                yield {
                    "type": "error",
                    "error": f"upstream_400: {str(ev.get('error') or '')[:400]}",
                    "raw_model": model,
                    "provider": provider,
                    "error_kind": "format",
                }
            return
        if et in ("delta", "tool_calls_delta"):
            if not started:
                started = True
                yield {
                    "type": "meta",
                    "layer": layer,
                    "provider": provider,
                    "raw_model": model,
                    "billing_mult": billing_mult,
                    "public_model": public_model,
                }
            yield ev
        elif et == "done":
            if not recorded:
                upstream_health.record_attempt(
                    provider, model, ok=True, ms=int((time.time() - t0) * 1000)
                )
                recorded = True
            raw = max(1, int(ev.get("tokens") or 1))
            p_in = max(1, int(ev.get("prompt_tokens") or 0))
            p_out = max(1, int(ev.get("completion_tokens") or 0))
            if p_in <= 1 and p_out <= 1:
                # 上游未给 in/out 拆分：按半估
                half = max(1, raw // 2)
                p_in, p_out = half, max(1, raw - half)
            billed = max(1, p_in * in_mult + p_out * out_mult)
            yield {
                "type": "done",
                "text": str(ev.get("text") or ""),
                "tokens": billed,
                "raw_model": str(ev.get("raw_model") or model),
                "provider": provider,
                "layer": layer,
                "billing_mult": billing_mult,
                "public_model": public_model,
                "billing_in": in_mult,
                "billing_out": out_mult,
                "tool_calls": ev.get("tool_calls"),
                "finish_reason": ev.get("finish_reason") or "stop",
                "tool_calls_streamed": bool(ev.get("tool_calls_streamed")),
            }
            return
    if not recorded:
        upstream_health.record_attempt(
            provider,
            model,
            ok=False,
            ms=int((time.time() - t0) * 1000),
            err="stream_ended_without_done",
        )
    if not started:
        return


def run_routed_chat_stream(
    *,
    prompt: str,
    requested_model: Optional[str],
    is_vip: bool,
    allow_names: Optional[set[str]] = None,
    temperature: float = 0.7,
    max_tokens: int = 1000,
    region_hint: Optional[str] = None,
    messages: Optional[list[dict[str, Any]]] = None,
    tools: Optional[list[dict[str, Any]]] = None,
    tool_choice: Any = None,
    include_reasoning: bool = False,
) -> Iterator[dict[str, Any]]:
    """真流式路由。事件：meta → delta* / tool_calls_delta* → done；全部失败则 error。"""
    tok = _INCLUDE_REASONING_CV.set(bool(include_reasoning))
    try:
        yield from _run_routed_chat_stream_inner(
            prompt=prompt,
            requested_model=requested_model,
            is_vip=is_vip,
            allow_names=allow_names,
            temperature=temperature,
            max_tokens=max_tokens,
            region_hint=region_hint,
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
        )
    finally:
        _INCLUDE_REASONING_CV.reset(tok)


def _run_routed_chat_stream_inner(
    *,
    prompt: str,
    requested_model: Optional[str],
    is_vip: bool,
    allow_names: Optional[set[str]] = None,
    temperature: float = 0.7,
    max_tokens: int = 1000,
    region_hint: Optional[str] = None,
    messages: Optional[list[dict[str, Any]]] = None,
    tools: Optional[list[dict[str, Any]]] = None,
    tool_choice: Any = None,
) -> Iterator[dict[str, Any]]:
    """真流式路由内核。"""
    use_tools = tools if (tools and _tools_passthrough_enabled()) else None
    use_choice = tool_choice if use_tools is not None else None
    pick = None
    pick_gate_on = False
    try:
        from model_warehouse import resolve_vip_pick, vip_pick_enabled

        pick = resolve_vip_pick(requested_model)
        pick_gate_on = bool(vip_pick_enabled())
    except Exception:
        pick = None
        pick_gate_on = False

    if pick:
        pick_allowed = is_vip or (
            allow_names is not None and str(pick.get("id") or "") in allow_names
        )
        if not pick_allowed:
            yield {"type": "error", "error": "vip_required"}
            return
        if pick_gate_on:
            yield from _run_vip_pick_chat_stream(
                pick=pick,
                prompt=prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                messages=messages,
                tools=use_tools,
                tool_choice=use_choice,
            )
            return
        yield {"type": "error", "error": "vip_pick_disabled"}
        return

    chain = resolve_chain(
        requested_model=requested_model, is_vip=is_vip, region_hint=region_hint
    )
    public = public_tier_name(requested_model or "flash", layer="", upstream_model="")
    targets: list[tuple[str, str, str, str, str, int]] = []
    # (layer, provider, base, key, model, mult)

    for layer, logical_model in chain:
        up = _layer_upstream(layer)
        mult = int(_layer_billing_mult(layer))
        if (
            layer in ("L1", "L2")
            and _upstream_mode() == "openrouter"
            and _ds_prefer_paid_enabled()
        ):
            ds = _deepseek_upstream_for_layer(layer)
            if ds.get("key") and ds.get("base"):
                targets.append(
                    (
                        layer,
                        "deepseek",
                        str(ds["base"]),
                        str(ds["key"]),
                        str(ds["model"]),
                        mult,
                    )
                )
        if up.get("key") and up.get("base"):
            api_model = _upstream_model_id(logical_model, up["model"], provider=up.get("provider"))
            targets.append(
                (
                    layer,
                    str(up.get("provider") or "upstream"),
                    str(up["base"]),
                    str(up["key"]),
                    api_model,
                    mult,
                )
            )
            # MiMo 官方直连同模型兜底（OR 的 xiaomi/mimo-* 失败后；2026-08-15）
            if (
                layer in ("L1", "L2")
                and _upstream_mode() == "openrouter"
                and _mimo_failover_enabled()
                and "mimo" in api_model.lower()
            ):
                mi = _layer_mimo_upstream(layer)
                if mi:
                    targets.append(
                        (
                            layer,
                            "mimo",
                            str(mi["base"]),
                            str(mi["key"]),
                            str(mi["model"]),
                            mult,
                        )
                    )
            # L0 免费通道：硅基免费失败后切 MiMo 独立付费 key（单独记账）
            if layer == "L0" and _mimo_failover_enabled():
                mi = _mimo_free_upstream()
                if mi:
                    targets.append(
                        (
                            layer,
                            "mimo",
                            str(mi["base"]),
                            str(mi["key"]),
                            str(mi["model"]),
                            mult,
                        )
                    )
            # L2/L3 QR 备用 target（04 实测 2026-08-13：同款 200 稳定且降本）
            if layer in ("L2", "L3") and _upstream_mode() == "openrouter":
                qr = _layer_qr_upstream(layer)
                if qr:
                    targets.append(
                        (
                            layer,
                            "quickrouter",
                            str(qr["base"]),
                            str(qr["key"]),
                            str(qr["model"]),
                            mult,
                        )
                    )

    if not targets:
        stub = _stub_response(prompt, layer="L0", model="stub")
        yield {
            "type": "meta",
            "layer": "L0",
            "provider": "stub",
            "raw_model": "stub",
            "billing_mult": 1,
            "public_model": public,
        }
        yield {"type": "delta", "text": stub["text"]}
        yield {
            "type": "done",
            "text": stub["text"],
            "tokens": int(stub["tokens"]),
            "raw_model": "stub",
            "provider": "stub",
            "layer": "L0",
            "billing_mult": 1,
            "public_model": public,
        }
        return

    last_err = ""
    for layer, provider, base, key, model, mult in targets:
        got_done = False
        for ev in _try_upstream_stream(
            base=base,
            key=key,
            model=model,
            prompt=prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            provider=provider,
            layer=layer,
            billing_mult=mult,
            public_model=public,
            messages=messages,
            tools=use_tools,
            tool_choice=use_choice,
        ):
            if ev.get("type") == "done":
                got_done = True
            elif ev.get("type") == "error" and ev.get("error_kind") == "format":
                # 400=格式错误：直接上报，不再切下一上游
                yield {"type": "error", "error": str(ev.get("error") or "upstream_400")}
                return
            yield ev
        if got_done:
            return
        last_err = f"{provider}/{model} failed"
    yield {"type": "error", "error": last_err or "all_upstreams_failed"}


def _run_vip_pick_chat_stream(
    *,
    pick: dict[str, Any],
    prompt: str,
    temperature: float,
    max_tokens: int,
    messages: Optional[list[dict[str, Any]]] = None,
    tools: Optional[list[dict[str, Any]]] = None,
    tool_choice: Any = None,
) -> Iterator[dict[str, Any]]:
    billing_mult = max(1, int(pick.get("billing_mult") or 1))
    in_mult = max(1, int(pick.get("in_mult") or pick.get("billing_mult") or 1))
    out_mult = max(1, int(pick.get("out_mult") or pick.get("billing_mult") or 1))
    # 2026-08-15 峰谷：DeepSeek 点名流式同样按当前时段倍率
    _pm = _peak_mults(pick)
    if _pm:
        in_mult, out_mult = _pm
    public_id = str(pick.get("id") or "vip_pick")
    or_id = (pick.get("openrouter_id") or "").strip()
    direct_id = (pick.get("direct_id") or "").strip()
    sf_id = (pick.get("siliconflow_id") or "").strip()
    is_ds_pick = public_id.startswith("vip-ds-")
    is_intl = (
        public_id.startswith("vip-gpt")
        or "claude" in public_id
        or "gemini" in public_id
        or "grok" in public_id
        or "llama" in public_id
    )
    targets: list[tuple[str, str, str, str]] = []  # provider, base, key, model

    # 2026-08-03：中国模 硅基.com 优先(价低+国际端点) → OR兜底；国际模 OR 优先
    if is_ds_pick and direct_id and _ds_failover_enabled():
        ds = _deepseek_official_upstream()
        if ds.get("key") and ds.get("base"):
            targets.append(("deepseek", str(ds["base"]), str(ds["key"]), direct_id))
    # B) 中国模：硅基 .com 优先（原厂价+国际CDN）
    if (not is_intl) and (not is_ds_pick) and sf_id and _vip_silicon_first_enabled():
        sf = _silicon_vip_upstream(sf_id)
        if sf:
            targets.append(("siliconflow", sf["base"], sf["key"], sf["model"]))
    # C+D) aggregator chain: 按仓库 channels 顺序（2026-08-12 修复：
    # 原硬编码「OR 优先 + break」忽略 channels（luna 应为 tokenlab 链首），
    # 导致 Codex 流式恒打 OpenRouter，TokenLab 主通道形同虚设）
    _chain = _vip_aggregator_chain(pick, or_id)
    for cand in _chain:
        targets.append((str(cand["provider"]), str(cand["base"]), str(cand["key"]), str(cand["model"])))
        # F) DS 点名：硅基同族插在 OR 之后、其余聚合商之前
        if is_ds_pick and sf_id and str(cand["provider"]) == "openrouter":
            sf = _silicon_vip_upstream(sf_id)
            if sf:
                targets.append(("siliconflow", sf["base"], sf["key"], sf["model"]))
    # C2) MiMo 点名：聚合链失败后官方直连兜底（2026-08-15）
    if "mimo" in or_id.lower() and _mimo_failover_enabled():
        mi = _layer_mimo_upstream("L2")
        if mi:
            targets.append(("mimo", str(mi["base"]), str(mi["key"]), str(mi["model"])))
    # F2) DS 点名且聚合链无 OR 时，硅基同族兜底
    if is_ds_pick and sf_id and not any(t[0] == "siliconflow" for t in targets):
        sf = _silicon_vip_upstream(sf_id)
        if sf:
            targets.append(("siliconflow", sf["base"], sf["key"], sf["model"]))
    last_err = ""
    first_detail = ""
    for provider, base, key, model in targets:
        got_done = False
        for ev in _try_upstream_stream(
            base=base,
            key=key,
            model=model,
            prompt=prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            provider=provider,
            layer="VIP",
            billing_mult=billing_mult,
            public_model=public_id,
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
            billing_in=in_mult,
            billing_out=out_mult,
        ):
            if ev.get("type") == "done":
                got_done = True
            elif ev.get("type") == "error" and ev.get("error_kind") == "format":
                # 400=格式错误：直接上报，不再切下一上游（主脑 2026-08-12 语义修正）
                yield {"type": "error", "error": str(ev.get("error") or "upstream_400")}
                return
            elif ev.get("type") == "error" and not first_detail:
                # 保留上游错误细节（含 4xx body）供 error_message 透出定位
                first_detail = str(ev.get("error") or "")[:500]
            yield ev
        if got_done:
            return
        last_err = f"{provider} failed"
    yield {"type": "error", "error": first_detail or last_err or "vip_upstream_failed"}
