"""
Email OTP sending (SMTP) with primary + backup channel auto-fallback.

When SMTP is not configured: non-production may use the local channel
(API returns local_code for the page card); production must configure SMTP.
"""
from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)


def _clean_password(pwd: str) -> str:
    return (pwd or "").strip().strip('"').strip("'")


def _eff_channel(name: str):
    """管理台覆盖优先；无覆盖时回落 settings。"""
    try:
        from admin_email_config import effective_channel

        return effective_channel(name)
    except Exception:
        return None


def smtp_configured() -> bool:
    cfg = _eff_channel("smtp")
    if cfg:
        return True
    host = (settings.smtp_host or "").strip()
    user = (settings.smtp_user or "").strip()
    password = _clean_password(settings.smtp_password)
    from_addr = (settings.smtp_from or user).strip()
    return bool(host and from_addr and user and password)


def smtp_backup_configured() -> bool:
    cfg = _eff_channel("smtp_backup")
    if cfg:
        return True
    host = (settings.smtp_backup_host or "").strip()
    user = (settings.smtp_backup_user or "").strip()
    password = _clean_password(settings.smtp_backup_password)
    from_addr = (settings.smtp_backup_from or user).strip()
    return bool(host and from_addr and user and password)


def _smtp_send(*, host: str, port: int, user: str, password: str,
               from_addr: str, use_ssl: bool, use_tls: bool,
               msg: EmailMessage) -> tuple[bool, str]:
    """Send via one SMTP channel. Returns (ok, err_msg_or_empty)."""
    try:
        if use_ssl or int(port) == 465:
            context = ssl.create_default_context()
            ssl_port = 465 if int(port) == 587 and use_ssl else int(port)
            with smtplib.SMTP_SSL(host, ssl_port, timeout=20, context=context) as smtp:
                smtp.login(user, password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(host, int(port), timeout=20) as smtp:
                smtp.ehlo()
                if use_tls:
                    context = ssl.create_default_context()
                    smtp.starttls(context=context)
                    smtp.ehlo()
                smtp.login(user, password)
                smtp.send_message(msg)
        return True, ""
    except smtplib.SMTPAuthenticationError:
        return False, "auth_failed"
    except Exception as e:
        return False, str(e)[:200]


def send_otp_email(*, to_email: str, code: str, purpose: str, lang: str = "zh") -> tuple[bool, str]:
    """
    Send OTP email. Returns (ok, message).
    Primary SMTP first; falls back to backup SMTP when primary fails.
    lang: "zh" or "en" selects the subject/body template language.
    """
    if not smtp_configured() and not smtp_backup_configured():
        return False, "邮件服务暂不可用，请稍后再试。"

    lang = (lang or "zh").strip().lower()
    is_en = lang.startswith("en")

    purpose_map = {
        "register": ("注册", "Registration"),
        "login": ("登录", "Login"),
        "reset": ("重置密码", "Password Reset"),
    }
    purpose_cn, purpose_en = purpose_map.get(
        (purpose or "").strip().lower(), ("验证", "Verification")
    )
    purpose_label = purpose_en if is_en else purpose_cn

    try:
        from admin_email_config import effective_subject, effective_body_template

        configured_subject = effective_subject()
        configured_body = effective_body_template()
    except Exception:
        configured_subject = (settings.email_otp_subject or "").strip()
        configured_body = (settings.email_otp_body_template or "").strip()
    if configured_subject:
        subject = configured_subject
        if "{purpose}" in subject:
            subject = subject.replace("{purpose}", purpose_label)
        else:
            subject = f"{subject} · {purpose_label}"
    else:
        subject = f"AI24X {purpose_en} Verification Code" if is_en else f"【AI24X】{purpose_cn}验证码"

    if configured_body:
        body = configured_body
    elif is_en:
        body = (
            "Your AI24X {purpose} verification code is: {code}\n\n"
            "It is valid for 5 minutes. Do not share it with anyone.\n\n— AI24X"
        )
    else:
        body = "您的 AI24X {purpose}验证码是：{code}\n\n5 分钟内有效，请勿泄露给他人。\n\n— AI24X"
    text = body.format(code=code, purpose=purpose_label)

    def _build_msg(from_addr: str) -> EmailMessage:
        m = EmailMessage()
        m["Subject"] = subject
        m["From"] = from_addr
        m["To"] = to_email
        m.set_content(text)
        return m

    # Primary channel
    primary_cfg = _eff_channel("smtp")
    if primary_cfg or smtp_configured():
        if primary_cfg:
            host = primary_cfg["host"]
            port = int(primary_cfg.get("port") or 587)
            user = primary_cfg["user"]
            password = primary_cfg["password"]
            from_addr = primary_cfg.get("from") or user
            use_ssl = bool(primary_cfg.get("use_ssl"))
            use_tls = bool(primary_cfg.get("use_tls"))
        else:
            host = (settings.smtp_host or "").strip()
            port = int(settings.smtp_port or 587)
            user = (settings.smtp_user or "").strip()
            password = _clean_password(settings.smtp_password)
            from_addr = (settings.smtp_from or user).strip()
            use_ssl = bool(settings.smtp_use_ssl)
            use_tls = bool(settings.smtp_use_tls)
        ok, err = _smtp_send(
            host=host, port=port, user=user, password=password,
            from_addr=from_addr,
            use_ssl=use_ssl, use_tls=use_tls,
            msg=_build_msg(from_addr),
        )
        if ok:
            logger.info("SMTP OTP sent (primary) to=%s purpose=%s host=%s", to_email, purpose, host)
            return True, "验证码已发送到邮箱，请查收"
        logger.warning("SMTP primary failed host=%s err=%s, trying backup", host, err)

    # Backup channel
    backup_cfg = _eff_channel("smtp_backup")
    if backup_cfg or smtp_backup_configured():
        if backup_cfg:
            host = backup_cfg["host"]
            port = int(backup_cfg.get("port") or 587)
            user = backup_cfg["user"]
            password = backup_cfg["password"]
            from_addr = backup_cfg.get("from") or user
            use_ssl = bool(backup_cfg.get("use_ssl"))
            use_tls = bool(backup_cfg.get("use_tls"))
        else:
            host = (settings.smtp_backup_host or "").strip()
            port = int(settings.smtp_backup_port or 587)
            user = (settings.smtp_backup_user or "").strip()
            password = _clean_password(settings.smtp_backup_password)
            from_addr = (settings.smtp_backup_from or user).strip()
            use_ssl = bool(settings.smtp_backup_use_ssl)
            use_tls = bool(settings.smtp_backup_use_tls)
        ok, err = _smtp_send(
            host=host, port=port, user=user, password=password,
            from_addr=from_addr,
            use_ssl=use_ssl, use_tls=use_tls,
            msg=_build_msg(from_addr),
        )
        if ok:
            logger.info("SMTP OTP sent (backup) to=%s purpose=%s host=%s", to_email, purpose, host)
            return True, "验证码已发送到邮箱，请查收"
        logger.error("SMTP backup failed host=%s err=%s", host, err)

    return False, "邮件发送失败，请稍后重试或联系管理员检查发信配置。"


def email_channel_status() -> dict:
    """Ops self-check (no plaintext secrets)."""
    def _ch(host, user, pwd, from_addr, tls, ssl):
        u = (user or "").strip()
        p = _clean_password(pwd)
        return {
            "configured": bool((host or "").strip() and u and p and (from_addr or u).strip()),
            "host": (host or "").strip() or None,
            "user_set": bool(u),
            "password_set": bool(p),
            "from": (from_addr or u).strip() or None,
            "use_tls": bool(tls),
            "use_ssl": bool(ssl),
        }

    def _snap(name: str):
        cfg = _eff_channel(name)
        if cfg:
            return _ch(
                cfg["host"], cfg["user"], cfg["password"],
                cfg.get("from") or cfg["user"],
                cfg.get("use_tls", True), cfg.get("use_ssl", False),
            )
        src = "smtp" if name == "smtp" else "smtp_backup"
        return _ch(
            getattr(settings, f"{src}_host", ""),
            getattr(settings, f"{src}_user", ""),
            getattr(settings, f"{src}_password", ""),
            getattr(settings, f"{src}_from", ""),
            getattr(settings, f"{src}_use_tls", True),
            getattr(settings, f"{src}_use_ssl", False),
        )

    primary = _snap("smtp")
    backup = _snap("smtp_backup")
    return {
        "smtp_configured": primary["configured"],
        "smtp_host": primary["host"],  # legacy compat for smoke/admin
        "smtp_backup_configured": backup["configured"],
        "smtp_primary": primary,
        "smtp_backup": backup,
        "app_env": settings.app_env,
    }


def send_test_email(*, to_email: str) -> tuple[bool, str]:
    """管理端测试发信：主通道优先，失败自动切备用通道。"""
    from email.message import EmailMessage

    if not (smtp_configured() or smtp_backup_configured()):
        return False, "未配置 SMTP，请先保存发信通道配置。"

    def _build_test_msg(from_addr: str) -> EmailMessage:
        m = EmailMessage()
        m["Subject"] = "AI24X 邮件服务测试"
        m["From"] = from_addr
        m["To"] = to_email
        m.set_content("这是一封来自 AI24X 平台的测试邮件。如果收到，说明发信通道配置正常。\n\n— AI24X")
        return m

    for name in ("smtp", "smtp_backup"):
        cfg = _eff_channel(name)
        if not cfg and not (smtp_configured() if name == "smtp" else smtp_backup_configured()):
            continue
        if cfg:
            host = cfg["host"]
            port = int(cfg.get("port") or 587)
            user = cfg["user"]
            password = cfg["password"]
            from_addr = cfg.get("from") or user
            use_ssl = bool(cfg.get("use_ssl"))
            use_tls = bool(cfg.get("use_tls"))
        else:
            src = "smtp" if name == "smtp" else "smtp_backup"
            host = getattr(settings, f"{src}_host", "")
            port = int(getattr(settings, f"{src}_port", 587) or 587)
            user = getattr(settings, f"{src}_user", "")
            password = _clean_password(getattr(settings, f"{src}_password", ""))
            from_addr = getattr(settings, f"{src}_from", "") or user
            use_ssl = bool(getattr(settings, f"{src}_use_ssl", False))
            use_tls = bool(getattr(settings, f"{src}_use_tls", True))
        ok, err = _smtp_send(
            host=host, port=port, user=user, password=password,
            from_addr=from_addr, use_ssl=use_ssl, use_tls=use_tls,
            msg=_build_test_msg(from_addr),
        )
        if ok:
            logger.info("SMTP test sent channel=%s host=%s to=%s", name, host, to_email)
            return True, f"测试邮件已发送（{host}），请查收 {to_email}"
        logger.warning("SMTP test failed channel=%s host=%s err=%s", name, host, err)

    return False, "测试邮件发送失败：主/备用通道均不可用，请检查配置。"
