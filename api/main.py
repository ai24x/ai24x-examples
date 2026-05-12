from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
import logging
import time

from database import get_db, init_db
from models import AuthUser, SmsSendLog
from schemas import (
    AuthEmailSendRequest,
    AuthEmailSendResponse,
    AuthLoginBody,
    AuthPasswordChangeBody,
    AuthPasswordResetBody,
    AuthBindPhoneBody,
    AuthBindEmailBody,
    AuthRegisterBody,
    AuthTokenResponse,
    AdminPasswordSetBody,
    AdminUserContactSetBody,
    AdminUserBootstrapBody,
    ChatRequest,
    ChatResponse,
    ErrorResponse,
    InternalSmsVerifyConsumeIn,
    SmsSendRequest,
    SmsSendResponse,
)
from services import AuthService, UserService, ChatService
from config import settings
from sms_106_client import (
    check_send_cooldown,
    generate_numeric_code,
    mark_sent,
    normalize_mobile,
    send_sms_106,
)
from email_otp_memory import store_otp as store_email_otp
from email_otp_memory import verify_and_consume_otp as verify_email_otp
from auth_tokens import create_auth_access_token
from auth_user_service import (
    authenticate_password,
    admin_set_contact,
    admin_set_password,
    bind_email_for_user,
    bind_phone_for_user,
    change_password_for_user,
    create_user_email,
    create_user_phone,
    get_by_email,
    get_by_phone,
    norm_email,
    reset_password_email,
    reset_password_phone,
)
from sms_abuse_guard import check_before_send, client_ip, record_attempt
from sms_otp_memory import store_otp, verify_and_consume_otp

# 配置日志
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 邮箱验证码发送冷却（进程内；多实例需 Redis）
_auth_email_last_sent: dict[str, float] = {}

# 创建FastAPI应用
app = FastAPI(
    title="AI24X API",
    description="AI24X Token aggregation platform — unified multi-model API gateway (PostgreSQL via SQLAlchemy).",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境中应限制来源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 中间件：记录请求日志
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    
    # 获取客户端信息
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    
    response = await call_next(request)
    
    process_time = time.time() - start_time
    logger.info(
        f"{request.method} {request.url.path} - "
        f"Status: {response.status_code} - "
        f"Time: {process_time:.3f}s - "
        f"IP: {ip_address}"
    )
    
    return response


# 中间件：速率限制（简化版）
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if not settings.enable_rate_limiting:
        return await call_next(request)
    
    # 实际项目中这里会有更复杂的速率限制逻辑
    # 例如：基于IP、用户ID、API key等
    
    return await call_next(request)


# 依赖项：获取当前用户
def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
):
    """从请求头获取当前用户"""
    # 从Header获取API Key
    api_key = request.headers.get("X-API-Key")
    
    # 从查询参数获取用户ID（用于测试）
    user_id = request.query_params.get("user_id")
    
    user = AuthService.authenticate_user(db, api_key=api_key, user_id=user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的API Key或用户ID"
        )
    
    # 检查速率限制
    allowed, error_msg = UserService.check_rate_limit(db, user)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=error_msg
        )
    
    return user


# 健康检查端点
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "AI24X API",
        "version": "1.0.0",
        "timestamp": time.time()
    }


# 主接口：/v1/chat/run
@app.post("/v1/chat/run", response_model=ChatResponse)
async def chat_run(
    request: ChatRequest,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
    http_request: Request = None
):
    """
    处理聊天请求
    
    - **prompt**: 用户输入的提示词
    - **model**: 使用的模型名称（可选）
    - **temperature**: 温度参数（可选）
    - **max_tokens**: 最大token数（可选）
    - **stream**: 是否流式输出（可选）
    
    返回AI回复和请求详情
    """
    try:
        # 获取客户端信息
        ip_address = http_request.client.host if http_request.client else None
        user_agent = http_request.headers.get("user-agent")
        
        # 处理聊天请求
        response = ChatService.process_chat_request(
            db=db,
            user=current_user,
            request=request,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        logger.info(f"Chat request processed: {response.request_id} for user: {current_user.user_id}")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing chat request: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"处理请求时发生错误: {str(e)}"
        )


