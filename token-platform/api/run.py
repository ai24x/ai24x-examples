#!/usr/bin/env python3
"""
AI24X 副脑01 API 启动脚本
"""

import uvicorn
from config import settings

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,  # 开发模式启用热重载
        log_level=settings.log_level.lower()
    )