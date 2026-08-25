"""Markets screener + technical health score — share the a1 engine, don't copy.

职责：
1. compute_score(): 复用 p\\a1 scoring.score_candles，输出英文标签/风险/一句话结论，
   供 /api/signals、/api/score、/api/ai/brief 共用（免费不限次，仅本地指标）。
2. run_screener(): 扫描美股池（腾讯主源 + 东财兜底），给出「今日值得看」描述性清单，
   模式均为技术事实描述（bottom volume surge / breakout / uptrend building / pullback），
   不出现 buy/sell/recommend/tips/picks/signal 等措辞，合规红线与 ai_brief 一致。
"""
from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import providers_us
from .a1_engine import scoring as a1scoring
from .a1_engine import signals as a1signals

_CACHE_DIR = Path(__file__).resolve().parent / ".." / "data" / "cache"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)

_SCREENER_CACHE_TTL = 900  # 15 分钟
_SCREENER_CONCURRENCY = 4
_CACHE_VERSION = 3  # 因子升级后 +1，强制全量重扫（旧缓存缺 mcap/pe/rsi/pos52w）

# ---- 美股扫描池（主流大盘 + 热门科技 + 中概 + 指数 ETF，约 80 只）----
UNIVERSE: List[Dict[str, str]] = [
    {"symbol": "AAPL", "name": "Apple"},
    {"symbol": "MSFT", "name": "Microsoft"},
    {"symbol": "GOOGL", "name": "Alphabet"},
    {"symbol": "AMZN", "name": "Amazon"},
    {"symbol": "NVDA", "name": "NVIDIA"},
    {"symbol": "META", "name": "Meta Platforms"},
    {"symbol": "TSLA", "name": "Tesla"},
    {"symbol": "AVGO", "name": "Broadcom"},
    {"symbol": "AMD", "name": "AMD"},
    {"symbol": "INTC", "name": "Intel"},
    {"symbol": "QCOM", "name": "Qualcomm"},
    {"symbol": "TXN", "name": "Texas Instruments"},
    {"symbol": "MU", "name": "Micron"},
    {"symbol": "ORCL", "name": "Oracle"},
    {"symbol": "CRM", "name": "Salesforce"},
    {"symbol": "ADBE", "name": "Adobe"},
    {"symbol": "NFLX", "name": "Netflix"},
    {"symbol": "DIS", "name": "Walt Disney"},
    {"symbol": "PYPL", "name": "PayPal"},
    {"symbol": "UBER", "name": "Uber"},
    {"symbol": "SHOP", "name": "Shopify"},
    {"symbol": "COIN", "name": "Coinbase"},
    {"symbol": "SQ", "name": "Block"},
    {"symbol": "PLTR", "name": "Palantir"},
    {"symbol": "SNOW", "name": "Snowflake"},
    {"symbol": "CRWD", "name": "CrowdStrike"},
    {"symbol": "PANW", "name": "Palo Alto Networks"},
    {"symbol": "ZS", "name": "Zscaler"},
    {"symbol": "DDOG", "name": "Datadog"},
    {"symbol": "MDB", "name": "MongoDB"},
    {"symbol": "NET", "name": "Cloudflare"},
    {"symbol": "V", "name": "Visa"},
    {"symbol": "MA", "name": "Mastercard"},
    {"symbol": "JPM", "name": "JPMorgan Chase"},
    {"symbol": "BAC", "name": "Bank of America"},
    {"symbol": "GS", "name": "Goldman Sachs"},
    {"symbol": "MS", "name": "Morgan Stanley"},
    {"symbol": "WMT", "name": "Walmart"},
    {"symbol": "COST", "name": "Costco"},
    {"symbol": "HD", "name": "Home Depot"},
    {"symbol": "MCD", "name": "McDonald's"},
    {"symbol": "SBUX", "name": "Starbucks"},
    {"symbol": "NKE", "name": "Nike"},
    {"symbol": "KO", "name": "Coca-Cola"},
    {"symbol": "PEP", "name": "PepsiCo"},
    {"symbol": "PG", "name": "Procter & Gamble"},
    {"symbol": "JNJ", "name": "Johnson & Johnson"},
    {"symbol": "PFE", "name": "Pfizer"},
    {"symbol": "MRK", "name": "Merck"},
    {"symbol": "ABBV", "name": "AbbVie"},
    {"symbol": "LLY", "name": "Eli Lilly"},
    {"symbol": "UNH", "name": "UnitedHealth"},
    {"symbol": "XOM", "name": "Exxon Mobil"},
    {"symbol": "CVX", "name": "Chevron"},
    {"symbol": "BA", "name": "Boeing"},
    {"symbol": "CAT", "name": "Caterpillar"},
    {"symbol": "GE", "name": "GE Aerospace"},
    {"symbol": "HON", "name": "Honeywell"},
    {"symbol": "MMM", "name": "3M"},
    {"symbol": "T", "name": "AT&T"},
    {"symbol": "VZ", "name": "Verizon"},
    {"symbol": "TMUS", "name": "T-Mobile"},
    {"symbol": "CSCO", "name": "Cisco"},
    {"symbol": "IBM", "name": "IBM"},
    {"symbol": "AMAT", "name": "Applied Materials"},
    {"symbol": "LRCX", "name": "Lam Research"},
    {"symbol": "KLAC", "name": "KLA"},
    {"symbol": "ASML", "name": "ASML"},
    {"symbol": "SMCI", "name": "Super Micro"},
    {"symbol": "ARM", "name": "Arm Holdings"},
    {"symbol": "RIVN", "name": "Rivian"},
    {"symbol": "LCID", "name": "Lucid"},
    {"symbol": "NIO", "name": "NIO"},
    {"symbol": "XPEV", "name": "XPeng"},
    {"symbol": "LI", "name": "Li Auto"},
    {"symbol": "BABA", "name": "Alibaba"},
    {"symbol": "PDD", "name": "PDD Holdings"},
    {"symbol": "JD", "name": "JD.com"},
    {"symbol": "BIDU", "name": "Baidu"},
    {"symbol": "TME", "name": "Tencent Music"},
    {"symbol": "SE", "name": "Sea Limited"},
    {"symbol": "SPY", "name": "SPDR S&P 500 ETF"},
    {"symbol": "QQQ", "name": "Invesco QQQ ETF"},
    {"symbol": "IWM", "name": "iShares Russell 2000 ETF"},
    {"symbol": "DIA", "name": "SPDR Dow Jones ETF"},
    {"symbol": "XLK", "name": "Technology Select SPDR"},
    {"symbol": "XLF", "name": "Financial Select SPDR"},
    {"symbol": "XLE", "name": "Energy Select SPDR"},
    {"symbol": "GLD", "name": "SPDR Gold Shares"},
    {"symbol": "SLV", "name": "iShares Silver Trust"},
]


