"""内容安全过滤 + 输入消毒 + 合规审计"""

from __future__ import annotations

import re
import time

# ── 敏感词库（基础版，上线前需扩充） ──
BLOCKED_WORDS = {
    "赌博", "彩票", "赌场", "现金", "提现", "充值", "返利",
    "政治", "敏感", "违法", "毒品", "色情", "裸聊", "诈骗",
    "传销", "洗钱", "套现", "代充", "外挂", "作弊",
    "vpn", "翻墙", "fq",
}

BLOCKED_PATTERNS = [
    re.compile(r"1[3-9]\d{9}"),           # 手机号
    re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+"),  # 邮箱
    re.compile(r"(http|https)://"),         # 外链
    re.compile(r"[QqQ]{1,2}[：:]*\s*\d{5,}"),  # QQ号
    re.compile(r"wxid|weixin.{0,5}[：:]\s*[a-zA-Z]"),  # 微信号
]


def check_content(text: str, context: str = "user_input") -> tuple[bool, str]:
    """检测内容是否合规。
    
    Returns:
        (is_safe, reason)
    """
    if not text or not text.strip():
        return True, ""

    s = text.strip().lower()

    # 1. 敏感词检测
    for word in BLOCKED_WORDS:
        if word in s:
            return False, f"blocked_word:{word}"

    # 2. 模式检测（联系方式/外链）
    for pattern in BLOCKED_PATTERNS:
        if pattern.search(s):
            return False, "contact_info_blocked"

    # 3. 长度限制
    if len(text) > 2048:
        return False, "content_too_long"

    return True, ""


def sanitize_input(text: str, max_len: int = 512) -> str:
    """消毒用户输入"""
    if not text:
        return ""
    s = text.strip()[:max_len]
    # 移除控制字符
    s = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", s)
    return s


def audit_log(player_id: int | None, action: str, detail: str = "", ip: str = ""):
    """审计日志（写入 PostgreSQL）"""
    # 使用 Python logging 输出到文件，不会阻塞请求
    import logging
    logger = logging.getLogger("fisher_audit")
    ts = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())
    logger.info(f"[{ts}] player={player_id} action={action} detail={detail[:256]} ip={ip}")
