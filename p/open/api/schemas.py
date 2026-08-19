from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from enum import Enum


class UserType(str, Enum):
    FREE = "free"
    VIP = "vip"


class ChatRequest(BaseModel):
    # ⚠️ 主脑 2026-08-12 NUL 清洗：入口统一去 NUL(0x00)，防 PostgreSQL 写库拒绝导致流中断
    @field_validator("prompt", mode="before")
    @classmethod
    def _strip_nul_prompt(cls, v):
        if v is None:
            return v
        return str(v).replace("\x00", "")

    prompt: str = Field(..., min_length=1, max_length=200000, description="用户输入的提示词")
    model: Optional[str] = Field(
        default="auto",
        description="模型名或 auto（按 FREE/VIP 走 L0–L3 fallback）",
    )
    temperature: Optional[float] = Field(default=0.7, ge=0.0, le=2.0, description="温度参数")
    max_tokens: Optional[int] = Field(default=1000, ge=1, le=16384, description="最大token数")
    stream: Optional[bool] = Field(default=False, description="是否流式输出")
    # OpenAI messages 透传（真流式 / 多轮）；无则上游仍用 prompt 拼单轮
    messages: Optional[List[Dict[str, Any]]] = Field(default=None, description="OpenAI messages")
    # OpenAI tools / tool_choice（OpenClaw function calling）
    tools: Optional[List[Dict[str, Any]]] = Field(default=None, description="OpenAI tools")
    tool_choice: Optional[Any] = Field(default=None, description="OpenAI tool_choice")

    class Config:
        json_schema_extra = {
            "example": {
                "prompt": "你好，请介绍一下Python",
                "model": "auto",
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
    layer: Optional[str] = Field(None, description="路由层级 L0–L3")
    provider: Optional[str] = Field(None, description="stub / openai_compatible")
    route_attempts: Optional[List[Dict[str, Any]]] = Field(None, description="fallback 尝试记录")
    attribution: Optional[Dict[str, Any]] = Field(
        None, description="平台溯源与使用声明（防未授权转售追责）"
    )
    tool_calls: Optional[List[Dict[str, Any]]] = Field(
        None, description="OpenAI tool_calls（若模型请求调用工具）"
    )
    finish_reason: Optional[str] = Field(
        None, description="stop / tool_calls / length 等"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "request_id": "req_123456789",
                "response": "Python是一种高级编程语言...",
                "model": "flash",
                "token_count": 150,
                "processing_time": 1.5,
                "user_type": "free",
                "remaining_quota": 85,
                "created_at": "2024-01-01T12:00:00Z",
                "provider": "ai24x",
            }
        }


class SupportAskBody(BaseModel):
    """控制台 AI 即时协助（不扣用户余额）。"""

    question: str = Field(..., min_length=2, max_length=2000)
    lang: Optional[str] = Field(default=None, max_length=8)


class SupportTicketCreateBody(BaseModel):
    category: str = Field(default="api", max_length=32)
    subject: Optional[str] = Field(default=None, max_length=120)
    body: str = Field(..., min_length=10, max_length=4000)
    ai_summary: Optional[str] = Field(default=None, max_length=2000)


class SupportTicketReplyBody(BaseModel):
    reply: str = Field(..., min_length=1, max_length=4000)
    close: bool = False


class SupportTicketUserReplyBody(BaseModel):
    """用户侧工单追加消息（多轮会话）。"""

    content: str = Field(..., min_length=1, max_length=4000)


class ErrorResponse(BaseModel):
    error: str = Field(..., description="错误信息（默认中文短句；勿塞整包 dict）")
    code: str = Field(..., description="错误代码")
    request_id: Optional[str] = Field(None, description="请求ID")
    detail: Optional[Any] = Field(
        None,
        description="结构化 detail；双语时含 message_zh / message_en，供前端按界面语言选取",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "error": "超出每日请求限制",
                "code": "RATE_LIMIT_EXCEEDED",
                "request_id": "req_123456789",
                "detail": {
                    "message_zh": "超出每日请求限制",
                    "message_en": "Daily request limit exceeded.",
                    "message": "超出每日请求限制",
                },
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

    mobile: str = Field(..., min_length=10, max_length=32, description="手机号，国内建议 11 位")
    purpose: Literal["register", "login", "reset", "bind", "test"] = Field(
        default="test", description="用途（当前仅影响日志，模板共用）"
    )
    # 子站管理端 admin_config 下发时可选；须与主站 SMS_INTERNAL_KEY 一致；非空字段覆盖本机 .env
    sms_106_endpoint: Optional[str] = Field(default=None, max_length=512)
    sms_106_account: Optional[str] = Field(default=None, max_length=128)
    sms_106_password: Optional[str] = Field(default=None, max_length=128)
    sms_106_sign_name: Optional[str] = Field(default=None, max_length=64)
    sms_106_template: Optional[str] = Field(default=None, max_length=600)
    # 聚合数据 / 腾讯短信（可选扩展）
    sms_provider: Optional[str] = Field(default=None, max_length=50, description="sms provider: 106/tencent/juhe")
    sms_juhe_key: Optional[str] = Field(default=None, max_length=128)
    sms_juhe_tpl_id: Optional[str] = Field(default=None, max_length=64)
    sms_juhe_vars: Optional[str] = Field(default=None, max_length=600, description="JSON string of template vars e.g. {\"code\":\"123456\"}")
    sms_tencent_secret_id: Optional[str] = Field(default=None, max_length=128)
    sms_tencent_secret_key: Optional[str] = Field(default=None, max_length=128)
    sms_tencent_sdk_app_id: Optional[str] = Field(default=None, max_length=64)
    sms_tencent_sign: Optional[str] = Field(default=None, max_length=64)
    sms_tencent_template_id: Optional[str] = Field(default=None, max_length=64)
    sms_tencent_region: Optional[str] = Field(default=None, max_length=32)


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

    password: str = Field(..., min_length=8, max_length=128)
    phone: Optional[str] = None
    email: Optional[str] = None
    sms_code: Optional[str] = None
    email_code: Optional[str] = None
    invite_code: Optional[str] = Field(default=None, max_length=32)
    # 蜜罐字段：真实用户不会填写（前端隐藏），非空即判定为机器人
    website: Optional[str] = Field(default=None, max_length=256)
    # 广告 / 渠道首触（可选；落库后不覆盖）
    utm_source: Optional[str] = Field(default=None, max_length=128)
    utm_medium: Optional[str] = Field(default=None, max_length=128)
    utm_campaign: Optional[str] = Field(default=None, max_length=128)
    utm_content: Optional[str] = Field(default=None, max_length=128)
    utm_term: Optional[str] = Field(default=None, max_length=128)
    gclid: Optional[str] = Field(default=None, max_length=128)

    @field_validator("phone", "email", mode="before")
    @classmethod
    def strip_str(cls, v):
        if v is None:
            return None
        s = str(v).strip()
        return s or None

    @field_validator(
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_content",
        "utm_term",
        "gclid",
        mode="before",
    )
    @classmethod
    def strip_utm(cls, v):
        if v is None:
            return None
        s = str(v).strip()
        return s or None

    @model_validator(mode="after")
    def one_channel_and_codes(self):
        p, e = self.phone, self.email
        if p and e:
            raise ValueError("请只填写手机号或邮箱之一")
        if not p and not e:
            raise ValueError("请填写手机号或邮箱")
        if p:
            sc = (self.sms_code or "").strip()
            if len(sc) != 6 or not sc.isdigit():
                raise ValueError("请填写短信里的 6 位数字验证码")
        if e:
            ec = (self.email_code or "").strip()
            if len(ec) != 6 or not ec.isdigit():
                raise ValueError("请填写邮箱里的 6 位数字验证码")
        return self


class AuthEmailSendRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=255)
    purpose: Literal["register", "login", "reset"] = Field(default="register")
    captcha_token: Optional[str] = Field(default=None, max_length=64)
    captcha_answer: Optional[str] = Field(default=None, max_length=16)
    lang: Optional[str] = Field(None, description="zh / en；缺省按 Accept-Language 推断，默认 zh")


class AuthEmailSendResponse(BaseModel):
    ok: bool
    message: str
    channel: Optional[str] = Field(
        None, description="smtp=真实发信；local=本机联调卡片（非正式）"
    )
    local_code: Optional[str] = Field(
        None, description="仅 channel=local 时可能返回；正式环境恒为 null"
    )
    # 兼容旧前端字段名
    dev_code: Optional[str] = Field(None, description="同 local_code（兼容）")


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
    new_password: str = Field(..., min_length=8, max_length=128)


class AuthPasswordResetBody(BaseModel):
    new_password: str = Field(..., min_length=8, max_length=128)
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
        if p:
            sc = (self.sms_code or "").strip()
            if len(sc) != 6 or not sc.isdigit():
                raise ValueError("请填写短信里的 6 位数字验证码")
        if e:
            ec = (self.email_code or "").strip()
            if len(ec) != 6 or not ec.isdigit():
                raise ValueError("请填写邮箱里的 6 位数字验证码")
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
        if len(c) != 6 or not c.isdigit():
            raise ValueError("请填写短信里的 6 位数字验证码")
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
        if len(c) != 6 or not c.isdigit():
            raise ValueError("请填写邮箱里的 6 位数字验证码")
        return self


class AdminPasswordSetBody(BaseModel):
    """管理员强制设置密码（仅内部调用；需 X-SMS-Internal-Key）。"""

    user_id: Optional[int] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    new_password: str = Field(..., min_length=8, max_length=128)

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


class AdminUserBootstrapBody(BaseModel):
    """管理员：若用户不存在则创建，并设置密码（仅内部调用；需 X-SMS-Internal-Key）。"""

    phone: Optional[str] = None
    email: Optional[str] = None
    new_password: str = Field(..., min_length=8, max_length=128)

    @model_validator(mode="after")
    def one_channel(self) -> "AdminUserBootstrapBody":
        p = (self.phone or "").strip() or None
        e = (self.email or "").strip().lower() or None
        self.phone = p
        self.email = e
        if bool(p) == bool(e):
            raise ValueError("请只提供 phone 或 email 之一")
        return self
# —— Token MVP ——

# --- Token MVP ---


class ApiKeyCreateBody(BaseModel):
    name: str = Field(default="默认密钥", min_length=1, max_length=64)


class ApiKeyRenameBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)