# 评分标签中文→英文（scoring.py 输出中文，国际版全站英文）
_TAG_EN: Dict[str, str] = {
    "MACD翻红·第1天": "MACD turned positive (day 1)",
    "MACD翻红·第2天": "MACD positive (day 2)",
    "MACD翻红·第3天": "MACD positive (day 3)",
    "红柱放大": "MACD histogram expanding",
    "均线多头": "MAs aligned higher",
    "MA20上翘": "MA20 sloping up",
    "均线金叉": "MA golden cross",
    "站上MA20": "Price above MA20",
    "温和放量": "Moderate volume",
    "价升量增": "Rise on higher volume",
    "异动回踩支撑": "Pullback holding support",
    "异动回踩中": "Consolidating after move",
    "MA57上方": "Above 57-day MA",
    "动能偏热": "Momentum warm",
    "动能健康": "Healthy momentum",
    "低位修复": "Recovering from lows",
    "超跌区": "Oversold zone",
    "量价配合": "Volume confirms price",
    "波动收敛": "Volatility compressing",
    "放量突破": "Breakout on volume",
    "首板": "Strong up day",
}

_RISK_EN: Dict[str, str] = {
    "RSI超买": "RSI overbought",
    "量价背离": "Price-volume divergence",
    "波动骤增": "Volatility spiking",
    "ST/退市风险": "Delisting risk",
    "连续下杀": "Consecutive drops",
    "多次跌停": "Repeated sharp drops",
    "破位下行": "Broken below MAs",
    "高位滞涨": "Stalling near highs",
    "量能低迷": "Thin volume",
    "放量杀跌": "Drop on heavy volume",
    "长上影滞涨": "Long upper shadow",
    "涨停开板": "Failed surge day",
    "创60日新低": "60-day low",
    "跌破双均线": "Below key MAs",
    "5日涨幅过大": "Rallied sharply in 5 days",
    "放量过热": "Volume overheated",
}


