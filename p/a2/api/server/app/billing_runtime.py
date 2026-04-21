"""
运行时集成配置：admin_config 覆盖环境变量（微信支付、统一身份与短信预留）。
"""
from __future__ import annotations

from types import SimpleNamespace

from . import db
from .config import settings


def _items() -> dict[str, str]:
    return db.admin_config_get_all() or {}


def resolve_wechat_pay() -> SimpleNamespace:
    """合并 DB 与 .env，供 Native 下单与回调验签。"""
    m = _items()

    def p(key: str, fallback: str) -> str:
        v = (m.get(key) or "").strip()
        return v if v else str(fallback or "").strip()
    skip_db = (m.get("wechat_notify_skip_verify") or "").strip().lower()
    if skip_db in ("1", "true", "yes"):
        skip = str(settings.env).strip().lower() != "prod"
    elif skip_db in ("0", "false", "no"):
        skip = False
    else:
        skip = bool(settings.wechat_notify_skip_verify)

    return SimpleNamespace(
        env=settings.env,
        wechat_mch_id=p("wechat_mch_id", settings.wechat_mch_id),
        wechat_app_id=p("wechat_app_id", settings.wechat_app_id),
        wechat_mch_serial_no=p("wechat_mch_serial_no", settings.wechat_mch_serial_no),
        wechat_mch_private_key_path=p("wechat_mch_private_key_path", settings.wechat_mch_private_key_path),
        wechat_mch_private_key_pem=(m.get("wechat_mch_private_key_pem") or "").strip(),
        wechat_api_v3_key=p("wechat_api_v3_key", settings.wechat_api_v3_key),
        wechat_notify_url=p("wechat_notify_url", settings.wechat_notify_url),
        wechat_pay_host=p("wechat_pay_host", settings.wechat_pay_host) or "https://api.mch.weixin.qq.com",
        wechat_notify_skip_verify=skip,
    )


def resolve_identity() -> SimpleNamespace:
    """主站转发短信/邮箱与内部密钥；腾讯短信字段仅占位。"""
    m = _items()

    def p(key: str, fallback: str) -> str:
        v = (m.get(key) or "").strip()
        return v if v else str(fallback or "").strip()

    prov = (m.get("sms_active_provider") or "").strip().lower() or "identity_proxy"
    cap_on = (m.get("sms_captcha_enabled") or "").strip().lower()
    if cap_on in ("1", "true", "yes", "on"):
        captcha_enabled = True
    elif cap_on in ("0", "false", "no", "off", ""):
        captcha_enabled = False
    else:
        captcha_enabled = False
    return SimpleNamespace(
        identity_api_base=p("identity_api_base", settings.identity_api_base),
        sms_internal_key=p("sms_internal_key", settings.sms_internal_key),
        sms_active_provider=prov,
        # Reserved: SMS captcha / anti-abuse (default off; enable via admin_config).
        sms_captcha_enabled=captcha_enabled,
        sms_captcha_provider=(m.get("sms_captcha_provider") or "").strip().lower() or "turnstile",
        sms_captcha_turnstile_site_key=(m.get("sms_captcha_turnstile_site_key") or "").strip(),
        sms_captcha_turnstile_secret_key=(m.get("sms_captcha_turnstile_secret_key") or "").strip(),
        # 106：存 admin_config，随 /v1/auth/sms/send 一并提交主站覆盖 .env（须主站 SMS_INTERNAL_KEY）
        sms_106_endpoint=(m.get("sms_106_endpoint") or "").strip(),
        sms_106_account=(m.get("sms_106_account") or "").strip(),
        sms_106_password=(m.get("sms_106_password") or "").strip(),
        sms_106_sign_name=(m.get("sms_106_sign_name") or "").strip(),
        sms_106_template=(m.get("sms_106_template") or "").strip(),
        sms_tencent_secret_id=p("sms_tencent_secret_id", ""),
        sms_tencent_secret_key=p("sms_tencent_secret_key", ""),
        sms_tencent_sdk_app_id=p("sms_tencent_sdk_app_id", ""),
        sms_tencent_sign=p("sms_tencent_sign", ""),
        sms_tencent_template_id=p("sms_tencent_template_id", ""),
        sms_tencent_region=p("sms_tencent_region", "ap-guangzhou"),
    )


def identity_configured() -> bool:
    return bool((resolve_identity().identity_api_base or "").strip())