class ApiKeyCreatedOut(BaseModel):
    id: int
    name: str
    api_key: str
    key_prefix: str
    created_at: Optional[str] = None
    is_active: bool = True
    warning: Optional[str] = None


class ApiKeyOut(BaseModel):
    id: int
    name: str
    key_prefix: str
    created_at: Optional[str] = None
    last_used_at: Optional[str] = None
    is_active: bool = True


class BillingBalanceOut(BaseModel):
    auth_user_id: int
    plan: str
    balance_tokens: int
    balance_usd: Optional[int] = None
    balance_usd_display: Optional[str] = None
    balance_cny_display: Optional[str] = None
    usd_cny: Optional[float] = None
    is_value_pack_active: Optional[bool] = None
    flash_ref_usd_per_m: Optional[float] = None
    bonus_period: Optional[str] = None
    free_monthly_bonus: int
    signup_bonus_tokens: Optional[int] = None
    vip_daily_bonus: int
    vip_expires_at: Optional[str] = None
    credits_expire_at: Optional[str] = None
    is_vip_active: bool = False
    email: Optional[str] = None
    prepaid_tokens: Optional[int] = None
    vip_daily_remaining: Optional[int] = None
    vip_daily_models: Optional[str] = None
    shared_enabled: Optional[bool] = None
    shared_auto_degrade: Optional[bool] = None
    shared_daily_req_cap: Optional[int] = None
    shared_daily_token_cap: Optional[int] = None
    shared_used_req: Optional[int] = None
    shared_used_tokens: Optional[int] = None
    shared_remain_req: Optional[int] = None
    shared_remain_tokens: Optional[int] = None


