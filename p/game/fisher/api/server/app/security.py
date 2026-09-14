"""安全模块：域名校验、速率限制、防爬虫"""

from __future__ import annotations

import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

# ── 允许的域名（空=不校验，设值后仅允许来自这些域名的请求） ──
ALLOWED_ORIGINS: set[str] = set(
    filter(None, [
        "localhost",
        "127.0.0.1",
        # 生产上线时添加正式域名:
        # "your-domain.com",
        # "www.your-domain.com",
    ])
)

# ── 速率限制配置 ──
RATE_LIMIT_WINDOW_S = 60  # 窗口 60秒
RATE_LIMIT_MAX_REQUESTS = 120  # 每窗口最多120次（2次/秒）
RATE_LIMIT_GAME_MAX = 30  # 游戏操作每窗口最多30次

# 游戏类路径（钓鱼/卖鱼/升级等操作）
_GAME_PATHS = {"/v1/game/", "/v1/market/", "/v1/fishery/"}

_ratelimit_store: dict[str, tuple[int, int, int]] = {}  # key -> (count, window_start, last_request)


class SecurityMiddleware(BaseHTTPMiddleware):
    """域名校验 + 速率限制 + 防爬虫"""

    async def dispatch(self, request: Request, call_next):
        # 跳过健康检查
        if request.url.path in ("/health", "/", "/docs", "/openapi.json", "/redoc"):
            return await call_next(request)

        # 1) Origin / Referer 校验（生产环境启用）
        if ALLOWED_ORIGINS:
            origin = request.headers.get("origin") or request.headers.get("referer") or ""
            if origin:
                from urllib.parse import urlparse
                try:
                    hostname = urlparse(origin).hostname or ""
                except Exception:
                    hostname = ""
                if hostname and not any(d in hostname for d in ALLOWED_ORIGINS):
                    return JSONResponse(
                        status_code=403,
                        content={"detail": "Access denied: origin not allowed"},
                    )

        # 2) 速率限制
        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path
        key = f"{client_ip}:{path}"

        now = time.time()
        entry = _ratelimit_store.get(key)
        if entry:
            count, window_start, last_req = entry
            if now - window_start > RATE_LIMIT_WINDOW_S:
                count = 0
                window_start = now
        else:
            count = 0
            window_start = now

        is_game = any(path.startswith(p) for p in _GAME_PATHS)
        limit = RATE_LIMIT_GAME_MAX if is_game else RATE_LIMIT_MAX_REQUESTS

        if count >= limit:
            retry_after = int(RATE_LIMIT_WINDOW_S - (now - window_start))
            return JSONResponse(
                status_code=429,
                content={"detail": "请求过多，请稍后再试", "retry_after_s": max(0, retry_after)},
                headers={"Retry-After": str(max(0, retry_after))},
            )

        _ratelimit_store[key] = (count + 1, window_start, now)

        # 3) 定期清理过期记录
        if int(now) % 60 == 0:
            expired = [k for k, v in _ratelimit_store.items() if now - v[1] > RATE_LIMIT_WINDOW_S * 2]
            for k in expired:
                _ratelimit_store.pop(k, None)

        return await call_next(request)


# ── 服务端状态校验（防客户端篡改） ──
def verify_player_state(player_coins: int, player_score: int, player_rod: int) -> bool:
    """服务端校验玩家状态合法性"""
    if player_coins < 0 or player_score < 0:
        return False
    if player_rod < 0 or player_rod > 15:
        return False
    return True
