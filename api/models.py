from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, Enum, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
import enum
from datetime import datetime

Base = declarative_base()


class UserType(str, enum.Enum):
    FREE = "free"
    VIP = "vip"


class User(Base):
    __tablename__ = "users"
    
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


class RateLimit(Base):
    __tablename__ = "rate_limits"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(255), index=True, nullable=False)
    window_type = Column(String(20), nullable=False)  # daily, monthly
    request_count = Column(Integer, default=0)
    window_start = Column(DateTime(timezone=True), nullable=False)
    window_end = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


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
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SmsSendLog(Base):
    """短信发送记录：用于审计、排障、用量统计"""
    __tablename__ = "sms_send_log"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    phone = Column(String(20), nullable=False, index=True)
    purpose = Column(String(50), nullable=False, default="login")  # login/register/forgot/admin
    provider = Column(String(50), nullable=False, default="106")  # 106/tencent/juhe
    template_text = Column(Text, nullable=True)   # 实际使用的模版（truncated）
    content_sent = Column(Text, nullable=True)    # 实际发送的内容
    status = Column(String(20), nullable=False, default="ok")  # ok/fail/blocked
    error_msg = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())