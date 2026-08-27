from pathlib import Path
import asyncio
import logging
import os
import subprocess
import time

from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

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
    ApiKeyCreateBody,
    ApiKeyCreatedOut,
    ApiKeyOut,
    ApiKeyRenameBody,
    BillingBalanceOut,
    BillingTopupBody,
    TokenPayCreateBody,
    TokenMockFulfillBody,
    TokenQueryFulfillBody,
    TokenCryptoSubmitBody,
    ChatRequest,
    ChatResponse,
    ErrorResponse,
    InternalSmsVerifyConsumeIn,
    SmsSendRequest,
    SmsSendResponse,
    SupportAskBody,
    SupportTicketCreateBody,
    SupportTicketReplyBody,
    SupportTicketUserReplyBody,
    TokenAdminSystemUpdateBody,
    TokenAdminWarehouseUpdateBody,
    TokenAdminFreeSharedUpdateBody,
    TokenAdminLlmKeysUpdateBody,
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
from sms_juhe_client import send_sms_juhe
from sms_tencent_client import send_sms_tencent
from email_otp_memory import store_otp as store_email_otp
from email_otp_memory import verify_and_consume_otp as verify_email_otp
from auth_tokens import create_auth_access_token
from auth_user_service import (
    authenticate_password,
    admin_set_contact,
    admin_set_password,
    auth_user_public_dict,
    bind_email_for_user,
    bind_phone_for_user,
    change_password_for_user,
    create_user_email,
    create_user_phone,
    get_by_email,
    get_by_phone,
    is_user_frozen,
    norm_email,
    raise_if_frozen,
    reset_password_email,
    reset_password_phone,
    set_user_frozen,
)
from sms_abuse_guard import check_before_send, client_ip, record_attempt
from sms_otp_memory import store_otp, verify_and_consume_otp
from security_util import (
    attribution_block,
    check_sliding_rate,
    client_ip as sec_client_ip,
    is_prod,
    security_headers,
)

# 配置日志
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 邮箱验证码发送冷却（进程内；多实例需 Redis）
_auth_email_last_sent: dict[str, float] = {}

_docs_on = not (is_prod() and bool(settings.disable_docs_in_prod))
# 创建FastAPI应用
app = FastAPI(
    title="AI24X API",
    description="AI24X Token aggregation platform — unified multi-model API gateway (PostgreSQL via SQLAlchemy).",
    version="1.0.0",
    docs_url="/docs" if _docs_on else None,
    redoc_url="/redoc" if _docs_on else None,
    openapi_url="/openapi.json" if _docs_on else None,
)

_cors_raw = (settings.cors_origins or "*").strip()
if is_prod() and (_cors_raw == "*" or not _cors_raw):
    # 生产默认收窄，避免任意站跨域带 Cookie；仍可用 CORS_ORIGINS 显式覆盖
    _cors_raw = "https://www.ai24x.com,https://ai24x.com"
    logger.warning("CORS_ORIGINS=* in prod — using default www.ai24x.com,ai24x.com")
_cors_origins = ["*"] if _cors_raw == "*" else [x.strip() for x in _cors_raw.split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=("*" not in _cors_origins),
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-API-Key",
        "X-SMS-Internal-Key",
        "X-Admin-Key",
        "X-Request-ID",
    ],
)


# 中间件：安全响应头 + 请求日志
_ADMIN_AUDIT_METHODS = {"POST", "PATCH", "DELETE"}
_ADMIN_AUDIT_SENSITIVE_HINTS = ("key", "secret", "token", "password")


def _admin_audit_body(raw: bytes, max_len: int = 800) -> str:
    """管理写操作请求体摘要（密钥类字段脱敏）。"""
    if not raw:
        return ""
    text = raw.decode("utf-8", errors="replace")[:max_len]
    try:
        import json as _json

        obj = _json.loads(text)
        if isinstance(obj, dict):
            for k in list(obj.keys()):
                kl = k.lower()
                if any(h in kl for h in _ADMIN_AUDIT_SENSITIVE_HINTS):
                    obj[k] = "***"
            return _json.dumps(obj, ensure_ascii=False)[:max_len]
    except Exception:
        pass
    return text


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    ip_address = sec_client_ip(request)
    is_admin_write = (
        request.method in _ADMIN_AUDIT_METHODS
        and (request.url.path or "").startswith("/v1/admin/")
    )
    admin_body = ""
    if is_admin_write:
        try:
            raw = await request.body()
            request._body = raw  # 放回缓存，保证下游可读
            admin_body = _admin_audit_body(raw)
        except Exception:
            admin_body = ""
    response = await call_next(request)
    for k, v in security_headers().items():
        response.headers.setdefault(k, v)
    process_time = time.time() - start_time
    logger.info(
        f"{request.method} {request.url.path} - "
        f"Status: {response.status_code} - "
        f"Time: {process_time:.3f}s - "
        f"IP: {ip_address}"
    )
    if is_admin_write:
        admin_key = request.headers.get("x-admin-key", "")
        admin_tag = f"admin_key={admin_key[:8]}***" if admin_key else "admin_key=(none)"
        logger.info(
            f"[ADMIN-AUDIT] {request.method} {request.url.path} "
            f"Status: {response.status_code} IP: {ip_address} {admin_tag} body={admin_body}"
        )
    return response


def _is_chat_post_path(path: str) -> bool:
    p = (path or "").rstrip("/")
    return (
        p.endswith("/v1/chat/run")
        or p.endswith("/v1/chat/completions")
        or p.endswith("/v1/responses")
    )


def _is_openai_completions_path(path: str) -> bool:
    p = (path or "").rstrip("/")
    return p.endswith("/v1/chat/completions") or p.endswith("/v1/responses")


# 中间件：chat 限流（IP + API Key / Bearer）
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if not settings.enable_rate_limiting:
        return await call_next(request)
    path = request.url.path or ""
    if _is_chat_post_path(path) and request.method.upper() == "POST":
        from openai_compat import extract_api_key, openai_error_body

        ip = sec_client_ip(request)
        ok_ip, _ = check_sliding_rate(
            f"ip:{ip}",
            limit=int(settings.chat_rate_per_ip_per_minute or 120),
            window_s=60.0,
        )
        if not ok_ip:
            if _is_openai_completions_path(path):
                return JSONResponse(
                    status_code=429,
                    content=openai_error_body(
                        "请求过于频繁（IP）",
                        err_type="rate_limit_error",
                        code="rate_limit_exceeded",
                    ),
                )
            return JSONResponse(
                status_code=429,
                content={"error": "请求过于频繁（IP）", "code": "429", "request_id": None},
            )
        api_key = extract_api_key(request) or ""
        if api_key:
            ok_k, _ = check_sliding_rate(
                f"key:{api_key[:24]}",
                limit=int(settings.chat_rate_per_minute or 60),
                window_s=60.0,
            )
            if not ok_k:
                if _is_openai_completions_path(path):
                    return JSONResponse(
                        status_code=429,
                        content=openai_error_body(
                            "请求过于频繁（API Key）",
                            err_type="rate_limit_error",
                            code="rate_limit_exceeded",
                        ),
                    )
                return JSONResponse(
                    status_code=429,
                    content={"error": "请求过于频繁（API Key）", "code": "429", "request_id": None},
                )
    return await call_next(request)


# 依赖项：获取当前用户
def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
):
    """从请求头获取当前用户。

    与控制台余额接口同一套认人：
    1) Authorization Bearer JWT（登录会话，非 sk-）
    2) X-API-Key / Bearer sk-（终端 API Key）
    避免「余额正常、试调用 401」——旧逻辑在 JWT 解码失败时会静默落到 STRICT_AUTH。
    """
    from openai_compat import extract_api_key
    from token_mvp_service import ensure_gateway_user

    request.state.auth_user_id = None

    auth = (request.headers.get("Authorization") or "").strip()
    bearer = ""
    if auth.lower().startswith("bearer "):
        bearer = auth[7:].strip()
    api_key = extract_api_key(request)
    has_console_jwt = bool(
        bearer and not bearer.startswith("sk-") and bearer.count(".") >= 2
    )
    has_sk = bool(api_key and str(api_key).startswith("sk-"))

    # 控制台 JWT 或 sk-：与 /v1/billing/balance 同一认人路径
    if has_console_jwt or has_sk:
        au = _auth_user_from_api_key_or_jwt(request, db)
        request.state.auth_user_id = int(au.id)
        # 2026-08-15: 仅当确实用 API Key 鉴权（无有效 JWT）才归属 key；JWT 会话归空
        request.state.auth_api_key_id = None
        if has_sk and not has_console_jwt and api_key:
            try:
                from token_mvp_service import get_api_key_row

                _krow = get_api_key_row(db, api_key)
                if _krow:
                    request.state.auth_api_key_id = int(_krow.id)
            except Exception:
                pass
        user = ensure_gateway_user(db, int(au.id))
        allowed, error_msg = UserService.check_rate_limit(db, user)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=error_msg,
            )
        return user

    # 有疑似 JWT 但未进上方分支时，禁止落到「无效的API Key或用户ID」
    if bearer and not bearer.startswith("sk-") and bearer.count(".") >= 2:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录已失效",
        )

    if bool(settings.strict_auth):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "message_zh": "请先登录，或提供有效的 API Key。",
                "message_en": "Please sign in, or provide a valid API key.",
                "message": "请先登录，或提供有效的 API Key。",
                "code": "auth_required",
            },
        )

    user_id = request.query_params.get("user_id")
    user = AuthService.authenticate_user(db, api_key=api_key, user_id=user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "message_zh": "请先登录，或提供有效的 API Key。",
                "message_en": "Please sign in, or provide a valid API key.",
                "message": "请先登录，或提供有效的 API Key。",
                "code": "auth_required",
            },
        )

    allowed, error_msg = UserService.check_rate_limit(db, user)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=error_msg,
        )
    return user


_GIT_COMMIT = None
_GIT_COMMIT_READ = False


