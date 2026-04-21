from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from enum import Enum


class UserType(str, Enum):
    FREE = "free"
    VIP = "vip"


class ChatRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=10000, description="用户输入的提示词")
    model: Optional[str] = Field(default="gpt-3.5-turbo", description="使用的模型名称")
    temperature: Optional[float] = Field(default=0.7, ge=0.0, le=2.0, description="温度参数")
    max_tokens: Optional[int] = Field(default=1000, ge=1, le=4000, description="最大token数")
    stream: Optional[bool] = Field(default=False, description="是否流式输出")
    
    class Config:
        json_schema_extra = {
            "example": {
                "prompt": "你好，请介绍一下Python",
                "model": "gpt-3.5-turbo",
                "temperature": 0.7,
                "max_tokens": 1000,
                "stream": False
            }
        }


class ChatResponse(BaseModel):
    request_id: str = Field(..., description="请求ID")
    response: str = Field(..., description="AI回复内容")
    model: str = Field(..., description="使用的模型")
    token_count: int = Field(..., description="消耗的token数量")
    processing_time: float = Field(..., description="处理时间（秒）")
    user_type: UserType = Field(..., description="用户类型")
    remaining_quota: Optional[int] = Field(None, description="剩余配额")
    created_at: datetime = Field(..., description="创建时间")
    
    class Config:
        json_schema_extra = {
            "example": {
                "request_id": "req_123456789",
                "response": "Python是一种高级编程语言...",
                "model": "gpt-3.5-turbo",
                "token_count": 150,
                "processing_time": 1.5,
                "user_type": "free",
                "remaining_quota": 85,
                "created_at": "2024-01-01T12:00:00Z"
            }
        }


class ErrorResponse(BaseModel):
    error: str = Field(..., description="错误信息")
    code: str = Field(..., description="错误代码")
    request_id: Optional[str] = Field(None, description="请求ID")
    
    class Config:
        json_schema_extra = {
            "example": {
                "error": "超出每日请求限制",
                "code": "RATE_LIMIT_EXCEEDED",
                "request_id": "req_123456789"
            }
        }


class UserInfo(BaseModel):
    user_id: str = Field(..., description="用户ID")
    user_type: UserType = Field(..., description="用户类型")
    daily_limit: int = Field(..., description="每日请求限制")
    monthly_limit: int = Field(..., description="每月请求限制")
    daily_used: int = Field(..., description="今日已使用")
    monthly_used: int = Field(..., description="本月已使用")
    is_active: bool = Field(..., description="是否激活")
    created_at: datetime = Field(..., description="创建时间")


class SmsSendRequest(BaseModel):
    """联调发送短信验证码（内容按模板拼验证码；须与 106 平台审核文案一致）。"""

    mobile: str = Field(..., min_length=10, max_length=20, description="手机号，国内建议 11 位")
    purpose: Literal["register", "login", "reset", "test"] = Field(
        default="test", description="用途（当前仅影响日志，模板共用）"
    )
    # 子站管理端 admin_config 下发时可选；须与主站 SMS_INTERNAL_KEY 一致；非空字段覆盖本机 .env
    sms_106_endpoint: Optional[str] = Field(default=None, max_length=512)
    sms_106_account: Optional[str] = Field(default=None, max_length=128)
    sms_106_password: Optional[str] = Field(default=None, max_length=128)
    sms_106_sign_name: Optional[str] = Field(default=None, max_length=64)
    sms_106_template: Optional[str] = Field(default=None, max_length=600)


class SmsSendResponse(BaseModel):
    ok: bool
    provider: str = "106jiekou"
    raw: str
    message: str
    cooldown_s: Optional[float] = Field(None, description="若因冷却被拒绝，剩余秒数")


class InternalSmsVerifyConsumeIn(BaseModel):
    """服务端带 X-SMS-Internal-Key 调用：校验并消费与 /v1/auth/sms/send 同存储的短信 OTP。"""

    mobile: str = Field(..., min_length=10, max_length=20)
    purpose: str = Field(default="login", max_length=32)
    code: str = Field(..., min_length=4, max_length=16)


class AuthRegisterBody(BaseModel):
    """手机注册须短信验证码；邮箱注册须邮箱验证码（进程内 OTP，生产换 Redis+邮件）。"""

    password: str = Field(..., min_length=6, max_length=128)
    phone: Optional[str] = None
    email: Optional[str] = None
    sms_code: Optional[str] = None
    email_code: Optional[str] = None

    @field_validator("phone", "email", mode="before")
    @classmethod
    def strip_str(cls, v):
        if v is None:
            return None
        s = str(v).strip()
        return s or None

    @model_validator(mode="after")
    def one_channel_and_codes(self):
        p, e = self.phone, self.email
        if p and e:
            raise ValueError("仅支持填写手机号或邮箱之一")
        if not p and not e:
            raise ValueError("请填写手机号或邮箱")
        if p:
            sc = (self.sms_code or "").strip()
            if len(sc) != 6 or not sc.isdigit():
                raise ValueError("手机注册需填写 6 位数字验证码")
        if e:
            ec = (self.email_code or "").strip()
            if len(ec) != 6 or not ec.isdigit():
                raise ValueError("邮箱注册需填写 6 位数字验证码")
        return self


class AuthEmailSendRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=255)
    purpose: Literal["register", "login", "reset"] = Field(default="register")


class AuthEmailSendResponse(BaseModel):
    ok: bool
    message: str
    dev_code: Optional[str] = Field(None, description="非生产环境可选返回，便于联调")


class AuthLoginBody(BaseModel):
    password: str = Field(..., min_length=1, max_length=128)
    phone: Optional[str] = None
    email: Optional[str] = None

    @field_validator("phone", "email", mode="before")
    @classmethod
    def strip_login(cls, v):
        if v is None:
            return None
        s = str(v).strip()
        return s or None

    @model_validator(mode="after")
    def one_login_channel(self):
        p, e = self.phone, self.email
        if bool(p) == bool(e):
            raise ValueError("请只填写手机号或邮箱之一")
        if e:
            self.email = e.lower()
        return self


class AuthTokenResponse(BaseModel):
    token: str
    user: dict


class AuthPasswordChangeBody(BaseModel):
    old_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=6, max_length=128)


class AuthPasswordResetBody(BaseModel):
    new_password: str = Field(..., min_length=6, max_length=128)
    phone: Optional[str] = None
    email: Optional[str] = None
    sms_code: Optional[str] = None
    email_code: Optional[str] = None

    @model_validator(mode="after")
    def one_reset_channel(self) -> "AuthPasswordResetBody":
        p = (self.phone or "").strip() or None
        e = (self.email or "").strip().lower() or None
        self.phone = p
        self.email = e
        if bool(p) == bool(e):
            raise ValueError("请只填写手机号或邮箱之一")
        if p and not (self.sms_code or "").strip():
            raise ValueError("手机找回请填写短信验证码")
        if e and not (self.email_code or "").strip():
            raise ValueError("邮箱找回请填写邮箱验证码")
        return self


class AuthBindPhoneBody(BaseModel):
    phone: str = Field(..., min_length=10, max_length=20)
    sms_code: str = Field(..., min_length=4, max_length=16)

    @model_validator(mode="after")
    def v(self) -> "AuthBindPhoneBody":
        p = (self.phone or "").strip()
        c = (self.sms_code or "").strip()
        self.phone = p
        self.sms_code = c
        if not p:
            raise ValueError("请填写手机号")
        if not c:
            raise ValueError("请填写短信验证码")
        return self


class AuthBindEmailBody(BaseModel):
    email: str = Field(..., min_length=5, max_length=255)
    email_code: str = Field(..., min_length=4, max_length=16)

    @model_validator(mode="after")
    def v(self) -> "AuthBindEmailBody":
        e = (self.email or "").strip().lower()
        c = (self.email_code or "").strip()
        self.email = e
        self.email_code = c
        if not e or "@" not in e:
            raise ValueError("邮箱格式不正确")
        if not c:
            raise ValueError("请填写邮箱验证码")
        return self


class AdminPasswordSetBody(BaseModel):
    """管理员强制设置密码（仅内部调用；需 X-SMS-Internal-Key）。"""

    user_id: Optional[int] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    new_password: str = Field(..., min_length=6, max_length=128)

    @model_validator(mode="after")
    def one_user_selector(self) -> "AdminPasswordSetBody":
        uid = self.user_id
        p = (self.phone or "").strip() or None
        e = (self.email or "").strip().lower() or None
        self.phone = p
        self.email = e
        if uid is None and not p and not e:
            raise ValueError("请提供 user_id 或 phone/email")
        if p and e:
            raise ValueError("请只提供 phone 或 email 之一")
        return self


class AdminUserContactSetBody(BaseModel):
    """管理员强制设置用户绑定信息（仅内部调用；需 X-SMS-Internal-Key）。"""

    user_id: int = Field(..., ge=1)
    phone: Optional[str] = None
    email: Optional[str] = None

    @model_validator(mode="after")
    def one_channel(self) -> "AdminUserContactSetBody":
        p = (self.phone or "").strip() or None
        e = (self.email or "").strip().lower() or None
        self.phone = p
        self.email = e
        if bool(p) == bool(e):
            raise ValueError("请只填写手机号或邮箱之一")
        return self