# 用户信息端点
@app.get("/v1/user/info")
async def get_user_info(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取当前用户信息"""
    return {
        "user_id": current_user.user_id,
        "user_type": current_user.user_type.value,
        "daily_limit": current_user.daily_request_limit,
        "monthly_limit": current_user.monthly_request_limit,
        "daily_used": current_user.current_daily_requests,
        "monthly_used": current_user.current_monthly_requests,
        "remaining_daily": current_user.daily_request_limit - current_user.current_daily_requests,
        "remaining_monthly": current_user.monthly_request_limit - current_user.current_monthly_requests,
        "is_active": current_user.is_active,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None
    }


def _http_detail_str(detail: object) -> str:
    if isinstance(detail, str):
        return detail
    return str(detail)


# 全局异常处理
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    body = ErrorResponse(
        error=_http_detail_str(exc.detail),
        code=str(int(exc.status_code)),
        request_id=request.headers.get("X-Request-ID"),
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=body.model_dump(),
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    # Log full traceback for server-side debugging (front-end receives a generic 500 message).
    logger.exception("Unhandled exception")
    body = ErrorResponse(
        error="服务器内部错误",
        code="INTERNAL_SERVER_ERROR",
        request_id=request.headers.get("X-Request-ID"),
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=body.model_dump(),
    )


# 应用启动事件
@app.on_event("startup")
async def startup_event():
    """应用启动时初始化数据库"""
    logger.info("Starting AI24X API...")
    if getattr(settings, "sms_106_enabled", False) and not getattr(settings, "sms_internal_key", ""):
        logger.warning(
            "SMS_106_ENABLED=true but SMS_INTERNAL_KEY empty — anyone can call /v1/auth/sms/send; set SMS_INTERNAL_KEY for production."
        )
    if getattr(settings, "skip_db_init", False):
        logger.warning("SKIP_DB_INIT enabled: database initialization skipped")
        return
    try:
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {str(e)}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时清理资源"""
    logger.info("Shutting down AI24X API...")


# —— 短信：106 网关（联调；生产务必配置 SMS_INTERNAL_KEY）——
@app.post("/v1/auth/sms/send", response_model=SmsSendResponse)
async def auth_sms_send(request: Request, body: SmsSendRequest, db: Session = Depends(get_db)):
    if not settings.sms_106_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SMS disabled: set SMS_106_ENABLED=true and credentials in environment.",
        )
    if settings.sms_internal_key and request.headers.get("X-SMS-Internal-Key") != settings.sms_internal_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing or invalid X-SMS-Internal-Key.",
        )

    def _pick(override: str | None, base: str) -> str:
        o = (override or "").strip()
        return o if o else (base or "").strip()

    endpoint = _pick(body.sms_106_endpoint, settings.sms_106_endpoint)
    account = _pick(body.sms_106_account, settings.sms_106_account)
    password = _pick(body.sms_106_password, settings.sms_106_password)
    sign_name_use = _pick(body.sms_106_sign_name, settings.sms_106_sign_name)
    template_use = _pick(body.sms_106_template, settings.sms_106_template)

    if not account or not password:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SMS 106 not configured: SMS_106_ACCOUNT / SMS_106_PASSWORD missing (env or request body with valid internal key).",
        )

    mob = normalize_mobile(body.mobile)
    if len(mob) != 11 or not mob.isdigit():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="手机号格式不正确（需 11 位国内号）")

    # Register flow: fail fast if the phone is already taken to avoid wasting SMS.
    # (User explicitly requested this behavior.)
    if (body.purpose or "").strip().lower() == "register":
        if get_by_phone(db, mob):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该手机号已注册")

    ip = client_ip(request)
    ok_abuse, abuse_msg = check_before_send(
        ip,
        mob,
        ip_min_interval_s=float(settings.sms_ip_min_interval_s),
        ip_max_per_hour=int(settings.sms_ip_max_send_per_hour),
        phone_max_per_hour=int(settings.sms_phone_max_send_per_hour),
    )
    if not ok_abuse:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=abuse_msg)

    allowed, remain = check_send_cooldown(mob, float(settings.sms_send_cooldown_s))
    if not allowed:
        return SmsSendResponse(
            ok=False,
            raw="COOLDOWN",
            message="发送过于频繁，请稍后再试",
            cooldown_s=round(remain or 0.0, 1),
        )

    code = generate_numeric_code(6)
    # Keep template unchanged (备案), only enrich the {code} variable display.
    # Store/verify still uses the pure numeric code.
    code_for_sms = str(code)
    try:
        content = template_use.format(code=code_for_sms)
    except Exception:
        content = f"您的验证码是：{code_for_sms}。请不要把验证码泄露给其他人。如非本人操作，可不用理会！"

    # 通过同号 60s 冷却后再记入 IP/手机号小时窗口，避免误伤正常重试
    record_attempt(ip, mob)

    ok, raw, msg = await send_sms_106(
        endpoint=endpoint or settings.sms_106_endpoint,
        account=account,
        password=password,
        mobile=mob,
        content=content,
        sign_name=sign_name_use or None,
    )
    if ok:
        mark_sent(mob)
        store_otp(mob, body.purpose, code, ttl_s=300.0)
    # Log SMS send result
    try:
        db.add(SmsSendLog(
            phone=mob, purpose=body.purpose or "login", provider="106",
            template_text=(template_use[:200] if template_use else None),
            content_sent=(content[:300] if content else None),
            status="ok" if ok else "fail",
            error_msg=(msg[:500] if not ok and msg else None),
            ip_address=ip,
        ))
        db.commit()
    except Exception:
        pass
    return SmsSendResponse(ok=ok, raw=raw, message=msg, cooldown_s=None)


