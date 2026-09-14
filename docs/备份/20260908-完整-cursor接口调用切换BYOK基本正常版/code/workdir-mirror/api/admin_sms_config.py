"""
管理后台短信多通道配置（热生效，无需重启 core）。

覆盖文件：api/data/admin_sms_config.json（gitignore，不入库）
优先级：管理台覆盖 > api/.env（settings 默认）

通道：
- 106 网关：endpoint / account / password / sign_name / template
- 腾讯短信：secret_id / secret_key / sdk_app_id / sign / template_id / region
- 聚合数据：key / template_id / sign / template（客户端仅用 key + template_id）

总开关（国内短信）仍走 system_flags.sms_106_enabled（热生效）。
密文只进覆盖文件，admin 快照一律脱敏，不回显明文。
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

_OVERRIDE_PATH = Path(__file__).resolve().parent / "data" / "admin_sms_config.json"


def get_override() -> dict[str, Any]:
    try:
        if not _OVERRIDE_PATH.is_file():
            return {}
        raw = json.loads(_OVERRIDE_PATH.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return {}
        return raw
    except Exception:
        return {}


def save_override(cfg: dict[str, Any]) -> None:
    _OVERRIDE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(cfg)
    payload["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    _OVERRIDE_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def active_provider() -> str:
    ov = get_override()
    p = str(ov.get("active_provider") or "").strip().lower()
    return p if p in ("tencent", "juhe") else "106"


def effective_106() -> dict[str, str]:
    from config import settings

    ov = get_override().get("sms_106") or {}
    return {
        "endpoint": str(ov.get("endpoint") or settings.sms_106_endpoint or "").strip(),
        "account": str(ov.get("account") or settings.sms_106_account or "").strip(),
        "password": str(ov.get("password") or settings.sms_106_password or "").strip(),
        "sign_name": str(ov.get("sign_name") or settings.sms_106_sign_name or "").strip(),
        "template": str(ov.get("template") or settings.sms_106_template or "").strip(),
    }


def effective_tencent() -> dict[str, str]:
    ov = get_override().get("sms_tencent") or {}
    return {
        "secret_id": str(ov.get("secret_id") or "").strip(),
        "secret_key": str(ov.get("secret_key") or "").strip(),
        "sdk_app_id": str(ov.get("sdk_app_id") or "").strip(),
        "sign": str(ov.get("sign") or "").strip(),
        "template_id": str(ov.get("template_id") or "").strip(),
        "region": str(ov.get("region") or "ap-guangzhou").strip(),
    }


def effective_juhe() -> dict[str, str]:
    ov = get_override().get("sms_juhe") or {}
    return {
        "key": str(ov.get("key") or "").strip(),
        "template_id": str(ov.get("template_id") or "").strip(),
        "sign": str(ov.get("sign") or "").strip(),
        "template": str(ov.get("template") or "").strip(),
    }


def _mask_secret(v: str, keep_tail: int = 4) -> str:
    s = str(v or "").strip()
    if not s:
        return ""
    if len(s) <= keep_tail:
        return "*" * len(s)
    return ("*" * max(6, len(s) - keep_tail)) + s[-keep_tail:]


def _mask_account(v: str) -> str:
    s = str(v or "").strip()
    if not s:
        return ""
    if len(s) <= 3:
        return "*" * len(s)
    return s[:1] + "*" * max(3, len(s) - 2) + s[-1:]


def admin_snapshot() -> dict[str, Any]:
    """管理端读取当前生效配置（脱敏），并带各通道就绪状态。"""
    from config import settings
    from system_flags import effective_sms_106_enabled
    from sms_failover import SMS_CIRCUIT, channel_order

    c106 = effective_106()
    tc = effective_tencent()
    jh = effective_juhe()
    ap = active_provider()
    return {
        "ok": True,
        "active_provider": ap,
        "active_provider_label": {"106": "106网关", "tencent": "腾讯短信", "juhe": "聚合数据"}.get(ap, "106网关"),
        "failover": {
            "order": channel_order(ap),
            "circuit": SMS_CIRCUIT.status(),
        },
        "sms_106_enabled": bool(effective_sms_106_enabled()),
        "internal_key_required": bool((settings.sms_internal_key or "").strip()),
        "internal_key_set": bool((settings.sms_internal_key or "").strip()),
        "sms_106": {
            "endpoint": c106["endpoint"],
            "account_masked": _mask_account(c106["account"]),
            "account_set": bool(c106["account"]),
            "password_set": bool(c106["password"]),
            "password_masked": _mask_secret(c106["password"], keep_tail=4),
            "sign_name": c106["sign_name"],
            "template": c106["template"],
        },
        "sms_tencent": {
            "secret_id_masked": _mask_secret(tc["secret_id"], keep_tail=4),
            "secret_id_set": bool(tc["secret_id"]),
            "secret_key_set": bool(tc["secret_key"]),
            "secret_key_masked": _mask_secret(tc["secret_key"], keep_tail=4),
            "sdk_app_id": tc["sdk_app_id"],
            "sign": tc["sign"],
            "template_id": tc["template_id"],
            "region": tc["region"],
        },
        "sms_juhe": {
            "key_masked": _mask_secret(jh["key"], keep_tail=4),
            "key_set": bool(jh["key"]),
            "template_id": jh["template_id"],
            "sign": jh["sign"],
            "template": jh["template"],
        },
        "admin_sms_otp": {
            "enabled": bool(getattr(settings, "admin_require_sms", False)),
            "phone_set": bool((settings.admin_phone or "").strip()),
        },
        "intl_sms": False,
        "intl_note": "国际用户请用邮箱验证码；国际短信本轮不接入。",
    }


def apply_update(body: dict[str, Any]) -> dict[str, Any]:
    """合并管理台提交（空字符串 = 保持原值/不覆盖），写覆盖文件，返回新快照。"""
    cur = get_override()
    if not isinstance(cur, dict):
        cur = {}

    def _merge_channel(key: str, field_map: dict[str, str]) -> None:
        ch = dict(cur.get(key) or {})
        changed = False
        for dst, src in field_map.items():
            v = body.get(src)
            if v is None:
                continue
            s = str(v).strip()
            if s:
                ch[dst] = s
                changed = True
        if changed:
            cur[key] = ch

    # 生效通道
    ap = str(body.get("active_provider") or "").strip().lower()
    if ap in ("106", "tencent", "juhe"):
        cur["active_provider"] = ap

    # 106：password 留空 = 保持原值（不回显）
    c106_fields = {
        "endpoint": "sms_106_endpoint",
        "account": "sms_106_account",
        "sign_name": "sms_106_sign_name",
        "template": "sms_106_template",
    }
    _merge_channel("sms_106", c106_fields)
    p106 = str(body.get("sms_106_password") or "").strip()
    if p106:
        ch106 = dict(cur.get("sms_106") or {})
        ch106["password"] = p106
        cur["sms_106"] = ch106

    # 腾讯：secret_key 留空 = 保持原值
    tc_fields = {
        "secret_id": "sms_tencent_secret_id",
        "sdk_app_id": "sms_tencent_sdk_app_id",
        "sign": "sms_tencent_sign",
        "template_id": "sms_tencent_template_id",
        "region": "sms_tencent_region",
    }
    _merge_channel("sms_tencent", tc_fields)
    p_tc = str(body.get("sms_tencent_secret_key") or "").strip()
    if p_tc:
        ch_tc = dict(cur.get("sms_tencent") or {})
        ch_tc["secret_key"] = p_tc
        cur["sms_tencent"] = ch_tc

    # 聚合：key 留空 = 保持原值
    jh_fields = {
        "template_id": "sms_juhe_tpl_id",
        "sign": "sms_juhe_sign",
        "template": "sms_juhe_template",
    }
    _merge_channel("sms_juhe", jh_fields)
    p_jh = str(body.get("sms_juhe_key") or "").strip()
    if p_jh:
        ch_jh = dict(cur.get("sms_juhe") or {})
        ch_jh["key"] = p_jh
        cur["sms_juhe"] = ch_jh

    save_override(cur)
    return admin_snapshot()
