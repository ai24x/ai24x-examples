from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


def _to_int(v: str | None, default: int) -> int:
    try:
        return int(v) if v is not None else default
    except Exception:
        return default


def _to_float(v: str | None, default: float) -> float:
    try:
        return float(v) if v is not None else default
    except Exception:
        return default


# 未配置 AI24X_ADMIN_MOUNT_PATH 时的默认前缀（日期弱隐蔽；安全仍主要靠强密钥、限流与网络隔离）
DEFAULT_ADMIN_MOUNT_PATH = "/admin20260501"


def normalize_admin_mount(raw: str | None) -> str:
    """浏览器管理台挂载路径，须以 / 开头、无尾斜杠。未配置时默认 DEFAULT_ADMIN_MOUNT_PATH。"""
    s = (raw or "").strip()
    if not s:
        return DEFAULT_ADMIN_MOUNT_PATH
    if not s.startswith("/"):
        s = "/" + s
    s = s.rstrip("/")
    parts = [p for p in s.split("/") if p]
    if not parts:
        return DEFAULT_ADMIN_MOUNT_PATH
    return "/" + "/".join(parts)


@dataclass(frozen=True)
class Settings:
    env: str
    db_kind: str
    database_url: str
    db_path: str
    jwt_secret: str
    jwt_expire_days: int
    admin_key: str
    # 管理台 HTML 挂载路径（不含 /login 后缀）；默认含日期前缀，可自行改 env 不定期轮换
    admin_mount_path: str
    # 每 IP 每 15 分钟允许 POST /api/admin/login 次数（防撞库/爆破；含失败与成功）
    admin_login_max_per_15m: int
    # 管理后台浏览器登录：总管手机 CSV（与 admin_operators 启用行并集非空时，须短信 OTP + 管理密钥）
    admin_otp_phones: str
    admin_otp_ttl_s: int
    admin_otp_send_per_15m: int
    # 非 prod 可选：未配置主站短信时，发码接口在 JSON 中回显 dev_code（与联调 dev 行为一致）
    admin_otp_dev_code: str

    free_daily_cap: int
    free_weekly: int

    vip_daily_cap: int
    vip_weekly: int
    dedupe_seconds: int

    cors_origins: str

    # 统一身份（api.ai24x.com）：与主站 `api/` 同 SECRET 签 JWT；本站代理注册/登录/验证码
    identity_api_base: str
    sms_internal_key: str

    # Rate limiting (MVP)
    kline_per_minute: int
    suggest_per_minute: int

    # Invite rewards (MVP)
    invite_reward_inviter_weekly: int
    invite_reward_invitee_weekly: int
    invite_weekly_cap: int
    invite_reward_inviter_daily: int
    invite_reward_invitee_daily: int

    # Market data robustness (MVP)
    kline_cache_ttl_s: float
    kline_fallback_sina: bool

    # Paid market-data provider (reserved; default off)
    paid_provider: str
    paid_provider_priority: str

    # TuShare Pro (optional paid provider)
    tushare_token: str
    tushare_use_rt_k: bool

    # WeChat Pay APIv3 (Native / JSAPI 共用商户参数；先接 Native 扫码调试)
    wechat_mch_id: str
    wechat_app_id: str
    wechat_mch_serial_no: str
    wechat_mch_private_key_path: str
    wechat_api_v3_key: str
    wechat_notify_url: str
    wechat_pay_host: str
    # 仅非 prod 且显式=1 时跳过回调验签（本地无公网 URL 时不要开）
    wechat_notify_skip_verify: bool
    price_vip_month_fen: int
    price_vip_year_fen: int
    price_vip_trial_fen: int
    # 体验卡额度：低于正式 VIP，避免「比月卡更划算」
    vip_trial_weekly: int
    vip_trial_daily_cap: int
    # 非 prod 且=1：微信下单按 dev_amount_fen 真实扣款（用于联调，勿上生产）
    billing_dev_real_pay: bool
    billing_dev_amount_fen: int