def _to_candles(rows: List[List[Any]], period: str = "day") -> List[Any]:
    candles = a1signals.candles_from_tencent_like_pack({"day": rows}, "day")
    if period == "week":
        candles = a1signals.aggregate_daily_to_week(candles)
    elif period == "month":
        candles = a1signals.aggregate_daily_to_month(candles)
    return candles


def _translate(tags: List[str], risks: List[str]) -> tuple[List[str], List[str]]:
    out_tags: List[str] = []
    for t in tags:
        en = _TAG_EN.get(t)
        if en:
            out_tags.append(en)
        elif t.startswith("位置") and t.endswith("%"):
            out_tags.append(t.replace("位置", "Position ").replace("%", "% of 60-day range"))
        elif t.startswith("MACD翻红·第"):
            day = "".join(ch for ch in t if ch.isdigit())
            out_tags.append(f"MACD positive ({day} days)" if day else "MACD turned positive")
        elif t.startswith("均线金叉×"):
            n = "".join(ch for ch in t if ch.isdigit())
            out_tags.append(f"MA golden crosses x{n}" if n else "MA golden cross")
    out_risks: List[str] = []
    for r in risks:
        en = _RISK_EN.get(r)
        if en:
            out_risks.append(en)
    return out_tags[:6], out_risks[:4]


def _summary(score: float, tags: List[str]) -> str:
    if score >= 75:
        return "Healthy technical momentum"
    if score >= 60:
        return "Moderate uptrend"
    if score >= 45:
        return "Neutral range"
    return "Weak / oversold"


def compute_score(symbol: str, period: str, candles: List[Any]) -> Dict[str, Any]:
    """0-100 technical health score + English tags/risks/one-line summary."""
    if not candles or len(candles) < 60:
        return {
            "ok": False,
            "symbol": (symbol or "").upper(),
            "period": period or "day",
            "score": 0,
            "msg": "insufficient data",
        }
    r = a1scoring.score_candles(candles, name=symbol or "")
    if not r.get("ok"):
        return {
            "ok": False,
            "symbol": (symbol or "").upper(),
            "period": period or "day",
            "score": 0,
            "msg": str(r.get("msg") or "score_failed"),
        }
    tags_en, risks_en = _translate(list(r.get("tags") or []), list(r.get("risks") or []))
    closes = [float(c.close) for c in candles]
    n = len(closes)
    pct5 = (closes[-1] / closes[-6] - 1.0) * 100.0 if n > 6 and closes[-6] > 0 else 0.0
    pct20 = (closes[-1] / closes[-21] - 1.0) * 100.0 if n > 21 and closes[-21] > 0 else 0.0
    score = float(r.get("score") or 0)
    return {
        "ok": True,
        "symbol": (symbol or "").upper(),
        "period": period or "day",
        "score": round(score, 1),
        "summary": _summary(score, tags_en),
        "tags": tags_en,
        "risks": risks_en,
        "cpos": r.get("cpos"),
        "vol_ratio": r.get("vol_ratio"),
        "up_pct": r.get("up_pct"),
        "red_days": r.get("red_days"),
        "pct5": round(pct5, 2),
        "pct20": round(pct20, 2),
        "latest_time": r.get("latest_time"),
    }


def _sma(values: List[float], n: int) -> List[Optional[float]]:
    out: List[Optional[float]] = []
    s = 0.0
    for i, v in enumerate(values):
        s += v
        if i >= n:
            s -= values[i - n]
        out.append(s / n if i >= n - 1 else None)
    return out


def _rsi(closes: List[float], period: int = 14) -> Optional[float]:
    """Wilder-smoothed RSI（与 alerts/main 同口径）。"""
    if len(closes) <= period:
        return None
    gains, losses = 0.0, 0.0
    for i in range(1, period + 1):
        chg = closes[i] - closes[i - 1]
        if chg >= 0:
            gains += chg
        else:
            losses -= chg
    avg_g, avg_l = gains / period, losses / period
    for i in range(period + 1, len(closes)):
        chg = closes[i] - closes[i - 1]
        avg_g = (avg_g * (period - 1) + max(chg, 0.0)) / period
        avg_l = (avg_l * (period - 1) + max(-chg, 0.0)) / period
    if avg_l == 0.0:
        return 100.0 if avg_g > 0 else 50.0
    return 100.0 - 100.0 / (1.0 + avg_g / avg_l)


