"""
106 短信网关（utf8 提交）。与 api/services.py 并存，避免 services 包名冲突。
"""

from __future__ import annotations

import logging
import secrets
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

STATUS_MESSAGES: dict[str, str] = {
    "100": "发送成功",
    "101": "验证失败",
    "102": "手机号码格式不正确",
    "103": "会员级别不够",
    "104": "内容未审核",
    "105": "内容过多",
    "106": "账户余额不足",
    "107": "IP 受限",
    "108": "手机号码发送太频繁",
    "109": "帐号被锁定",
    "110": "发送通道不正确",
    "111": "当前时间段禁止短信发送",
    "112": "账号未认证",
    "120": "系统升级",
}


def normalize_mobile(mobile: str) -> str:
    s = "".join(c for c in (mobile or "").strip() if c.isdigit() or c == "+")
    if s.startswith("+86"):
        s = s[3:]
    if s.startswith("86") and len(s) == 13:
        s = s[2:]
    return s


def generate_numeric_code(digits: int = 6) -> str:
    if digits < 4 or digits > 8:
        digits = 6
    upper = 10**digits
    lower = 10 ** (digits - 1)
    n = secrets.randbelow(upper - lower) + lower
    return str(n)


async def send_sms_106(
    *,
    endpoint: str,
    account: str,
    password: str,
    mobile: str,
    content: str,
    sign_name: str | None = None,
    timeout_s: float = 15.0,
) -> tuple[bool, str, str]:
    """
    106 utf8 网关：与浏览器/厂商 GET 示例一致（account、password、mobile、content 走 query）。
    示例（返回体为纯文本状态码，如 100）：
    http://sms.106jiekou.com/utf8/sms.aspx?account=...&password=...&mobile=...&content=...
    """
    url = (endpoint or "").strip()
    params: dict[str, Any] = {
        "account": account,
        "password": password,
        "mobile": mobile,
        "content": content,
    }
    if sign_name:
        params["signName"] = sign_name

    async with httpx.AsyncClient(timeout=timeout_s) as client:
        r = await client.get(url, params=params)
        raw = (r.text or "").strip()

    ok = raw == "100"
    msg = STATUS_MESSAGES.get(raw, f"未知状态码: {raw}")
    if not ok:
        logger.warning("106 sms send failed mobile=%s raw=%s", mobile[:3] + "****", raw)
    return ok, raw, msg


_last_sent_at: dict[str, float] = {}


def check_send_cooldown(mobile: str, cooldown_s: float) -> tuple[bool, float | None]:
    now = time.time()
    key = normalize_mobile(mobile)
    last = _last_sent_at.get(key)
    if last is None:
        return True, None
    elapsed = now - last
    if elapsed >= cooldown_s:
        return True, None
    return False, max(0.0, cooldown_s - elapsed)


def mark_sent(mobile: str) -> None:
    _last_sent_at[normalize_mobile(mobile)] = time.time()
