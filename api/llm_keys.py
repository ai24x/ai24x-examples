"""
上游 LLM Key 解析：主收银 vs 免费通道；可选管理台覆盖（不含进 git）。

优先级：api/data/llm_keys_override.json > env / .env（dotenv）
"""
from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

_API_ROOT = Path(__file__).resolve().parent
_OVERRIDE_PATH = _API_ROOT / "data" / "llm_keys_override.json"
_ENV_PATH = _API_ROOT / ".env"

try:
    from dotenv import load_dotenv

    # 保证 FREE Key 等未进 Settings 的项也能被读到（NSSM/uvicorn 未必预载 dotenv）
    load_dotenv(_ENV_PATH, override=False)
except Exception:
    pass

# 允许管理台临时改的键（不含随意扩面）
_ALLOWED = (
    "OPENROUTER_API_KEY",
    "OPENROUTER_API_KEY_FREE",
    "SILICONFLOW_API_KEY",
    "SILICONFLOW_API_KEY_FREE",
    "TOGETHER_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GOOGLE_AI_API_KEY",
)

# VIP 降级事件（内存环，供告警；进程重启清空）
_VIP_DEGRADE: list[dict[str, Any]] = []
_VIP_DEGRADE_MAX = 40


def _raw_env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def _load_ov() -> dict[str, str]:
    try:
        if not _OVERRIDE_PATH.is_file():
            return {}
        raw = json.loads(_OVERRIDE_PATH.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return {}
        keys = raw.get("keys") if "keys" in raw else raw
        if not isinstance(keys, dict):
            return {}
        out: dict[str, str] = {}
        for k, v in keys.items():
            kk = str(k).strip()
            if kk in _ALLOWED and str(v or "").strip():
                out[kk] = str(v).strip()
        return out
    except Exception:
        return {}


def _save_ov(keys: dict[str, str]) -> None:
    _OVERRIDE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {"keys": keys, "updated_note": "admin_ui"}
    _OVERRIDE_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def get_key(name: str, default: str = "") -> str:
    """读取单一密钥：覆盖 > os.environ / .env > Settings 字段。"""
    ov = _load_ov()
    if name in ov and ov[name]:
        return ov[name]
    v = _raw_env(name, "")
    if v:
        return v
    try:
        from config import settings

        alias = {
            "OPENROUTER_API_KEY": "openrouter_api_key",
            "OPENROUTER_API_KEY_FREE": "openrouter_api_key_free",
            "SILICONFLOW_API_KEY": "siliconflow_api_key",
            "SILICONFLOW_API_KEY_FREE": "siliconflow_api_key_free",
            "TOGETHER_API_KEY": "together_api_key",
            "OPENAI_API_KEY": "openai_api_key",
            "ANTHROPIC_API_KEY": "anthropic_api_key",
            "GOOGLE_AI_API_KEY": "google_ai_api_key",
            "TOKEN_LLM_KEY": "openrouter_api_key",
            "TOKEN_LLM_L0_KEY": "siliconflow_api_key",
        }
        attr = alias.get(name)
        if attr:
            sv = str(getattr(settings, attr, "") or "").strip()
            if sv:
                return sv
    except Exception:
        pass
    return (default or "").strip()


def openrouter_main_key() -> str:
    return get_key("OPENROUTER_API_KEY") or get_key("TOKEN_LLM_KEY")


def openrouter_free_key() -> str:
    """免费共享 / 试验；未配则回落主 Key（并应尽快切开）。"""
    return get_key("OPENROUTER_API_KEY_FREE") or openrouter_main_key()


def silicon_main_key() -> str:
    return get_key("SILICONFLOW_API_KEY") or get_key("TOKEN_LLM_L0_KEY")


def silicon_free_key() -> str:
    """L0 / 免费共享优先；未配回落主 Key。"""
    return get_key("SILICONFLOW_API_KEY_FREE") or silicon_main_key()


def silicon_degrade_key() -> str:
    """VIP/主档降级：优先主硅基，否则免费硅基。"""
    return silicon_main_key() or silicon_free_key()


def mask(secret: str) -> str:
    s = (secret or "").strip()
    if not s:
        return ""
    if len(s) <= 10:
        return s[:2] + "***"
    return s[:6] + "…" + s[-4:]


def list_keys_admin() -> dict[str, Any]:
    ov = _load_ov()

    def row(env_name: str, value: str, *, role: str) -> dict[str, Any]:
        return {
            "name": env_name,
            "role": role,
            "set": bool(value),
            "masked": mask(value) if value else "",
            "source": "admin" if env_name in ov else ("env" if value else "unset"),
        }

    return {
        "ok": True,
        "editable": True,
        "keys": [
            row("OPENROUTER_API_KEY", openrouter_main_key(), role="main"),
            row("OPENROUTER_API_KEY_FREE", get_key("OPENROUTER_API_KEY_FREE"), role="free"),
            row("SILICONFLOW_API_KEY", silicon_main_key(), role="main"),
            row("SILICONFLOW_API_KEY_FREE", get_key("SILICONFLOW_API_KEY_FREE"), role="free"),
            row("TOGETHER_API_KEY", get_key("TOGETHER_API_KEY"), role="backup"),
            row("OPENAI_API_KEY", get_key("OPENAI_API_KEY"), role="direct"),
            row("ANTHROPIC_API_KEY", get_key("ANTHROPIC_API_KEY"), role="direct"),
            row("GOOGLE_AI_API_KEY", get_key("GOOGLE_AI_API_KEY"), role="direct"),
        ],
        "ops_note": (
            "此处展示当前进程已加载的密钥（掩码）。"
            "改 .env 后须重启 API 才会出现在「来源 env」；"
            "也可在下方粘贴后点保存，写入覆盖文件立即生效（优先于 .env）。"
            "免费通道请用 *_FREE，勿与主收银混用。"
            "Together=开源模备用；OpenAI/Anthropic/Google=国际旗舰直连备用（填 Key 即启用骨架）。"
        ),
        "vip_degrade_recent": list(_VIP_DEGRADE[-10:]),
    }


def update_keys_admin(patch: dict[str, Any]) -> dict[str, Any]:
    cur = _load_ov()
    if not isinstance(patch, dict):
        patch = {}
    for name in _ALLOWED:
        if name not in patch:
            continue
        val = patch.get(name)
        if val is None:
            continue
        s = str(val).strip()
        if s in ("", "-", "clear", "__clear__"):
            cur.pop(name, None)
        else:
            # 拒绝把对话里常见省略号写进密钥
            if "…" in s or "\u2026" in s:
                raise ValueError("invalid_key_ellipsis")
            cur[name] = s
    clear = patch.get("clear") or []
    if isinstance(clear, str):
        clear = [clear]
    for k in clear:
        kk = str(k).strip()
        if kk in cur:
            del cur[kk]
    _save_ov(cur)
    return list_keys_admin()


def note_vip_degrade(
    *,
    public_id: str,
    to_provider: str,
    to_model: str,
    reason: str = "",
) -> None:
    evt = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "public_id": public_id,
        "to_provider": to_provider,
        "to_model": to_model,
        "reason": (reason or "")[:160],
    }
    _VIP_DEGRADE.append(evt)
    if len(_VIP_DEGRADE) > _VIP_DEGRADE_MAX:
        del _VIP_DEGRADE[: len(_VIP_DEGRADE) - _VIP_DEGRADE_MAX]
    logger.warning(
        "vip_degrade id=%s -> %s/%s reason=%s",
        public_id,
        to_provider,
        to_model,
        reason,
    )


def recent_vip_degrades(limit: int = 20) -> list[dict[str, Any]]:
    return list(_VIP_DEGRADE[-max(1, min(40, int(limit or 20))) :])