@app.post("/v1/internal/sms/verify-consume", include_in_schema=False)
async def internal_sms_verify_consume(request: Request, body: InternalSmsVerifyConsumeIn):
    """子站管理后台登录：校验主站进程内短信 OTP（须 X-SMS-Internal-Key，与发短信接口一致）。"""
    if not settings.sms_internal_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SMS_INTERNAL_KEY not configured: internal verify disabled.",
        )
    if request.headers.get("X-SMS-Internal-Key") != settings.sms_internal_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing or invalid X-SMS-Internal-Key.",
        )
    mob = normalize_mobile(body.mobile)
    if len(mob) != 11 or not mob.isdigit():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="手机号格式不正确（需 11 位国内号）")
    purpose = (body.purpose or "login").strip().lower() or "login"
    if not verify_and_consume_otp(mob, purpose, body.code or ""):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="验证码错误或已过期",
        )
    return {"ok": True}


def _mask_sms_account(s: str | None) -> str:
    s = (s or "").strip()
    if not s:
        return ""
    if len(s) <= 4:
        return "****"
    return "*" * (len(s) - 4) + s[-4:]


@app.get("/v1/auth/sms/diagnostics")
async def auth_sms_diagnostics(request: Request):
    """供子站管理端读取 106 网关配置（脱敏）；与 /v1/auth/sms/send 相同校验 X-SMS-Internal-Key（若主站已配置）。"""
    if settings.sms_internal_key:
        if (request.headers.get("X-SMS-Internal-Key") or "").strip() != settings.sms_internal_key:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Missing or invalid X-SMS-Internal-Key.",
            )
    return {
        "ok": True,
        "gateway": "106接口网",
        "sms_106_enabled": bool(settings.sms_106_enabled),
        "endpoint": settings.sms_106_endpoint,
        "account_masked": _mask_sms_account(settings.sms_106_account),
        "password_configured": bool((settings.sms_106_password or "").strip()),
        "sign_name": (settings.sms_106_sign_name or "").strip(),
        "template": settings.sms_106_template,
        "send_cooldown_s": float(settings.sms_send_cooldown_s),
        "ip_min_interval_s": float(settings.sms_ip_min_interval_s),
        "ip_max_send_per_hour": int(settings.sms_ip_max_send_per_hour),
        "phone_max_send_per_hour": int(settings.sms_phone_max_send_per_hour),
        "internal_key_required": bool((settings.sms_internal_key or "").strip()),
    }


