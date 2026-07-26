"""
安全加固工具：密钥哈希、进程内限流、溯源字段。

说明：无法从数学上阻止别人「抄代码」；能做的是：
- 密钥不以明文落库
- 无 Key / 伪造身份难调用
- 滥用可限流、可追溯
- 生产关闭调试入口
"""
from __future__ import annotations

import hashlib
import hmac
import time
from collections import defaultdict, deque
from threading import Lock
from typing import Deque, Optional

from config import settings

_HASH_PREFIX = "sha256:"
_lock = Lock()
_buckets: dict[str, Deque[float]] = defaultdict(deque)


def is_prod() -> bool:
    return str(settings.app_env or "").strip().lower() in ("prod", "production")


def hash_api_key(raw: str) -> str:
    """HMAC-SHA256(SECRET_KEY, raw)；库内只存此值。"""
    pepper = (settings.secret_key or "ai24x").encode("utf-8")
    digest = hmac.new(pepper, (raw or "").encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{_HASH_PREFIX}{digest}"


def is_hashed_api_key(stored: str) -> bool:
    return str(stored or "").startswith(_HASH_PREFIX)


def api_key_matches(raw: str, stored: str) -> bool:
    s = str(stored or "")
    if is_hashed_api_key(s):
        return hmac.compare_digest(hash_api_key(raw), s)
    # 遗留明文：常量时间尽量比较
    return hmac.compare_digest(str(raw or ""), s)


def check_sliding_rate(key: str, *, limit: int, window_s: float = 60.0) -> tuple[bool, int]:
    """
    进程内滑动窗口。返回 (允许?, 窗口内已用次数)。
    多 worker 不共享；生产建议前置 Nginx/Redis。
    """
    if limit <= 0:
        return True, 0
    now = time.time()
    with _lock:
        q = _buckets[key]
        while q and now - q[0] > window_s:
            q.popleft()
        if len(q) >= limit:
            return False, len(q)
        q.append(now)
        return True, len(q)


def client_ip(request) -> str:
    try:
        xff = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
        if xff:
            return xff[:64]
        if request.client and request.client.host:
            return str(request.client.host)[:64]
    except Exception:
        pass
    return "unknown"


def attribution_block(*, request_id: str, auth_user_id: Optional[int] = None) -> dict:
    """响应内嵌溯源（防洗白转卖时便于追责；不能替代法务）。"""
    uid = f"u{auth_user_id}" if auth_user_id is not None else "anon"
    trace = hashlib.sha256(f"{request_id}:{uid}:{settings.secret_key[:8]}".encode()).hexdigest()[:16]
    return {
        "platform": "AI24X",
        "notice": "© AI24X — 接口输出仅授权给持钥调用方使用，禁止未授权转售、镜像或批量爬取。",
        "trace": trace,
        "request_id": request_id,
    }


def security_headers() -> dict[str, str]:
    return {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
        "X-AI24X-Platform": "AI24X-Token-Gateway",
        "Cache-Control": "no-store",
    }
