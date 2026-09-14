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


def smtp_configured() -> bool:
    host = (settings.smtp_host or "").strip()
    user = (settings.smtp_user or "").strip()
    password = _clean_password(settings.smtp_password)
    from_addr = (settings.smtp_from or user).strip()
    return bool(host and from_addr and user and password)


def smtp_backup_configured() -> bool:
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

    configured_subject = (settings.email_otp_subject or "").strip()
    if configured_subject:
        subject = configured_subject
        if "{purpose}" in subject:
            subject = subject.replace("{purpose}", purpose_label)
        else:
            subject = f"{subject} · {purpose_label}"
    else:
        subject = f"AI24X {purpose_en} Verification Code" if is_en else f"【AI24X】{purpose_cn}验证码"

    configured_body = (settings.email_otp_body_template or "").strip()
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
    if smtp_configured():
        host = (settings.smtp_host or "").strip()
        port = int(settings.smtp_port or 587)
        user = (settings.smtp_user or "").strip()
        password = _clean_password(settings.smtp_password)
        from_addr = (settings.smtp_from or user).strip()
        ok, err = _smtp_send(
            host=host, port=port, user=user, password=password,
            from_addr=from_addr,
            use_ssl=bool(settings.smtp_use_ssl), use_tls=bool(settings.smtp_use_tls),
            msg=_build_msg(from_addr),
        )
        if ok:
            logger.info("SMTP OTP sent (primary) to=%s purpose=%s host=%s", to_email, purpose, host)
            return True, "验证码已发送到邮箱，请查收"
        logger.warning("SMTP primary failed host=%s err=%s, trying backup", host, err)

    # Backup channel
    if smtp_backup_configured():
        host = (settings.smtp_backup_host or "").strip()
        port = int(settings.smtp_backup_port or 587)
        user = (settings.smtp_backup_user or "").strip()
        password = _clean_password(settings.smtp_backup_password)
        from_addr = (settings.smtp_backup_from or user).strip()
        ok, err = _smtp_send(
            host=host, port=port, user=user, password=password,
            from_addr=from_addr,
            use_ssl=bool(settings.smtp_backup_use_ssl), use_tls=bool(settings.smtp_backup_use_tls),
            msg=_build_msg(from_addr),
        )
        if ok:
            logger.info("SMTP OTP sent (backup) to=%s purpose=%s host=%s", to_email, purpose, host)
            return True, "验证码已发送到邮箱，请查收"
        logger.error("SMTP backup failed host=%s err=%s", host, err)

    return False, "邮件发送失败，请稍后重试。"


def send_text_email(*, to_email: str, subject: str, body: str) -> tuple[bool, str]:
    """
    发送纯文本通知邮件（续费提醒等）。返回 (ok, message)。
    message 面向用户/运维日志，勿含 SMTP 主机细节给浏览器。
    """
    to_email = (to_email or "").strip()
    if not to_email or "@" not in to_email:
        return False, "invalid_email"
    if not smtp_configured() and not smtp_backup_configured():
        return False, "邮件服务暂不可用，请稍后再试。"

    def _build_msg(from_addr: str) -> EmailMessage:
        m = EmailMessage()
        m["Subject"] = (subject or "AI24X").strip()[:200]
        m["From"] = from_addr
        m["To"] = to_email
        m.set_content((body or "").strip() + "\n")
        return m

    if smtp_configured():
        host = (settings.smtp_host or "").strip()
        port = int(settings.smtp_port or 587)
        user = (settings.smtp_user or "").strip()
        password = _clean_password(settings.smtp_password)
        from_addr = (settings.smtp_from or user).strip()
        ok, err = _smtp_send(
            host=host, port=port, user=user, password=password,
            from_addr=from_addr,
            use_ssl=bool(settings.smtp_use_ssl), use_tls=bool(settings.smtp_use_tls),
            msg=_build_msg(from_addr),
        )
        if ok:
            logger.info("SMTP text mail sent (primary) to=%s subject=%s", to_email, subject[:60])
            return True, "ok"
        logger.warning("SMTP primary text mail failed host=%s err=%s", host, err)

    if smtp_backup_configured():
        host = (settings.smtp_backup_host or "").strip()
        port = int(settings.smtp_backup_port or 587)
        user = (settings.smtp_backup_user or "").strip()
        password = _clean_password(settings.smtp_backup_password)
        from_addr = (settings.smtp_backup_from or user).strip()
        ok, err = _smtp_send(
            host=host, port=port, user=user, password=password,
            from_addr=from_addr,
            use_ssl=bool(settings.smtp_backup_use_ssl), use_tls=bool(settings.smtp_backup_use_tls),
            msg=_build_msg(from_addr),
        )
        if ok:
            logger.info("SMTP text mail sent (backup) to=%s subject=%s", to_email, subject[:60])
            return True, "ok"
        logger.error("SMTP backup text mail failed host=%s err=%s", host, err)

    return False, "邮件发送失败，请稍后重试。"


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

    primary = _ch(
        settings.smtp_host, settings.smtp_user, settings.smtp_password,
        settings.smtp_from, settings.smtp_use_tls, settings.smtp_use_ssl,
    )
    backup = _ch(
        settings.smtp_backup_host, settings.smtp_backup_user, settings.smtp_backup_password,
        settings.smtp_backup_from, settings.smtp_backup_use_tls, settings.smtp_backup_use_ssl,
    )
    return {
        "smtp_configured": primary["configured"],
        "smtp_host": primary["host"],  # legacy compat for smoke/admin
        "smtp_backup_configured": backup["configured"],
        "smtp_primary": primary,
        "smtp_backup": backup,
        "app_env": settings.app_env,
    }