def _mask_secret_tail(s: str | None, keep_tail: int = 4) -> str:
    v = (s or "").strip()
    if not v:
        return ""
    if len(v) <= keep_tail:
        return "*" * len(v)
    return ("*" * max(6, len(v) - keep_tail)) + v[-keep_tail:]


@app.get("/v1/admin/sms/effective")
async def admin_sms_effective(request: Request):
    """管理端读取主站 106 短信“当前生效配置”（便于维护参考）。必须提供 X-SMS-Internal-Key。"""
    if not (settings.sms_internal_key or "").strip():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="SMS_INTERNAL_KEY not configured.")
    if (request.headers.get("X-SMS-Internal-Key") or "").strip() != settings.sms_internal_key:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Missing or invalid X-SMS-Internal-Key.")
    return {
        "ok": True,
        "sms_106_enabled": bool(settings.sms_106_enabled),
        "sms_106_endpoint": (settings.sms_106_endpoint or "").strip(),
        "sms_106_account": (settings.sms_106_account or "").strip(),
        "sms_106_password_masked": _mask_secret_tail(settings.sms_106_password, keep_tail=4),
        "sms_106_sign_name": (settings.sms_106_sign_name or "").strip(),
        "sms_106_template": (settings.sms_106_template or "").strip(),
    }


@app.get("/v1/admin/sms/logs")
async def admin_sms_logs(
    request: Request,
    db: Session = Depends(get_db),
    phone: str = "",
    purpose: str = "",
    status: str = "",
    limit: int = 50,
    offset: int = 0,
):
    """查询短信发送记录（需 X-SMS-Internal-Key）。"""
    if not (settings.sms_internal_key or "").strip():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="SMS_INTERNAL_KEY not configured.")
    if (request.headers.get("X-SMS-Internal-Key") or "").strip() != settings.sms_internal_key:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Missing or invalid X-SMS-Internal-Key.")
    q = db.query(SmsSendLog)
    if phone:
        q = q.filter(SmsSendLog.phone.like(f"%{phone}%"))
    if purpose:
        q = q.filter(SmsSendLog.purpose == purpose)
    if status:
        q = q.filter(SmsSendLog.status == status)
    total = q.count()
    rows = q.order_by(SmsSendLog.id.desc()).offset(offset).limit(min(limit, 200)).all()
    return {
        "total": total,
        "limit": min(limit, 200),
        "offset": offset,
        "rows": [
            {
                "id": r.id, "phone": r.phone, "purpose": r.purpose,
                "provider": r.provider, "status": r.status,
                "error_msg": r.error_msg,
                "ip_address": r.ip_address,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }


# —— 官网联调占位路由（返回 501，实现后替换为真实业务）——
@app.post("/v1/auth/login", response_model=AuthTokenResponse)
async def auth_login(body: AuthLoginBody, db: Session = Depends(get_db)):
    u = authenticate_password(
        db,
        phone=body.phone,
        email=body.email,
        password=body.password,
    )
    if not u:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="手机号/邮箱或密码错误",
        )
    token = create_auth_access_token(
        user_id=int(u.id),
        email=u.email,
        phone=u.phone,
        secret=settings.secret_key,
        expire_days=int(settings.auth_jwt_expire_days),
    )
    return AuthTokenResponse(
        token=token,
        user={"id": int(u.id), "email": u.email or "", "phone": u.phone or ""},
    )


@app.post("/v1/auth/email/send", response_model=AuthEmailSendResponse)
async def auth_email_send(body: AuthEmailSendRequest):
    em = norm_email(body.email)
    if not em or "@" not in em:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="邮箱格式不正确")

    now = time.time()
    last = _auth_email_last_sent.get(em, 0.0)
    if now - last < 60.0:
        return AuthEmailSendResponse(
            ok=False,
            message="发送过于频繁，请稍后再试",
            dev_code=None,
        )

    code = generate_numeric_code(6)
    store_email_otp(em, body.purpose, code, ttl_s=300.0)
    _auth_email_last_sent[em] = now

    dev_code: str | None = None
    if str(settings.app_env).lower() not in ("prod", "production"):
        dev_code = code
    logger.info("Email OTP stored purpose=%s email=%s (dev_code only in non-prod response)", body.purpose, em)
    return AuthEmailSendResponse(
        ok=True,
        message="验证码已发送，请注意查收。",
        dev_code=dev_code,
    )


