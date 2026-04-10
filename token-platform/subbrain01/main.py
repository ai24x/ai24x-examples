from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
import logging
import time

from database import get_db, init_db
from schemas import ChatRequest, ChatResponse, ErrorResponse
from services import AuthService, UserService, ChatService
from config import settings

# 配置日志
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title="AI24X 副脑01 API",
    description="AI24X副脑01·首席开发官 - 专注于编程相关任务的API服务",
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
        "service": "AI24X Subbrain01 API",
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


# 全局异常处理
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=exc.detail,
            code=exc.status_code,
            request_id=request.headers.get("X-Request-ID")
        ).dict()
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="服务器内部错误",
            code="INTERNAL_SERVER_ERROR",
            request_id=request.headers.get("X-Request-ID")
        ).dict()
    )


# 应用启动事件
@app.on_event("startup")
async def startup_event():
    """应用启动时初始化数据库"""
    logger.info("Starting AI24X Subbrain01 API...")
    try:
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {str(e)}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时清理资源"""
    logger.info("Shutting down AI24X Subbrain01 API...")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        workers=settings.api_workers,
        reload=True  # 开发模式
    )