class BillingTopupBody(BaseModel):
    """Internal topup; requires X-SMS-Internal-Key."""

    auth_user_id: int = Field(..., ge=1)
    amount: int = Field(..., gt=0, description="token amount")
    note: Optional[str] = Field(default=None, max_length=255)
    set_vip: bool = Field(default=False, description="also upgrade to VIP")
    validity_days: Optional[int] = Field(
        default=None, ge=1, le=3650, description="credit lot validity days; default 365"
    )


class TokenPayCreateBody(BaseModel):
    plan: str = Field(..., min_length=4, max_length=64)
    product: str = Field(default="token", max_length=16, description="token / byok")


class TokenMockFulfillBody(BaseModel):
    out_trade_no: str = Field(..., min_length=4, max_length=32)


class TokenQueryFulfillBody(BaseModel):
    out_trade_no: str = Field(..., min_length=4, max_length=32)


class TokenCryptoSubmitBody(BaseModel):
    out_trade_no: str = Field(..., min_length=4, max_length=32)
    txid: str = Field(..., min_length=8, max_length=128, description="TRC20 transaction hash")


class TokenAdminSystemUpdateBody(BaseModel):
    token_pay_enabled: Optional[bool] = None
    token_pay_mock_enabled: Optional[bool] = None
    sms_106_enabled: Optional[bool] = None
    token_llm_upstream: Optional[str] = Field(default=None, max_length=32)
    clear: Optional[list[str]] = Field(default=None, max_length=16)