def _git_head_short():
    """启动后首次 /health 读取一次仓库 HEAD（12 位短哈希），失败回落 None。"""
    global _GIT_COMMIT, _GIT_COMMIT_READ
    if not _GIT_COMMIT_READ:
        _GIT_COMMIT_READ = True
        try:
            repo = Path(__file__).resolve().parent.parent
            out = subprocess.run(
                ["git", "-C", str(repo), "rev-parse", "--short=12", "HEAD"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            v = (out.stdout or "").strip()
            _GIT_COMMIT = v if out.returncode == 0 and v else None
        except Exception:
            _GIT_COMMIT = None
    return _GIT_COMMIT


# 健康检查端点
@app.get("/health")
async def health_check():
    """进程存活 + 只读上游摘要（不探活、不泄露密钥）。"""
    from model_router import _layer_upstream, _upstream_mode

    mode = _upstream_mode()
    layers = {}
    for ly in ("L0", "L1", "L2", "L3", "QI"):
        up = _layer_upstream(ly)
        layers[ly] = {"key_set": bool(up.get("key")), "provider": up.get("provider") or ""}
    build = (
        (os.environ.get("AI24X_BUILD_STAMP") or "").strip()
        or (os.environ.get("BUILD_STAMP") or "").strip()
        or _git_head_short()
        or ""
    )
    return {
        "status": "healthy",
        "service": "AI24X API",
        "version": "1.0.0",
        "build_stamp": build or None,
        "commit": _git_head_short(),
        "upstream_mode": mode,
        "layers": layers,
        "timestamp": time.time(),
    }


# 主接口：/v1/chat/run
@app.post("/v1/chat/run", response_model=ChatResponse)
async def chat_run(
    http_request: Request,
    request: ChatRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
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
        
        # 处理聊天请求（auth_user_id 由 get_current_user 写入 request.state）
        auth_uid = getattr(http_request.state, "auth_user_id", None)
        auth_api_key_id = getattr(http_request.state, "auth_api_key_id", None)
        region_hint = (
            (http_request.headers.get("x-ai24x-region") or "").strip()
            or (http_request.headers.get("cf-ipcountry") or "").strip()
            or None
        )
        byok_project = (http_request.headers.get("x-byok-project") or "").strip()[:64] or None
        response = ChatService.process_chat_request(
            db=db,
            user=current_user,
            request=request,
            ip_address=ip_address,
            user_agent=user_agent,
            auth_user_id=auth_uid,
            auth_api_key_id=auth_api_key_id,
            region_hint=region_hint,
            byok_project=byok_project,
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


# OpenAI 兼容：/v1/chat/completions（与 /v1/chat/run 并存，复用鉴权计费）
@app.post("/v1/chat/completions")
async def chat_completions(
    http_request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    OpenAI Chat Completions 兼容入口。
    Authorization: Bearer <API_KEY> 或 X-API-Key；body 为 messages[] + model + stream。
    支持 OpenAI tools / tool_choice / tool_calls（含流式增量），供 OpenClaw 等执行本机工具。
    """
    from openai_compat import (
        build_chat_request_schema,
        completion_id,
        streaming_response,
        to_openai_completion,
        true_streaming_response,
    )
    from model_router import true_stream_enabled

    try:
        body = await http_request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请求体必须是 JSON",
        )
    if not isinstance(body, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请求体必须是 JSON 对象",
        )

    chat_req = build_chat_request_schema(body)
    want_stream = bool(body.get("stream"))
    ip_address = http_request.client.host if http_request.client else None
    user_agent = http_request.headers.get("user-agent")
    auth_uid = getattr(http_request.state, "auth_user_id", None)
    auth_api_key_id = getattr(http_request.state, "auth_api_key_id", None)
    region_hint = (
        (http_request.headers.get("x-ai24x-region") or "").strip()
        or (http_request.headers.get("cf-ipcountry") or "").strip()
        or None
    )
    byok_project = (http_request.headers.get("x-byok-project") or "").strip()[:64] or None

    cmpl_id = completion_id()

    # 真流式：边生成边写，流末扣费（OpenClaw / LobeChat）
    if want_stream and true_stream_enabled():
        try:
            # 2026-08-12：流前余额预检——流中无法改状态码，402/403 必须先返回
            ChatService.preflight_stream(db=db, request=chat_req, auth_user_id=auth_uid)
            events = ChatService.stream_chat_request(
                db=db,
                user=current_user,
                request=chat_req,
                ip_address=ip_address,
                user_agent=user_agent,
                auth_user_id=auth_uid,
                auth_api_key_id=auth_api_key_id,
                region_hint=region_hint,
                byok_project=byok_project,
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error starting stream completions: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="处理请求时发生错误",
            )
        logger.info(
            "Chat completions TRUE stream user=%s model=%s id=%s",
            current_user.user_id,
            chat_req.model,
            cmpl_id,
        )
        return true_streaming_response(
            events, requested_model=chat_req.model or "flash", cmpl_id=cmpl_id
        )

    try:
        response = ChatService.process_chat_request(
            db=db,
            user=current_user,
            request=chat_req,
            ip_address=ip_address,
            user_agent=user_agent,
            auth_user_id=auth_uid,
            auth_api_key_id=auth_api_key_id,
            region_hint=region_hint,
            byok_project=byok_project,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing chat completions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="处理请求时发生错误",
        )

    logger.info(
        "Chat completions: %s stream=%s user=%s model=%s",
        response.request_id,
        want_stream,
        current_user.user_id,
        response.model,
    )
    if want_stream:
        return streaming_response(
            response, requested_model=chat_req.model or "flash", cmpl_id=cmpl_id
        )
    return to_openai_completion(
        response, requested_model=chat_req.model or "flash", cmpl_id=cmpl_id
    )


@app.post("/v1/responses")
async def openai_responses_create(
    http_request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    OpenAI Responses API 兼容（Codex / Cursor / LobeChat 等）。
    鉴权计费与 /v1/chat/completions 相同；支持 tools / function_call 工具循环；
    流式优先真流式透传上游 SSE（与 chat/completions 对齐，避免客户端空闲断连）。
    """
    from openai_compat import (
        build_chat_request_from_responses,
        response_id,
        streaming_responses_response,
        to_openai_response,
        true_streaming_responses_response,
    )
    from model_router import true_stream_enabled

    try:
        body = await http_request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请求体必须是 JSON",
        )
    if not isinstance(body, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请求体必须是 JSON 对象",
        )

    chat_req = build_chat_request_from_responses(body)
    want_stream = bool(body.get("stream"))
    ip_address = http_request.client.host if http_request.client else None
    user_agent = http_request.headers.get("user-agent")
    auth_uid = getattr(http_request.state, "auth_user_id", None)
    auth_api_key_id = getattr(http_request.state, "auth_api_key_id", None)
    region_hint = (
        (http_request.headers.get("x-ai24x-region") or "").strip()
        or (http_request.headers.get("cf-ipcountry") or "").strip()
        or None
    )
    byok_project = (http_request.headers.get("x-byok-project") or "").strip()[:64] or None
    rid = response_id()

    # ⚠️ 主脑 2026-08-12 五修【DIAG】：Codex 完整请求 400 诊断（临时，定位后移除/精简）
    try:
        _dt = body.get("tools")
        _dn = []
        if isinstance(_dt, list):
            for _t in _dt[:20]:
                if isinstance(_t, dict):
                    _fn = _t.get("function")
                    _nn = _t.get("name") or (_fn.get("name") if isinstance(_fn, dict) else None)
                    _dn.append(str(_nn or ""))
        _di = body.get("input")
        _dmsgs = len(_di) if isinstance(_di, list) else (1 if isinstance(_di, str) else 0)
        _dlen = len(json.dumps(body, ensure_ascii=False)) if body else 0
        logger.warning(f"【DIAG】responses entry model={body.get('model')!r} stream={body.get('stream')} tools_n={len(_dn)} tools={_dn[:20]} input_items={_dmsgs} has_instructions={'instructions' in body} has_reasoning={'reasoning' in body} body_len={_dlen} user={auth_uid}")
    except Exception:
        pass

    # 真流式：先发 response.created 心跳，边生成边写 SSE 事件（Codex/Cursor 工具循环）
    if want_stream and true_stream_enabled():
        try:
            # 2026-08-12：流前余额预检——流中无法改状态码，402/403 必须先返回
            ChatService.preflight_stream(db=db, request=chat_req, auth_user_id=auth_uid)
            events = ChatService.stream_chat_request(
                db=db,
                user=current_user,
                request=chat_req,
                ip_address=ip_address,
                user_agent=user_agent,
                auth_user_id=auth_uid,
                auth_api_key_id=auth_api_key_id,
                region_hint=region_hint,
                byok_project=byok_project,
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error starting stream responses: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="处理请求时发生错误",
            )
        logger.info(
            "Responses TRUE stream user=%s model=%s id=%s",
            current_user.user_id,
            chat_req.model,
            rid,
        )
        return true_streaming_responses_response(
            events, requested_model=chat_req.model or "flash", resp_id=rid
        )

    try:
        response = ChatService.process_chat_request(
            db=db,
            user=current_user,
            request=chat_req,
            ip_address=ip_address,
            user_agent=user_agent,
            auth_user_id=auth_uid,
            auth_api_key_id=auth_api_key_id,
            region_hint=region_hint,
            byok_project=byok_project,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing responses: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="处理请求时发生错误",
        )

    logger.info(
        "Responses: %s stream=%s user=%s model=%s",
        response.request_id,
        want_stream,
        current_user.user_id,
        response.model,
    )
    if want_stream:
        return streaming_responses_response(
            response, requested_model=chat_req.model or "flash", resp_id=rid
        )
    return to_openai_response(
        response, requested_model=chat_req.model or "flash", resp_id=rid
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


# 全局异常处理
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if _is_openai_completions_path(request.url.path or ""):
        from openai_compat import openai_error_response

        return openai_error_response(exc)
    from user_i18n import flatten_http_detail, is_bilingual_detail

    err_text, detail_out = flatten_http_detail(exc.detail)
    body = ErrorResponse(
        error=err_text,
        code=str(int(exc.status_code)),
        request_id=request.headers.get("X-Request-ID"),
        detail=detail_out if is_bilingual_detail(detail_out) else None,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=body.model_dump(exclude_none=True),
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    # Log full traceback for server-side debugging (front-end receives a generic 500 message).
    logger.exception("Unhandled exception")
    if _is_openai_completions_path(request.url.path or ""):
        from openai_compat import openai_error_body

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=openai_error_body(
                "服务器内部错误",
                err_type="server_error",
                code="server_error",
            ),
        )
    body = ErrorResponse(
        error="服务器内部错误",
        code="INTERNAL_SERVER_ERROR",
        request_id=request.headers.get("X-Request-ID"),
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=body.model_dump(),
    )


async def _stuck_processing_scan() -> None:
    """兜底扫描：status=processing 且超时未完成的请求标记 failed（不扣费）。

    2026-08-12 记账根治的一部分——即使主流程异常/进程残留，也不留永续
    processing；正常完成的请求由 stream_chat_request 的 finally 路径收尾，
    request_id 幂等防重复扣费。开关：TOKEN_STUCK_SCAN_ENABLED=0 关闭；
    间隔 TOKEN_STUCK_SCAN_INTERVAL_S（默认 300）、超时 TOKEN_STUCK_SCAN_STALE_S（默认 1800）。
    """
    if (os.getenv("TOKEN_STUCK_SCAN_ENABLED") or "1").strip().lower() in ("0", "false", "no", "off"):
        return
    try:
        interval = max(30, int(os.getenv("TOKEN_STUCK_SCAN_INTERVAL_S") or "300"))
    except (TypeError, ValueError):
        interval = 300
    try:
        stale = max(60, int(os.getenv("TOKEN_STUCK_SCAN_STALE_S") or "1800"))
    except (TypeError, ValueError):
        stale = 1800
    while True:
        await asyncio.sleep(interval)
        try:
            from datetime import datetime, timedelta

            from database import SessionLocal
            from models import ChatRequest

            db = SessionLocal()
            try:
                cutoff = datetime.utcnow() - timedelta(seconds=stale)
                rows = (
                    db.query(ChatRequest)
                    .filter(
                        ChatRequest.status == "processing",
                        ChatRequest.request_time < cutoff,
                    )
                    .limit(200)
                    .all()
                )
                for r in rows:
                    r.status = "failed"
                    r.error_message = (r.error_message or "") + " | stuck_timeout_scan"
                    r.response_time = datetime.utcnow()
                if rows:
                    db.commit()
                    logger.warning(
                        "stuck_processing_scan: %d row(s) marked failed", len(rows)
                    )
            finally:
                db.close()
        except Exception as e:
            logger.error("stuck_processing_scan error: %s", e)


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
        try:
            app.state._stuck_scan_task = asyncio.create_task(_stuck_processing_scan())
        except Exception as e:
            logger.error("start stuck scan failed: %s", e)
        return
    try:
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {str(e)}")
        raise
    try:
        app.state._stuck_scan_task = asyncio.create_task(_stuck_processing_scan())
        logger.info("stuck processing scan started")
    except Exception as e:
        logger.error("start stuck scan failed: %s", e)


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时清理资源"""
    logger.info("Shutting down AI24X API...")
    task = getattr(app.state, "_stuck_scan_task", None)
    if task is not None:
        try:
            task.cancel()
        except Exception:
            pass


# —— 短信：106 网关（联调；生产务必配置 SMS_INTERNAL_KEY）——
@app.post("/v1/auth/sms/send", response_model=SmsSendResponse)
async def auth_sms_send(request: Request, body: SmsSendRequest, db: Session = Depends(get_db)):
    # 与管理台「国内短信」对齐：读 system_flags 覆盖，勿只看 .env
    from system_flags import effective_sms_106_enabled

    if not effective_sms_106_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="短信服务暂不可用，请稍后再试。",
        )
    if settings.sms_internal_key and request.headers.get("X-SMS-Internal-Key") != settings.sms_internal_key:
        # 常见：副站 AI24X_SMS_INTERNAL_KEY 未配或与主站 SMS_INTERNAL_KEY 不一致
        logger.warning(
            "sms send forbidden: internal key missing or mismatch (header_present=%s)",
            bool((request.headers.get("X-SMS-Internal-Key") or "").strip()),
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="短信服务暂时不可用，请稍后再试。",
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
            detail="短信服务暂不可用，请稍后再试。",
        )

    mob = normalize_mobile(body.mobile)
    if len(mob) != 11 or not mob.isdigit():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="手机号格式不正确，请填写 11 位手机号")

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

    # 邮件语言：请求显式 lang 优先，否则按 Accept-Language 推断（含 zh 即中文，默认中文）
    req_lang = (body.lang or "").strip().lower()
    if not req_lang:
        accept = (request.headers.get("accept-language") or "").lower()
        req_lang = "zh" if ("zh" in accept or "cn" in accept) else "en"
    if req_lang not in ("zh", "en"):
        req_lang = "zh"

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

    # Record SMS send
    provider_name = "106"
    try:
        if body.sms_provider == "juhe" and body.sms_juhe_key:
            provider_name = "juhe"
            ok, raw, msg = await send_sms_juhe(
                app_key=body.sms_juhe_key,
                mobile=mob,
                tpl_id=body.sms_juhe_tpl_id or "",
                tpl_vars={"code": code_for_sms},
            )
        elif body.sms_provider == "tencent" and body.sms_tencent_secret_id:
            provider_name = "tencent"
            ok, raw, msg = await send_sms_tencent(
                secret_id=body.sms_tencent_secret_id,
                secret_key=body.sms_tencent_secret_key or "",
                sdk_app_id=body.sms_tencent_sdk_app_id or "",
                sign_name=body.sms_tencent_sign or "",
                template_id=body.sms_tencent_template_id or "",
                template_params=[code_for_sms],
                phone=mob,
                region=body.sms_tencent_region or "ap-guangzhou",
            )
        else:
            ok, raw, msg = await send_sms_106(
                endpoint=endpoint or settings.sms_106_endpoint,
                account=account,
                password=password,
                mobile=mob,
                content=content,
                sign_name=sign_name_use or None,
            )
    except Exception as e:
        ok, raw, msg = False, "", f"发送异常: {e}"
    if ok:
        mark_sent(mob)
        store_otp(mob, body.purpose, code, ttl_s=300.0)
    # Log SMS send result
    try:
        db.add(SmsSendLog(
            phone=mob, purpose=body.purpose or "login", provider=provider_name,
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
            detail="短信服务暂时不可用，请稍后再试。",
        )
    if request.headers.get("X-SMS-Internal-Key") != settings.sms_internal_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="短信服务暂时不可用，请稍后再试。",
        )
    mob = normalize_mobile(body.mobile)
    if len(mob) != 11 or not mob.isdigit():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="手机号格式不正确，请填写 11 位手机号")
    purpose = (body.purpose or "login").strip().lower() or "login"
    if not verify_and_consume_otp(mob, purpose, body.code or ""):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="验证码错误或已过期，请重新获取",
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
                detail="短信服务暂时不可用，请稍后再试。",
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
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="短信服务暂时不可用，请稍后再试。")
    if (request.headers.get("X-SMS-Internal-Key") or "").strip() != settings.sms_internal_key:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="禁止访问")
    return {
        "ok": True,
        "sms_106_enabled": bool(settings.sms_106_enabled),
        "sms_106_endpoint": (settings.sms_106_endpoint or "").strip(),
        # 完整账号仅内部密钥可读（行情官管理台回填）；对外勿暴露
        "sms_106_account": (settings.sms_106_account or "").strip(),
        "sms_106_account_masked": _mask_sms_account(settings.sms_106_account),
        "sms_106_account_set": bool((settings.sms_106_account or "").strip()),
        "sms_106_password_set": bool((settings.sms_106_password or "").strip()),
        "sms_106_password_masked": _mask_secret_tail(settings.sms_106_password, keep_tail=4),
        "sms_106_sign_name": (settings.sms_106_sign_name or "").strip(),
        "sms_106_template": (settings.sms_106_template or "").strip(),
        "intl_sms": False,
        "intl_note": "国际用户请用邮箱验证码；国际短信本轮不接入。",
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
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="短信服务暂时不可用，请稍后再试。")
    if (request.headers.get("X-SMS-Internal-Key") or "").strip() != settings.sms_internal_key:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="禁止访问")
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
async def auth_login(request: Request, body: AuthLoginBody, db: Session = Depends(get_db)):
    from security_util import (
        check_login_throttle,
        clear_login_failures,
        record_login_failure,
    )

    identity = (body.email or body.phone or "").strip().lower()
    ip = sec_client_ip(request)
    ok_th, th_msg = check_login_throttle(identity=identity, ip=ip)
    if not ok_th:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=th_msg)

    u = authenticate_password(
        db,
        phone=body.phone,
        email=body.email,
        password=body.password,
    )
    if not u:
        # 国际版统一账号（DEC-0007）：本地无此账号 → 转发 core 验证。
        # core 为身份真源；验证通过后本站自动建档影子用户，密码不落盘。
        core_res, core_err = await _core_login(
            phone=body.phone,
            email=body.email,
            password=body.password,
        )
        if core_res:
            clear_login_failures(identity=identity, ip=ip)
            core_user = core_res.get("user") or {}
            core_token = (core_res.get("token") or "").strip()
            from auth_user_service import resolve_or_create_shadow

            u = resolve_or_create_shadow(
                db,
                platform_user_id=int(core_user.get("id") or 0) or None,
                email=core_user.get("email") or body.email,
                phone=core_user.get("phone") or body.phone,
            )
            if not u:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="手机号或密码错误，请检查后重试。",
                )
            raise_if_frozen(u)
            if not core_token:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="登录服务暂时不可用，请稍后再试。",
                )
            return AuthTokenResponse(
                token=core_token,
                user={"id": int(u.id), "email": u.email or "", "phone": u.phone or ""},
            )
        if core_err == "bad_credentials":
            record_login_failure(identity=identity, ip=ip)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="手机号或密码错误，请检查后重试。",
            )
        if core_err == "too_many":
            record_login_failure(identity=identity, ip=ip)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="尝试过于频繁，请稍后再试。",
            )
        record_login_failure(identity=identity, ip=ip)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="登录服务暂时不可用，请稍后再试。",
        )
    clear_login_failures(identity=identity, ip=ip)
    raise_if_frozen(u)
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


async def _core_login(*, phone: str | None, email: str | None, password: str):
    """转发 core /v1/auth/login 校验国际版统一账号（DEC-0007）。

    返回 (payload_dict | None, err_code | "")；密码只经 HTTPS 转发，不落盘、不打日志。
    """
    base = (
        (getattr(settings, "ai24x_core_api_base", "") or "https://api.ai24x.com")
        .strip()
        .rstrip("/")
    )
    if not base.startswith("http"):
        return None, "core_base_invalid"
    body = {"password": password}
    if email:
        body["email"] = email
    if phone:
        body["phone"] = phone
    try:
        import httpx

        async with httpx.AsyncClient(timeout=12.0) as client:
            r = await client.post(base + "/v1/auth/login", json=body)
    except Exception:
        logger.warning("core auth proxy request failed for base=%s", base)
        return None, "core_unavailable"
    if r.status_code == 200:
        try:
            return r.json(), ""
        except Exception:
            return None, "core_bad_response"
    if r.status_code == 401:
        return None, "bad_credentials"
    if r.status_code == 429:
        return None, "too_many"
    logger.warning("core auth proxy unexpected status=%s", r.status_code)
    return None, "core_unavailable"


@app.get("/v1/auth/captcha")
async def auth_captcha(request: Request):
    """图形验证码（注册/找回密码发码前必填；ENABLE_CAPTCHA=0 关闭）。"""
    from captcha_guard import create_captcha

    ip = sec_client_ip(request)
    try:
        r = create_captcha(ip)
    except Exception:
        r = None
    if not r:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="验证码服务暂不可用，请稍后再试",
        )
    token, data_url = r
    return {"ok": True, "token": token, "image": data_url}


@app.post("/v1/auth/email/send", response_model=AuthEmailSendResponse)
async def auth_email_send(request: Request, body: AuthEmailSendRequest):
    from captcha_guard import captcha_enabled, verify_captcha
    from email_abuse_guard import (
        check_email_send_allowed,
        client_ip as email_client_ip,
        record_email_send_attempt,
    )
    from email_smtp import send_otp_email, smtp_configured
    from security_util import is_prod

    em = norm_email(body.email)
    if not em or "@" not in em:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="邮箱格式不正确")

    ip = email_client_ip(request)

    _peer = ""
    try:
        _peer = (request.client.host if request.client else "") or ""
    except Exception:
        _peer = ""
    # 图形验证码（防批量发码/撞库；关闭时放行；开发本机回环免验——按 TCP 对端判断，防伪造）
    if captcha_enabled() and not verify_captcha(body.captcha_token or "", body.captcha_answer or "", bypass_ip=_peer):
        return AuthEmailSendResponse(
            ok=False,
            message="图形验证码错误或已过期，请刷新后重试",
            channel=None,
            local_code=None,
            dev_code=None,
        )
    ok_abuse, abuse_msg = check_email_send_allowed(ip, em)
    if not ok_abuse:
        return AuthEmailSendResponse(
            ok=False,
            message=abuse_msg or "发送过于频繁，请稍后再试",
            channel=None,
            local_code=None,
            dev_code=None,
        )

    now = time.time()
    last = _auth_email_last_sent.get(em, 0.0)
    if now - last < 60.0:
        return AuthEmailSendResponse(
            ok=False,
            message="发送过于频繁，请稍后再试",
            channel=None,
            local_code=None,
            dev_code=None,
        )

    # 邮件语言：请求显式 lang 优先，否则按 Accept-Language 推断（含 zh 即中文，默认中文）
    req_lang = (body.lang or "").strip().lower()
    if not req_lang:
        accept = (request.headers.get("accept-language") or "").lower()
        req_lang = "zh" if ("zh" in accept or "cn" in accept) else "en"
    if req_lang not in ("zh", "en"):
        req_lang = "zh"

    code = generate_numeric_code(6)
    store_email_otp(em, body.purpose, code, ttl_s=300.0)
    record_email_send_attempt(ip, em)

    # 测试邮箱（*.local / example.com）：即使已配 SMTP 也走 local，避免假邮箱触发真发信
    is_test_mailbox = em.endswith(".local") or em.endswith("@example.com") or em.endswith(".example.com")

    if smtp_configured() and not is_test_mailbox:
        ok, msg = send_otp_email(to_email=em, code=code, purpose=body.purpose, lang=req_lang)
        if not ok:
            # 发信失败：作废本次 OTP；不写入限流，便于改配置后立即重试
            try:
                from email_otp_memory import store_otp as _store

                _store(em, body.purpose, "__invalid__", ttl_s=1.0)
            except Exception:
                pass
            return AuthEmailSendResponse(
                ok=False,
                message=msg or "邮件发送失败",
                channel="smtp",
                local_code=None,
                dev_code=None,
            )
        _auth_email_last_sent[em] = time.time()
        logger.info("Email OTP sent via SMTP purpose=%s email=%s", body.purpose, em)
        return AuthEmailSendResponse(
            ok=True,
            message=msg or "验证码已发送到邮箱，请查收。",
            channel="smtp",
            local_code=None,
            dev_code=None,
        )

    # 无 SMTP：生产禁止暴露验证码；开发可走 local 卡片（仅本机联调）
    if is_prod():
        logger.error("Email OTP blocked: SMTP not configured in production")
        return AuthEmailSendResponse(
            ok=False,
            message="邮件服务暂不可用，请稍后再试。",
            channel=None,
            local_code=None,
            dev_code=None,
        )

    expose = bool(getattr(settings, "email_otp_expose_local_code", True))
    local = code if expose else None
    _auth_email_last_sent[em] = time.time()
    logger.info(
        "Email OTP local channel purpose=%s email=%s expose=%s",
        body.purpose,
        em,
        expose,
    )
    return AuthEmailSendResponse(
        ok=True,
        # 用户可见文案：勿写 SMTP / 联调 / 正式环境 等运维用语
        message="验证码已生成，请查看下方并完成注册。",
        channel="local",
        local_code=local,
        dev_code=local,
    )


@app.get("/v1/auth/email/status")
async def auth_email_status():
    """运维自检：邮箱通道是否就绪（不含密钥）。"""
    from email_smtp import email_channel_status

    return {"ok": True, **email_channel_status()}


@app.post("/v1/auth/register", response_model=AuthTokenResponse)
async def auth_register(request: Request, body: AuthRegisterBody, db: Session = Depends(get_db)):
    from email_abuse_guard import check_register_allowed, record_register

    # 蜜罐字段：真实用户不会填写（前端隐藏），非空即判定为机器人
    if (body.website or "").strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请求无效，请刷新页面重试")

    # 注册级 IP 封顶（防批量注册打穿免费套餐）
    ok_ip, ip_msg = check_register_allowed(sec_client_ip(request))
    if not ok_ip:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=ip_msg)

    if body.phone:
        from system_flags import effective_sms_106_enabled

        # 国际对外邮箱为主：管理台「国内短信」关 = 禁止一切手机号注册（含子站内部密钥）
        # 行情官已本地身份后，04 不再接受信任跳过写 auth_users
        if not effective_sms_106_enabled():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="手机号注册暂未开放，请使用邮箱注册。",
            )
        # 短信开着时：持有效内部密钥可跳过主站 OTP（子站已本地验码）；仍须开关为开
        _trusted = bool(settings.sms_internal_key) and (
            request.headers.get("X-SMS-Internal-Key") == settings.sms_internal_key
        )
        mob = normalize_mobile(body.phone)
        if len(mob) != 11 or not mob.isdigit():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="手机号格式不正确，请填写 11 位手机号")
        if get_by_phone(db, mob):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该手机号已注册")
        if not _trusted:
            if not verify_and_consume_otp(mob, "register", body.sms_code or ""):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="验证码错误或已过期，请重新获取验证码",
                )
        u = create_user_phone(db, mob, body.password)
    else:
        em = norm_email(body.email or "")
        from email_abuse_guard import assert_email_ok_for_register

        ok_em, em_msg = assert_email_ok_for_register(em)
        if not ok_em:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=em_msg)
        if get_by_email(db, em):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该邮箱已注册")
        if not verify_email_otp(em, "register", body.email_code or ""):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="邮箱验证码错误或已过期，请重新获取",
            )
        u = create_user_email(db, em, body.password)

    record_register(sec_client_ip(request))

    # Token MVP：可选邀请码绑定（无效码静默忽略，不阻断注册）
    try:
        from token_mvp_service import (
            bind_referral_on_register,
            get_or_create_wallet,
            grant_signup_bonus,
        )

        bind_referral_on_register(
            db,
            referee_id=int(u.id),
            invite_code=body.invite_code,
            client_ip=sec_client_ip(request),
        )
        get_or_create_wallet(db, int(u.id))
        # 注册欢迎礼（一次性；已发则跳过）。与邀请注册奖独立。
        try:
            grant_signup_bonus(db, int(u.id))
        except Exception:
            logger.exception("signup welcome bonus failed for user %s", u.id)
    except Exception:
        logger.exception("referral bind / wallet bootstrap failed for user %s", u.id)

    # 广告 UTM / gclid 首触落库（不影响注册成功）
    try:
        from utm_attribution import apply_acquisition_on_register

        apply_acquisition_on_register(
            db,
            u,
            {
                "utm_source": body.utm_source,
                "utm_medium": body.utm_medium,
                "utm_campaign": body.utm_campaign,
                "utm_content": body.utm_content,
                "utm_term": body.utm_term,
                "gclid": body.gclid,
            },
        )
    except Exception:
        logger.exception("acquisition utm persist failed for user %s", u.id)

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
        # 国际版统一账号（DEC-0007）：token 可能由 core（共享 SECRET_KEY）签发，
        # sub 为 core 用户 id → 自动解析/建档本站影子用户。
        from auth_user_service import resolve_or_create_shadow

        u = resolve_or_create_shadow(
            db,
            platform_user_id=uid,
            email=str(payload.get("email") or "") or None,
            phone=str(payload.get("phone") or "") or None,
        )
        if not u:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")
    raise_if_frozen(u)
    return u


@app.post("/v1/auth/session", response_model=AuthTokenResponse)
async def auth_session_from_cookie(request: Request, db: Session = Depends(get_db)):
    """国际版统一账号（DEC-0007）：从共享 cookie 恢复会话。

    主站（www/api.ai24x.com）登录后会写 Domain=.ai24x.com 的 cookie（核心 JWT），
    open 与 core 共享 SECRET_KEY → 本站直接校验并自动建档影子用户，实现
    「主站登录 → open 自动登录」。
    """
    raw = (request.cookies.get("ai24x_auth_token") or "").strip()
    if not raw:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无会话")
    try:
        from jose import JWTError, jwt

        payload = jwt.decode(raw, settings.secret_key, algorithms=["HS256"])
        uid = int(payload["sub"])
    except (JWTError, ValueError, TypeError, KeyError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="会话已失效")
    from auth_user_service import resolve_or_create_shadow

    u = resolve_or_create_shadow(
        db,
        platform_user_id=uid,
        email=str(payload.get("email") or "") or None,
        phone=str(payload.get("phone") or "") or None,
    )
    if not u:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="会话已失效")
    raise_if_frozen(u)
    return AuthTokenResponse(
        token=raw,
        user={"id": int(u.id), "email": u.email or "", "phone": u.phone or ""},
    )


def _auth_user_from_api_key_or_jwt(request: Request, db: Session) -> AuthUser:
    """控制台 JWT 或终端 API Key 均可。

    若同时带 Bearer JWT 与 X-API-Key：优先 JWT（登录身份），避免 Playground
    残留其它账号的 sk 导致余额/身份串号。仅 Key、无有效 JWT 时再走 Key。
    """
    from openai_compat import extract_api_key
    from token_mvp_service import get_api_key_row

    auth = (request.headers.get("Authorization") or "").strip()
    bearer = ""
    if auth.lower().startswith("bearer "):
        bearer = auth[7:].strip()
    # JWT（非 sk-）：校验失败直接报登录失效，禁止把同一 Bearer 再当 API Key 解析
    if bearer and not bearer.startswith("sk-") and bearer.count(".") >= 2:
        return _auth_user_from_bearer(request, db)

    api_key = extract_api_key(request)
    if api_key:
        row = get_api_key_row(db, api_key)
        if row:
            u = db.query(AuthUser).filter(AuthUser.id == int(row.auth_user_id)).first()
            if not u:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在"
                )
            raise_if_frozen(u)
            return u
        # sk- 前缀按 Key 处理，避免误走 JWT 解码报「登录已失效」
        if api_key.startswith("sk-"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "message_zh": "无效的 API Key",
                    "message_en": "Invalid API key",
                    "message": "无效的 API Key",
                    "code": "invalid_api_key",
                },
            )
    return _auth_user_from_bearer(request, db)


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
    from system_flags import effective_sms_106_enabled

    if not effective_sms_106_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="手机号绑定暂未开放。",
        )
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
        raise HTTPException(status_code=503, detail="短信服务暂时不可用，请稍后再试。")
    if (request.headers.get("X-SMS-Internal-Key") or "").strip() != (
        settings.sms_internal_key or ""
    ).strip():
        raise HTTPException(status_code=403, detail="禁止访问")
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
        raise HTTPException(status_code=503, detail="短信服务暂时不可用，请稍后再试。")
    if (request.headers.get("X-SMS-Internal-Key") or "").strip() != (
        settings.sms_internal_key or ""
    ).strip():
        raise HTTPException(status_code=403, detail="禁止访问")
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
        raise HTTPException(status_code=503, detail="短信服务暂时不可用，请稍后再试。")
    if (request.headers.get("X-SMS-Internal-Key") or "").strip() != (
        settings.sms_internal_key or ""
    ).strip():
        raise HTTPException(status_code=403, detail="禁止访问")
    p = (phone or "").strip()
    e = (email or "").strip().lower()
    if not p and not e:
        raise HTTPException(status_code=400, detail="请填写手机号或邮箱")
    q = db.query(AuthUser)
    u = None
    if p:
        u = q.filter(AuthUser.phone == p).first()
    if u is None and e:
        u = q.filter(AuthUser.email == e).first()
    if u is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"ok": True, "user": auth_user_public_dict(u)}


@app.get("/v1/admin/users")
async def admin_users_list(
    request: Request,
    db: Session = Depends(get_db),
    q: str = "",
    limit: int = 50,
    offset: int = 0,
):
    """管理端用户列表（邮箱/手机/ID 搜索）。"""
    _require_internal_key(request)
    from admin_ops_service import admin_list_users

    return admin_list_users(db, q=q, limit=limit, offset=offset)


@app.get("/v1/admin/token/economics")
async def admin_token_economics(request: Request, days: int = 7, db: Session = Depends(get_db)):
    """成本/收入粗算（非上游账单对账）。"""
    _require_internal_key(request)
    from admin_ops_service import admin_economics

    return admin_economics(db, days=days)


@app.get("/v1/admin/token/acquisition")
async def admin_token_acquisition(request: Request, days: int = 14, db: Session = Depends(get_db)):
    """投流归因：渠道→注册→已支付（join 用户首触 UTM）。"""
    _require_internal_key(request)
    from admin_ops_service import admin_acquisition_funnel

    return admin_acquisition_funnel(db, days=days)


@app.get("/v1/admin/token/alerts")
async def admin_token_alerts(request: Request, db: Session = Depends(get_db)):
    """运维告警摘要（只读）。"""
    _require_internal_key(request)
    from admin_ops_service import admin_ops_alerts

    return admin_ops_alerts(db)


@app.post("/v1/admin/token/orders/cleanup")
async def admin_token_orders_cleanup(request: Request, db: Session = Depends(get_db)):
    """清理超时未付订单（默认 dry-run 只预览；body {"dry_run": false} 才真正作废无交易号的超时单）。"""
    _require_internal_key(request)
    dry_run = True
    try:
        body = await request.json()
        if isinstance(body, dict):
            v = body.get("dry_run", True)
            if isinstance(v, bool):
                dry_run = v
            else:
                dry_run = str(v).strip().lower() not in ("0", "false", "no")
    except Exception:
        dry_run = True
    from token_pay_service import cleanup_expired_pending_orders

    return cleanup_expired_pending_orders(db, dry_run=dry_run)


@app.post("/v1/admin/token/orders/{order_id}/confirm_unpaid")
async def admin_token_order_confirm_unpaid(
    order_id: int, request: Request, db: Session = Depends(get_db)
):
    """对账确认某笔 pending 订单未收款（有交易号但渠道确认无捕获/未完成支付）。幂等。"""
    _require_internal_key(request)
    from token_pay_service import confirm_order_unpaid

    return confirm_order_unpaid(db, order_id=order_id)


@app.get("/v1/admin/token/usage_monitor")
async def admin_token_usage_monitor(
    request: Request,
    days: int = 1,
    top_n: int = 20,
    db: Session = Depends(get_db),
):
    """高消耗用户/模型 + 上游通道就绪摘要（防刷与对账）。"""
    _require_internal_key(request)
    from admin_ops_service import admin_usage_monitor

    return admin_usage_monitor(db, days=days, top_n=top_n)


@app.post("/v1/admin/users/{user_id}/freeze")
async def admin_user_freeze(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """冻结账号：禁登录、chat、充值。Body 可选 {\"reason\":\"...\"}。"""
    _require_internal_key(request)
    reason = ""
    try:
        body = await request.json()
        if isinstance(body, dict):
            reason = str(body.get("reason") or "")
    except Exception:
        reason = ""
    try:
        u = set_user_frozen(db, user_id=int(user_id), frozen=True, reason=reason)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {"ok": True, "user": auth_user_public_dict(u)}


@app.post("/v1/admin/users/{user_id}/unfreeze")
async def admin_user_unfreeze(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    _require_internal_key(request)
    try:
        u = set_user_frozen(db, user_id=int(user_id), frozen=False)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {"ok": True, "user": auth_user_public_dict(u)}


@app.post("/v1/admin/users/bootstrap", response_model=AuthTokenResponse)
async def admin_user_bootstrap(
    request: Request,
    body: AdminUserBootstrapBody,
    db: Session = Depends(get_db),
):
    """Create user if missing (phone/email) and set password; requires X-SMS-Internal-Key."""
    if not (settings.sms_internal_key or "").strip():
        raise HTTPException(status_code=503, detail="短信服务暂时不可用，请稍后再试。")
    if (request.headers.get("X-SMS-Internal-Key") or "").strip() != (
        settings.sms_internal_key or ""
    ).strip():
        raise HTTPException(status_code=403, detail="禁止访问")
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
async def keys_list(request: Request, db: Session = Depends(get_db)):
    from token_mvp_service import list_api_keys

    u = _auth_user_from_bearer(request, db)
    return {"keys": list_api_keys(db, int(u.id))}


@app.post("/v1/keys", response_model=ApiKeyCreatedOut)
async def keys_create(request: Request, body: ApiKeyCreateBody, db: Session = Depends(get_db)):
    from token_mvp_service import create_api_key

    u = _auth_user_from_bearer(request, db)
    return create_api_key(db, int(u.id), body.name)


@app.patch("/v1/keys/{key_id}", response_model=ApiKeyOut)
async def keys_rename(key_id: int, request: Request, body: ApiKeyRenameBody, db: Session = Depends(get_db)):
    from token_mvp_service import rename_api_key

    u = _auth_user_from_bearer(request, db)
    return rename_api_key(db, int(u.id), int(key_id), body.name)


@app.delete("/v1/keys/{key_id}")
async def keys_delete(key_id: int, request: Request, db: Session = Depends(get_db)):
    from token_mvp_service import delete_api_key

    u = _auth_user_from_bearer(request, db)
    return delete_api_key(db, int(u.id), int(key_id))


@app.get("/v1/billing/balance", response_model=BillingBalanceOut)
async def billing_balance(request: Request, db: Session = Depends(get_db)):
    """登录 JWT 或 API Key 均可。用调试 Key 调本接口可核对 is_vip_active / 是否同一账号。"""
    from token_mvp_service import get_balance_snapshot

    u = _auth_user_from_api_key_or_jwt(request, db)
    return get_balance_snapshot(db, int(u.id))


@app.post("/v1/billing/topup", response_model=BillingBalanceOut)
async def billing_topup(request: Request, body: BillingTopupBody, db: Session = Depends(get_db)):
    """内部充值接口：需 X-SMS-Internal-Key。"""
    if not (settings.sms_internal_key or "").strip():
        raise HTTPException(status_code=503, detail="服务暂不可用，请稍后再试。")
    if (request.headers.get("X-SMS-Internal-Key") or "").strip() != (
        settings.sms_internal_key or ""
    ).strip():
        raise HTTPException(status_code=403, detail="禁止访问")
    from token_mvp_service import topup_tokens

    return topup_tokens(
        db,
        auth_user_id=int(body.auth_user_id),
        amount=int(body.amount),
        note=body.note,
        set_vip=bool(body.set_vip),
        validity_days=body.validity_days,
    )


@app.get("/v1/billing/usage")
async def billing_usage(
    request: Request,
    db: Session = Depends(get_db),
    limit: int = 50,
    offset: int = 0,
    entry_type: str | None = None,
    since: str | None = None,
    until: str | None = None,
):
    from token_mvp_service import list_usage

    u = _auth_user_from_bearer(request, db)
    return list_usage(
        db,
        int(u.id),
        limit=limit,
        offset=offset,
        entry_type=entry_type,
        since=since,
        until=until,
    )


@app.get("/v1/billing/transactions")
async def billing_transactions(
    request: Request,
    db: Session = Depends(get_db),
    limit: int = 50,
    offset: int = 0,
    entry_type: str | None = None,
    since: str | None = None,
    until: str | None = None,
):
    """账单流水：充值/消耗/赠送/返利/过期全类型 + 交易后余额 + 收支汇总。"""
    from token_mvp_service import list_transactions

    u = _auth_user_from_bearer(request, db)
    return list_transactions(
        db,
        int(u.id),
        limit=limit,
        offset=offset,
        entry_type=entry_type,
        since=since,
        until=until,
    )


@app.get("/v1/billing/usage/daily")
async def billing_usage_daily(
    request: Request,
    db: Session = Depends(get_db),
    days: int = 30,
):
    """每日消耗趋势（UTC 日口径）：tokens / 花费 / 请求次数，缺天补零。"""
    from token_mvp_service import usage_daily

    u = _auth_user_from_bearer(request, db)
    return usage_daily(db, int(u.id), days=days)


@app.get("/v1/billing/usage/models")
async def billing_usage_models(
    request: Request,
    db: Session = Depends(get_db),
    days: int = 30,
    top_n: int = 10,
):
    """模型消耗榜：按 model 聚合 tokens / 花费 / 请求次数 + 占比。"""
    from token_mvp_service import usage_models

    u = _auth_user_from_bearer(request, db)
    return usage_models(db, int(u.id), days=days, top_n=top_n)


@app.get("/v1/billing/usage/keys")
async def billing_usage_keys(
    request: Request,
    db: Session = Depends(get_db),
    days: int = 30,
    top_n: int = 8,
):
    """按 API Key 消耗榜：JWT 会话（api_key_id 为空）归为「控制台会话」。"""
    from token_mvp_service import usage_keys

    u = _auth_user_from_bearer(request, db)
    return usage_keys(db, int(u.id), days=days, top_n=top_n)


@app.get("/v1/referrals/code")
async def referrals_code(request: Request, db: Session = Depends(get_db)):
    from token_mvp_service import get_or_create_invite_code

    u = _auth_user_from_bearer(request, db)
    row = get_or_create_invite_code(db, int(u.id))
    return {"code": row.code, "auth_user_id": int(u.id)}


@app.get("/v1/referrals/stats")
async def referrals_stats(request: Request, db: Session = Depends(get_db)):
    from token_mvp_service import get_or_create_invite_code, referral_stats

    u = _auth_user_from_bearer(request, db)
    get_or_create_invite_code(db, int(u.id))
    return referral_stats(db, int(u.id))


@app.get("/v1/referrals/earnings")
async def referrals_earnings(
    request: Request,
    db: Session = Depends(get_db),
    limit: int = 50,
    offset: int = 0,
):
    from token_mvp_service import referral_earnings

    u = _auth_user_from_bearer(request, db)
    return referral_earnings(db, int(u.id), limit=limit, offset=offset)




@app.get("/v1/referrals/invitees")
async def referrals_invitees(
    request: Request,
    db: Session = Depends(get_db),
    limit: int = 50,
    offset: int = 0,
):
    """被邀请人列表：脱敏用户名 / 注册时间 / 是否激活。"""
    from token_mvp_service import referral_invitees

    u = _auth_user_from_bearer(request, db)
    return referral_invitees(db, int(u.id), limit=limit, offset=offset)
@app.get("/v1/referrals/summary")
async def referrals_summary(request: Request, db: Session = Depends(get_db)):
    """兼容旧占位路径：等同 stats + code。"""
    from token_mvp_service import get_or_create_invite_code, referral_stats

    u = _auth_user_from_bearer(request, db)
    code = get_or_create_invite_code(db, int(u.id)).code
    stats = referral_stats(db, int(u.id))
    return {"code": code, **stats}


@app.post("/v1/support/ask")
async def support_ask(request: Request, body: SupportAskBody, db: Session = Depends(get_db)):
    """登录用户即时协助：平台成本，不扣用户 Token；有日帽。"""
    from support_bot import ask_support

    u = _auth_user_from_bearer(request, db)
    lang = (body.lang or "").strip().lower()
    if lang not in ("zh", "en"):
        # 粗判：含中文则 zh
        lang = "zh" if any("\u4e00" <= ch <= "\u9fff" for ch in (body.question or "")) else "en"
    return ask_support(auth_user_id=int(u.id), question=body.question, lang_hint=lang)


@app.post("/v1/support/tickets")
async def support_ticket_create(
    request: Request, body: SupportTicketCreateBody, db: Session = Depends(get_db)
):
    from support_tickets import create_ticket

    u = _auth_user_from_bearer(request, db)
    r = create_ticket(
        db,
        auth_user_id=int(u.id),
        category=body.category,
        body=body.body,
        subject=body.subject or "",
        ai_summary=body.ai_summary,
    )
    if not r.get("ok"):
        raise HTTPException(status_code=400, detail=r.get("message") or "提交失败")
    return r


@app.get("/v1/support/tickets")
async def support_ticket_list(
    request: Request,
    db: Session = Depends(get_db),
    limit: int = 20,
    offset: int = 0,
):
    from support_tickets import list_tickets_for_user

    u = _auth_user_from_bearer(request, db)
    return list_tickets_for_user(db, int(u.id), limit=limit, offset=offset)


@app.get("/v1/support/tickets/{ticket_id}")
async def support_ticket_detail(
    request: Request, ticket_id: int, db: Session = Depends(get_db)
):
    from support_tickets import get_ticket_detail

    u = _auth_user_from_bearer(request, db)
    r = get_ticket_detail(db, int(u.id), int(ticket_id))
    if not r.get("ok"):
        raise HTTPException(status_code=404, detail=r.get("message") or "工单不存在")
    return r


@app.post("/v1/support/tickets/{ticket_id}/reply")
async def support_ticket_user_reply(
    request: Request,
    ticket_id: int,
    body: SupportTicketUserReplyBody,
    db: Session = Depends(get_db),
):
    from support_tickets import user_reply_ticket

    u = _auth_user_from_bearer(request, db)
    r = user_reply_ticket(db, int(u.id), int(ticket_id), body.content)
    if not r.get("ok"):
        raise HTTPException(status_code=400, detail=r.get("message") or "回复失败")
    return r


@app.get("/v1/admin/token/referrals")
async def admin_token_referrals(
    request: Request,
    db: Session = Depends(get_db),
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    _require_internal_key(request)
    from token_mvp_service import admin_referral_overview

    return admin_referral_overview(db, q=q, limit=limit, offset=offset)


@app.get("/v1/admin/token/referrals/{auth_user_id}")
async def admin_token_referral_detail(
    request: Request,
    auth_user_id: int,
    db: Session = Depends(get_db),
    limit: int = 100,
):
    _require_internal_key(request)
    from token_mvp_service import admin_referral_detail

    return admin_referral_detail(db, int(auth_user_id), limit=limit)


@app.get("/v1/admin/token/tickets")
async def admin_token_tickets(
    request: Request,
    db: Session = Depends(get_db),
    status: str | None = None,
    category: str | None = None,
    auth_user_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
):
    _require_internal_key(request)
    from support_tickets import admin_list_tickets

    return admin_list_tickets(
        db,
        status=status,
        category=category,
        auth_user_id=auth_user_id,
        limit=limit,
        offset=offset,
    )


@app.post("/v1/admin/token/tickets/{ticket_id}/reply")
async def admin_token_ticket_reply(
    request: Request,
    ticket_id: int,
    body: SupportTicketReplyBody,
    db: Session = Depends(get_db),
):
    _require_internal_key(request)
    from support_tickets import admin_reply_ticket

    r = admin_reply_ticket(db, ticket_id=int(ticket_id), reply=body.reply, close=bool(body.close))
    if not r.get("ok"):
        raise HTTPException(status_code=400, detail=r.get("message") or "回复失败")
    return r


# —— Token 套餐 / 在线支付（独立于 a1；默认 TOKEN_PAY_ENABLED=false）——


_ADMIN_RATE: dict[str, list[float]] = {}


def _admin_rate_limited(request: Request) -> None:
    """管理接口简单限速：同一 IP 每分钟超过上限直接 429（进程内；多实例建议网关层再限）。"""
    limit = max(10, int(getattr(settings, "admin_rate_limit_per_min", 0) or 60))
    ip = client_ip(request)
    now = time.time()
    bucket = _ADMIN_RATE.setdefault(ip, [])
    while bucket and now - bucket[0] > 60:
        bucket.pop(0)
    if len(bucket) >= limit:
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试。")
    bucket.append(now)


def _admin_ip_allowed(request: Request) -> bool:
    """可选 ADMIN_IP_WHITELIST：逗号分隔 IP/CIDR；未配置=放行全部（依赖密钥鉴权）。"""
    wl = (getattr(settings, "admin_ip_whitelist", "") or "").strip()
    if not wl:
        return True
    import ipaddress

    ip = client_ip(request)
    try:
        addr = ipaddress.ip_address(ip)
    except Exception:
        return False
    for item in wl.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            if "/" in item:
                if addr in ipaddress.ip_network(item, strict=False):
                    return True
            elif item == ip:
                return True
        except Exception:
            continue
    return False


def _require_internal_key(request: Request) -> None:
    """管理接口鉴权：配了独立 ADMIN_API_KEY 则仅接受该钥（头 X-Admin-Key）；
    未配时回退 SMS 内部密钥（兼容旧部署，生产建议尽快配置独立管理密钥）。
    附：同 IP 限速 + 可选 ADMIN_IP_WHITELIST 白名单。
    """
    admin = (getattr(settings, "admin_api_key", "") or "").strip()
    sms_k = (settings.sms_internal_key or "").strip()
    if not (admin or sms_k):
        raise HTTPException(status_code=503, detail="服务暂不可用，请稍后再试。")
    if not _admin_ip_allowed(request):
        raise HTTPException(status_code=403, detail="禁止访问")
    _admin_rate_limited(request)
    provided = (
        (request.headers.get("X-Admin-Key") or "").strip()
        or (request.headers.get("X-SMS-Internal-Key") or "").strip()
    )
    if admin:
        # 已配置独立管理密钥：仅接受该钥，SMS 密钥不再放行（防双钥混用/弱钥穿透）
        if provided and provided == admin:
            return
        raise HTTPException(status_code=403, detail="禁止访问")
    if sms_k and provided == sms_k:
        return
    raise HTTPException(status_code=403, detail="禁止访问")




@app.get("/v1/billing/plans")
async def billing_plans():
    """公开套餐目录 + 支付通道就绪状态（不含密钥）。"""
    from token_pay_service import public_plans

    return public_plans()


@app.get("/v1/billing/pay/status")
async def billing_pay_status():
    """支付通道自检（不含密钥）；与控制台按钮同一套 wechat_pay_configured / alipay_configured。"""
    from pathlib import Path

    from pay_alipay_wap import alipay_configured
    from pay_creem import creem_configured
    from pay_paypal import paypal_configured
    from pay_wechat_v3 import wechat_pay_configured
    from token_pay_service import pay_settings_ns, token_pay_enabled, token_pay_mock_allowed

    cfg = pay_settings_ns()
    wx_path = (cfg.wechat_mch_private_key_path or "").strip()
    wx_pem = bool((cfg.wechat_mch_private_key_pem or "").strip())
    api_v3 = str(cfg.wechat_api_v3_key or "")
    wx_checks = {
        "mch_id": bool(cfg.wechat_mch_id),
        "app_id": bool(cfg.wechat_app_id),
        "serial_no": bool(cfg.wechat_mch_serial_no),
        "private_key": bool(wx_pem or wx_path),
        "private_key_pem_inline": wx_pem,
        "private_key_path_set": bool(wx_path),
        "private_key_path_exists": bool(wx_path and Path(wx_path).exists()),
        "api_v3_key_len_32": len(api_v3) == 32,
        "api_v3_key_len": len(api_v3),
        "notify_url": bool(cfg.wechat_notify_url),
    }
    wx_missing = [k for k, ok in wx_checks.items() if k in (
        "mch_id", "app_id", "serial_no", "private_key", "api_v3_key_len_32", "notify_url"
    ) and not ok]
    wx_cfg = wechat_pay_configured(cfg)
    ali_cfg = alipay_configured(cfg)
    pp_cfg = paypal_configured(cfg)
    creem_cfg = creem_configured(cfg)
    enabled = token_pay_enabled()
    wechat_notify = cfg.wechat_notify_url or ""
    alipay_notify = cfg.alipay_notify_url or ""
    return {
        "ok": True,
        "token_pay_enabled": enabled,
        "token_pay_mock_enabled": token_pay_mock_allowed(),
        "wechat": {
            "merchant_configured": wx_cfg,
            "ui_ready": bool(enabled and wx_cfg),
            "checks": wx_checks,
            "missing": wx_missing,
            "notify_url_set": bool(wechat_notify),
            "notify_url_hint": wechat_notify[:80] + ("…" if len(wechat_notify) > 80 else ""),
        },
        "alipay": {
            "merchant_configured": ali_cfg,
            "ui_ready": bool(enabled and ali_cfg),
            "notify_url_set": bool(alipay_notify),
            "notify_url_hint": alipay_notify[:80] + ("…" if len(alipay_notify) > 80 else ""),
            "return_url_set": bool((cfg.alipay_return_url or "").strip()),
        },
        "creem": {
            "merchant_configured": bool(creem_cfg),
            "ui_ready": bool(enabled and creem_cfg),
            "mode": str(getattr(cfg, "creem_mode", "test") or "test"),
            "webhook_secret_set": bool(getattr(cfg, "creem_webhook_secret", "") or ""),
            "return_url_set": bool(getattr(cfg, "creem_return_url", "") or ""),
        },
        "paypal": {
            "merchant_configured": pp_cfg,
            "ui_ready": bool(enabled and pp_cfg),
            "mode": str(getattr(cfg, "paypal_mode", "sandbox") or "sandbox"),
            "webhook_id_set": bool(getattr(cfg, "paypal_webhook_id", "") or ""),
            "return_url_set": bool(getattr(cfg, "paypal_return_url", "") or ""),
            "locale": str(getattr(cfg, "paypal_locale", "") or "en-US"),
            "landing_page": str(getattr(cfg, "paypal_landing_page", "") or "BILLING"),
        },
        "console_hint": (
            "控制台只显示 wechat_ready/alipay_ready/paypal_ready=true 的通道；"
            "看 /v1/billing/plans 的 pay 字段，或本接口 wechat.missing"
        ),
        "next_steps": [
            "确认 TOKEN_*_NOTIFY_URL 与 a1 回调不同，并在商户平台登记 Token 回调",
            "微信缺项见 wechat.missing（常见：serial_no 空，或 api_v3_key 不是正好 32 位）",
            "PayPal：配 PAYPAL_CLIENT_ID/SECRET，MODE=sandbox 联调；Live 仅开在副脑04",
            "改完 api/.env 后 pm2 restart core-api-8002 --update-env",
            "实付后核对 token_pay_orders + 钱包；并回归 a1 支付",
        ],
        "a1_safety": "本接口不读写 a1 pay_orders；同步脚本从不复制 a1 notify",
    }


@app.post("/v1/billing/wechat/native")
async def billing_wechat_native(
    request: Request, body: TokenPayCreateBody, db: Session = Depends(get_db)
):
    from token_pay_service import create_wechat_native

    u = _auth_user_from_bearer(request, db)
    return await create_wechat_native(
        db, auth_user_id=int(u.id), plan=body.plan, product=body.product
    )


@app.post("/v1/billing/alipay/wap")
async def billing_alipay_wap(
    request: Request, body: TokenPayCreateBody, db: Session = Depends(get_db)
):
    from token_pay_service import create_alipay_wap

    u = _auth_user_from_bearer(request, db)
    return await create_alipay_wap(
        db, auth_user_id=int(u.id), plan=body.plan, product=body.product
    )


@app.post("/v1/billing/paypal/order")
async def billing_paypal_order(
    request: Request, body: TokenPayCreateBody, db: Session = Depends(get_db)
):
    from token_pay_service import create_paypal_order

    u = _auth_user_from_bearer(request, db)
    return await create_paypal_order(
        db, auth_user_id=int(u.id), plan=body.plan, product=body.product
    )


@app.post("/v1/billing/creem/order")
async def billing_creem_order(
    request: Request, body: TokenPayCreateBody, db: Session = Depends(get_db)
):
    from token_pay_service import create_creem_order

    u = _auth_user_from_bearer(request, db)
    return await create_creem_order(
        db, auth_user_id=int(u.id), plan=body.plan, product=body.product
    )


@app.post("/v1/billing/creem/query")
async def billing_creem_query(
    request: Request, body: TokenQueryFulfillBody, db: Session = Depends(get_db)
):
    from token_pay_service import query_creem_order

    u = _auth_user_from_bearer(request, db)
    return await query_creem_order(db, out_trade_no=body.out_trade_no, auth_user_id=int(u.id))


@app.post("/v1/billing/dodo/order")
async def billing_dodo_order(
    request: Request, body: TokenPayCreateBody, db: Session = Depends(get_db)
):
    from token_pay_service import create_dodo_order

    u = _auth_user_from_bearer(request, db)
    return await create_dodo_order(
        db, auth_user_id=int(u.id), plan=body.plan, product=body.product
    )


@app.post("/v1/billing/dodo/query")
async def billing_dodo_query(
    request: Request, body: TokenQueryFulfillBody, db: Session = Depends(get_db)
):
    from token_pay_service import query_dodo_order

    u = _auth_user_from_bearer(request, db)
    return await query_dodo_order(db, out_trade_no=body.out_trade_no, auth_user_id=int(u.id))


@app.get("/v1/billing/orders")
async def billing_orders_mine(request: Request, db: Session = Depends(get_db), limit: int = 20):
    from token_pay_service import list_orders_for_user

    u = _auth_user_from_bearer(request, db)
    return list_orders_for_user(db, int(u.id), limit=limit)


@app.post("/v1/billing/orders/mock_fulfill")
async def billing_orders_mock_fulfill(
    request: Request, body: TokenMockFulfillBody, db: Session = Depends(get_db)
):
    """
    本地/联调模拟到账。需登录；订单须属于当前用户。
    生产请保持 TOKEN_PAY_MOCK_ENABLED=false，且不要开 TOKEN_PAY_ENABLED 前乱测真钱。
    """
    from token_pay_service import mock_fulfill

    u = _auth_user_from_bearer(request, db)
    return mock_fulfill(db, out_trade_no=body.out_trade_no, auth_user_id=int(u.id))


@app.post("/v1/billing/crypto/order")
async def billing_crypto_order(
    request: Request, body: TokenPayCreateBody, db: Session = Depends(get_db)
):
    """USDT-TRC20 下单：返回收款地址/金额/单号。"""
    from token_pay_service import create_crypto_order

    u = _auth_user_from_bearer(request, db)
    return create_crypto_order(
        db, auth_user_id=int(u.id), plan=body.plan, product=body.product
    )


@app.post("/v1/billing/crypto/submit")
async def billing_crypto_submit(
    request: Request, body: TokenCryptoSubmitBody, db: Session = Depends(get_db)
):
    """用户提交链上 txid，订单进入 awaiting_verify。"""
    from token_pay_service import submit_crypto_txid

    u = _auth_user_from_bearer(request, db)
    return submit_crypto_txid(
        db, out_trade_no=body.out_trade_no, txid=body.txid, auth_user_id=int(u.id)
    )


@app.post("/v1/billing/crypto/verify")
async def billing_crypto_verify(
    request: Request, body: TokenMockFulfillBody, db: Session = Depends(get_db)
):
    """v1 人工核验：仅 mock 环境（本地/测试）允许模拟入账；生产需 X-Admin-Key 且强制 TronScan 链上核验，防白嫖。"""
    from token_pay_service import verify_crypto_order, token_pay_mock_allowed

    mock = token_pay_mock_allowed()
    if not mock:
        _require_internal_key(request)
    u = _auth_user_from_bearer(request, db)
    return verify_crypto_order(
        db, out_trade_no=body.out_trade_no, auth_user_id=int(u.id), mock=mock
    )


@app.post("/v1/billing/wechat/query_and_fulfill")
async def billing_wechat_query_and_fulfill(
    request: Request, body: TokenQueryFulfillBody, db: Session = Depends(get_db)
):
    from token_pay_service import query_and_fulfill_wechat

    u = _auth_user_from_bearer(request, db)
    return await query_and_fulfill_wechat(db, out_trade_no=body.out_trade_no, auth_user_id=int(u.id))


@app.post("/v1/billing/alipay/query_and_fulfill")
async def billing_alipay_query_and_fulfill(
    request: Request, body: TokenQueryFulfillBody, db: Session = Depends(get_db)
):
    from token_pay_service import query_and_fulfill_alipay

    u = _auth_user_from_bearer(request, db)
    return query_and_fulfill_alipay(db, out_trade_no=body.out_trade_no, auth_user_id=int(u.id))


@app.post("/v1/billing/paypal/capture")
async def billing_paypal_capture(
    request: Request, body: TokenQueryFulfillBody, db: Session = Depends(get_db)
):
    """PayPal 支付返回后 Capture + 履约（也可当「确认到账」）。"""
    from token_pay_service import capture_and_fulfill_paypal

    u = _auth_user_from_bearer(request, db)
    return await capture_and_fulfill_paypal(
        db, out_trade_no=body.out_trade_no, auth_user_id=int(u.id)
    )


@app.post("/v1/billing/paypal/query_and_fulfill")
async def billing_paypal_query_and_fulfill(
    request: Request, body: TokenQueryFulfillBody, db: Session = Depends(get_db)
):
    from token_pay_service import query_and_fulfill_paypal

    u = _auth_user_from_bearer(request, db)
    return await query_and_fulfill_paypal(db, out_trade_no=body.out_trade_no, auth_user_id=int(u.id))


@app.get("/v1/models")
async def list_models(request: Request, db: Session = Depends(get_db)):
    """公开模型目录；若已登录则按 VIP 状态返回推荐链。"""
    from model_router import list_models_public

    is_vip = False
    allow_names = None
    try:
        u = _auth_user_from_bearer(request, db)
        from token_mvp_service import get_balance_snapshot, value_pack_allowed_models

        snap = get_balance_snapshot(db, int(u.id))
        is_vip = bool(snap.get("is_vip_active"))
        if not is_vip:
            allow_names = value_pack_allowed_models(db, int(u.id))
    except HTTPException:
        pass
    m = list_models_public(is_vip=is_vip, allow_names=allow_names)
    from openai_compat import openai_models_payload
    return {**m, **openai_models_payload(m)}


@app.post("/v1/billing/wechat/notify")
async def billing_wechat_notify(request: Request, db: Session = Depends(get_db)):
    """微信异步通知 → 仅履约 token_pay_orders（T 前缀）。不碰 a1 pay_orders。"""
    from token_pay_service import pay_settings_ns, try_fulfill, token_pay_enabled

    if not token_pay_enabled():
        return JSONResponse(status_code=200, content={"code": "FAIL", "message": "token_pay_disabled"})
    body_str = (await request.body()).decode("utf-8", errors="replace")
    headers = {k: v for k, v in request.headers.items()}
    try:
        from pay_wechat_v3 import parse_payment_notify

        txn = await parse_payment_notify(pay_settings_ns(), headers=headers, body_str=body_str)
    except Exception as e:
        logger.warning("token wechat notify verify failed: %s", e)
        return JSONResponse(status_code=200, content={"code": "FAIL", "message": "verify_failed"})

    if str(txn.get("trade_state") or "") != "SUCCESS":
        return JSONResponse(status_code=200, content={"code": "SUCCESS", "message": "ignored"})

    otn = str(txn.get("out_trade_no") or "")
    txid = str(txn.get("transaction_id") or "")
    total = int(((txn.get("amount") or {}) if isinstance(txn.get("amount"), dict) else {}).get("total") or 0)
    r = try_fulfill(db, out_trade_no=otn, transaction_id=txid, amount_fen=total, channel_tag="wechat")
    if not r.get("ok"):
        logger.warning("token wechat fulfill fail otn=%s err=%s", otn, r.get("error"))
        return JSONResponse(status_code=200, content={"code": "FAIL", "message": str(r.get("error") or "fail")})
    return JSONResponse(status_code=200, content={"code": "SUCCESS", "message": "成功"})


@app.post("/v1/billing/alipay/notify")
async def billing_alipay_notify(request: Request, db: Session = Depends(get_db)):
    """支付宝异步通知 → 仅履约 token_pay_orders。"""
    from token_pay_service import pay_settings_ns, try_fulfill, token_pay_enabled

    if not token_pay_enabled():
        return "failure"
    form = dict(await request.form())
    form_s = {str(k): str(v) for k, v in form.items()}
    try:
        from pay_alipay_wap import verify_notify

        ok, err = verify_notify(pay_settings_ns(), form=form_s)
    except Exception as e:
        logger.warning("token alipay notify error: %s", e)
        return "failure"
    if not ok:
        logger.warning("token alipay verify fail: %s", err)
        return "failure"

    trade_status = (form_s.get("trade_status") or "").strip()
    if trade_status not in ("TRADE_SUCCESS", "TRADE_FINISHED"):
        return "success"

    otn = (form_s.get("out_trade_no") or "").strip()
    trade_no = (form_s.get("trade_no") or "").strip()
    try:
        yuan = float(form_s.get("total_amount") or "0")
        fen = int(round(yuan * 100))
    except Exception:
        fen = 0
    r = try_fulfill(db, out_trade_no=otn, transaction_id=trade_no, amount_fen=fen, channel_tag="alipay")
    if not r.get("ok"):
        logger.warning("token alipay fulfill fail otn=%s err=%s", otn, r.get("error"))
        return "failure"
    return "success"


@app.post("/v1/billing/paypal/webhook")
async def billing_paypal_webhook(request: Request, db: Session = Depends(get_db)):
    """PayPal Webhook → Capture 完成后履约。生产必须 WEBHOOK_ID + 验签通过。"""
    import json

    from security_util import is_prod
    from token_pay_service import pay_settings_ns, try_fulfill, token_pay_enabled

    if not token_pay_enabled():
        return JSONResponse(status_code=200, content={"ok": False, "reason": "disabled"})
    body_str = (await request.body()).decode("utf-8", errors="replace")
    headers = {k: v for k, v in request.headers.items()}
    cfg = pay_settings_ns()
    from pay_paypal import (
        extract_capture_id,
        extract_captured_usd_cents,
        extract_custom_id,
        verify_webhook_signature,
    )

    webhook_id = str(getattr(cfg, "paypal_webhook_id", "") or "").strip()
    mode = str(getattr(cfg, "paypal_mode", "sandbox") or "sandbox").lower()
    if is_prod() or mode in ("live", "production"):
        if not webhook_id:
            logger.error("paypal webhook rejected: PAYPAL_WEBHOOK_ID empty in prod/live")
            return JSONResponse(status_code=503, content={"ok": False, "reason": "webhook_not_configured"})

    verified = False
    try:
        verified = await verify_webhook_signature(cfg, headers=headers, body=body_str)
    except Exception as e:
        logger.warning("paypal webhook verify error: %s", e)
    if not verified:
        if is_prod() or mode in ("live", "production"):
            return JSONResponse(status_code=400, content={"ok": False, "reason": "verify_failed"})
        if mode not in ("sandbox", "test", "dev"):
            return JSONResponse(status_code=400, content={"ok": False, "reason": "verify_failed"})
        logger.warning("paypal webhook unverified — allowed only in sandbox/test/dev")

    try:
        event = json.loads(body_str or "{}")
    except Exception:
        return JSONResponse(status_code=400, content={"ok": False, "reason": "bad_json"})

    et = str(event.get("event_type") or "")
    resource = event.get("resource") or {}
    # 兼容 CHECKOUT.ORDER.APPROVED / PAYMENT.CAPTURE.COMPLETED
    otn = extract_custom_id(resource) if isinstance(resource, dict) else ""
    if not otn and isinstance(resource, dict):
        otn = str(resource.get("custom_id") or resource.get("invoice_id") or "").strip()
        # capture 资源里 custom_id 可能在 supplementary_data / purchase_units
        if not otn:
            for pu in resource.get("purchase_units") or []:
                otn = str(pu.get("custom_id") or pu.get("reference_id") or "").strip()
                if otn:
                    break
    if not otn.startswith("T"):
        return JSONResponse(status_code=200, content={"ok": True, "ignored": True, "event": et})

    cents = extract_captured_usd_cents(resource) if isinstance(resource, dict) else 0
    if cents <= 0 and isinstance(resource, dict):
        try:
            cents = int(round(float((resource.get("amount") or {}).get("value") or 0) * 100))
        except Exception:
            cents = 0
    txid = extract_capture_id(resource) if isinstance(resource, dict) else ""
    if not txid and isinstance(resource, dict):
        txid = str(resource.get("id") or "")[:128]
    if cents <= 0 or not txid:
        logger.warning("paypal webhook incomplete otn=%s event=%s", otn, et)
        return JSONResponse(status_code=200, content={"ok": False, "reason": "incomplete"})

    r = try_fulfill(db, out_trade_no=otn, transaction_id=txid, amount_fen=cents, channel_tag="paypal_webhook")
    if not r.get("ok"):
        logger.warning("paypal webhook fulfill fail otn=%s err=%s", otn, r.get("error"))
        return JSONResponse(status_code=200, content={"ok": False, "error": r.get("error")})
    return JSONResponse(status_code=200, content={"ok": True, "out_trade_no": otn})


@app.post("/v1/billing/creem/webhook")
async def billing_creem_webhook(request: Request, db: Session = Depends(get_db)):
    """Creem Webhook -> checkout.completed fulfill (HMAC-SHA256 verified)."""
    import json

    from security_util import is_prod
    from token_pay_service import pay_settings_ns, try_fulfill, token_pay_enabled

    if not token_pay_enabled():
        return JSONResponse(status_code=200, content={"ok": False, "reason": "disabled"})
    body_str = (await request.body()).decode("utf-8", errors="replace")
    headers = {k: v for k, v in request.headers.items()}
    cfg = pay_settings_ns()
    from pay_creem import extract_checkout_data, verify_webhook_signature

    mode = str(getattr(cfg, "creem_mode", "test") or "test").lower()
    verified = False
    try:
        verified = verify_webhook_signature(cfg, headers=headers, body=body_str)
    except Exception as e:
        logger.warning("creem webhook verify error: %s", e)
    if not verified:
        if is_prod() or mode in ("live", "production"):
            return JSONResponse(status_code=400, content={"ok": False, "reason": "verify_failed"})
        if mode not in ("test", "sandbox", "dev"):
            return JSONResponse(status_code=400, content={"ok": False, "reason": "verify_failed"})
        logger.warning("creem webhook unverified - allowed only in test/sandbox/dev")

    try:
        event = json.loads(body_str or "{}")
    except Exception:
        return JSONResponse(status_code=400, content={"ok": False, "reason": "bad_json"})

    et = str(event.get("eventType") or event.get("event_type") or "")
    if et != "checkout.completed":
        return JSONResponse(status_code=200, content={"ok": True, "ignored": True, "event": et})

    d = extract_checkout_data(event)
    otn = d["request_id"]
    if not otn.startswith("T"):
        return JSONResponse(status_code=200, content={"ok": True, "ignored": True, "event": et})
    if d["status"] not in ("completed", "paid", ""):
        return JSONResponse(status_code=200, content={"ok": True, "ignored": True, "event": et})
    txid = d["order_id"] or d["checkout_id"]
    if not txid:
        return JSONResponse(status_code=200, content={"ok": False, "reason": "incomplete"})

    from models import TokenPayOrder
    from token_plans import get_plan

    row = db.query(TokenPayOrder).filter(TokenPayOrder.out_trade_no == otn).first()
    if not row:
        return JSONResponse(status_code=200, content={"ok": False, "reason": "order_not_found"})
    meta = get_plan(str(row.plan)) or {}
    expect_pid = str(meta.get("creem_product_id") or "").strip()
    if not expect_pid:
        logger.warning("creem webhook plan missing product id otn=%s plan=%s", otn, row.plan)
        return JSONResponse(status_code=200, content={"ok": False, "reason": "product_not_configured"})
    if d["product_id"] and expect_pid != d["product_id"]:
        logger.warning(
            "creem webhook product mismatch otn=%s expect=%s got=%s",
            otn,
            expect_pid,
            d["product_id"],
        )
        return JSONResponse(status_code=200, content={"ok": False, "reason": "product_mismatch"})
    if d["amount"] and int(row.amount_fen) != int(d["amount"]):
        logger.warning(
            "creem webhook amount diff otn=%s local=%s creem=%s currency=%s",
            otn,
            row.amount_fen,
            d["amount"],
            d["currency"],
        )
        # 2026-08-09 harden: USD 订单金额不一致 = 本地定价与 Creem 产品价不一致（配置错误），
        # 拒绝履约，避免按错误金额到账；非 USD（汇率换算）仅告警不阻断。
        if str(d["currency"] or "").upper() == "USD":
            return JSONResponse(status_code=200, content={"ok": False, "reason": "amount_mismatch"})

    r = try_fulfill(
        db,
        out_trade_no=otn,
        transaction_id=txid,
        amount_fen=int(row.amount_fen),
        channel_tag="creem_webhook",
    )
    if not r.get("ok"):
        logger.warning("creem webhook fulfill fail otn=%s err=%s", otn, r.get("error"))
        return JSONResponse(status_code=200, content={"ok": False, "error": r.get("error")})
    return JSONResponse(status_code=200, content={"ok": True, "out_trade_no": otn})


@app.post("/v1/billing/dodo/webhook")
async def billing_dodo_webhook(request: Request, db: Session = Depends(get_db)):
    """Dodo Payments Webhook -> payment.succeeded fulfill (Standard Webhooks verified)."""
    import json

    from security_util import is_prod
    from token_pay_service import pay_settings_ns, try_fulfill, token_pay_enabled

    if not token_pay_enabled():
        return JSONResponse(status_code=200, content={"ok": False, "reason": "disabled"})
    body_str = (await request.body()).decode("utf-8", errors="replace")
    headers = {k: v for k, v in request.headers.items()}
    cfg = pay_settings_ns()
    from pay_dodo import extract_payment_data, verify_webhook_signature

    mode = str(getattr(cfg, "dodo_mode", "test") or "test").lower()
    verified = False
    try:
        verified = verify_webhook_signature(cfg, headers=headers, body=body_str)
    except Exception as e:
        logger.warning("dodo webhook verify error: %s", e)
    if not verified:
        if is_prod() or mode in ("live", "production"):
            return JSONResponse(status_code=400, content={"ok": False, "reason": "verify_failed"})
        if mode not in ("test", "sandbox", "dev"):
            return JSONResponse(status_code=400, content={"ok": False, "reason": "verify_failed"})
        logger.warning("dodo webhook unverified - allowed only in test/sandbox/dev")

    try:
        event = json.loads(body_str or "{}")
    except Exception:
        return JSONResponse(status_code=400, content={"ok": False, "reason": "bad_json"})

    d = extract_payment_data(event)
    et = d["event_type"]
    if et not in ("payment.succeeded", "payment.failed"):
        return JSONResponse(status_code=200, content={"ok": True, "ignored": True, "event": et})
    otn = d["out_trade_no"]
    if not otn:
        return JSONResponse(status_code=200, content={"ok": False, "reason": "missing_out_trade_no"})
    txid = d["payment_id"] or d["checkout_id"]
    if not txid:
        return JSONResponse(status_code=200, content={"ok": False, "reason": "incomplete"})

    from models import TokenPayOrder

    row = db.query(TokenPayOrder).filter(TokenPayOrder.out_trade_no == otn).first()
    if not row:
        return JSONResponse(status_code=200, content={"ok": False, "reason": "order_not_found"})

    # 失败事件：pending -> failed（不改已到账单）
    if et == "payment.failed":
        if str(row.status) in ("pending", "awaiting_verify"):
            row.status = "failed"
            db.commit()
        return JSONResponse(status_code=200, content={"ok": True, "event": et})

    # 产品校验：BYOK 走 byok_plans；token 走 token_plans
    if str(row.product) == "byok":
        from byok_plans import resolve_byok_plan

        meta = resolve_byok_plan(str(row.plan)) or {}
    else:
        from token_plans import get_plan

        meta = get_plan(str(row.plan)) or {}
    expect_pid = str(meta.get("dodo_product_id") or "").strip()
    if not expect_pid:
        logger.warning("dodo webhook plan missing product id otn=%s plan=%s", otn, row.plan)
        return JSONResponse(status_code=200, content={"ok": False, "reason": "product_not_configured"})
    if d["product_id"] and expect_pid != d["product_id"]:
        logger.warning(
            "dodo webhook product mismatch otn=%s expect=%s got=%s",
            otn,
            expect_pid,
            d["product_id"],
        )
        return JSONResponse(status_code=200, content={"ok": False, "reason": "product_mismatch"})
    # Dodo total_amount 为最小货币单位且含税：允许 >= 本地价（容税），不足才拒绝
    if d["amount"] and int(d["amount"]) < int(row.amount_fen):
        logger.warning(
            "dodo webhook amount below local otn=%s local=%s dodo=%s currency=%s",
            otn,
            row.amount_fen,
            d["amount"],
            d["currency"],
        )
        return JSONResponse(status_code=200, content={"ok": False, "reason": "amount_mismatch"})
    if d["currency"] and d["currency"] != "USD":
        logger.warning(
            "dodo webhook non-USD currency otn=%s currency=%s", otn, d["currency"]
        )

    r = try_fulfill(
        db,
        out_trade_no=otn,
        transaction_id=txid,
        amount_fen=int(row.amount_fen),
        channel_tag="dodo_webhook",
    )
    if not r.get("ok"):
        logger.warning("dodo webhook fulfill fail otn=%s err=%s", otn, r.get("error"))
        return JSONResponse(status_code=200, content={"ok": False, "error": r.get("error")})
    return JSONResponse(status_code=200, content={"ok": True, "out_trade_no": otn})


@app.get("/v1/admin/token/wallet")
async def admin_token_wallet(request: Request, auth_user_id: int, db: Session = Depends(get_db)):
    _require_internal_key(request)
    from token_mvp_service import get_balance_snapshot

    snap = get_balance_snapshot(db, int(auth_user_id))
    u = db.query(AuthUser).filter(AuthUser.id == int(auth_user_id)).first()
    if u:
        snap["user"] = auth_user_public_dict(u)
        snap["frozen"] = is_user_frozen(u)
    else:
        snap["frozen"] = False
    return snap


@app.get("/v1/admin/token/ledger")
async def admin_token_ledger(
    request: Request,
    auth_user_id: int,
    db: Session = Depends(get_db),
    entry_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    """管理端查看用户 BillingLedger（充值/消耗/过期等）。"""
    _require_internal_key(request)
    from token_mvp_service import list_usage

    return list_usage(
        db,
        int(auth_user_id),
        limit=limit,
        offset=offset,
        entry_type=(entry_type or "").strip() or None,
    )


@app.get("/v1/admin/token/orders")
async def admin_token_orders(
    request: Request,
    db: Session = Depends(get_db),
    auth_user_id: int | None = None,
    status: str | None = None,
    channel: str | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
    include_expired: int = 0,
):
    _require_internal_key(request)
    from token_pay_service import admin_list_orders

    return admin_list_orders(
        db,
        auth_user_id=auth_user_id,
        status=status,
        channel=channel,
        q=q,
        limit=limit,
        offset=offset,
        include_expired=bool(include_expired),
    )


@app.get("/v1/admin/token/orders/export.csv")
async def admin_token_orders_export(
    request: Request,
    db: Session = Depends(get_db),
    auth_user_id: int | None = None,
    status: str | None = None,
    channel: str | None = None,
    q: str | None = None,
    limit: int = 2000,
):
    """订单 CSV 导出（内部密钥）。"""
    _require_internal_key(request)
    from fastapi.responses import Response

    from token_pay_service import admin_orders_csv_text

    text = admin_orders_csv_text(
        db,
        auth_user_id=auth_user_id,
        status=status,
        channel=channel,
        q=q,
        limit=limit,
    )
    return Response(
        content=text.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="token_orders.csv"'},
    )


@app.post("/v1/admin/token/topup", response_model=BillingBalanceOut)
async def admin_token_topup(request: Request, body: BillingTopupBody, db: Session = Depends(get_db)):
    """管理端手工充值（同 /v1/billing/topup，路径更明确）。"""
    _require_internal_key(request)
    from token_mvp_service import topup_tokens

    return topup_tokens(
        db,
        auth_user_id=int(body.auth_user_id),
        amount=int(body.amount),
        note=body.note or "admin_topup",
        set_vip=bool(body.set_vip),
        validity_days=body.validity_days,
    )


@app.get("/v1/admin/token/summary")
async def admin_token_summary_api(request: Request, db: Session = Depends(get_db)):
    _require_internal_key(request)
    from token_pay_service import admin_token_summary

    return admin_token_summary(db)


@app.get("/v1/admin/token/routing")
async def admin_token_routing(request: Request):
    """运维只读：上游模式与各档真实 model id（用户端不展示）。"""
    _require_internal_key(request)
    from model_router import _layer_upstream, _upstream_mode, list_models_public

    mode = _upstream_mode()
    layers = {}
    for ly in ("L0", "L1", "L2", "L3", "QI"):
        up = _layer_upstream(ly)
        layers[ly] = {
            "provider": up.get("provider"),
            "model": up.get("model"),
            "key_set": bool(up.get("key")),
        }
    pub = list_models_public(is_vip=True)
    return {
        "ok": True,
        "upstream_mode": mode,
        "layers": layers,
        "public_note": "用户 API/控制台只见 auto/flash/pro/ultra；本接口供管理台。",
        "upstream_public": pub.get("upstream") or {},
    }


@app.get("/v1/admin/token/upstream_probe")
async def admin_token_upstream_probe(request: Request, live: int = 0):
    """
    上游探活（只读）。
    live=0：只报各层 key_set / provider / model（默认，不花钱）。
    live=1：对已配 Key 的 L1（及有 Key 的 L0）发极短请求测通断。
    """
    _require_internal_key(request)
    import time as _time

    from model_router import _call_openai_compatible, _layer_upstream, _upstream_mode

    mode = _upstream_mode()
    out_layers = {}
    for ly in ("L0", "L1", "L2", "L3", "QI"):
        up = _layer_upstream(ly)
        row = {
            "provider": up.get("provider"),
            "model": up.get("model"),
            "key_set": bool(up.get("key")),
            "probe": None,
        }
        if int(live or 0) == 1 and ly in ("L0", "L1") and up.get("key") and up.get("base"):
            t0 = _time.time()
            try:
                _call_openai_compatible(
                    base=str(up["base"]),
                    key=str(up["key"]),
                    model=str(up["model"]),
                    prompt="ping",
                    temperature=0,
                    max_tokens=1,
                    timeout_s=15.0,
                    provider=str(up.get("provider") or ""),
                )
                row["probe"] = {"ok": True, "ms": int((_time.time() - t0) * 1000)}
            except Exception as e:
                row["probe"] = {
                    "ok": False,
                    "ms": int((_time.time() - t0) * 1000),
                    "error": str(e)[:160],
                }
        out_layers[ly] = row
    return {
        "ok": True,
        "upstream_mode": mode,
        "live": bool(int(live or 0) == 1),
        "layers": out_layers,
        "note": "默认 live=0 不花钱；live=1 仅探 L0/L1。OR 挂了请行级切 TOKEN_LLM_UPSTREAM=direct 后重启。",
    }


@app.get("/v1/admin/upstream/health")
async def admin_upstream_health(request: Request):
    """运维只读：上游通道健康快照（窗口失败率 / 连续失败 / 熔断状态）。"""
    _require_internal_key(request)
    from upstream_health import snapshot

    return snapshot()


@app.post("/v1/admin/upstream/health/reset")
async def admin_upstream_health_reset(request: Request):
    """运维：清空上游健康统计与熔断（排查/修复后手动恢复）。"""
    _require_internal_key(request)
    from upstream_health import reset

    reset()
    return {"ok": True, "reset": True}

@app.get("/v1/admin/price/monitor")
async def admin_price_monitor(request: Request):
    """运维只读：价格与供应链监控（售价/成本/毛利三口径 + 供货商比价 + 倒挂检测）。"""
    _require_internal_key(request)
    from price_monitor import snapshot

    return snapshot()


@app.post("/v1/admin/price/refresh")
async def admin_price_refresh(request: Request):
    """运维：实拉 OR/TL/Requesty 价目并返回最新监控快照（12h 缓存，force 强制）。"""
    _require_internal_key(request)
    import asyncio
    from price_monitor import refresh_provider_prices, snapshot

    rep = await asyncio.to_thread(refresh_provider_prices, True)
    snap = snapshot()
    snap["refresh"] = {k: v for k, v in rep.items() if k in ("ok", "cached", "age_s", "providers")}
    return snap


@app.get("/v1/admin/token/system")
async def admin_token_system(request: Request):
    """运维系统开关：可覆盖并立即生效（密钥只读）。"""
    _require_internal_key(request)
    from system_flags import list_system_flags

    return list_system_flags()


@app.put("/v1/admin/token/system")
@app.post("/v1/admin/token/system")
async def admin_token_system_update(request: Request, body: TokenAdminSystemUpdateBody):
    """管理台改开关：写入覆盖文件，立即对前台生效。"""
    _require_internal_key(request)
    from system_flags import update_system_flags

    try:
        return update_system_flags(body.model_dump(exclude_none=True))
    except ValueError as e:
        raise HTTPException(status_code=400, detail="参数无效，请检查后再试。") from e


@app.get("/v1/admin/token/model_warehouse")
async def admin_token_model_warehouse(request: Request):
    """模型仓库：档位映射、层单价、容灾链、套餐毛利粗算、VIP 自选规划。"""
    _require_internal_key(request)
    from model_warehouse import warehouse_snapshot

    return warehouse_snapshot()


@app.post("/v1/admin/token/model_warehouse")
async def admin_token_model_warehouse_update(request: Request, body: TokenAdminWarehouseUpdateBody):
    """保存层模型 / VIP 费率（成本+倍率）/ 层倍率 / VIP 自选开关。"""
    _require_internal_key(request)
    from model_warehouse import update_warehouse

    try:
        return update_warehouse(body.model_dump(exclude_none=True), actor="token-admin")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e) or "参数无效，请检查后再试。")


@app.get("/v1/admin/token/free_shared")
async def admin_token_free_shared(request: Request, db: Session = Depends(get_db)):
    """免费共享通道（余额用尽可走运营池）。"""
    _require_internal_key(request)
    from free_shared import admin_snapshot

    return admin_snapshot(db)


@app.post("/v1/admin/token/free_shared")
async def admin_token_free_shared_update(request: Request, body: TokenAdminFreeSharedUpdateBody):
    _require_internal_key(request)
    from free_shared import update_config

    return update_config(body.model_dump(exclude_none=True))


@app.get("/v1/admin/token/llm_keys")
async def admin_token_llm_keys(request: Request):
    """上游 Key 掩码摘要；可查看 VIP 降级最近事件。"""
    _require_internal_key(request)
    from llm_keys import list_keys_admin

    return list_keys_admin()


@app.post("/v1/admin/token/llm_keys")
async def admin_token_llm_keys_update(request: Request, body: TokenAdminLlmKeysUpdateBody):
    """临时覆盖上游 Key（写入覆盖文件，立即生效）。传空字符串或 clear 可回退 env。"""
    _require_internal_key(request)
    from llm_keys import update_keys_admin

    try:
        return update_keys_admin(body.model_dump(exclude_none=True))
    except ValueError:
        raise HTTPException(status_code=400, detail="密钥无效，请检查后再试。")


@app.get("/v1/admin/token/plans")
async def admin_token_plans(request: Request):
    """运维价表（含 env 覆盖键提示）。"""
    _require_internal_key(request)
    from token_plans import list_admin_plans

    return list_admin_plans()


@app.post("/v1/admin/token/plans")
async def admin_token_plans_update(request: Request):
    """写入价表覆盖（api/data/token_plans_override.json）。"""
    _require_internal_key(request)
    from token_plans import update_admin_plans

    body = await request.json()
    plans = body.get("plans") if isinstance(body, dict) else None
    if not isinstance(plans, list):
        raise HTTPException(status_code=400, detail="参数无效，请检查后再试。")
    return update_admin_plans(plans)


@app.get("/v1/admin/byok/plans")
async def admin_byok_plans(request: Request):
    """BYOK 服务费套餐目录（管理台编辑回显）。"""
    _require_internal_key(request)
    from byok_plans import list_admin_byok_plans

    return list_admin_byok_plans()


@app.post("/v1/admin/byok/plans")
async def admin_byok_plans_update(request: Request):
    """写入 BYOK 套餐覆盖（p/open/api/data/byok_plans_override.json），前台定价页立即生效。"""
    _require_internal_key(request)
    from byok_plans import update_admin_byok_plans

    body = await request.json()
    plans = body.get("plans") if isinstance(body, dict) else None
    if not isinstance(plans, list):
        raise HTTPException(status_code=400, detail="参数无效，请检查后再试。")
    return update_admin_byok_plans(plans)


@app.get("/v1/admin/token/alert_config")
async def admin_alert_config(request: Request):
    "运维预警通道配置（webhook 脱敏返回）。"
    _require_internal_key(request)
    from ops_alert import public_config

    return public_config()


@app.post("/v1/admin/token/alert_config")
async def admin_alert_config_update(request: Request):
    "保存预警通道配置（api/data/ops_alert_config.json）。"
    _require_internal_key(request)
    from ops_alert import save_config

    body = await request.json()
    if not isinstance(body, dict):
        body = {}
    return save_config(body)


@app.post("/v1/admin/token/alerts/reset")
async def admin_alerts_reset(request: Request):
    "清空预警状态（active 标记与最近推送快照）；测试订单未清理则下次巡检可能再次出现。"
    _require_internal_key(request)
    from ops_alert import reset_state

    reset_state()
    return {"ok": True, "reset_at": ""}


@app.post("/v1/admin/token/alerts/run")
async def admin_alerts_run(request: Request, db: Session = Depends(get_db)):
    "立即巡检一次并推送（管理台「立即巡检并推送」）。"
    _require_internal_key(request)
    from ops_alert import run_check

    return run_check(db, push=True)


@app.get("/v1/admin/token/alerts/live")
async def admin_alerts_live(request: Request, db: Session = Depends(get_db)):
    "实时聚合预警（不推送、不改状态）：预警中心「当前告警」实时展示用。"
    _require_internal_key(request)
    from ops_alert import collect_alerts

    return collect_alerts(db)


@app.get("/v1/admin/token/alerts/latest")
async def admin_alerts_latest(request: Request):
    "只读：最近一次巡检 + 最近一次推送快照（供副脑04 轮询飞书私信去重）。"
    _require_internal_key(request)
    from ops_alert import latest_alert

    return latest_alert()


@app.post("/v1/admin/byok/renewal-remind")
async def admin_byok_renewal_remind(request: Request, db: Session = Depends(get_db)):
    """BYOK Pro 续费提醒：默认 dry-run；body {\"apply\": true} 才发信。"""
    _require_internal_key(request)
    apply = False
    lang = "en"
    try:
        body = await request.json()
        if isinstance(body, dict):
            v = body.get("apply", False)
            if isinstance(v, bool):
                apply = v
            else:
                apply = str(v).strip().lower() in ("1", "true", "yes")
            lang = str(body.get("lang") or "en").strip().lower() or "en"
    except Exception:
        apply = False
    from byok_renewal import run_renewal_reminders

    return run_renewal_reminders(db=db, apply=apply, lang=lang)




@app.post("/v1/admin/token/orders/query_fulfill")
async def admin_token_orders_query_fulfill(
    request: Request, body: TokenQueryFulfillBody, db: Session = Depends(get_db)
):
    """管理端对 pending 单主动查通道并履约（不代替用户登录）。"""
    _require_internal_key(request)
    from token_pay_service import admin_query_fulfill_order

    return await admin_query_fulfill_order(db, out_trade_no=body.out_trade_no)


# BYOK 智能网关（2026-08-18）：用户自有 key 管理 / 用量统计 / 状态
# 鉴权复用 get_current_user（JWT 或 sk-），须挂在静态站点 mount 之前
from byok_routes import router as byok_router

app.include_router(
    byok_router,
    prefix="/v1",
    dependencies=[Depends(get_current_user)],
)


# 静态官网（与 API 同端口 8000）；须挂在所有 API 路由之后
_WEB_ROOT = Path(__file__).resolve().parent.parent / "web"
if _WEB_ROOT.is_dir():
    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon_ico():
        # 浏览器默认要 .ico；站点用 SVG，避免无害 404
        from fastapi.responses import FileResponse

        svg = _WEB_ROOT / "favicon.svg"
        if svg.is_file():
            return FileResponse(svg, media_type="image/svg+xml")
        from fastapi import HTTPException

        raise HTTPException(status_code=404)

    @app.api_route("/r/{code}", methods=["GET", "HEAD"], include_in_schema=False)
    async def invite_short_link(code: str):
        """邀请短链：/r/{CODE} → 注册页并带上 invite（便于分享复制）。"""
        import re

        from fastapi.responses import RedirectResponse

        raw = (code or "").strip().upper()
        safe = re.sub(r"[^A-Z0-9]", "", raw)[:32]
        if len(safe) < 4:
            return RedirectResponse(url="/register.html", status_code=302)
        return RedirectResponse(
            url=f"/register.html?invite={safe}",
            status_code=302,
        )

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
        reload=False,
        # 使用应用自身 logging 配置（basicConfig），保留 __main__ 请求/审计日志输出。
        log_config=None
    )
