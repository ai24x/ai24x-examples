"""
系统运行时开关（管理台可改，立即生效；不含密钥）。

优先级：api/data/system_flags_override.json > env / settings 默认

可改：支付总开关、模拟支付、国内短信开关、上游模式（direct|openrouter）
不可改：SMTP/短信账号密码、各厂 API Key、内部密钥（仍须行级改 .env）
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

_OVERRIDE_PATH = Path(__file__).resolve().parent / "data" / "system_flags_override.json"

_ALLOWED_BOOL = ("token_pay_enabled", "token_pay_mock_enabled", "sms_106_enabled")
_ALLOWED_STR = ("token_llm_upstream",)
_LLM_MODES = ("direct", "openrouter")


def _load() -> dict[str, Any]:
    try:
        if not _OVERRIDE_PATH.is_file():
            return {}
        raw = json.loads(_OVERRIDE_PATH.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return {}
        flags = raw.get("flags") if "flags" in raw else raw
        return dict(flags) if isinstance(flags, dict) else {}
    except Exception:
        return {}


def _save(flags: dict[str, Any]) -> None:
    _OVERRIDE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {"flags": flags, "updated_note": "admin_ui"}
    _OVERRIDE_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def get_override(key: str) -> Any:
    flags = _load()
    return flags[key] if key in flags else None


def flag_bool(key: str, default: bool) -> bool:
    v = get_override(key)
    if v is None:
        return bool(default)
    return bool(v)


def flag_str(key: str, default: str = "") -> Optional[str]:
    """有覆盖则返回覆盖值；无覆盖返回 None（调用方继续走默认逻辑）。"""
    v = get_override(key)
    if v is None:
        return None
    s = str(v).strip().lower()
    return s if s else None


def effective_token_pay_enabled() -> bool:
    from config import settings

    return flag_bool("token_pay_enabled", bool(settings.token_pay_enabled))


def effective_token_pay_mock_flag() -> bool:
    """仅返回 MOCK 配置位（不含 local 环境自动放开）。"""
    from config import settings

    return flag_bool("token_pay_mock_enabled", bool(settings.token_pay_mock_enabled))


def effective_sms_106_enabled() -> bool:
    from config import settings

    return flag_bool("sms_106_enabled", bool(settings.sms_106_enabled))


def effective_llm_upstream_override() -> Optional[str]:
    """返回 direct|openrouter；无覆盖则 None。"""
    raw = flag_str("token_llm_upstream")
    if not raw:
        return None
    if raw in ("openrouter", "aggregator", "or"):
        return "openrouter"
    if raw in ("direct", "official", "legacy"):
        return "direct"
    return None


def list_system_flags() -> dict[str, Any]:
    """管理台展示：当前生效值 + 是否有管理台覆盖。"""
    from config import settings
    from email_smtp import smtp_configured
    from model_router import _upstream_mode
    from token_pay_service import token_pay_enabled, token_pay_mock_allowed

    ov = _load()
    pay_on = token_pay_enabled()
    mock_on = token_pay_mock_allowed()
    sms_on = effective_sms_106_enabled()
    mode = _upstream_mode()

    def _src(key: str) -> str:
        return "admin" if key in ov else "env"

    return {
        "ok": True,
        "editable": True,
        "pay": {
            "enabled": pay_on,
            "mock_allowed": mock_on,
            "mock_flag": effective_token_pay_mock_flag(),
            "enabled_editable": True,
            "mock_editable": True,
            "enabled_source": _src("token_pay_enabled"),
            "mock_source": _src("token_pay_mock_enabled"),
            "paypal_mode": str(getattr(settings, "paypal_mode", "sandbox") or "sandbox"),
        },
        "llm": {
            "upstream_mode": mode,
            "upstream_editable": True,
            "upstream_source": _src("token_llm_upstream"),
            "options": list(_LLM_MODES),
        },
        "sms": {
            "enabled": sms_on,
            "enabled_editable": True,
            "enabled_source": _src("sms_106_enabled"),
            "internal_key_set": bool((settings.sms_internal_key or "").strip()),
            "account_set": bool((settings.sms_106_account or "").strip()),
            "intl_sms": False,
        },
        "email": {
            "smtp_configured": bool(smtp_configured()),
            "editable": False,
        },
        "readonly_note": "邮件账号、短信密钥、各厂 API Key 不可在网页修改。",
        "ops_note": (
            "开关可在本页修改并保存，立即对前台生效（写入覆盖文件，优先于 .env）。"
            "密钥类仍须服务器行级改配置后重启。"
            "国际用户用邮箱验证；国际短信暂不接入。"
        ),
        "overrides": {k: ov[k] for k in ov if k in _ALLOWED_BOOL or k in _ALLOWED_STR},
    }


def update_system_flags(patch: dict[str, Any]) -> dict[str, Any]:
    cur = _load()
    if not isinstance(patch, dict):
        patch = {}

    if "token_pay_enabled" in patch and patch["token_pay_enabled"] is not None:
        cur["token_pay_enabled"] = bool(patch["token_pay_enabled"])
    if "token_pay_mock_enabled" in patch and patch["token_pay_mock_enabled"] is not None:
        cur["token_pay_mock_enabled"] = bool(patch["token_pay_mock_enabled"])
    if "sms_106_enabled" in patch and patch["sms_106_enabled"] is not None:
        cur["sms_106_enabled"] = bool(patch["sms_106_enabled"])
    if "token_llm_upstream" in patch and patch["token_llm_upstream"] is not None:
        mode = str(patch["token_llm_upstream"]).strip().lower()
        if mode in ("or", "aggregator"):
            mode = "openrouter"
        if mode in ("official", "legacy"):
            mode = "direct"
        if mode not in _LLM_MODES:
            raise ValueError(f"invalid_token_llm_upstream:{mode}")
        cur["token_llm_upstream"] = mode

    # 可选：清除某键覆盖，回退 env
    clear = patch.get("clear") or []
    if isinstance(clear, str):
        clear = [clear]
    for k in clear:
        kk = str(k).strip()
        if kk in cur:
            del cur[kk]

    _save(cur)
    return list_system_flags()
