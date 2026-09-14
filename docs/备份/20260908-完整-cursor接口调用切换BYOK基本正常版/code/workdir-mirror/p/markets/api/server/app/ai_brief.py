"""AI24X Markets · AI 技术体检点评（Pro 主力功能）。

输入：美股代码 + 周期 → K线统计/均线/MACD/RSI/位置/量能 → 核心层模型
输出「技术体检报告」式描述（教育定位，不构成投资建议；不个性化、不喊单）。

合规红线（写死在 prompt + 后置黑名单双重保险）：
- 不收集用户持仓/风险偏好；输入仅代码 + 公开行情
- 输出禁词：buy / sell / hold / accumulate / target / guarantee / advice /
  advisor / signal / tips / picks / broker / trade / trading / you should / you must
- 全站免责：生成内容附 education disclaimer
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

from . import providers_us
from .a1_engine import signals as a1signals
from . import screener

_CACHE_DIR = Path(__file__).resolve().parent / ".." / "data" / "cache"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)

CORE_BASE = os.environ.get("AI24X_CORE_BASE", "http://127.0.0.1:8000").rstrip("/")
MODEL_KEY = os.environ.get("AI24X_MARKETS_MODEL_KEY", "").strip()
MODEL_NAME = os.environ.get("AI24X_MARKETS_MODEL", "flash").strip() or "flash"
# 降本默认：LLM 点评默认关闭，技术简报走规则模板（零 token 成本）；付费增长后再开。
LLM_ENABLED = os.environ.get("AI24X_MARKETS_BRIEF_LLM", "0").strip().lower() in ("1", "true", "yes", "on")

_DISCLAIMER = (
    "This content is for educational purposes only and is not investment advice. "
    "Market data is delayed at least 15 minutes."
)

# 输出黑名单：命中即剔除/降级（合规红线，宁可保守）
_FORBIDDEN_RE = re.compile(
    r"\b("
    r"buy|sell|hold|accumulate|avoid|recommend|recommendation|signal|signals|"
    r"target|targets|guarantee|guaranteed|tips|picks|broker|"
    r"trade|trading|you should|you must|you can profit|don't miss"
    r")\b",
    re.IGNORECASE,
)

# 部分技术语境可接受的词（描述事实，非建议）——仅提示，不硬删
_ALLOWED_TECH_WORDS = {"holding period", "hold period", "trading range", "trading session"}

# 技术描述中合法的 "trading ..." 短语 → 中性化，避免误杀；其余 trade/trading 仍命中黑名单
_NEUTRALIZE_PHRASES = (
    ("trading below", "price below"),
    ("trading above", "price above"),
    ("trading around", "price around"),
    ("trading near", "price near"),
    ("trading at", "price at"),
    ("trading in", "price in"),
    ("trading within", "price within"),
    ("trading range", "price range"),
    ("trading session", "session"),
    ("trading day", "day"),
    ("signal line", "DEA line"),
    ("signal lines", "DEA lines"),
)


def _rsi_series(closes: List[float], period: int = 14) -> List[Optional[float]]:
    """Wilder-smoothed RSI series（与 main.py 口径一致）。"""
    n = len(closes)
    if n <= period:
        return [None] * n
    out: List[Optional[float]] = [None] * n

    def _val(avg_g: float, avg_l: float) -> float:
        if avg_l == 0.0:
            return 100.0 if avg_g > 0 else 50.0
        rs = avg_g / avg_l
        return 100.0 - 100.0 / (1.0 + rs)

    gains = 0.0
    losses = 0.0
    for i in range(1, period + 1):
        chg = closes[i] - closes[i - 1]
        if chg >= 0:
            gains += chg
        else:
            losses -= chg
    avg_g = gains / period
    avg_l = losses / period
    out[period] = _val(avg_g, avg_l)
    for i in range(period + 1, n):
        chg = closes[i] - closes[i - 1]
        avg_g = (avg_g * (period - 1) + max(chg, 0.0)) / period
        avg_l = (avg_l * (period - 1) + max(-chg, 0.0)) / period
        out[i] = _val(avg_g, avg_l)
    return out


def _f(x: Any, nd: int = 2) -> str:
    """数字转固定小数位字符串，None/NaN → 'n/a'。"""
    if x is None:
        return "n/a"
    try:
        v = float(x)
    except Exception:
        return "n/a"
    if v != v or v in (float("inf"), float("-inf")):
        return "n/a"
    return f"{v:.{nd}f}"


def _to_candles(rows: List[List[Any]], period: str):
    candles = a1signals.candles_from_tencent_like_pack({"day": rows}, "day")
    if period == "week":
        candles = a1signals.aggregate_daily_to_week(candles)
    elif period == "month":
        candles = a1signals.aggregate_daily_to_month(candles)
    return candles


def _pct(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None or b == 0:
        return None
    return (float(a) / float(b) - 1.0) * 100.0


def _position_pct(closes: List[float], window: int = 60) -> Optional[float]:
    """当前价在近 window 根（含当日）高低区间的位置 0-100%。"""
    if len(closes) < 2:
        return None
    seg = closes[-window:]
    lo, hi = min(seg), max(seg)
    if hi == lo:
        return 50.0
    return (closes[-1] - lo) / (hi - lo) * 100.0


def _volume_note(candles) -> str:
    vols = [float(c.vol or 0) for c in candles]
    if len(vols) < 21:
        return "insufficient volume history"
    last = vols[-1]
    avg20 = sum(vols[-21:-1]) / 20.0
    if avg20 <= 0:
        return "volume data unavailable"
    ratio = last / avg20
    if ratio >= 1.5:
        return f"volume ~{ratio:.1f}x the 20-day average (elevated)"
    if ratio >= 1.15:
        return f"volume ~{ratio:.1f}x the 20-day average (moderately above)"
    if ratio <= 0.6:
        return f"volume ~{ratio:.1f}x the 20-day average (below average)"
    return f"volume ~{ratio:.1f}x the 20-day average (in line)"


def _rsi_note(rsi: Optional[float]) -> str:
    if rsi is None:
        return "RSI unavailable (history too short)"
    if rsi >= 70:
        return f"RSI-14 at {rsi:.0f} (elevated zone)"
    if rsi >= 55:
        return f"RSI-14 at {rsi:.0f} (firm zone)"
    if rsi >= 45:
        return f"RSI-14 at {rsi:.0f} (neutral zone)"
    if rsi >= 30:
        return f"RSI-14 at {rsi:.0f} (soft zone)"
    return f"RSI-14 at {rsi:.0f} (oversold zone)"


def _trend_note(closes: List[float]) -> str:
    if len(closes) < 60:
        return "trend context unavailable (history too short)"
    last = closes[-1]
    ma20 = a1signals._sma(closes, 20)[-1]
    ma60 = a1signals._sma(closes, 60)[-1]
    if ma20 is None or ma60 is None:
        return "trend context unavailable"
    above20 = last > ma20
    above60 = last > ma60
    if above20 and above60:
        return f"price is above both the 20-day ({_f(ma20)}) and 60-day ({_f(ma60)}) averages"
    if above20:
        return f"price is above the 20-day average ({_f(ma20)}) but below the 60-day average ({_f(ma60)})"
    if above60:
        return f"price is below the 20-day average ({_f(ma20)}) but above the 60-day average ({_f(ma60)})"
    return f"price is below both the 20-day ({_f(ma20)}) and 60-day ({_f(ma60)}) averages"


def _macd_note(sig: Dict[str, Any]) -> str:
    macd = sig.get("macd") or []
    if len(macd) < 2:
        return "MACD unavailable (history too short)"
    cur = macd[-1]
    prev = macd[-2]
    dif, dea, bar = cur.get("dif"), cur.get("dea"), cur.get("bar")
    if dif is None or dea is None or bar is None:
        return "MACD unavailable"
    rising = bar >= prev.get("bar", bar)
    above = dif > dea
    recent_golden = any(m.get("golden_cross") for m in macd[-3:])
    recent_dead = any(m.get("dead_cross") for m in macd[-3:])
    parts = []
    if above:
        parts.append("MACD DIF is above DEA")
    else:
        parts.append("MACD DIF is below DEA")
    parts.append("histogram " + ("expanding" if rising else "contracting"))
    if recent_golden:
        parts.append("a fresh golden cross appeared within the last 3 bars")
    if recent_dead:
        parts.append("a fresh dead cross appeared within the last 3 bars")
    return "; ".join(parts) + f" (DIF {_f(dif, 3)}, DEA {_f(dea, 3)}, bar {_f(bar, 3)})"


def _build_stats(symbol: str, period: str, candles) -> Dict[str, Any]:
    closes = [float(c.close) for c in candles]
    if len(closes) < 3:
        raise ValueError("insufficient_history")
    last = closes[-1]
    prev = closes[-2]
    ma20 = a1signals._sma(closes, 20)[-1]
    ma60 = a1signals._sma(closes, 60)[-1]
    trend = _trend_note(closes)
    ma5 = a1signals._sma(closes, 5)[-1]
    ma10 = a1signals._sma(closes, 10)[-1]
    rsi = _rsi_series(closes)[-1]
    return {
        "symbol": symbol.upper(),
        "period": period,
        "asof": str(candles[-1].time),
        "last_close": last,
        "day_change_pct": _pct(last, prev),
        "chg_5d_pct": _pct(last, closes[-6]) if len(closes) >= 6 else None,
        "chg_20d_pct": _pct(last, closes[-21]) if len(closes) >= 21 else None,
        "chg_60d_pct": _pct(last, closes[-61]) if len(closes) >= 61 else None,
        "ma5": ma5,
        "ma10": ma10,
        "ma20": ma20,
        "ma60": ma60,
        "trend": trend,
        "rsi14": rsi,
        "pos_60d_pct": _position_pct(closes, 60),
        "volume": _volume_note(candles),
    }


def _cache_path(symbol: str, period: str) -> Path:
    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    # v3：规则模板默认（零 LLM），含支撑阻力/52周位置/风险提示；旧缓存自动失效
    return _CACHE_DIR / f"brief_v3_{symbol.upper()}_{period}_{day}.json"


def _read_cache(symbol: str, period: str) -> Optional[Dict[str, Any]]:
    p = _cache_path(symbol, period)
    if not p.exists():
        return None
    try:
        with open(p, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def _write_cache(symbol: str, period: str, data: Dict[str, Any]) -> None:
    try:
        with open(_cache_path(symbol, period), "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False)
    except Exception:
        pass


_SYSTEM_PROMPT = (
    "You are a technical-analysis chart assistant for AI24X Markets, an educational "
    "charting tool for US equities and ETFs. Describe only the factual technical state "
    "of the symbol from the numeric data provided.\n"
    "HARD RULES:\n"
    "1. Never give recommendations. Never use words like buy, sell, hold, accumulate, avoid, "
    "recommend, advice, advisor, signal, target, guarantee, tips, picks, broker, trade, "
    "trading, 'you should', 'you must'.\n"
    "2. Never personalize: do not refer to the user, their portfolio, or their situation.\n"
    "3. Do not mention future price levels as targets.\n"
    "4. Use neutral, factual, educational language. If data is missing, say so.\n"
    "5. Reply in plain text with exactly three short sections, each with a heading line "
    "like 'Technical Snapshot:', 'Watch Points:', 'Education:'. Keep the whole reply "
    "under 180 words.\n"
    "6. Describe price position with 'price is above/below' — never use the verb "
    "'trading' or the word 'trade'.\n"
    "7. For MACD, refer to DIF and DEA lines; never use the word 'signal'.\n"
    "8. End with the exact sentence: This content is for educational purposes only "
    "and is not investment advice."
)


def _user_prompt(symbol: str, stats: Dict[str, Any]) -> str:
    return (
        f"Symbol: {symbol} (daily {stats['period']} bars, as of {stats['asof']})\n"
        f"Last close: {_f(stats['last_close'])}\n"
        f"Change vs prior bar: {_f(stats['day_change_pct'])}%\n"
        f"5-bar change: {_f(stats['chg_5d_pct'])}% | 20-bar change: {_f(stats['chg_20d_pct'])}% | "
        f"60-bar change: {_f(stats['chg_60d_pct'])}%\n"
        f"MA5 {_f(stats['ma5'])} | MA10 {_f(stats['ma10'])} | MA20 {_f(stats['ma20'])} | "
        f"MA60 {_f(stats['ma60'])}\n"
        f"Trend: {stats['trend']}\n"
        f"MACD: {stats['macd_note']}\n"
        f"RSI: {_rsi_note(stats['rsi14'])}\n"
        f"60-bar position in range: {_f(stats['pos_60d_pct'], 0)}%\n"
        f"Volume: {stats['volume']}\n"
    )


async def _call_model(symbol: str, stats: Dict[str, Any], macd_note: str) -> str:
    if not MODEL_KEY:
        raise RuntimeError("model_key_not_configured")
    user_prompt = _user_prompt(symbol, {**stats, "macd_note": macd_note})
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "max_tokens": 800,
        "temperature": 0.3,
    }
    async with httpx.AsyncClient(timeout=45.0) as client:
        r = await client.post(
            f"{CORE_BASE}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {MODEL_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
    if r.status_code != 200:
        raise RuntimeError(f"model_http_{r.status_code}")
    j = r.json()
    try:
        content = (j.get("choices") or [{}])[0].get("message", {}).get("content") or ""
    except Exception:
        content = ""
    if not content.strip():
        raise RuntimeError("model_empty_response")
    return content.strip()


def _sanitize_output(text: str) -> Tuple[str, int]:
    """黑名单后置过滤：命中计数；危险词剔除（整体降级由调用方决定）。"""
    for src, dst in _NEUTRALIZE_PHRASES:
        text = re.sub(re.escape(src), dst, text, flags=re.IGNORECASE)
    hits = 0
    out_lines: List[str] = []
    for line in text.splitlines():
        found = _FORBIDDEN_RE.findall(line)
        if found:
            hits += len(found)
            line = _FORBIDDEN_RE.sub("[filtered]", line)
        out_lines.append(line)
    return "\n".join(out_lines).strip(), hits


def _strip_trailing_disclaimer(text: str) -> str:
    """去掉模型自带/截断的免责尾巴，统一由我们追加完整版。"""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    while lines and lines[-1].strip().lower().startswith("this content"):
        lines.pop()
    return "\n".join(lines).strip()


def _trend_bias(closes: List[float]) -> str:
    """均线排列 → 多空倾向（纯描述）。"""
    if len(closes) < 60:
        return "trend context unavailable (history too short)"
    ma5 = a1signals._sma(closes, 5)[-1]
    ma10 = a1signals._sma(closes, 10)[-1]
    ma20 = a1signals._sma(closes, 20)[-1]
    ma60 = a1signals._sma(closes, 60)[-1]
    if None in (ma5, ma10, ma20, ma60):
        return "trend context unavailable"
    last = closes[-1]
    if ma5 > ma10 > ma20 > ma60:
        return "moving averages are aligned higher (MA5 > MA10 > MA20 > MA60); price is above the 20-day and 60-day averages"
    if ma5 < ma10 < ma20 < ma60:
        return "moving averages are aligned lower (MA5 < MA10 < MA20 < MA60); price is below the 20-day and 60-day averages"
    above20 = last > ma20
    above60 = last > ma60
    if above20 and above60:
        return "moving averages are mixed but price holds above both the 20-day and 60-day averages"
    if above20:
        return "moving averages are mixed; price is above the 20-day average but below the 60-day average"
    if above60:
        return "moving averages are mixed; price is below the 20-day average but above the 60-day average"
    return "moving averages are mixed; price is below both the 20-day and 60-day averages"


def _risk_notes(score: Dict[str, Any], stats: Dict[str, Any], levels: Dict[str, Any]) -> List[str]:
    """风险提示：评分风险标签 + 计算型风险（破位/高位/超买），全部描述性措辞。"""
    notes: List[str] = []
    seen = set()
    for r in list(score.get("risks") or [])[:4]:
        key = r.lower()
        if key not in seen:
            seen.add(key)
            notes.append(r)
    closes_ok = (stats.get("ma20") is not None and stats.get("ma60") is not None
                 and stats.get("last_close") is not None)
    if closes_ok and stats["last_close"] < stats["ma20"] and stats["last_close"] < stats["ma60"]:
        notes.append("Price is below key moving averages — breakdown caution")
    rsi = stats.get("rsi14")
    if rsi is not None and rsi >= 70:
        notes.append("RSI-14 in the elevated zone")
    pos52 = levels.get("pos_52w_pct")
    if pos52 is not None and pos52 >= 90:
        notes.append("Price near 52-week highs")
    if pos52 is not None and pos52 <= 10:
        notes.append("Price near 52-week lows")
    return notes[:5]


def _rule_brief(symbol: str, stats: Dict[str, Any], macd_note: str,
                score: Dict[str, Any], levels: Dict[str, Any], closes: List[float]) -> str:
    """规则模板技术简报（零 LLM）：趋势/参考位/风险/教育，全描述性、守合规。"""
    bias = _trend_bias(closes)
    sup = levels.get("support")
    res = levels.get("resistance")
    ds = levels.get("dist_support_pct")
    dr = levels.get("dist_resistance_pct")
    atr = levels.get("atr")
    atr_pct = levels.get("atr_pct")
    pos52 = levels.get("pos_52w_pct")
    risks = _risk_notes(score, stats, levels)

    lines = [
        "Technical Snapshot:",
        f"{symbol} closed at {_f(stats['last_close'])} on the latest {stats['period']} bar "
        f"(change {_f(stats['day_change_pct'])}%). {bias.capitalize()}.",
        f"{macd_note}. {_rsi_note(stats['rsi14'])}. "
        f"The price sits at {_f(stats['pos_60d_pct'], 0)}% of its 60-bar range"
        + (f" and {_f(pos52, 0)}% of its 52-week range" if pos52 is not None else "")
        + f". {stats['volume'].capitalize()}.",
        "",
        "Technical Reference Levels:",
        f"- Near support: {_f(sup)}"
        + (f" (~{_f(ds, 1)}% below last close)" if ds is not None else "")
        + f". Near resistance: {_f(res)}"
        + (f" (~{_f(dr, 1)}% above last close)" if dr is not None else "")
        + ".",
        f"- ATR-14: {_f(atr, 2)}"
        + (f" ({_f(atr_pct, 2)}% of price)" if atr_pct is not None else "")
        + ". These are technical reference levels based on recent price geometry and volatility, not predictions.",
        "",
        "Risk Notes:",
    ]
    if risks:
        lines += [f"- {r}" for r in risks]
    else:
        lines.append("- No elevated risk flags detected in the current indicator set.")
    lines += [
        "",
        "Education:",
        "Moving averages, MACD, RSI, range position and ATR are technical descriptors, not predictions. "
        "They summarize past price behavior and can change quickly.",
        "",
        _DISCLAIMER,
    ]
    return "\n".join(lines)


async def generate_brief(user_id: str, symbol: str, period: str = "day") -> Dict[str, Any]:
    """生成（或命中缓存）AI 技术体检点评。免费档日 3 次，Pro 不限。"""
    from . import billing

    symbol = (symbol or "").strip().upper()
    period = (period or "day").strip().lower()
    if not symbol:
        raise ValueError("empty_symbol")
    if period not in ("day", "week", "month"):
        raise ValueError(f"unknown_period:{period}")

    cached = _read_cache(symbol, period)
    if cached:
        return {**cached, "cached": True}

    # 免费额度（Pro 不限）
    remaining = billing.consume_ai_brief(user_id)
    if remaining is None:
        raise ValueError("quota_exceeded")

    obj = await providers_us.get_kline_rows(symbol, period, 500)
    candles = _to_candles(obj["rows"], period)
    stats = _build_stats(symbol, period, candles)
    closes = [float(c.close) for c in candles]
    sig = a1signals.build_signals_v3(candles, cache_key=f"markets-brief:{symbol}:{period}")
    macd_note = _macd_note(sig)
    score = screener.compute_score(symbol, period, candles)
    from .key_levels import compute_key_levels

    levels = compute_key_levels(candles)

    brief = ""
    mode = "rules"
    if LLM_ENABLED:
        try:
            brief = await _call_model(symbol, stats, macd_note)
            brief, hits = _sanitize_output(brief)
            if not brief or hits > 0:
                # 黑名单命中说明模型跑偏，宁可用保守规则模板
                brief = ""
                mode = "fallback_blacklist" if hits else "fallback_empty"
            else:
                mode = "ai"
        except Exception:
            brief = ""
            mode = "fallback_error"
    if not brief:
        brief = _rule_brief(symbol, stats, macd_note, score, levels, closes)

    brief = _strip_trailing_disclaimer(brief)
    if _DISCLAIMER not in brief:
        brief = brief.rstrip() + "\n\n" + _DISCLAIMER

    data = {
        "symbol": symbol,
        "period": period,
        "brief": brief,
        "score": score,
        "levels": levels,
        "risks": list(score.get("risks") or [])[:5],
        "mode": mode,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "cached": False,
        "remaining_today": remaining,
    }
    _write_cache(symbol, period, data)
    return data