def _detect_patterns(
    symbol: str, name: str, candles: List[Any], score: Dict[str, Any]
) -> List[str]:
    """技术事实描述式模式，全部中性措辞（无建议词）。"""
    if not candles or len(candles) < 70:
        return []
    closes = [float(c.close) for c in candles]
    highs = [float(c.high) for c in candles]
    lows = [float(c.low) for c in candles]
    vols = [float(c.vol or 0.0) for c in candles]
    n = len(closes)
    avg20_vol = (sum(vols[-21:-1]) / 20.0) if n >= 21 else (sum(vols) / max(1, n))
    if avg20_vol <= 0:
        return []
    cur = closes[-1]
    ma5 = _sma(closes, 5)[-1]
    ma10 = _sma(closes, 10)[-1]
    ma20 = _sma(closes, 20)[-1]
    h20 = max(highs[-20:]) if n >= 20 else max(highs)
    vol_ratio = vols[-1] / avg20_vol
    cpos = float(score.get("cpos") or 0.5)
    pct20 = float(score.get("pct20") or 0.0)

    patterns: List[str] = []

    # 底部放量异动：近15日单日涨幅≥4% 且量≥1.8×20日均量 且异动日位置≤50%
    surge_days = 0
    for i in range(max(1, n - 15), n):
        chg = (closes[i] / closes[i - 1] - 1.0) * 100.0 if closes[i - 1] > 0 else 0.0
        if chg >= 4.0 and vols[i] >= avg20_vol * 1.8:
            lo = min(lows[max(0, i - 59) : i + 1])
            hi = max(highs[max(0, i - 59) : i + 1])
            day_pos = (closes[i] - lo) / (hi - lo) if hi > lo else 0.5
            if day_pos <= 0.5:
                surge_days += 1
    if surge_days >= 1 and ma5 is not None and cur > ma5:
        patterns.append("Bottom volume surge")

    # 放量突破：收盘≥20日高 且 量比≥1.5
    if cur >= h20 * 0.999 and vol_ratio >= 1.5:
        patterns.append("Breakout on volume")

    # 趋势启动：均线多头 或 MACD 翻红初期
    if ma5 is not None and ma10 is not None and ma20 is not None and ma5 > ma10 > ma20:
        patterns.append("Uptrend building")
    elif int(score.get("red_days") or 0) in (1, 2, 3, 4, 5, 6):
        patterns.append("MACD momentum building")

    # 异动后回踩企稳：15日内异动 且 当前价在 MA5~MA10 之间
    if (
        surge_days >= 1
        and ma5 is not None
        and ma10 is not None
        and ma10 > cur >= ma5
    ):
        patterns.append("Pullback holding near MAs")

    # 刚启动约束：20日涨幅不过大 + 位置不过高
    if pct20 > 35.0 or cpos > 0.82:
        patterns = []
    return patterns


def _cache_file() -> Path:
    return _CACHE_DIR / "screener_us.json"


def _read_cache() -> Optional[Dict[str, Any]]:
    p = _cache_file()
    if not p.exists():
        return None
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
        if obj.get("day") == datetime.now(timezone.utc).strftime("%Y-%m-%d") and (
            time.time() - obj.get("ts", 0) < _SCREENER_CACHE_TTL
        ) and obj.get("v") == _CACHE_VERSION:
            return obj
    except Exception:
        pass
    return None


def _write_cache(data: Dict[str, Any]) -> None:
    try:
        _cache_file().write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