class TokenAdminWarehouseLayerPatch(BaseModel):
    layer: str = Field(..., min_length=1, max_length=8)
    model: Optional[str] = Field(default=None, max_length=128)
    enabled: Optional[bool] = None


class TokenAdminVipRatePatch(BaseModel):
    id: str = Field(..., min_length=1, max_length=64)
    billing_mult: Optional[int] = Field(default=None, ge=1, le=200)
    cost_in: Optional[float] = Field(default=None, ge=0, le=1000)
    cost_out: Optional[float] = Field(default=None, ge=0, le=1000)
    enabled: Optional[bool] = None


class TokenAdminWarehouseUpdateBody(BaseModel):
    layers: Optional[list[TokenAdminWarehouseLayerPatch]] = Field(default=None, max_length=16)
    vip_pick_enabled: Optional[bool] = None
    vip_pick_models: Optional[list[str]] = Field(default=None, max_length=32)
    note: Optional[str] = Field(default=None, max_length=200)
    vip_rates: Optional[list[TokenAdminVipRatePatch]] = Field(default=None, max_length=64)
    layer_mult: Optional[dict[str, int]] = None


class TokenAdminFreeSharedUpdateBody(BaseModel):
    enabled: Optional[bool] = None
    daily_req_cap: Optional[int] = Field(default=None, ge=1, le=500)
    daily_token_cap: Optional[int] = Field(default=None, ge=1000, le=2_000_000)
    prefer: Optional[str] = Field(default=None, max_length=64)
    pool_enabled: Optional[list[str]] = Field(default=None, max_length=16)
    upgrade_first: Optional[bool] = None
    auto_degrade: Optional[bool] = None
    brand_model: Optional[str] = Field(default=None, max_length=32)
    dispatch_mode: Optional[str] = Field(default=None, max_length=32)


class TokenAdminLlmKeysUpdateBody(BaseModel):
    OPENROUTER_API_KEY: Optional[str] = Field(default=None, max_length=256)
    OPENROUTER_API_KEY_FREE: Optional[str] = Field(default=None, max_length=256)
    SILICONFLOW_API_KEY: Optional[str] = Field(default=None, max_length=256)
    SILICONFLOW_API_KEY_FREE: Optional[str] = Field(default=None, max_length=256)
    DEEPSEEK_API_KEY: Optional[str] = Field(default=None, max_length=256)
    TOGETHER_API_KEY: Optional[str] = Field(default=None, max_length=256)
    OPENAI_API_KEY: Optional[str] = Field(default=None, max_length=256)
    ANTHROPIC_API_KEY: Optional[str] = Field(default=None, max_length=256)
    GOOGLE_AI_API_KEY: Optional[str] = Field(default=None, max_length=256)
    clear: Optional[list[str]] = Field(default=None, max_length=16)

