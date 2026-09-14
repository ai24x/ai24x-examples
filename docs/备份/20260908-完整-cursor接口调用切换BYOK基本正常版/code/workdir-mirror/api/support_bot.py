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
    "The platform also runs AI24X Markets (markets.ai24x.com): US/A-share/HK "
    "charts with technical indicators and AI briefs; Pro subscription "
    "$9.9/week, $24.9/month or $199/year, bought in the user center "
    "console → Plans with WeChat/Alipay/PayPal, plus Google/Apple sign-in. "
    "If a user asks about a specific stock or indicator, point them to the "
    "Markets app (chart & AI brief) instead of refusing. "
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

# 常见问题关键词先行命中：命中即秒回，不调模型（覆盖绝大多数咨询）
_FAQ_RULES: list[dict[str, Any]] = [
    {
        "name": "markets",
        "keys": ["markets", "行情", "美股", "行情官", "pro 订阅", "pro subscription", "周卡", "月卡", "年卡", "升级 pro", "upgrade to pro"],
        "en": (
            "AI24X Markets Pro (US stocks, ETFs & indices with AI briefs):\n"
            "- $9.9/week · $24.9/month · $199/year\n"
            "- Open your user center → Plans → pick \"AI24X Markets Pro\" → choose WeChat / Alipay / PayPal.\n"
            "Free plan: 10 AI briefs/day and a 10-symbol watchlist; Pro unlocks unlimited briefs and 50 symbols.\n"
            "If not signed in yet, use the Sign up / Google button first."
        ),
        "zh": (
            "AI24X Markets Pro（美股/ETF/指数行情 + AI 点评）：\n"
            "- $9.9/周 · $24.9/月 · $199/年\n"
            "- 打开用户中心 → 套餐 → 选「AI24X Markets Pro」→ 微信 / 支付宝 / PayPal 任选支付，开通立即生效。\n"
            "免费版每天 10 次 AI 点评、自选 10 只；Pro 不限次、自选 50 只。\n"
            "还没注册的话，先点右上角注册或 Google 登录即可。"
        ),
    },
    {
        "name": "topup",
        "keys": ["top up", "topup", "充值", "余额", "balance", "wechat", "微信", "alipay", "支付宝", "paypal", "付款", "支付", "recharge"],
        "en": (
            "Top-up & plans live in your user center: console → Plans.\n"
            "- Token API packs (for developers): Starter / Builder / VIP passes — WeChat, Alipay, PayPal.\n"
            "- AI24X Markets Pro: $9.9/w · $24.9/m · $199/y — WeChat, Alipay, PayPal.\n"
            "Payment activates instantly. Check \"My orders\" for pending confirmations."
        ),
        "zh": (
            "充值和套餐都在用户中心统一购买：控制台 → 套餐。\n"
            "- 托管额度包：入门包 / 常用包 / VIP 资格包等 — 微信、支付宝、PayPal 均可。\n"
            "- AI24X Markets Pro：$9.9/周 · $24.9/月 · $199/年 — 微信、支付宝、PayPal 均可。\n"
            "支付成功立即到账；「我的订单」可查看待确认订单。"
        ),
    },
    {
        "name": "http401",
        "keys": ["401", "invalid api key", "api key 无效", "密钥无效"],
        "en": "401 means the API key is missing or invalid. Create a key in Console → API Keys and send it as the X-API-Key header (or Authorization: Bearer <key>).",
        "zh": "401 表示 API Key 缺失或无效：到控制台「API 密钥」创建/复制完整 Key，请求头用 X-API-Key（或 Authorization: Bearer <key>）携带。",
    },
    {
        "name": "http402",
        "keys": ["402", "insufficient balance", "余额不足", "余额不够"],
        "en": "402 means insufficient balance. Top up in Console → Plans (WeChat / Alipay / PayPal), or use the free shared tier when available.",
        "zh": "402 表示余额不足：到用户中心「套餐」充值（微信/支付宝/PayPal），或余额不足时用免费共享通道（若已开放）。",
    },
    {
        "name": "http429",
        "keys": ["429", "rate limit", "限流", "频率限制"],
        "en": "429 means rate limiting. Add backoff / slow down requests, or raise your tier for higher limits.",
        "zh": "429 表示触发限流：请降低请求频率并做退避重试；需要更高限额可升级档位。",
    },
    {
        "name": "vip",
        "keys": ["vip", "点名", "named model", "kimi", "glm", "qwen", "deepseek", "资格包", "会员"],
        "en": "VIP named China models (Kimi / GLM / Qwen / DeepSeek etc.) need an active VIP pass + credits. See Console → Plans → VIP pass, or the Models page.",
        "zh": "点名中国名模（Kimi / GLM / Qwen / DeepSeek 等）需要有效的 VIP 资格包 + 额度：到用户中心「套餐」选 VIP 资格包，或查看 Models 名模清单页。",
    },
    {
        "name": "tiers",
        "keys": ["flash", "pro tier", "ultra", "auto", "shared", "档位", "模型档位", "model tier", "tier"],
        "en": "Tiers: auto = automatic choice; flash = daily workhorse; pro = higher quality; ultra = flagship; shared = free daily pool. All use the same API endpoint — just change the model field.",
        "zh": "档位：auto 自动选档；flash 日常主力；pro 更高品质；ultra 旗舰；shared 免费日额度。统一接口，改 model 字段即可。",
    },
    {
        "name": "google",
        "keys": ["google", "谷歌", "oauth", "账号登录", "sign in with"],
        "en": "Google sign-in is available on the login and register pages (desktop & mobile). Pick your Google account, come back, and you are signed in — then open Console → Plans to subscribe.",
        "zh": "谷歌登录在登录页和注册页都有（电脑/手机通用）：选 Google 账号授权后自动登录，然后到用户中心「套餐」开通订阅即可。",
    },
    {
        "name": "invite",
        "keys": ["invite", "邀请", "返利", "referral", "奖励", "reward"],
        "en": "Referral: both sides get 5000 tokens at signup; you earn L1 10% / L2 2% back after their top-ups. See Console → Overview → Invite & earn.",
        "zh": "邀请奖励：对方注册后双方各得 5000 Token；对方充值后你拿 L1 10% / L2 2% 返利。见用户中心概览「邀请有奖」。",
    },
    {
        "name": "ticket",
        "keys": ["人工", "ticket", "工单", "human", "客服", "support"],
        "en": "For a human agent: open this panel → \"Transfer to human\" → submit a ticket. Weekdays reply within 24h. For urgent billing issues, include the order number.",
        "zh": "需要人工：点本面板「转人工」提交工单，工作日 24 小时内回复；涉及账单请附订单号。",
    },
]