@app.post("/v1/auth/register", response_model=AuthTokenResponse)
async def auth_register(body: AuthRegisterBody, db: Session = Depends(get_db)):
    if body.phone:
        mob = normalize_mobile(body.phone)
        if len(mob) != 11 or not mob.isdigit():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="手机号格式不正确（需 11 位国内号）")
        if get_by_phone(db, mob):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该手机号已注册")
        if not verify_and_consume_otp(mob, "register", body.sms_code or ""):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="验证码错误或已过期，请重新获取验证码",
            )
        u = create_user_phone(db, mob, body.password)
    else:
        em = norm_email(body.email or "")
        if get_by_email(db, em):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该邮箱已注册")
        if not verify_email_otp(em, "register", body.email_code or ""):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="邮箱验证码错误或已过期，请重新获取",
            )
        u = create_user_email(db, em, body.password)

    token = create_auth_access_token(
        user_id=int(u.id),
        email=u.email,
        phone=u.phone,
        secret=settings.secret_key,
        expire_days=int(settings.auth_jwt_expire_days),
    )
    return AuthTokenResponse(
        token=token,
        user={"id": int(u.id), "email": u.email or "", "phone": u.phone or ""},
    )


def _auth_user_from_bearer(request: Request, db: Session) -> AuthUser:
    h = (request.headers.get("Authorization") or "").strip()
    if not h.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="需要登录")
    raw = h[7:].strip()
    if not raw:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="需要登录")
    try:
        from jose import JWTError, jwt

        payload = jwt.decode(raw, settings.secret_key, algorithms=["HS256"])
        uid = int(payload["sub"])
    except (JWTError, ValueError, TypeError, KeyError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录已失效")
    u = db.query(AuthUser).filter(AuthUser.id == uid).first()
    if not u:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")
    return u


@app.post("/v1/auth/password/change", response_model=AuthTokenResponse)
async def auth_password_change(
    request: Request,
    body: AuthPasswordChangeBody,
    db: Session = Depends(get_db),
):
    u = _auth_user_from_bearer(request, db)
    try:
        change_password_for_user(db, int(u.id), body.old_password, body.new_password)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    db.refresh(u)
    token = create_auth_access_token(
        user_id=int(u.id),
        email=u.email,
        phone=u.phone,
        secret=settings.secret_key,
        expire_days=int(settings.auth_jwt_expire_days),
    )
    return AuthTokenResponse(
        token=token,
        user={"id": int(u.id), "email": u.email or "", "phone": u.phone or ""},
    )


@app.post("/v1/auth/password/reset", response_model=AuthTokenResponse)
async def auth_password_reset(body: AuthPasswordResetBody, db: Session = Depends(get_db)):
    try:
        if body.phone:
            u = reset_password_phone(db, body.phone, body.sms_code or "", body.new_password)
        else:
            u = reset_password_email(db, body.email or "", body.email_code or "", body.new_password)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    token = create_auth_access_token(
        user_id=int(u.id),
        email=u.email,
        phone=u.phone,
        secret=settings.secret_key,
        expire_days=int(settings.auth_jwt_expire_days),
    )
    return AuthTokenResponse(
        token=token,
        user={"id": int(u.id), "email": u.email or "", "phone": u.phone or ""},
    )


@app.post("/v1/auth/phone/bind", response_model=AuthTokenResponse)
async def auth_bind_phone(request: Request, body: AuthBindPhoneBody, db: Session = Depends(get_db)):
    u = _auth_user_from_bearer(request, db)
    try:
        u2 = bind_phone_for_user(db, user_id=int(u.id), phone=body.phone, sms_code=body.sms_code)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    token = create_auth_access_token(
        user_id=int(u2.id),
        email=u2.email,
        phone=u2.phone,
        secret=settings.secret_key,
        expire_days=int(settings.auth_jwt_expire_days),
    )
    return AuthTokenResponse(
        token=token,
        user={"id": int(u2.id), "email": u2.email or "", "phone": u2.phone or ""},
    )


@app.post("/v1/auth/email/bind", response_model=AuthTokenResponse)
async def auth_bind_email(request: Request, body: AuthBindEmailBody, db: Session = Depends(get_db)):
    u = _auth_user_from_bearer(request, db)
    try:
        u2 = bind_email_for_user(db, user_id=int(u.id), email=body.email, email_code=body.email_code)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    token = create_auth_access_token(
        user_id=int(u2.id),
        email=u2.email,
        phone=u2.phone,
        secret=settings.secret_key,
        expire_days=int(settings.auth_jwt_expire_days),
    )
    return AuthTokenResponse(
        token=token,
        user={"id": int(u2.id), "email": u2.email or "", "phone": u2.phone or ""},
    )


@app.post("/v1/admin/users/password/set", response_model=AuthTokenResponse)
async def admin_password_set(
    request: Request, body: AdminPasswordSetBody, db: Session = Depends(get_db)
):
    """Admin-only force set password; requires X-SMS-Internal-Key."""
    if not (settings.sms_internal_key or "").strip():
        raise HTTPException(status_code=503, detail="SMS_INTERNAL_KEY not configured.")
    if (request.headers.get("X-SMS-Internal-Key") or "").strip() != (
        settings.sms_internal_key or ""
    ).strip():
        raise HTTPException(status_code=403, detail="Forbidden")
    try:
        u = admin_set_password(
            db,
            user_id=body.user_id,
            phone=body.phone,
            email=body.email,
            new_password=body.new_password,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    token = create_auth_access_token(
        user_id=int(u.id),
        email=u.email,
        phone=u.phone,
        secret=settings.secret_key,
        expire_days=int(settings.auth_jwt_expire_days),
    )
    return AuthTokenResponse(
        token=token,
        user={"id": int(u.id), "email": u.email or "", "phone": u.phone or ""},
    )


@app.post("/v1/admin/users/contact/set", response_model=AuthTokenResponse)
async def admin_user_contact_set(
    request: Request, body: AdminUserContactSetBody, db: Session = Depends(get_db)
):
    """Admin-only force set user phone/email binding; requires X-SMS-Internal-Key."""
    if not (settings.sms_internal_key or "").strip():
        raise HTTPException(status_code=503, detail="SMS_INTERNAL_KEY not configured.")
    if (request.headers.get("X-SMS-Internal-Key") or "").strip() != (
        settings.sms_internal_key or ""
    ).strip():
        raise HTTPException(status_code=403, detail="Forbidden")
    try:
        u = admin_set_contact(db, user_id=int(body.user_id), phone=body.phone, email=body.email)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    token = create_auth_access_token(
        user_id=int(u.id),
        email=u.email,
        phone=u.phone,
        secret=settings.secret_key,
        expire_days=int(settings.auth_jwt_expire_days),
    )
    return AuthTokenResponse(
        token=token,
        user={"id": int(u.id), "email": u.email or "", "phone": u.phone or ""},
    )


@app.get("/v1/admin/users/lookup")
async def admin_user_lookup(
    request: Request,
    phone: str = "",
    email: str = "",
    db: Session = Depends(get_db),
):
    """Lookup auth user by phone/email; requires X-SMS-Internal-Key."""
    if not (settings.sms_internal_key or "").strip():
        raise HTTPException(status_code=503, detail="SMS_INTERNAL_KEY not configured.")
    if (request.headers.get("X-SMS-Internal-Key") or "").strip() != (
        settings.sms_internal_key or ""
    ).strip():
        raise HTTPException(status_code=403, detail="Forbidden")
    p = (phone or "").strip()
    e = (email or "").strip().lower()
    if not p and not e:
        raise HTTPException(status_code=400, detail="phone or email required")
    q = db.query(AuthUser)
    u = None
    if p:
        u = q.filter(AuthUser.phone == p).first()
    if u is None and e:
        u = q.filter(AuthUser.email == e).first()
    if u is None:
        raise HTTPException(status_code=404, detail="User not found")
    return {"ok": True, "user": {"id": int(u.id), "email": u.email or "", "phone": u.phone or ""}}


@app.post("/v1/admin/users/bootstrap", response_model=AuthTokenResponse)
async def admin_user_bootstrap(
    request: Request,
    body: AdminUserBootstrapBody,
    db: Session = Depends(get_db),
):
    """Create user if missing (phone/email) and set password; requires X-SMS-Internal-Key."""
    if not (settings.sms_internal_key or "").strip():
        raise HTTPException(status_code=503, detail="SMS_INTERNAL_KEY not configured.")
    if (request.headers.get("X-SMS-Internal-Key") or "").strip() != (
        settings.sms_internal_key or ""
    ).strip():
        raise HTTPException(status_code=403, detail="Forbidden")
    try:
        if body.phone:
            u = get_by_phone(db, body.phone) or create_user_phone(db, body.phone, body.new_password)
        else:
            u = get_by_email(db, body.email or "") or create_user_email(db, body.email or "", body.new_password)
        # Ensure password matches requested one even if user existed.
        u = admin_set_password(db, user_id=int(u.id), new_password=body.new_password)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    token = create_auth_access_token(
        user_id=int(u.id),
        email=u.email,
        phone=u.phone,
        secret=settings.secret_key,
        expire_days=int(settings.auth_jwt_expire_days),
    )
    return AuthTokenResponse(token=token, user={"id": int(u.id), "email": u.email or "", "phone": u.phone or ""})


@app.get("/v1/keys")
async def keys_list_placeholder():
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="API keys list not implemented.",
    )


@app.post("/v1/keys")
async def keys_create_placeholder():
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="API key create not implemented.",
    )


@app.get("/v1/billing/balance")
async def billing_balance_placeholder():
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Billing balance not implemented.",
    )


@app.get("/v1/referrals/summary")
async def referrals_summary_placeholder():
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Referrals summary not implemented.",
    )


# 静态官网（与 API 同端口 8000）；须挂在所有 API 路由之后
_WEB_ROOT = Path(__file__).resolve().parent.parent / "web"
if _WEB_ROOT.is_dir():
    app.mount(
        "/",
        StaticFiles(directory=str(_WEB_ROOT), html=True),
        name="web",
    )
    logger.info("Serving static site from %s", _WEB_ROOT)
else:
    logger.warning("web/ not found at %s — static site disabled", _WEB_ROOT)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        workers=settings.api_workers,
        # PM2/Windows 下 uvicorn reload 会触发 WinError 6 且日志难定位；统一由进程管理器重启。
        reload=False
    )