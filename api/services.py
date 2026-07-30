import uuid
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from models import User, ChatRequest, UserType
from schemas import ChatRequest as ChatRequestSchema, ChatResponse
from config import settings
from security_util import attribution_block


class UserService:
    @staticmethod
    def get_user_by_id(db: Session, user_id: str) -> Optional[User]:
        return db.query(User).filter(User.user_id == user_id).first()
    
    @staticmethod
    def get_user_by_api_key(db: Session, api_key: str) -> Optional[User]:
        return db.query(User).filter(User.api_key == api_key).first()
    
    @staticmethod
    def create_user(db: Session, user_id: str, user_type: UserType = UserType.FREE) -> User:
        user = User(
            user_id=user_id,
            user_type=user_type,
            api_key=f"sk_{uuid.uuid4().hex[:32]}",
            daily_request_limit=100 if user_type == UserType.FREE else 1000,
            monthly_request_limit=3000 if user_type == UserType.FREE else 30000
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    
    @staticmethod
    def check_rate_limit(db: Session, user: User) -> tuple[bool, Optional[str]]:
        """检查用户是否超出速率限制"""
        now = datetime.utcnow()
        
        # 检查每日限制
        if user.current_daily_requests >= user.daily_request_limit:
            # 检查是否是新的一天
            if user.updated_at and (now - user.updated_at.replace(tzinfo=None)).days >= 1:
                user.current_daily_requests = 0
                db.commit()
            else:
                return False, "超出每日请求限制"
        
        # 检查每月限制
        if user.current_monthly_requests >= user.monthly_request_limit:
            # 检查是否是新的一月
            if user.updated_at and (now - user.updated_at.replace(tzinfo=None)).days >= 30:
                user.current_monthly_requests = 0
                db.commit()
            else:
                return False, "超出每月请求限制"
        
        return True, None
    
    @staticmethod
    def increment_request_count(db: Session, user: User):
        """增加用户请求计数"""
        user.current_daily_requests += 1
        user.current_monthly_requests += 1
        user.updated_at = datetime.utcnow()
        db.commit()


class ChatService:
    @staticmethod
    def process_chat_request(
        db: Session,
        user: User,
        request: ChatRequestSchema,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        auth_user_id: Optional[int] = None,
        region_hint: Optional[str] = None,
    ) -> ChatResponse:
        """处理聊天请求；若提供 auth_user_id 则走 Token 钱包扣减。"""
        request_id = f"req_{uuid.uuid4().hex[:16]}"
        start_time = time.time()

        # Token 钱包预检（MVP：至少要有余额）
        if auth_user_id is not None:
            from token_mvp_service import assert_can_spend

            assert_can_spend(db, int(auth_user_id), need_tokens=1)

        # 创建请求记录
        chat_request = ChatRequest(
            request_id=request_id,
            user_id=user.user_id,
            user_type=user.user_type,
            prompt=request.prompt,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            ip_address=ip_address,
            user_agent=user_agent,
            status="processing",
        )
        db.add(chat_request)
        db.commit()

        try:
            from token_mvp_service import get_balance_snapshot
            from model_router import run_routed_chat

            is_vip = False
            if auth_user_id is not None:
                snap0 = get_balance_snapshot(db, int(auth_user_id))
                is_vip = bool(snap0.get("is_vip_active"))

            routed = run_routed_chat(
                prompt=request.prompt,
                requested_model=request.model,
                is_vip=is_vip,
                temperature=float(request.temperature or 0.7),
                max_tokens=int(request.max_tokens or 1000),
                region_hint=region_hint,
            )
            if not routed.ok:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="模型服务暂时繁忙，请稍后再试。",
                )

            response_text = routed.text
            used_model = routed.model
            from model_router import public_tier_name

            public_model = public_tier_name(
                request.model, layer=routed.layer or "", upstream_model=used_model or ""
            )
            # 全上游失败落 stub：不计费（总纲 v3.3）；纯联调 stub（未配 Key）仍计最小 token 便于测钱包
            billable = not (
                routed.provider == "stub"
                and (routed.error or "") == "all_live_failed_used_stub"
            )
            token_count = max(1, int(routed.token_count)) if billable else 0

            processing_time = time.time() - start_time

            # 更新请求记录（库内仍记上游型号便于运维）
            chat_request.response = response_text
            chat_request.model = used_model
            chat_request.response_time = datetime.utcnow()
            chat_request.processing_duration = processing_time
            chat_request.status = "completed"
            chat_request.is_success = True
            chat_request.token_count = int(token_count)
            chat_request.cost = token_count * (0.000002 if user.user_type == UserType.FREE else 0.000001)
            db.commit()

            # 增加用户请求计数
            UserService.increment_request_count(db, user)

            remaining_quota = user.daily_request_limit - user.current_daily_requests
            if auth_user_id is not None:
                from token_mvp_service import consume_tokens, get_balance_snapshot

                if billable and token_count > 0:
                    consume_tokens(
                        db,
                        auth_user_id=int(auth_user_id),
                        tokens=int(token_count),
                        model=public_model,
                        request_id=request_id,
                    )
                snap = get_balance_snapshot(db, int(auth_user_id))
                remaining_quota = int(snap.get("balance_tokens") or 0)

            return ChatResponse(
                request_id=request_id,
                response=response_text,
                model=public_model,
                token_count=int(token_count),
                processing_time=processing_time,
                user_type=user.user_type,
                remaining_quota=remaining_quota,
                created_at=datetime.utcnow(),
                layer=None,
                provider="ai24x",
                route_attempts=None,
                attribution=attribution_block(
                    request_id=request_id, auth_user_id=auth_user_id
                ),
            )

        except Exception as e:
            # 记录错误
            chat_request.error_message = str(e)
            chat_request.status = "failed"
            chat_request.response_time = datetime.utcnow()
            chat_request.processing_duration = time.time() - start_time
            db.commit()
            raise
    
    @staticmethod
    def _generate_response(prompt: str) -> str:
        """生成回复（模拟AI响应）"""
        # 实际项目中这里会调用真实的AI API
        # 这里返回一个模拟回复
        responses = {
            "你好": "你好！我是AI24X副脑01，很高兴为您服务。",
            "python": "Python是一种高级编程语言，以其简洁易读的语法而闻名。它广泛应用于Web开发、数据分析、人工智能等领域。",
            "fastapi": "FastAPI是一个现代、快速（高性能）的Web框架，用于构建API。它基于Python 3.6+，使用类型提示，并自动生成API文档。",
            "postgresql": "PostgreSQL是一个强大的开源关系型数据库系统，以其可靠性、功能丰富性和性能而闻名。"
        }
        
        prompt_lower = prompt.lower()
        for key, response in responses.items():
            if key in prompt_lower:
                return response
        
        # 默认回复
        return f"我已经收到您的请求：'{prompt[:50]}...'。作为AI24X副脑01，我专注于编程相关任务，包括代码编写、功能实现、接口逻辑、数据库设计等。请告诉我具体的开发需求。"


class AuthService:
    @staticmethod
    def authenticate_user(db: Session, api_key: Optional[str] = None, user_id: Optional[str] = None) -> Optional[User]:
        """用户认证"""
        if api_key:
            user = UserService.get_user_by_api_key(db, api_key)
        elif user_id:
            user = UserService.get_user_by_id(db, user_id)
        else:
            return None
        
        if user and user.is_active:
            return user
        return None
    
    @staticmethod
    def determine_user_type(api_key: Optional[str] = None) -> UserType:
        """确定用户类型（免费/VIP）"""
        # 实际项目中这里会有更复杂的逻辑
        # 例如：检查API key前缀、查询数据库等
        if api_key and api_key.startswith("sk_vip_"):
            return UserType.VIP
        return UserType.FREE