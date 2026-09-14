"""
管理后台邮件服务配置（主 SMTP + 备用 SMTP 自动切换，热生效）。

覆盖文件：api/data/admin_email_config.json（gitignore，不入库）
优先级：管理台覆盖 > api/.env（settings 默认）

主通道失败自动切备用通道；模板支持 {code} / {purpose} 变量。
密文只进覆盖文件，admin 快照一律脱敏，不回显明文。
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional

_OVERRIDE_PATH = Path(__file__).resolve().parent / "data" / "admin_email_config.json"


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


def effective_channel(name: str) -> Optional[dict[str, Any]]:
    """返回某通道生效配置 dict 或 None（未配置）。name: smtp | smtp_backup"""
    from config import settings

    if name == "smtp":
        ov = get_override().get("smtp") or {}
        host = str(ov.get("host") or settings.smtp_host or "").strip()
        port = int(ov.get("port") if ov.get("port") is not None else settings.smtp_port or 587)
        user = str(ov.get("user") or settings.smtp_user or "").strip()
        password = str(ov.get("password") or settings.smtp_password or "").strip()
        from_addr = str(ov.get("from") or settings.smtp_from or user).strip()
        use_tls = bool(ov.get("use_tls") if ov.get("use_tls") is not None else settings.smtp_use_tls)
        use_ssl = bool(ov.get("use_ssl") if ov.get("use_ssl") is not None else settings.smtp_use_ssl)
    elif name == "smtp_backup":
        ov = get_override().get("smtp_backup") or {}
        host = str(ov.get("host") or settings.smtp_backup_host or "").strip()
        port = int(ov.get("port") if ov.get("port") is not None else settings.smtp_backup_port or 587)
        user = str(ov.get("user") or settings.smtp_backup_user or "").strip()
        password = str(ov.get("password") or settings.smtp_backup_password or "").strip()
        from_addr = str(ov.get("from") or settings.smtp_backup_from or user).strip()
        use_tls = bool(ov.get("use_tls") if ov.get("use_tls") is not None else settings.smtp_backup_use_tls)
        use_ssl = bool(ov.get("use_ssl") if ov.get("use_ssl") is not None else settings.smtp_backup_use_ssl)
    else:
        return None

    if not (host and user and password and from_addr):
        return None
    return {
        "host": host,
        "port": int(port or 587),
        "user": user,
        "password": password,
        "from": from_addr,
        "use_tls": use_tls,
        "use_ssl": use_ssl,
    }


def effective_subject() -> str:
    from config import settings

    return str(get_override().get("email_otp_subject") or settings.email_otp_subject or "").strip()


def effective_body_template() -> str:
    from config import settings

    return str(
        get_override().get("email_otp_body_template") or settings.email_otp_body_template or ""
    ).strip()


def _mask_secret(v: str, keep_tail: int = 4) -> str:
    s = str(v or "").strip()
    if not s:
        return ""
    if len(s) <= keep_tail:
        return "*" * len(s)
    return ("*" * max(6, len(s) - keep_tail)) + s[-keep_tail:]


def _mask_user(v: str) -> str:
    s = str(v or "").strip()
    if not s:
        return ""
    if "@" in s:
        name, _, domain = s.partition("@")
        if len(name) <= 1:
            return name + "*@" + domain
        return name[0] + "*" * max(3, len(name) - 1) + "@" + domain
    if len(s) <= 3:
        return "*" * len(s)
    return s[:1] + "*" * max(3, len(s) - 2) + s[-1:]


def _channel_snapshot(name: str) -> dict[str, Any]:
    cfg = effective_channel(name)
    if not cfg:
        return {
            "configured": False,
            "host": "",
            "user_masked": "",
            "user_set": False,
            "password_set": False,
            "password_masked": "",
            "from": "",
            "port": 587,
            "use_tls": True,
            "use_ssl": False,
        }
    return {
        "configured": True,
        "host": cfg["host"],
        "user_masked": _mask_user(cfg["user"]),
        "user_set": True,
        "password_set": True,
        "password_masked": _mask_secret(cfg["password"], keep_tail=4),
        "from": cfg["from"],
        "port": cfg["port"],
        "use_tls": cfg["use_tls"],
        "use_ssl": cfg["use_ssl"],
    }


def admin_snapshot() -> dict[str, Any]:
    """管理端读取邮件配置（脱敏）+ 就绪状态。"""
    primary = _channel_snapshot("smtp")
    backup = _channel_snapshot("smtp_backup")
    return {
        "ok": True,
        "smtp_configured": primary["configured"],
        "smtp_backup_configured": backup["configured"],
        "smtp_primary": primary,
        "smtp_backup": backup,
        "email_otp_subject": effective_subject(),
        "email_otp_body_template": effective_body_template(),
        "app_env": _app_env(),
    }


def _app_env() -> str:
    try:
        from config import settings

        return str(getattr(settings, "app_env", "local") or "local")
    except Exception:
        return "local"


def apply_update(body: dict[str, Any]) -> dict[str, Any]:
    """合并管理台提交（空字符串 = 保持原值/不覆盖），写覆盖文件，返回新快照。"""
    cur = get_override()
    if not isinstance(cur, dict):
        cur = {}

    def _merge_channel(name: str, field_map: dict[str, str]) -> None:
        ch = dict(cur.get(name) or {})
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
            cur[name] = ch

    # 主通道
    _merge_channel(
        "smtp",
        {
            "host": "smtp_host",
            "user": "smtp_user",
            "from": "smtp_from",
        },
    )
    _merge_channel(
        "smtp_backup",
        {
            "host": "smtp_backup_host",
            "user": "smtp_backup_user",
            "from": "smtp_backup_from",
        },
    )
    for dst, src, default in (
        ("port", "smtp_port", 587),
        ("use_tls", "smtp_use_tls", True),
        ("use_ssl", "smtp_use_ssl", False),
        ("port", "smtp_backup_port", 587),
        ("use_tls", "smtp_backup_use_tls", True),
        ("use_ssl", "smtp_backup_use_ssl", False),
    ):
        v = body.get(src)
        if v is None:
            continue
        name = "smtp" if src.startswith("smtp_") and not src.startswith("smtp_backup_") else "smtp_backup"
        ch = dict(cur.get(name) or {})
        if isinstance(v, bool):
            ch[dst] = v
        else:
            s = str(v).strip()
            if s:
                try:
                    ch[dst] = int(s) if dst == "port" else s
                except ValueError:
                    ch[dst] = default
        cur[name] = ch

    # 密码：留空 = 保持原值
    for name, src in (("smtp", "smtp_password"), ("smtp_backup", "smtp_backup_password")):
        p = str(body.get(src) or "").strip()
        if p:
            ch = dict(cur.get(name) or {})
            ch["password"] = p
            cur[name] = ch

    # 模板
    for dst, src in (("email_otp_subject", "email_otp_subject"), ("email_otp_body_template", "email_otp_body_template")):
        v = body.get(src)
        if v is not None and str(v).strip():
            cur[dst] = str(v).strip()

    save_override(cur)
    return admin_snapshot()