def load_settings() -> Settings:
    # In Windows/PM2 deployments, the process may inherit stale global env vars.
    # We prefer the per-service `.env` next to `api/server` as the single source of truth.
    load_dotenv(override=True)
    db_kind = str(os.getenv("AI24X_DB_KIND", "pgsql")).strip().lower()
    if db_kind in ("sqlite", "sqlite3"):
        raise RuntimeError("SQLite is disabled. Set AI24X_DB_KIND=pgsql and configure AI24X_DATABASE_URL.")
    if db_kind not in ("pg", "pgsql", "postgres", "postgresql"):
        raise RuntimeError(f"Unsupported AI24X_DB_KIND={db_kind!r}. Only pgsql is allowed.")
    return Settings(
        env=os.getenv("AI24X_ENV", "dev"),
        db_kind=db_kind,
        database_url=str(os.getenv("AI24X_DATABASE_URL", "")).strip(),
        db_path=os.getenv("AI24X_DB_PATH", "./data/ai24x.db"),
        jwt_secret=os.getenv("AI24X_JWT_SECRET", "change-me"),
        jwt_expire_days=_to_int(os.getenv("AI24X_JWT_EXPIRE_DAYS"), 7),
        admin_key=os.getenv("AI24X_ADMIN_KEY", "change-me-admin"),
        admin_mount_path=normalize_admin_mount(os.getenv("AI24X_ADMIN_MOUNT_PATH")),
        admin_login_max_per_15m=max(1, _to_int(os.getenv("AI24X_ADMIN_LOGIN_MAX_PER_15M"), 24)),
        admin_otp_phones=str(os.getenv("AI24X_ADMIN_OTP_PHONES", "")).strip(),
        admin_otp_ttl_s=max(60, _to_int(os.getenv("AI24X_ADMIN_OTP_TTL_S"), 300)),
        admin_otp_send_per_15m=max(1, _to_int(os.getenv("AI24X_ADMIN_OTP_SEND_PER_15M"), 8)),
        admin_otp_dev_code=str(os.getenv("AI24X_ADMIN_OTP_DEV_CODE", "")).strip(),
        # Quota (CN-first / mid-term product)
        free_daily_cap=_to_int(os.getenv("AI24X_FREE_DAILY_CAP"), 10),
        free_weekly=_to_int(os.getenv("AI24X_FREE_WEEKLY"), 50),
        vip_daily_cap=_to_int(os.getenv("AI24X_VIP_DAILY_CAP"), 150),
        vip_weekly=_to_int(os.getenv("AI24X_VIP_WEEKLY"), 500),
        dedupe_seconds=_to_int(os.getenv("AI24X_DEDUPE_SECONDS"), 60),
        cors_origins=os.getenv("AI24X_CORS_ORIGINS", "*"),
        identity_api_base=str(os.getenv("AI24X_IDENTITY_API_BASE", "")).strip().rstrip("/"),
        sms_internal_key=str(os.getenv("AI24X_SMS_INTERNAL_KEY", "")).strip(),
        kline_per_minute=_to_int(os.getenv("AI24X_KLINE_PER_MINUTE"), 60),
        suggest_per_minute=_to_int(os.getenv("AI24X_SUGGEST_PER_MINUTE"), 120),
        invite_reward_inviter_weekly=_to_int(os.getenv("AI24X_INVITE_REWARD_INVITER_WEEKLY"), 100),
        invite_reward_invitee_weekly=_to_int(os.getenv("AI24X_INVITE_REWARD_INVITEE_WEEKLY"), 50),
        invite_weekly_cap=_to_int(os.getenv("AI24X_INVITE_WEEKLY_CAP"), 500),
        invite_reward_inviter_daily=_to_int(os.getenv("AI24X_INVITE_REWARD_INVITER_DAILY"), 0),
        invite_reward_invitee_daily=_to_int(os.getenv("AI24X_INVITE_REWARD_INVITEE_DAILY"), 0),
        kline_cache_ttl_s=_to_float(os.getenv("AI24X_KLINE_CACHE_TTL_S"), 30.0),
        kline_fallback_sina=str(os.getenv("AI24X_KLINE_FALLBACK_SINA", "1")).strip() not in ("0", "false", "False", "no", "NO"),
        paid_provider=str(os.getenv("AI24X_PAID_PROVIDER", "off")).strip().lower(),
        # Default: paid first, public sources as backup.
        paid_provider_priority=str(os.getenv("AI24X_PAID_PROVIDER_PRIORITY", "paid,tencent,eastmoney,sina")).strip().lower(),
        tushare_token=str(os.getenv("AI24X_TUSHARE_TOKEN", "")).strip(),
        tushare_use_rt_k=str(os.getenv("AI24X_TUSHARE_USE_RT_K", "0")).strip() not in ("0", "false", "False", "no", "NO", ""),
        wechat_mch_id=str(os.getenv("AI24X_WECHAT_MCH_ID", "")).strip(),
        wechat_app_id=str(os.getenv("AI24X_WECHAT_APP_ID", "")).strip(),
        wechat_mch_serial_no=str(os.getenv("AI24X_WECHAT_MCH_SERIAL_NO", "")).strip(),
        wechat_mch_private_key_path=str(os.getenv("AI24X_WECHAT_MCH_PRIVATE_KEY_PATH", "")).strip(),
        wechat_api_v3_key=str(os.getenv("AI24X_WECHAT_API_V3_KEY", "")).strip(),
        wechat_notify_url=str(os.getenv("AI24X_WECHAT_NOTIFY_URL", "")).strip(),
        wechat_pay_host=str(os.getenv("AI24X_WECHAT_PAY_HOST", "https://api.mch.weixin.qq.com")).strip().rstrip("/")
        or "https://api.mch.weixin.qq.com",
        wechat_notify_skip_verify=str(os.getenv("AI24X_WECHAT_NOTIFY_SKIP_VERIFY", "0")).strip()
        in ("1", "true", "True", "yes", "YES")
        and str(os.getenv("AI24X_ENV", "dev")).strip().lower() != "prod",
        price_vip_month_fen=_to_int(os.getenv("AI24X_PRICE_VIP_MONTH_FEN"), 9900),
        price_vip_year_fen=_to_int(os.getenv("AI24X_PRICE_VIP_YEAR_FEN"), 99900),
        price_vip_trial_fen=_to_int(os.getenv("AI24X_PRICE_VIP_TRIAL_FEN"), 990),
        vip_trial_weekly=_to_int(os.getenv("AI24X_VIP_TRIAL_WEEKLY"), 100),
        vip_trial_daily_cap=_to_int(os.getenv("AI24X_VIP_TRIAL_DAILY_CAP"), 20),
        billing_dev_real_pay=str(os.getenv("AI24X_BILLING_DEV_REAL_PAY", "0")).strip()
        in ("1", "true", "True", "yes", "YES")
        and str(os.getenv("AI24X_ENV", "dev")).strip().lower() != "prod",
        billing_dev_amount_fen=_to_int(os.getenv("AI24X_BILLING_DEV_AMOUNT_FEN"), 10),
    )


settings = load_settings()

