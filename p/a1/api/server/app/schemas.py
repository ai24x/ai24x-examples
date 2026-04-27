from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class AdminLoginIn(BaseModel):
    """管理后台浏览器登录：管理密钥；若启用 OTP 白名单则须同时提交 phone + otp。"""

    key: str = Field(min_length=1, max_length=512)
    phone: str | None = Field(default=None, max_length=20)
    otp: str | None = Field(default=None, max_length=16)


class AdminOtpSendIn(BaseModel):
    """向白名单手机号发送管理后台登录验证码（须已配置主站短信或开发态 dev_code）。"""

    phone: str = Field(min_length=10, max_length=20)


class RequestCodeIn(BaseModel):
    email: str = Field(min_length=6, max_length=128)
    phone: str | None = Field(default=None, min_length=6, max_length=32)
    purpose: str = Field(default="register", max_length=32)


class RequestCodeOut(BaseModel):
    ok: bool
    dev_code: str | None = None
    message: str | None = None


class LoginIn(BaseModel):
    email: str | None = Field(default=None, max_length=128)
    phone: str | None = Field(default=None, max_length=32)
    password: str | None = Field(default=None, min_length=1, max_length=128)
    code: str | None = Field(default=None, max_length=16)


class RegisterIn(BaseModel):
    password: str = Field(min_length=6, max_length=128)
    phone: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=128)
    sms_code: str | None = Field(default=None, max_length=16)
    email_code: str | None = Field(default=None, max_length=16)

    @model_validator(mode="after")
    def one_register_channel(self) -> "RegisterIn":
        p = (self.phone or "").strip() or None
        e = (self.email or "").strip() or None
        self.phone = p
        self.email = e.lower() if e else None
        if bool(p) == bool(e):
            raise ValueError("请只填写手机号或邮箱之一")
        if p and not (self.sms_code or "").strip():
            raise ValueError("手机注册请填写短信验证码")
        if e and not (self.email_code or "").strip():
            raise ValueError("邮箱注册请填写邮箱验证码")
        return self


class SmsSendProxyIn(BaseModel):
    mobile: str = Field(min_length=10, max_length=20)
    purpose: str = Field(default="register", max_length=32)
    # Reserved: enable SMS captcha (e.g. Turnstile) via admin config later.
    captcha_token: str | None = Field(default=None, max_length=4096)


class LoginOut(BaseModel):
    token: str
    user: dict


class PasswordChangeIn(BaseModel):
    old_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=6, max_length=128)


class PasswordResetIn(BaseModel):
    new_password: str = Field(min_length=6, max_length=128)
    phone: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=128)
    sms_code: str | None = Field(default=None, max_length=16)
    email_code: str | None = Field(default=None, max_length=16)

    @model_validator(mode="after")
    def one_reset_channel(self) -> "PasswordResetIn":
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


class QuotaConsumeIn(BaseModel):
    secid: str
    period: str
    ok: bool = True
    idempotency_key: str


class QuotaConsumeOut(BaseModel):
    result: str
    deduped: bool
    consumed_at: int
    quota: dict | None = None


class InviteBindIn(BaseModel):
    code: str = Field(min_length=3, max_length=32)


class FeedbackCreateIn(BaseModel):
    """用户反馈工单（须登录）；分类与后台 `user_feedback.category` 对齐。"""

    category: str = Field(min_length=2, max_length=32)
    title: str = Field(default="", max_length=200)
    body: str = Field(min_length=5, max_length=8000)
    contact: str = Field(default="", max_length=200)


class PayNativeIn(BaseModel):
    """下单套餐：与 quota.plan 口径一致（体验 / 月 / 年）。"""

    plan: str = Field(min_length=6, max_length=32)


class PayNativeOut(BaseModel):
    out_trade_no: str
    code_url: str
    # 真值：用于对账/返佣/日志
    amount_fen: int
    priced_amount_fen: int
    # 展示：用于前台/后台避免看错（字符串，已按 2 位小数格式化）
    amount_yuan_display: str
    priced_amount_yuan_display: str
    plan: str


class PayWapIn(BaseModel):
    """支付宝 H5 下单：与 quota.plan 口径一致（体验 / 月 / 年）。"""

    plan: str = Field(min_length=6, max_length=32)


class PayWapOut(BaseModel):
    out_trade_no: str
    pay_url: str
    # 真值：用于对账/返佣/日志
    amount_fen: int
    priced_amount_fen: int
    # 展示：用于前台/后台避免看错（字符串，已按 2 位小数格式化）
    amount_yuan_display: str
    priced_amount_yuan_display: str
    plan: str

