from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

# NOTE: We standardize on PostgreSQL in all environments.
# SQLite support was previously used for quick local runs but is now forbidden
# to prevent "works on my machine" drift and sub-brain configuration mistakes.
_API_ROOT = Path(__file__).resolve().parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str = Field(
        default="postgresql://user:password@localhost:5432/ai24x_subbrain01",
        validation_alias="DATABASE_URL",
    )

    @field_validator("database_url", mode="after")
    @classmethod
    def anchor_relative_sqlite_url(cls, v: str) -> str:
        s = (v or "").strip()
        if not s:
            return s
        try:
            u = make_url(s)
        except Exception:
            return s
        if u.drivername == "sqlite":
            raise ValueError("SQLite is disabled. Use PostgreSQL DATABASE_URL (postgresql://...)")
        if u.drivername != "sqlite":
            return s
        db = u.database
        if not db or db == ":memory:":
            return s
        p = Path(db)
        if p.is_absolute():
            return s
        abs_db = (_API_ROOT / p).resolve()
        return str(u.set(database=str(abs_db)))
    
    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0", validation_alias="REDIS_URL")
    
    # API
    api_host: str = Field(default="0.0.0.0", validation_alias="API_HOST")
    api_port: int = Field(default=8000, validation_alias="API_PORT")
    api_workers: int = Field(default=4, validation_alias="API_WORKERS")
    
    # Security
    secret_key: str = Field(default="your-secret-key-here-change-in-production", validation_alias="SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", validation_alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=30, validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    # 与行情官 p/a `AI24X_JWT_SECRET` / 过期天数对齐（Bearer 会话）
    auth_jwt_expire_days: int = Field(default=7, validation_alias="AUTH_JWT_EXPIRE_DAYS")

    app_env: str = Field(default="dev", validation_alias="APP_ENV")
    
    # Feature flags
    enable_rate_limiting: bool = Field(default=True, validation_alias="ENABLE_RATE_LIMITING")
    enable_caching: bool = Field(default=True, validation_alias="ENABLE_CACHING")

    # 安全：生产默认更严
    strict_auth: bool = Field(
        default=True,
        validation_alias="STRICT_AUTH",
        description="禁止仅凭 user_id 调用 chat（必须 X-API-Key）",
    )
    disable_docs_in_prod: bool = Field(default=True, validation_alias="DISABLE_DOCS_IN_PROD")
    cors_origins: str = Field(
        default="*",
        validation_alias="CORS_ORIGINS",
        description="逗号分隔；生产请改为 https://www.ai24x.com 等",
    )
    chat_rate_per_minute: int = Field(default=60, validation_alias="CHAT_RATE_PER_MINUTE")
    chat_rate_per_ip_per_minute: int = Field(default=120, validation_alias="CHAT_RATE_PER_IP_PER_MINUTE")

    # Dev switches
    skip_db_init: bool = Field(default=False, validation_alias="SKIP_DB_INIT")
    
    # Logging
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    log_format: str = Field(default="json", validation_alias="LOG_FORMAT")

    # 106 短信（utf8 提交）；密钥仅环境变量，勿提交仓库
    sms_106_enabled: bool = Field(default=False, validation_alias="SMS_106_ENABLED")
    sms_106_account: str = Field(default="", validation_alias="SMS_106_ACCOUNT")
    sms_106_password: str = Field(default="", validation_alias="SMS_106_PASSWORD")
    sms_106_endpoint: str = Field(
        default="http://sms.106jiekou.com/utf8/sms.aspx",
        validation_alias="SMS_106_ENDPOINT",
    )
    sms_106_sign_name: str = Field(default="", validation_alias="SMS_106_SIGN_NAME")
    sms_106_template: str = Field(
        default="您的验证码是：{code}。请不要把验证码泄露给其他人。如非本人操作，可不用理会！",
        validation_alias="SMS_106_TEMPLATE",
    )
    # 同号两次发送最短间隔：60s 与常见 App 一致，兼顾体验与成本
    sms_send_cooldown_s: float = Field(default=60.0, validation_alias="SMS_SEND_COOLDOWN_S")
    # 若非空：请求头须带 X-SMS-Internal-Key 且值一致，否则拒绝发送（建议生产必配）
    sms_internal_key: str = Field(default="", validation_alias="SMS_INTERNAL_KEY")
    # 防刷（进程内；多实例需网关/Redis）。当前默认偏宽松，遇盗刷再收紧 .env
    sms_ip_min_interval_s: float = Field(default=2.0, validation_alias="SMS_IP_MIN_INTERVAL_S")
    sms_ip_max_send_per_hour: int = Field(default=150, validation_alias="SMS_IP_MAX_SEND_PER_HOUR")
    sms_phone_max_send_per_hour: int = Field(default=25, validation_alias="SMS_PHONE_MAX_SEND_PER_HOUR")

    # —— 邮箱验证码（SMTP；未配置时非生产可走 local 卡片）——
    smtp_host: str = Field(default="", validation_alias="SMTP_HOST")
    smtp_port: int = Field(default=587, validation_alias="SMTP_PORT")
    smtp_user: str = Field(default="", validation_alias="SMTP_USER")
    smtp_password: str = Field(default="", validation_alias="SMTP_PASSWORD")
    smtp_from: str = Field(default="", validation_alias="SMTP_FROM")
    smtp_use_tls: bool = Field(default=True, validation_alias="SMTP_USE_TLS")
    smtp_use_ssl: bool = Field(default=False, validation_alias="SMTP_USE_SSL")
    email_otp_subject: str = Field(default="【AI24X】验证码", validation_alias="EMAIL_OTP_SUBJECT")
    email_otp_body_template: str = Field(
        default="您的 AI24X {purpose}验证码是：{code}\n\n5 分钟内有效，请勿泄露给他人。\n\n— AI24X",
        validation_alias="EMAIL_OTP_BODY_TEMPLATE",
    )
    # 非生产且未配 SMTP 时，是否在 API 响应里带回 local_code（默认 true 便于本机联调）
    email_otp_expose_local_code: bool = Field(default=True, validation_alias="EMAIL_OTP_EXPOSE_LOCAL_CODE")

    # 邀请注册即时奖励反作弊（每邀请人 / 每 IP · 滑动 24h）
    referral_register_bonus_per_referrer_day: int = Field(
        default=30, validation_alias="REFERRAL_REGISTER_BONUS_PER_REFERRER_DAY"
    )
    referral_register_bonus_per_ip_day: int = Field(
        default=8, validation_alias="REFERRAL_REGISTER_BONUS_PER_IP_DAY"
    )

    # —— Token 在线支付（与 a1 可共用商户号，但 notify URL 必须独立指向主站）——
    # 默认关闭真实支付；本地可 TOKEN_PAY_MOCK_ENABLED=true 测履约
    token_pay_enabled: bool = Field(default=False, validation_alias="TOKEN_PAY_ENABLED")
    token_pay_mock_enabled: bool = Field(default=False, validation_alias="TOKEN_PAY_MOCK_ENABLED")
    # 为 true 时：core 未配齐的商户字段自动从行情官 a1（admin_config / a1 .env）补齐；仍不复用 a1 回调
    token_pay_reuse_a1: bool = Field(default=True, validation_alias="TOKEN_PAY_REUSE_A1")
    token_wechat_notify_url: str = Field(default="", validation_alias="TOKEN_WECHAT_NOTIFY_URL")
    token_alipay_notify_url: str = Field(default="", validation_alias="TOKEN_ALIPAY_NOTIFY_URL")
    token_alipay_return_url: str = Field(default="", validation_alias="TOKEN_ALIPAY_RETURN_URL")

    wechat_mch_id: str = Field(default="", validation_alias="WECHAT_MCH_ID")
    wechat_app_id: str = Field(default="", validation_alias="WECHAT_APP_ID")
    wechat_mch_serial_no: str = Field(default="", validation_alias="WECHAT_MCH_SERIAL_NO")
    wechat_mch_private_key_path: str = Field(default="", validation_alias="WECHAT_MCH_PRIVATE_KEY_PATH")
    wechat_mch_private_key_pem: str = Field(default="", validation_alias="WECHAT_MCH_PRIVATE_KEY_PEM")
    wechat_api_v3_key: str = Field(default="", validation_alias="WECHAT_API_V3_KEY")
    wechat_pay_host: str = Field(
        default="https://api.mch.weixin.qq.com", validation_alias="WECHAT_PAY_HOST"
    )
    wechat_notify_skip_verify: bool = Field(default=False, validation_alias="WECHAT_NOTIFY_SKIP_VERIFY")

    alipay_app_id: str = Field(default="", validation_alias="ALIPAY_APP_ID")
    alipay_gateway: str = Field(
        default="https://openapi.alipay.com/gateway.do", validation_alias="ALIPAY_GATEWAY"
    )
    alipay_merchant_private_key_path: str = Field(
        default="", validation_alias="ALIPAY_MERCHANT_PRIVATE_KEY_PATH"
    )
    alipay_merchant_private_key_pem: str = Field(
        default="", validation_alias="ALIPAY_MERCHANT_PRIVATE_KEY_PEM"
    )
    alipay_public_key: str = Field(default="", validation_alias="ALIPAY_PUBLIC_KEY")

    # —— PayPal（国际 USD；Sandbox / Live）——
    paypal_client_id: str = Field(default="", validation_alias="PAYPAL_CLIENT_ID")
    paypal_client_secret: str = Field(default="", validation_alias="PAYPAL_CLIENT_SECRET")
    paypal_mode: str = Field(default="sandbox", validation_alias="PAYPAL_MODE")  # sandbox|live
    paypal_webhook_id: str = Field(default="", validation_alias="PAYPAL_WEBHOOK_ID")
    token_paypal_return_url: str = Field(
        default="https://www.ai24x.com/console.html", validation_alias="TOKEN_PAYPAL_RETURN_URL"
    )
    token_paypal_cancel_url: str = Field(
        default="https://www.ai24x.com/console.html", validation_alias="TOKEN_PAYPAL_CANCEL_URL"
    )
    # 结账页语言 BCP-47（国际默认 en-US）；买家账号偏好仍可能覆盖
    paypal_locale: str = Field(default="en-US", validation_alias="TOKEN_PAYPAL_LOCALE")
    # LOGIN | BILLING | NO_PREFERENCE — BILLING 略偏向卡/账单页，不保证 Guest
    paypal_landing_page: str = Field(default="BILLING", validation_alias="TOKEN_PAYPAL_LANDING_PAGE")

    # —— LLM upstream（默认聚合 OpenRouter；直连为可选）——
    token_llm_upstream: str = Field(default="direct", validation_alias="TOKEN_LLM_UPSTREAM")
    openrouter_api_key: str = Field(default="", validation_alias="OPENROUTER_API_KEY")
    openrouter_api_key_free: str = Field(default="", validation_alias="OPENROUTER_API_KEY_FREE")
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1", validation_alias="OPENROUTER_BASE_URL"
    )
    deepseek_api_key: str = Field(default="", validation_alias="DEEPSEEK_API_KEY")
    deepseek_base_url: str = Field(default="https://api.deepseek.com", validation_alias="DEEPSEEK_BASE_URL")
    deepseek_model: str = Field(default="deepseek-v4-flash", validation_alias="DEEPSEEK_MODEL")
    siliconflow_api_key: str = Field(default="", validation_alias="SILICONFLOW_API_KEY")
    siliconflow_api_key_free: str = Field(default="", validation_alias="SILICONFLOW_API_KEY_FREE")
    siliconflow_com_api_key: str = Field(default="", validation_alias="SILICONFLOW_COM_API_KEY")
    siliconflow_base_url: str = Field(
        default="https://api.siliconflow.com/v1", validation_alias="SILICONFLOW_BASE_URL"
    )
    siliconflow_model: str = Field(
        default="Qwen/Qwen2.5-7B-Instruct", validation_alias="SILICONFLOW_MODEL"
    )
    # 国际备用：Together（开源）+ 厂直连（旗舰）；空 Key=未启用
    together_api_key: str = Field(default="", validation_alias="TOGETHER_API_KEY")
    together_base_url: str = Field(
        default="https://api.together.xyz/v1", validation_alias="TOGETHER_BASE_URL"
    )
    openai_api_key: str = Field(default="", validation_alias="OPENAI_API_KEY")
    openai_base_url: str = Field(
        default="https://api.openai.com/v1", validation_alias="OPENAI_BASE_URL"
    )
    anthropic_api_key: str = Field(default="", validation_alias="ANTHROPIC_API_KEY")
    anthropic_base_url: str = Field(
        default="https://api.anthropic.com/v1", validation_alias="ANTHROPIC_BASE_URL"
    )
    google_ai_api_key: str = Field(default="", validation_alias="GOOGLE_AI_API_KEY")
    google_ai_base_url: str = Field(
        default="https://generativelanguage.googleapis.com/v1beta/openai/",
        validation_alias="GOOGLE_AI_BASE_URL",
    )
    token_llm_timeout_s: float = Field(default=30.0, validation_alias="TOKEN_LLM_TIMEOUT_S")


settings = Settings()