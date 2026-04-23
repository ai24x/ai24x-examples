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


settings = Settings()