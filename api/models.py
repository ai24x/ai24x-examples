from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, Enum, Float, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import validates
from sqlalchemy.sql import func
import enum

Base = declarative_base()


class UserType(str, enum.Enum):
    FREE = "free"
    VIP = "vip"


class User(Base):
    __tablename__ = "token_gateway_users"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(255), unique=True, index=True, nullable=False)
    user_type = Column(Enum(UserType), default=UserType.FREE, nullable=False)
    api_key = Column(String(255), unique=True, index=True, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    is_active = Column(Boolean, default=True)

    # Rate limiting
    daily_request_limit = Column(Integer, default=100)  # Free users
    monthly_request_limit = Column(Integer, default=3000)
    current_daily_requests = Column(Integer, default=0)
    current_monthly_requests = Column(Integer, default=0)


class ChatRequest(Base):
    __tablename__ = "chat_requests"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(String(255), unique=True, index=True, nullable=False)
    user_id = Column(String(255), index=True, nullable=False)
    user_type = Column(Enum(UserType), nullable=False)

    # Request data
    prompt = Column(Text, nullable=False)
    model = Column(String(100), nullable=True)
    temperature = Column(Float, default=0.7)
    max_tokens = Column(Integer, default=1000)

    # Response data
    response = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)

    # Metadata
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)

    # Timing
    request_time = Column(DateTime(timezone=True), server_default=func.now())
    response_time = Column(DateTime(timezone=True), nullable=True)
    processing_duration = Column(Float, nullable=True)  # in seconds

    # Status
    status = Column(String(50), default="pending")  # pending, processing, completed, failed
    is_success = Column(Boolean, default=False)

    # Billing/usage
    token_count = Column(Integer, default=0)
    cost = Column(Float, default=0.0)

    # ⚠️ 主脑 2026-08-12 NUL 清洗：PostgreSQL 拒绝 NUL(0x00) 字符，写库字符串统一去 NUL 防断流（创建/更新均生效）
    @validates("prompt", "response", "error_message", "user_agent")
    def _strip_nul(self, key: str, value):
        if isinstance(value, str) and "\x00" in value:
            return value.replace("\x00", "")
        return value


