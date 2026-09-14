"""
用户侧 AI 即时答疑（平台成本，不扣用户余额）。
用 L1 flash 路由；失败则返回 FAQ 兜底文案。
"""
from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are AI24X Help, the support assistant for the AI24X API platform. "
    "Help developers with: API keys, tiers (auto/flash/pro/ultra/shared), "
    "VIP named China models (Kimi/MiMo/MiniMax/GLM/DeepSeek/Qwen), "
    "PayPal/WeChat top-up, 401/402/429 errors, OpenClaw and integrations. "
    "Be concise. Do not invent refunds or change account balances. "
    "Do not expose upstream vendor ops jargon (SMTP, env vars, internal hostnames). "
    "If unsure, tell the user to open a billing ticket from Help/Console. "
    "Answer in the user's language."
)

_FAQ_FALLBACK_EN = (
    "I couldn't reach the live assistant just now. Quick tips:\n"
    "- Use model tiers: flash / pro / ultra / auto (or shared when out of credits).\n"
    "- 401: check X-API-Key.\n"
    "- 402: top up in Console (PayPal USD) or continue with shared if enabled.\n"
    "- VIP named models need an active VIP plan.\n"
    "See /help.html and /docs.html for more."
)

_FAQ_FALLBACK_ZH = (
    "助手暂时繁忙。快速提示：\n"
    "- 档位：flash / pro / ultra / auto（余额不足可用 shared）。\n"
    "- 401：检查 API Key。\n"
    "- 402：控制台充值，或继续免费共享（若已开放）。\n"
    "- 点名中国模需有效会员。\n"
    "更多见帮助中心与使用说明。"
)

# 简易内存日帽：auth_user_id -> (day, count)
_daily: dict[int, tuple[str, int]] = {}
_DAILY_CAP = 40


def _day() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


def _under_cap(auth_user_id: int) -> bool:
    d = _day()
    prev = _daily.get(int(auth_user_id))
    if not prev or prev[0] != d:
        _daily[int(auth_user_id)] = (d, 0)
        return True
    return prev[1] < _DAILY_CAP


def _bump(auth_user_id: int) -> None:
    d = _day()
    prev = _daily.get(int(auth_user_id))
    if not prev or prev[0] != d:
        _daily[int(auth_user_id)] = (d, 1)
    else:
        _daily[int(auth_user_id)] = (d, prev[1] + 1)


def ask_support(*, auth_user_id: int, question: str, lang_hint: str = "en") -> dict[str, Any]:
    q = (question or "").strip()
    if len(q) < 2:
        return {"ok": False, "message": "Please enter a question." if lang_hint != "zh" else "请输入问题。"}
    if len(q) > 2000:
        q = q[:2000]
    if not _under_cap(int(auth_user_id)):
        return {
            "ok": False,
            "message": "Daily help limit reached. See Help center or try tomorrow."
            if lang_hint != "zh"
            else "今日帮助次数已用完，请查阅帮助中心或明日再试。",
        }

    from model_router import run_routed_chat

    prompt = f"[AI24X Help]\nUser question:\n{q}"
    # 注入系统身份：经 flash 路径；system 由 model_router 默认 AI24X 提示，另加 help 前缀
    routed = run_routed_chat(
        prompt=_SYSTEM + "\n\n" + prompt,
        requested_model="flash",
        is_vip=True,  # 帮助通道走 VIP 链更稳；不计用户费
        temperature=0.3,
        max_tokens=600,
    )
    _bump(int(auth_user_id))
    if routed.ok and (routed.text or "").strip():
        return {
            "ok": True,
            "answer": routed.text.strip(),
            "model": "help",
            "remaining_today": max(0, _DAILY_CAP - _daily[int(auth_user_id)][1]),
        }
    fb = _FAQ_FALLBACK_ZH if lang_hint == "zh" else _FAQ_FALLBACK_EN
    return {
        "ok": True,
        "answer": fb,
        "model": "faq_fallback",
        "remaining_today": max(0, _DAILY_CAP - _daily.get(int(auth_user_id), (_day(), 0))[1]),
    }
