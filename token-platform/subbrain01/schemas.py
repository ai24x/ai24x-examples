from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
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