def faq_answer_for(question: str, lang_hint: str = "en") -> str | None:
    q = (question or "").strip().lower()
    if not q:
        return None
    for rule in _FAQ_RULES:
        if any(k in q for k in rule["keys"]):
            return rule["zh"] if lang_hint == "zh" else rule["en"]
    return None


def faq_timeout_answer(lang_hint: str = "en") -> dict[str, Any]:
    """模型超时兜底：秒回 FAQ（不抛 500，不干等）。"""
    fb = _FAQ_FALLBACK_ZH if lang_hint == "zh" else _FAQ_FALLBACK_EN
    return {
        "ok": True,
        "answer": fb,
        "model": "faq_timeout",
        "remaining_today": max(0, _DAILY_CAP - _daily.get(0, (_day(), 0))[1]),
    }

# 简易内存日帽：登录用户 auth_user_id -> (day, count)；游客 client_ip -> (day, count)
_daily: dict[int, tuple[str, int]] = {}
_guest_daily: dict[str, tuple[str, int]] = {}
_DAILY_CAP = 40
_GUEST_DAILY_CAP = 8

# 游客不可答账户私有信息（防探测 / 省模型成本）
_ACCOUNT_KEYS = (
    "我的余额",
    "my balance",
    "我的订单",
    "my order",
    "我的账户",
    "my account",
    "我付了",
    "i paid",
    "没到账",
    "not credited",
    "refund",
    "退款",
    "发票",
    "invoice",
    "order #",
    "订单号",
    "out_trade",
    "api key 泄漏",
    "key leak",
    "泄漏的 key",
)


def _day() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


def _norm_ip(client_ip: str) -> str:
    ip = (client_ip or "").strip()[:64]
    return ip or "unknown"


def _needs_account_context(question: str) -> bool:
    low = (question or "").strip().lower()
    if not low:
        return False
    return any(k in low for k in _ACCOUNT_KEYS)


def _guest_sign_in_hint(lang_hint: str) -> str:
    if lang_hint == "zh":
        return (
            "这类问题需要登录后才能查看你的账户数据。\n"
            "请先登录用户中心，再打开右下角协助；或到「套餐 → 我的订单」核对。\n"
            "涉及账单可登录后点「转人工」提交工单。"
        )
    return (
        "Sign in to view account-specific details (balance, orders, refunds).\n"
        "Open Console → Plans or My orders after login, or use Human support for billing."
    )


