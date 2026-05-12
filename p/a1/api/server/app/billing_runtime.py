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


def resolve_alipay() -> SimpleNamespace:
    """合并 DB 与 .env，供支付宝 WAP 下单与回调验签。"""
    m = _items()

    def p(key: str, fallback: str) -> str:
        v = (m.get(key) or "").strip()
        return v if v else str(fallback or "").strip()

    return SimpleNamespace(
        env=settings.env,
        alipay_app_id=p("alipay_app_id", settings.alipay_app_id),
        alipay_gateway=p("alipay_gateway", settings.alipay_gateway) or "https://openapi.alipay.com/gateway.do",
        alipay_notify_url=p("alipay_notify_url", settings.alipay_notify_url),
        alipay_return_url=p("alipay_return_url", settings.alipay_return_url),
        alipay_merchant_private_key_path=p(
            "alipay_merchant_private_key_path",
            settings.alipay_merchant_private_key_path,
        ),
        alipay_merchant_private_key_pem=(m.get("alipay_merchant_private_key_pem") or "").strip(),
        alipay_public_key=p("alipay_public_key", settings.alipay_public_key),
    )


def resolve_billing() -> SimpleNamespace:
    """
    会员套餐与计费相关的运行时配置：允许 admin_config 临时覆盖 .env，用于测试/促销。

    Keys:
    - price_vip_trial_fen / price_vip_month_fen / price_vip_year_fen
    - vip_title_trial / vip_title_month / vip_title_year
    - price_agent_growth_fen / price_agent_pro_fen
    - agent_title_growth / agent_title_pro
    - agent_upgrade_growth_enabled / agent_upgrade_pro_enabled
    - billing_dev_real_pay / billing_dev_amount_fen（非 prod 才生效）
    - billing_pay_wechat_enabled / billing_pay_alipay_enabled
    """
    m = _items()

    def p_int(key: str, fallback: int) -> int:
        v = (m.get(key) or "").strip()
        if v == "":
            return int(fallback)
        try:
            return int(float(v))
        except Exception:
            return int(fallback)

    def p_str(key: str, fallback: str) -> str:
        v = (m.get(key) or "").strip()
        return v if v else str(fallback or "").strip()

    def p_bool_default_on(key: str) -> bool:
        v = (m.get(key) or "").strip().lower()
        if v in ("0", "false", "no", "off"):
            return False
        if v in ("1", "true", "yes", "on"):
            return True
        return True

    # Only allow dev real-pay in non-prod; same behavior as settings.
    dev_real_pay_raw = (m.get("billing_dev_real_pay") or "").strip().lower()
    if dev_real_pay_raw in ("1", "true", "yes", "on"):
        dev_real_pay = str(settings.env).strip().lower() != "prod"
    elif dev_real_pay_raw in ("0", "false", "no", "off"):
        dev_real_pay = False
    else:
        dev_real_pay = bool(settings.billing_dev_real_pay)

    return SimpleNamespace(
        env=settings.env,
        price_vip_month_fen=p_int("price_vip_month_fen", int(settings.price_vip_month_fen)),
        price_vip_year_fen=p_int("price_vip_year_fen", int(settings.price_vip_year_fen)),
        price_vip_trial_fen=p_int("price_vip_trial_fen", int(settings.price_vip_trial_fen)),
        vip_title_month=p_str("vip_title_month", "AI24X VIP月会员"),
        vip_title_year=p_str("vip_title_year", "AI24X VIP年会员"),
        vip_title_trial=p_str("vip_title_trial", "AI24X VIP体验卡"),
        # Agent tier paid upgrades (default: enabled; titles/prices can be overridden in admin_config).
        price_agent_growth_fen=p_int("price_agent_growth_fen", 29900),
        price_agent_pro_fen=p_int("price_agent_pro_fen", 99900),
        agent_title_growth=p_str("agent_title_growth", "伙伴计划 · 成长档"),
        agent_title_pro=p_str("agent_title_pro", "伙伴计划 · 专业档"),
        agent_upgrade_growth_enabled=bool(p_bool_default_on("agent_upgrade_growth_enabled")),
        agent_upgrade_pro_enabled=bool(p_bool_default_on("agent_upgrade_pro_enabled")),
        billing_dev_real_pay=bool(dev_real_pay),
        billing_dev_amount_fen=p_int("billing_dev_amount_fen", int(settings.billing_dev_amount_fen)),
        billing_pay_wechat_enabled=bool(p_bool_default_on("billing_pay_wechat_enabled")),
        billing_pay_alipay_enabled=bool(p_bool_default_on("billing_pay_alipay_enabled")),
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
        # 聚合数据（预留）
        sms_juhe_key=p("sms_juhe_key", ""),
        sms_juhe_template_id=p("sms_juhe_template_id", ""),
        sms_juhe_sign=p("sms_juhe_sign", ""),
        sms_juhe_template=p("sms_juhe_template", ""),
    )


def identity_configured() -> bool:
    return bool((resolve_identity().identity_api_base or "").strip())
