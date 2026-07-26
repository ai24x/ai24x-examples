"""
L0–L3 模型路由（MVP）。

未配置 upstream Key 时走本地 stub（仍返回 layer/model，便于联调）。
配置 OpenAI 兼容端点后走真实调用，单层超时默认 5s，失败则 fallback 下一档。
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
    # 品牌档（对外；底层映射见 resolve）
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
    # 兼容旧默认
    "gpt-3.5-turbo": "L1",
}

# FREE：DeepSeek 主打（平台月赠额度限额）；失败再落 L0 硅基流动兜底
# VIP：DeepSeek 主力 → reasoner → 扩展
CHAIN_FREE = ["L1", "L0"]
CHAIN_VIP = ["L1", "L2", "L3"]

LAYER_DEFAULT_MODEL = {
    "L0": "siliconflow-free",
    # DeepSeek 新账号仅支持 v4：flash=主打，pro=增强
    "L1": "deepseek-chat",
    "L2": "deepseek-pro",
    "L3": "kimi-k3",
}

# 逻辑名 → upstream 实际 model id（DeepSeek 平台现要求 v4 系列）
LOGICAL_TO_UPSTREAM_MODEL = {
    # L0 硅基流动免费额度常用模型（可改 SILICONFLOW_MODEL）
    "glm-4-flash": "THUDM/glm-4-9b-chat",
    "siliconflow-free": "Qwen/Qwen2.5-7B-Instruct",
    # L1 DeepSeek Flash
    "flash": "deepseek-v4-flash",
    "deepseek-flash": "deepseek-v4-flash",
    "deepseek-chat": "deepseek-v4-flash",
    "deepseek-v4-flash": "deepseek-v4-flash",
    # L2 DeepSeek Pro
    "pro": "deepseek-v4-pro",
    "deepseek-pro": "deepseek-v4-pro",
    "deepseek-reasoner": "deepseek-v4-pro",
    "deepseek-v4-pro": "deepseek-v4-pro",
    # L3 品牌占位
    "ultra": "kimi-k3",
    "gpt-3.5-turbo": "deepseek-v4-flash",
    "auto": "deepseek-v4-flash",
    "free": "deepseek-v4-flash",
}

# 计费倍率（相对 completion token 估算）
LAYER_COST_MULT = {"L0": 1, "L1": 1, "L2": 5, "L3": 8}


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
    l0 = _layer_upstream("L0")
    l1 = _layer_upstream("L1")
    return {
        "layers": {
            "L0": {
                "title": "兜底层（硅基流动等，DeepSeek 不可用时）",
                "models": ["siliconflow-free", "glm-4-flash"],
                "free": True,
                "ready": bool(l0.get("key")),
                "provider": l0.get("provider"),
            },
            "L1": {
                "title": "主打层（DeepSeek Flash/Chat，免费用户靠平台额度限额）",
                "models": ["flash", "deepseek-flash", "deepseek-chat", "auto"],
                "free": True,
                "ready": bool(l1.get("key")),
                "provider": l1.get("provider"),
            },
            "L2": {
                "title": "VIP 增强层",
                "models": ["pro", "deepseek-pro", "deepseek-reasoner"],
                "vip_only": True,
            },
            "L3": {
                "title": "扩展层",
                "models": ["ultra", "kimi-k3", "minimax", "qwen-plus", "doubao-pro"],
                "vip_only": True,
            },
        },
        "brand": {
            "free": "auto（FREE 链 L1→L0）",
            "flash": "L1 DeepSeek",
            "pro": "L2（VIP）",
            "ultra": "L3（VIP）",
        },
        "default": "auto",
        "chain": CHAIN_VIP if is_vip else CHAIN_FREE,
        "upstream": {
            "l0_ready": bool(l0.get("key")),
            "l1_deepseek_ready": bool(l1.get("key")),
            "deepseek_ready": bool(l1.get("key")),
            "mode": "live" if (l0.get("key") or l1.get("key")) else "stub",
            "l0_base": l0.get("base") or None,
            "l1_base": l1.get("base") or None,
        },
        "note": "免费用户默认 DeepSeek（平台月赠额度限额）；DeepSeek 故障时 fallback 硅基流动。VIP 走 L1→L2→L3。",
    }


def _env(name: str, default: str = "") -> str:
    v = (os.getenv(name) or "").strip()
    if v:
        return v
    # pydantic Settings 已读 .env，但不会自动写入 os.environ；这里回退
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
        }
        attr = alias_map.get(name)
        if attr and hasattr(_s, attr):
            return str(getattr(_s, attr) or "").strip() or default
    except Exception:
        pass
    return default


def _normalize_openai_base(base: str) -> str:
    base = (base or "").rstrip("/")
    if base in ("https://api.deepseek.com", "http://api.deepseek.com"):
        return base + "/v1"
    if base.endswith("api.deepseek.com"):
        return base + "/v1"
    if base in ("https://api.siliconflow.cn", "http://api.siliconflow.cn"):
        return base + "/v1"
    return base


def _layer_upstream(layer: str) -> dict[str, str]:
    """
    分层独立 upstream，避免 L0 误用 DeepSeek Key。
    L0 → 硅基流动（免费额度测试）
    L1 → DeepSeek
    """
    layer = (layer or "").upper()
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
    return LOGICAL_TO_UPSTREAM_MODEL.get(logical, layer_default or logical)


def resolve_chain(*, requested_model: Optional[str], is_vip: bool) -> list[tuple[str, str]]:
    """
    返回 [(layer, logical_model), ...] 尝试序列。
    """
    req = (requested_model or "auto").strip().lower() or "auto"
    if req in ("auto", "free"):
        layers = CHAIN_VIP if is_vip else CHAIN_FREE
        return [(ly, LAYER_DEFAULT_MODEL[ly]) for ly in layers]

    layer = MODEL_LAYER.get(req, "L1")
    if layer == "auto":
        layers = CHAIN_VIP if is_vip else CHAIN_FREE
        return [(ly, LAYER_DEFAULT_MODEL[ly]) for ly in layers]

    # 品牌档映射到默认逻辑模型
    brand_logical = {"flash": "deepseek-chat", "pro": "deepseek-pro", "ultra": "kimi-k3"}
    logical = brand_logical.get(req, req)

    # VIP 限定层：FREE 用户降到 L1→L0，禁止静默按 VIP 价升档
    if layer in ("L2", "L3") and not is_vip:
        return [("L1", LAYER_DEFAULT_MODEL["L1"]), ("L0", LAYER_DEFAULT_MODEL["L0"])]

    chain_layers = CHAIN_VIP if is_vip else CHAIN_FREE
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


def _call_openai_compatible(
    *,
    base: str,
    key: str,
    model: str,
    prompt: str,
    temperature: float,
    max_tokens: int,
    timeout_s: float,
) -> dict[str, Any]:
    url = f"{base}/chat/completions"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    body: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    # DeepSeek v4 默认会写 reasoning_content，易把 max_tokens 吃光导致 content 为空
    # 默认关闭 thinking；需要推理时设 DEEPSEEK_THINKING=1
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


def run_routed_chat(
    *,
    prompt: str,
    requested_model: Optional[str],
    is_vip: bool,
    temperature: float = 0.7,
    max_tokens: int = 1000,
) -> RouteResult:
    attempts: list[dict[str, Any]] = []
    chain = resolve_chain(requested_model=requested_model, is_vip=is_vip)
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
                )
                provider = str(up.get("provider") or "openai_compatible")
                if "deepseek.com" in up["base"]:
                    provider = "deepseek"
                elif "siliconflow" in up["base"]:
                    provider = "siliconflow"
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
            logger.warning("model route fail layer=%s model=%s err=%s", layer, logical_model, e)
            attempts.append(
                {
                    "layer": layer,
                    "model": logical_model,
                    "ok": False,
                    "ms": int(elapsed * 1000),
                    "error": str(e)[:200],
                }
            )
            continue

    # 所有 live 失败时：测试环境回落 stub，避免无效 DeepSeek Key 把整条链打死
    layer0, logical0 = chain[0] if chain else ("L0", "siliconflow-free")
    stub = _stub_response(prompt, layer=layer0, model=logical0)
    attempts.append({"layer": layer0, "model": logical0, "provider": "stub", "ok": True, "fallback": "all_live_failed"})
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