def _under_cap(auth_user_id: int) -> bool:
    d = _day()
    prev = _daily.get(int(auth_user_id))
    if not prev or prev[0] != d:
        _daily[int(auth_user_id)] = (d, 0)
        return True
    return prev[1] < _DAILY_CAP


def _guest_under_cap(client_ip: str) -> bool:
    d = _day()
    key = _norm_ip(client_ip)
    prev = _guest_daily.get(key)
    if not prev or prev[0] != d:
        _guest_daily[key] = (d, 0)
        return True
    return prev[1] < _GUEST_DAILY_CAP


def _remaining_user(auth_user_id: int) -> int:
    d = _day()
    prev = _daily.get(int(auth_user_id))
    if not prev or prev[0] != d:
        return _DAILY_CAP
    return max(0, _DAILY_CAP - prev[1])


def _remaining_guest(client_ip: str) -> int:
    d = _day()
    key = _norm_ip(client_ip)
    prev = _guest_daily.get(key)
    if not prev or prev[0] != d:
        return _GUEST_DAILY_CAP
    return max(0, _GUEST_DAILY_CAP - prev[1])


def _bump(auth_user_id: int) -> None:
    d = _day()
    prev = _daily.get(int(auth_user_id))
    if not prev or prev[0] != d:
        _daily[int(auth_user_id)] = (d, 1)
    else:
        _daily[int(auth_user_id)] = (d, prev[1] + 1)


def _guest_bump(client_ip: str) -> None:
    d = _day()
    key = _norm_ip(client_ip)
    prev = _guest_daily.get(key)
    if not prev or prev[0] != d:
        _guest_daily[key] = (d, 1)
    else:
        _guest_daily[key] = (d, prev[1] + 1)


def ask_support(
    *,
    auth_user_id: int | None,
    client_ip: str = "",
    question: str,
    lang_hint: str = "en",
) -> dict[str, Any]:
    q = (question or "").strip()
    if len(q) < 2:
        return {"ok": False, "message": "Please enter a question." if lang_hint != "zh" else "请输入问题。"}
    if len(q) > 2000:
        q = q[:2000]

    is_guest = auth_user_id is None
    if is_guest:
        if not _guest_under_cap(client_ip):
            return {
                "ok": False,
                "guest": True,
                "message": "Daily guest help limit reached. Sign in for more, or try tomorrow."
                if lang_hint != "zh"
                else "游客今日帮助次数已用完，请登录后继续使用或明日再试。",
            }
        if _needs_account_context(q):
            _guest_bump(client_ip)
            return {
                "ok": True,
                "guest": True,
                "answer": _guest_sign_in_hint(lang_hint),
                "model": "sign_in",
                "remaining_today": _remaining_guest(client_ip),
            }
    elif not _under_cap(int(auth_user_id)):
        return {
            "ok": False,
            "guest": False,
            "message": "Daily help limit reached. See Help center or try tomorrow."
            if lang_hint != "zh"
            else "今日帮助次数已用完，请查阅帮助中心或明日再试。",
        }

    # 常见问题关键词命中：秒回，不调模型
    hit = faq_answer_for(q, lang_hint)
    if hit:
        if is_guest:
            _guest_bump(client_ip)
            return {
                "ok": True,
                "guest": True,
                "answer": hit,
                "model": "faq",
                "remaining_today": _remaining_guest(client_ip),
            }
        _bump(int(auth_user_id))
        return {
            "ok": True,
            "guest": False,
            "answer": hit,
            "model": "faq",
            "remaining_today": _remaining_user(int(auth_user_id)),
        }

    from model_router import run_routed_chat

    prompt = f"[AI24X Help]\nUser question:\n{q}"
    if is_guest:
        prompt = (
            "[Visitor — not signed in; answer only general product/API/pricing questions. "
            "Do not guess account balance or orders.]\n" + prompt
        )
    routed = run_routed_chat(
        prompt=_SYSTEM + "\n\n" + prompt,
        requested_model="deepseek-flash",
        is_vip=True,
        temperature=0.3,
        max_tokens=200 if is_guest else 300,
    )
    if is_guest:
        _guest_bump(client_ip)
        remain = _remaining_guest(client_ip)
    else:
        _bump(int(auth_user_id))
        remain = _remaining_user(int(auth_user_id))
    if routed.ok and (routed.text or "").strip():
        return {
            "ok": True,
            "guest": is_guest,
            "answer": routed.text.strip(),
            "model": "help",
            "remaining_today": remain,
        }
    fb = _FAQ_FALLBACK_ZH if lang_hint == "zh" else _FAQ_FALLBACK_EN
    return {
        "ok": True,
        "guest": is_guest,
        "answer": fb,
        "model": "faq_fallback",
        "remaining_today": remain,
    }
