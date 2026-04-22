from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import Settings

logger = logging.getLogger(__name__)


def _prod_recommends_admin_otp(settings: "Settings") -> bool:
    try:
        from .admin_otp import admin_browser_otp_required

        return str(settings.env or "").lower() in ("prod", "production") and not admin_browser_otp_required()
    except Exception:
        return False

# 常见示例/弱口令：命中则告警（不阻断启动，便于本地开发）
_ADMIN_KEY_WEAK_EXACT = frozenset(
    {
        "admin",
        "123456",
        "password",
        "secret",
        "change-me-admin",
    }
)


def log_admin_security_baseline(settings: "Settings") -> None:
    """
    启动时打印「首推安全基线」相关告警：弱管理密钥、生产弱 JWT 等。
    不替代人工检查；详见 p/a/docs/管理后台-安全基线与后期加强预案.md
    """
    key = str(settings.admin_key or "").strip()
    jwt = str(settings.jwt_secret or "").strip()
    env = str(settings.env or "").lower()
    msgs: list[str] = []

    if len(key) < 20:
        msgs.append(
            "AI24X_ADMIN_KEY 过短：建议至少 20 位随机字符（推荐用密码管理器生成 32+），"
            "并勿提交到仓库。"
        )

    kl = key.lower()
    if kl in _ADMIN_KEY_WEAK_EXACT:
        msgs.append("AI24X_ADMIN_KEY 为常见弱/默认值，请务必改为随机长串。")
    elif "change-me" in kl:
        msgs.append("AI24X_ADMIN_KEY 含 change-me 等示例特征，上线前请改为随机长串。")

    if env in ("prod", "production"):
        if len(jwt) < 24 or jwt.lower() == "change-me":
            msgs.append("生产环境 AI24X_JWT_SECRET 过弱或过短：请改为长随机串。")

    for m in msgs:
        logger.warning("[admin-security] %s", m)
    if msgs:
        logger.warning(
            "[admin-security] 基线说明与后期加强预案：p/a/docs/管理后台-安全基线与后期加强预案.md"
        )
    if _prod_recommends_admin_otp(settings):
        logger.warning(
            "[admin-security] 生产环境建议在管理后台「系统配置」开启管理登录短信 OTP（admin_browser_otp_enabled），"
            "并配置 AI24X_ADMIN_OTP_PHONES 与主站 identity 短信；详见同文档。"
        )