async def _scan_one(item: Dict[str, str]) -> Optional[Dict[str, Any]]:
    symbol = item["symbol"]
    try:
        obj = await providers_us.get_kline_rows(symbol, "day", 300)
        rows = obj.get("rows") or []
        if len(rows) < 60:
            return None
        candles = _to_candles(rows, "day")
        score = compute_score(symbol, "day", candles)
        if not score.get("ok"):
            return None
        cur = float(candles[-1].close)
        if cur <= 0 or cur < 2.0:
            return None
        closes = [float(c.close) for c in candles]
        avg_close = sum(float(c.close) for c in candles[-21:-1]) / 20.0
        avg20_vol = sum(float(c.vol or 0.0) for c in candles[-21:-1]) / 20.0
        if avg_close <= 0 or avg20_vol <= 0 or avg20_vol * avg_close < 2_000_000:
            return None
        patterns = _detect_patterns(symbol, item.get("name", ""), candles, score)
        if not patterns and float(score.get("score") or 0) < 50:
            return None
        chg_pct = float(score.get("up_pct") or 0.0)
        # 行情因子（市值/PE/52周高低）——腾讯 quote，失败则 n/a 不阻断
        q = None
        try:
            q = await providers_us.fetch_tencent_quote(symbol)
        except Exception:
            q = None
        mcap = None
        if q and q.get("mcap_usd"):
            mcap = float(q["mcap_usd"])
        seg52 = closes[-260:] if len(closes) >= 60 else closes
        lo52, hi52 = min(seg52), max(seg52)
        pos52 = (cur - lo52) / (hi52 - lo52) if hi52 > lo52 else 0.5
        rsi = _rsi(closes)
        return {
            "symbol": symbol,
            "name": item.get("name", symbol),
            "price": round(cur, 2),
            "chg_pct": round(chg_pct, 2),
            "pct5": score.get("pct5"),
            "pct20": score.get("pct20"),
            "score": score.get("score"),
            "summary": score.get("summary"),
            "patterns": patterns,
            "tags": score.get("tags"),
            "risks": score.get("risks"),
            "pos60": round(float(score.get("cpos") or 0.5), 2),
            "pos52w": round(float(pos52), 2),
            "vol_ratio": score.get("vol_ratio"),
            "rsi": round(rsi, 1) if rsi is not None else None,
            "pe": q.get("pe") if q else None,
            "mcap_usd": round(mcap, 2) if mcap else None,
            "high52w": q.get("high52w") if q else None,
            "low52w": q.get("low52w") if q else None,
            "source": obj.get("source"),
        }
    except Exception:
        return None


def _num(x: Any) -> Optional[float]:
    if x is None:
        return None
    try:
        v = float(x)
    except Exception:
        return None
    return v


def _apply_filters(items: List[Dict[str, Any]], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
    """多因子筛选：市值/PE/RSI/52周位置/量比（任一项缺省即通过）。"""
    out: List[Dict[str, Any]] = []
    for it in items:
        ok = True
        mcap = _num(it.get("mcap_usd"))
        pe = _num(it.get("pe"))
        rsi = _num(it.get("rsi"))
        pos52 = _num(it.get("pos52w"))
        vr = _num(it.get("vol_ratio"))
        for key, lo, hi, val in (
            ("min_mcap", "min_mcap", None, mcap),
            ("max_mcap", None, "max_mcap", mcap),
            ("min_pe", "min_pe", None, pe),
            ("max_pe", None, "max_pe", pe),
            ("min_rsi", "min_rsi", None, rsi),
            ("max_rsi", None, "max_rsi", rsi),
            ("min_pos52", "min_pos52", None, pos52),
            ("max_pos52", None, "max_pos52", pos52),
            ("min_vol_ratio", "min_vol_ratio", None, vr),
        ):
            if val is None:
                continue
            if lo and filters.get(lo) is not None and val < _num(filters[lo]):
                ok = False
                break
            if hi and filters.get(hi) is not None and val > _num(filters[hi]):
                ok = False
                break
        if ok:
            out.append(it)
    return out


async def run_screener(
    mode: str = "all",
    limit: int = 24,
    filters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    mode = (mode or "all").strip()
    if mode.lower() != "all" and mode.lower() not in (
        "bottom volume surge",
        "breakout on volume",
        "uptrend building",
        "macd momentum building",
        "pullback holding near mas",
    ):
        mode = "all"
    cached = _read_cache()
    items: List[Dict[str, Any]] = []
    cached_hit = False
    if cached:
        items = cached.get("items") or []
        cached_hit = True
    else:
        sem = asyncio.Semaphore(_SCREENER_CONCURRENCY)

        async def _limited(item: Dict[str, str]):
            async with sem:
                return await _scan_one(item)

        results = await asyncio.gather(*[_limited(x) for x in UNIVERSE])
        items = [r for r in results if r]
        items.sort(
            key=lambda x: (1 if x.get("patterns") else 0, float(x.get("score") or 0)),
            reverse=True,
        )
        _write_cache(
            {
                "v": _CACHE_VERSION,
                "day": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "ts": time.time(),
                "items": items,
            }
        )

    if mode != "all":
        m_low = mode.lower()
        items = [
            x for x in items if any(m_low == (p or "").lower() for p in (x.get("patterns") or []))
        ]
    if filters:
        items = _apply_filters(items, filters)
    items = items[: max(1, min(40, int(limit) if limit else 24))]
    return {
        "ok": True,
        "mode": mode,
        "count": len(items),
        "cached": cached_hit,
        "scanned": len(UNIVERSE),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "items": items,
        "filters": {k: v for k, v in (filters or {}).items() if v is not None},
        "note": "Educational technical screen — market data delayed at least 15 minutes.",
    }
