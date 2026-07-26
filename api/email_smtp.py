"""
邮箱验证码发送（SMTP）。

未配置 SMTP 时：非生产可走 local 通道（API 返回 local_code 供页面卡片展示）；
生产必须配置 SMTP，否则拒绝发送。
"""
from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)


def smtp_configured() -> bool:
    host = (settings.smtp_host or "").strip()
    from_addr = (settings.smtp_from or settings.smtp_user or "").strip()
    return bool(host and from_addr)


def send_otp_email(*, to_email: str, code: str, purpose: str) -> tuple[bool, str]:
    """
    发送验证码邮件。返回 (ok, message)。
    """
    if not smtp_configured():
        return False, "SMTP 未配置"

    host = (settings.smtp_host or "").strip()
    port = int(settings.smtp_port or 587)
    user = (settings.smtp_user or "").strip()
    password = (settings.smtp_password or "").strip()
    from_addr = (settings.smtp_from or user).strip()
    use_ssl = bool(settings.smtp_use_ssl)
    use_tls = bool(settings.smtp_use_tls)

    purpose_cn = {"register": "注册", "login": "登录", "reset": "重置密码"}.get(
        (purpose or "").strip().lower(), "验证"
    )
    subject = (settings.email_otp_subject or "【AI24X】验证码").strip()
    if "{purpose}" in subject:
        subject = subject.replace("{purpose}", purpose_cn)
    else:
        subject = f"{subject} · {purpose_cn}"

    body = (
        settings.email_otp_body_template
        or "您的 AI24X {purpose}验证码是：{code}\n\n5 分钟内有效，请勿泄露给他人。\n\n— AI24X"
    )
    text = body.format(code=code, purpose=purpose_cn)

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_email
    msg.set_content(text)

    try:
        if use_ssl:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, port, timeout=20, context=context) as smtp:
                if user:
                    smtp.login(user, password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=20) as smtp:
                smtp.ehlo()
                if use_tls:
                    context = ssl.create_default_context()
                    smtp.starttls(context=context)
                    smtp.ehlo()
                if user:
                    smtp.login(user, password)
                smtp.send_message(msg)
        logger.info("SMTP OTP sent to=%s purpose=%s", to_email, purpose)
        return True, "验证码已发送到邮箱，请查收"
    except Exception as e:
        logger.exception("SMTP OTP send failed to=%s", to_email)
        return False, f"邮件发送失败：{str(e)[:160]}"


def email_channel_status() -> dict:
    """供运维自检（不含密钥）。"""
    return {
        "smtp_configured": smtp_configured(),
        "smtp_host": (settings.smtp_host or "").strip() or None,
        "smtp_port": int(settings.smtp_port or 587),
        "smtp_from": (settings.smtp_from or settings.smtp_user or "").strip() or None,
        "smtp_use_tls": bool(settings.smtp_use_tls),
        "smtp_use_ssl": bool(settings.smtp_use_ssl),
        "app_env": settings.app_env,
    }