class RateLimit(Base):
    __tablename__ = "rate_limits"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(255), index=True, nullable=False)
    window_type = Column(String(20), nullable=False)  # daily, monthly
    request_count = Column(Integer, default=0)
    window_start = Column(DateTime(timezone=True), nullable=False)
    window_end = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class VipNamedDailyUsage(Base):
    """P2 保护：单用户单模型每日点名模用量计数（超限拒绝点名，防国际旗舰倒挂被刷）。"""

    __tablename__ = "vip_named_daily_usage"
    __table_args__ = (
        UniqueConstraint("auth_user_id", "model_id", "usage_date", name="uq_vip_named_daily_usage"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    auth_user_id = Column(Integer, index=True, nullable=False)
    model_id = Column(String(100), index=True, nullable=False)
    usage_date = Column(String(10), index=True, nullable=False)  # UTC YYYY-MM-DD
    call_count = Column(Integer, default=0, nullable=False)
    credits_used = Column(Integer, default=0, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AuthUser(Base):
    """
    终端用户账号（手机/邮箱 + 密码），供 www、a 子域等共用。
    与 chat 网关用的 `User`（api_key 计次）表分离。
    """

    __tablename__ = "auth_users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    phone = Column(String(20), unique=True, nullable=True, index=True)
    email = Column(String(255), unique=True, nullable=True, index=True)
    password_hash = Column(String(255), nullable=False)
    phone_verified_at = Column(DateTime(timezone=True), nullable=True)
    email_verified_at = Column(DateTime(timezone=True), nullable=True)
    # 冻结：非空即冻结（禁登录 / chat / 充值）；管理台可解冻
    frozen_at = Column(DateTime(timezone=True), nullable=True)
    freeze_reason = Column(String(255), nullable=True)
    # 获客首触（广告 UTM / gclid）；注册时写入，不随后续访问覆盖
    utm_source = Column(String(128), nullable=True, index=True)
    utm_medium = Column(String(128), nullable=True)
    utm_campaign = Column(String(128), nullable=True, index=True)
    utm_content = Column(String(128), nullable=True)
    utm_term = Column(String(128), nullable=True)
    gclid = Column(String(128), nullable=True, index=True)
    acquired_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SmsSendLog(Base):
    """短信发送记录：用于审计、排障、用量统计"""

    __tablename__ = "sms_send_log"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    phone = Column(String(20), nullable=False, index=True)
    purpose = Column(String(50), nullable=False, default="login")  # login/register/forgot/admin
    provider = Column(String(50), nullable=False, default="106")  # 106/tencent/juhe
    template_text = Column(Text, nullable=True)  # 实际使用的模版（截断）
    content_sent = Column(Text, nullable=True)  # 实际发送的内容
    status = Column(String(20), nullable=False, default="ok")  # ok/fail/blocked
    error_msg = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class BillingPlan(str, enum.Enum):
    FREE = "free"
    VIP = "vip"


class ApiKey(Base):
    """终端用户 API Key（绑 auth_users；chat/run 鉴权）。"""

    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    auth_user_id = Column(
        Integer, ForeignKey("auth_users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name = Column(String(64), nullable=False, default="默认密钥")
    api_key = Column(String(128), unique=True, nullable=False, index=True)
    key_prefix = Column(String(16), nullable=False, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)


class TokenWallet(Base):
    """Token 钱包：balance_usd 为主余额（美分），balance_tokens 为内部核算单位。"""

    __tablename__ = "token_wallets"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    auth_user_id = Column(
        Integer, ForeignKey("auth_users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    plan = Column(Enum(BillingPlan), default=BillingPlan.FREE, nullable=False)
    balance_tokens = Column(Integer, default=0, nullable=False)
    balance_usd = Column(Integer, default=0, nullable=False)  # USD 美分（主余额） 2026-08-03
    bonus_period = Column(String(16), nullable=True)
    vip_expires_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class TokenCreditLot(Base):
    """
    预充值/赠送额度批次：按到期日 FIFO 扣费。
    remaining=0 表示已用尽或已过期核销。
    """

    __tablename__ = "token_credit_lots"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    auth_user_id = Column(
        Integer, ForeignKey("auth_users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source = Column(String(16), nullable=False, default="topup")  # topup/bonus/vip_daily/referral/legacy
    plan = Column(String(64), nullable=True)
    amount_initial = Column(Integer, nullable=False)
    amount_remaining = Column(Integer, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    ledger_id = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class BillingLedger(Base):
    """计费流水：正数入账，负数消耗。amount 为 token，amount_usd 为美分。"""

    __tablename__ = "billing_ledger"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    auth_user_id = Column(
        Integer, ForeignKey("auth_users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entry_type = Column(String(16), nullable=False)  # consume / topup / bonus / referral / expire
    amount = Column(Integer, nullable=False)
    amount_usd = Column(Integer, default=0, nullable=False)  # USD 美分（消耗为负）2026-08-03
    model = Column(String(64), nullable=True)
    tokens = Column(Integer, nullable=True)
    prompt_tokens = Column(Integer, nullable=True)       # 2026-08-15: 输入 Token 拆分（上游 usage）
    completion_tokens = Column(Integer, nullable=True)   # 2026-08-15: 输出 Token 拆分
    api_key_id = Column(Integer, nullable=True, index=True)  # 2026-08-15: 按 API Key 统计（JWT 会话为空）
    request_id = Column(String(64), nullable=True, index=True)
    note = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class InviteCode(Base):
    """用户邀请码（一对一）。"""

    __tablename__ = "token_invite_codes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    auth_user_id = Column(
        Integer, ForeignKey("auth_users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    code = Column(String(16), unique=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Referral(Base):
    """推荐关系与返利记录。"""

    __tablename__ = "token_referrals"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    referrer_id = Column(
        Integer, ForeignKey("auth_users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    referee_id = Column(
        Integer, ForeignKey("auth_users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    level = Column(Integer, default=1, nullable=False)
    reward_tokens = Column(Integer, default=0, nullable=False)
    status = Column(String(16), default="pending", nullable=False)
    topup_ledger_id = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class TokenPayOrder(Base):
    """
    Token 产品支付订单（独立于 a1 的 pay_orders）。
    out_trade_no 前缀 T；product 固定 token。
    """

    __tablename__ = "token_pay_orders"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    out_trade_no = Column(String(32), unique=True, nullable=False, index=True)
    auth_user_id = Column(
        Integer, ForeignKey("auth_users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    plan = Column(String(64), nullable=False)
    amount_fen = Column(Integer, nullable=False)
    amount_usd = Column(Integer, default=0, nullable=False)  # USD 美分（实际到账）2026-08-03
    channel = Column(String(16), nullable=False, default="wechat")
    status = Column(String(16), nullable=False, default="pending")  # pending/paid/failed
    code_url = Column(Text, nullable=True)
    transaction_id = Column(String(128), nullable=True, index=True)
    product = Column(String(16), nullable=False, default="token")
    paid_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    confirmed_unpaid_at = Column(DateTime(timezone=True), nullable=True)  # 非空=对账确认未收款，值=确认时间


class SupportTicket(Base):
    """主站 Token 人工工单（与行情官 user_feedback 隔离）。"""

    __tablename__ = "token_support_tickets"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    auth_user_id = Column(
        Integer, ForeignKey("auth_users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category = Column(String(32), nullable=False, default="api")  # billing/api/account/suggestion/complaint
    subject = Column(String(120), nullable=False, default="")
    body = Column(Text, nullable=False)
    ai_summary = Column(Text, nullable=True)
    status = Column(String(16), nullable=False, default="open", index=True)  # open/replied/closed
    admin_reply = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SupportTicketMessage(Base):
    """工单对话消息（2026-08-15：工单升级为多轮会话）。"""

    __tablename__ = "token_support_ticket_messages"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    ticket_id = Column(
        Integer, ForeignKey("token_support_tickets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sender = Column(String(16), nullable=False, default="user")  # user / system / admin
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
