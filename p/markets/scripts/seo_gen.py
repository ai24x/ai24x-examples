"""AI24X Markets · 程序化 SEO 落地页生成器（首批 20 页）。

产出 p/markets/web/seo/：
- 10 热门美股页（NVDA/AAPL/TSLA/MSFT/AMZN/META/GOOGL/AMD/PLTR/NFLX）
- 5 指数对比页（QQQ vs SPY 等）
- 5 技术指标教程页（RSI/MACD/均线/支撑压力/量价）

数据：优先本地 markets API（127.0.0.1:18012），失败回退 data/cache kline 缓存。
合规：页面 AI 摘要为确定性技术描述（纯描述，过 P0 措辞铁律黑名单）。
用法：python seo_gen.py [--api http://127.0.0.1:18012] [--force]
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web" / "seo"
ASSETS = WEB / "assets"
CACHE_DIR = ROOT / "api" / "server" / "data" / "cache"
APP_URL = "https://markets.ai24x.com"

FORBIDDEN_RE = re.compile(
    r"\b("
    r"buy|sell|hold|accumulate|avoid|recommend|recommendation|signal|signals|"
    r"target|targets|guarantee|guaranteed|tips|picks|broker|"
    r"trade|trading|you should|you must|you can profit|don't miss"
    r")\b",
    re.IGNORECASE,
)
DISCLAIMER = (
    "This content is for educational purposes only and is not investment advice. "
    "Market data is delayed at least 15 minutes."
)

STOCKS: List[Dict[str, str]] = [
    {"sym": "NVDA", "name": "NVIDIA", "blurb": "AI accelerator leader"},
    {"sym": "AAPL", "name": "Apple", "blurb": "consumer electronics and services"},
    {"sym": "TSLA", "name": "Tesla", "blurb": "electric vehicles and energy"},
    {"sym": "MSFT", "name": "Microsoft", "blurb": "cloud and productivity software"},
    {"sym": "AMZN", "name": "Amazon", "blurb": "e-commerce and cloud (AWS)"},
    {"sym": "META", "name": "Meta Platforms", "blurb": "social platforms and AI"},
    {"sym": "GOOGL", "name": "Alphabet", "blurb": "search, cloud and YouTube"},
    {"sym": "AMD", "name": "AMD", "blurb": "CPU and GPU semiconductors"},
    {"sym": "PLTR", "name": "Palantir", "blurb": "data analytics software"},
    {"sym": "NFLX", "name": "Netflix", "blurb": "streaming entertainment"},
]

INDEX_PAIRS: List[Tuple[str, str, str, str]] = [
    ("QQQ", "SPY", "Nasdaq-100 ETF vs S&P 500 ETF", "growth vs broad market"),
    ("VOO", "SPY", "Vanguard S&P 500 ETF vs SPY", "low-cost index tracking"),
    ("DIA", "SPY", "Dow Jones ETF vs S&P 500 ETF", "blue chips vs broad market"),
    ("IWM", "SPY", "Russell 2000 ETF vs S&P 500 ETF", "small caps vs large caps"),
    ("QQQ", "VOO", "Nasdaq-100 ETF vs VOO", "tech-heavy vs market-cap index"),
]

TUTORIALS: List[Dict[str, str]] = [
    {
        "slug": "rsi-indicator-guide",
        "title": "RSI Indicator Guide",
        "desc": "What the Relative Strength Index measures, overbought and oversold zones, and how to read RSI-14 readings on a chart.",
    },
    {
        "slug": "macd-indicator-guide",
        "title": "MACD Indicator Guide",
        "desc": "How MACD, DIF and DEA lines, and histogram bars describe momentum, plus what golden and dead crosses look like.",
    },
    {
        "slug": "moving-averages-guide",
        "title": "Moving Averages Guide",
        "desc": "How the 20-day and 60-day moving averages describe trend structure and what price above or below them means.",
    },
    {
        "slug": "support-resistance-guide",
        "title": "Support and Resistance Guide",
        "desc": "How to identify support and resistance levels from recent swing highs and lows using daily price data.",
    },
    {
        "slug": "volume-price-guide",
        "title": "Volume and Price Guide",
        "desc": "What volume compared with its 20-day average says about participation, and how volume confirms price moves.",
    },
]


def _f(x: Any, nd: int = 2) -> str:
    if x is None:
        return "n/a"
    try:
        v = float(x)
    except Exception:
        return "n/a"
    if v != v or v in (float("inf"), float("-inf")):
        return "n/a"
    return f"{v:.{nd}f}"


def _pct(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None or not b:
        return None
    return (float(a) / float(b) - 1.0) * 100.0


def _sma(values: List[float], n: int) -> List[Optional[float]]:
    out: List[Optional[float]] = [None] * len(values)
    if len(values) < n:
        return out
    s = sum(values[:n])
    out[n - 1] = s / n
    for i in range(n, len(values)):
        s += values[i] - values[i - n]
        out[i] = s / n
    return out


def _rsi(values: List[float], period: int = 14) -> List[Optional[float]]:
    n = len(values)
    out: List[Optional[float]] = [None] * n
    if n <= period:
        return out
    gains = losses = 0.0
    for i in range(1, period + 1):
        chg = values[i] - values[i - 1]
        gains += max(chg, 0.0)
        losses += max(-chg, 0.0)
    avg_g, avg_l = gains / period, losses / period
    out[period] = 100.0 if avg_l == 0 else 100.0 - 100.0 / (1.0 + avg_g / avg_l)
    for i in range(period + 1, n):
        chg = values[i] - values[i - 1]
        avg_g = (avg_g * (period - 1) + max(chg, 0.0)) / period
        avg_l = (avg_l * (period - 1) + max(-chg, 0.0)) / period
        out[i] = 100.0 if avg_l == 0 else 100.0 - 100.0 / (1.0 + avg_g / avg_l)
    return out


def _macd(closes: List[float]) -> List[Dict[str, Any]]:
    ema12: List[Optional[float]] = [None] * len(closes)
    ema26: List[Optional[float]] = [None] * len(closes)
    if len(closes) < 35:
        return []
    k12, k26 = 2 / 13, 2 / 27
    e12 = e26 = closes[0]
    for i, c in enumerate(closes):
        e12 = c * k12 + e12 * (1 - k12)
        e26 = c * k26 + e26 * (1 - k26)
        ema12[i], ema26[i] = e12, e26
    dif = [ (a or 0) - (b or 0) for a, b in zip(ema12, ema26) ]
    dea: List[Optional[float]] = [None] * len(dif)
    k9 = 2 / 10
    e9 = dif[0]
    for i, d in enumerate(dif):
        e9 = d * k9 + e9 * (1 - k9)
        dea[i] = e9
    out = []
    for i, d in enumerate(dif):
        bar = (d - (dea[i] or 0)) * 2
        golden = i > 0 and (dea[i - 1] or 0) is not None and d > (dea[i] or 0) and dif[i - 1] <= (dea[i - 1] or 0)
        dead = i > 0 and d < (dea[i] or 0) and dif[i - 1] >= (dea[i - 1] or 0)
        out.append({"dif": d, "dea": dea[i], "bar": bar, "golden_cross": bool(golden), "dead_cross": bool(dead)})
    return out


def load_kline(sym: str, api_base: str, count: int = 250) -> Optional[Dict[str, Any]]:
    rows: Optional[List[List[Any]]] = None
    source = ""
    if api_base:
        try:
            import urllib.request

            url = f"{api_base}/api/kline?symbol={sym}&period=day&count={count}"
            with urllib.request.urlopen(url, timeout=10) as resp:
                j = json.loads(resp.read().decode("utf-8"))
            if j.get("code") == 0 and (j.get("data") or {}).get("candles"):
                rows = j["data"]["candles"]
                source = "api:" + str(j["data"].get("source", ""))
        except Exception:
            rows = None
    if not rows:
        fp = CACHE_DIR / f"kline_us{sym}_day.json"
        if fp.exists():
            try:
                with open(fp, "r", encoding="utf-8") as fh:
                    j = json.load(fh)
                rows = j.get("rows")
                source = "cache"
            except Exception:
                rows = None
    if not rows:
        return None
    candles = []
    for r in rows[-count:]:
        try:
            candles.append(
                {
                    "date": str(r[0]),
                    "open": float(r[1]),
                    "close": float(r[2]),
                    "high": float(r[3]),
                    "low": float(r[4]),
                    "vol": float(r[5]) if len(r) > 5 else 0.0,
                }
            )
        except Exception:
            continue
    if len(candles) < 30:
        return None
    return {"symbol": sym, "candles": candles, "source": source}


def compute_stats(data: Dict[str, Any]) -> Dict[str, Any]:
    candles = data["candles"]
    closes = [c["close"] for c in candles]
    last, prev = closes[-1], closes[-2]
    ma5 = _sma(closes, 5)[-1]
    ma10 = _sma(closes, 10)[-1]
    ma20 = _sma(closes, 20)[-1]
    ma60 = _sma(closes, 60)[-1]
    rsi = _rsi(closes)[-1]
    macd = _macd(closes)
    macd_note = "MACD data insufficient"
    golden = dead = False
    if macd:
        cur = macd[-1]
        golden = any(m["golden_cross"] for m in macd[-3:])
        dead = any(m["dead_cross"] for m in macd[-3:])
        above = cur["dif"] > (cur["dea"] or 0)
        macd_note = "MACD DIF is " + ("above" if above else "below") + " DEA"
        if golden:
            macd_note += "; a fresh golden cross appeared within the last 3 bars"
        if dead:
            macd_note += "; a fresh dead cross appeared within the last 3 bars"
    seg = closes[-60:]
    lo, hi = min(seg), max(seg)
    pos = 50.0 if hi == lo else (last - lo) / (hi - lo) * 100.0
    vols = [c["vol"] for c in candles]
    avg20 = sum(vols[-21:-1]) / 20.0 if len(vols) >= 21 else 0
    vratio = vols[-1] / avg20 if avg20 else None
    vol_note = "volume data unavailable"
    if vratio is not None:
        if vratio >= 1.5:
            vol_note = f"volume ~{vratio:.1f}x the 20-day average (elevated)"
        elif vratio >= 1.15:
            vol_note = f"volume ~{vratio:.1f}x the 20-day average (moderately above)"
        elif vratio <= 0.6:
            vol_note = f"volume ~{vratio:.1f}x the 20-day average (below average)"
        else:
            vol_note = f"volume ~{vratio:.1f}x the 20-day average (in line)"
    # 近 60 根 swing 高低 → 支撑/压力参考位（描述性）
    ref = candles[-60:]
    ref_low = min(c["low"] for c in ref)
    ref_high = max(c["high"] for c in ref)
    recent_lows = sorted(c["low"] for c in candles[-20:])
    recent_highs = sorted((c["high"] for c in candles[-20:]), reverse=True)
    support = recent_lows[min(2, len(recent_lows) - 1)]
    resistance = recent_highs[min(2, len(recent_highs) - 1)]
    return {
        "asof": candles[-1]["date"],
        "last": last,
        "day_chg": _pct(last, prev),
        "chg5": _pct(last, closes[-6]) if len(closes) >= 6 else None,
        "chg20": _pct(last, closes[-21]) if len(closes) >= 21 else None,
        "chg60": _pct(last, closes[-61]) if len(closes) >= 61 else None,
        "ma5": ma5,
        "ma10": ma10,
        "ma20": ma20,
        "ma60": ma60,
        "rsi": rsi,
        "macd_note": macd_note,
        "pos60": pos,
        "vol_note": vol_note,
        "support": support,
        "resistance": resistance,
        "range_low": ref_low,
        "range_high": ref_high,
    }


def trend_phrase(st: Dict[str, Any]) -> str:
    above20 = st["last"] > st["ma20"]
    above60 = st["last"] > st["ma60"]
    if above20 and above60:
        return f"price is above both the 20-day ({_f(st['ma20'])}) and 60-day ({_f(st['ma60'])}) averages"
    if above20:
        return f"price is above the 20-day average ({_f(st['ma20'])}) but below the 60-day average ({_f(st['ma60'])})"
    if above60:
        return f"price is below the 20-day average ({_f(st['ma20'])}) but above the 60-day average ({_f(st['ma60'])})"
    return f"price is below both the 20-day ({_f(st['ma20'])}) and 60-day ({_f(st['ma60'])}) averages"


def rsi_phrase(rsi: Optional[float]) -> str:
    if rsi is None:
        return "RSI unavailable"
    if rsi >= 70:
        return f"RSI-14 at {rsi:.0f} (elevated zone)"
    if rsi >= 55:
        return f"RSI-14 at {rsi:.0f} (firm zone)"
    if rsi >= 45:
        return f"RSI-14 at {rsi:.0f} (neutral zone)"
    if rsi >= 30:
        return f"RSI-14 at {rsi:.0f} (soft zone)"
    return f"RSI-14 at {rsi:.0f} (oversold zone)"


def compliant_assert(text: str, what: str) -> None:
    hits = FORBIDDEN_RE.findall(text)
    if hits:
        raise SystemExit(f"COMPLIANCE FAIL on {what}: {sorted(set(h.lower() for h in hits))}")


def render_candle_svg(data: Dict[str, Any], slug: str) -> Path:
    candles = data["candles"][-90:]
    W, H, pad_l, pad_r, pad_t, pad_b = 760, 420, 8, 8, 12, 24
    lo = min(c["low"] for c in candles)
    hi = max(c["high"] for c in candles)
    pad_price = (hi - lo) * 0.06
    lo -= pad_price
    hi += pad_price
    plot_w = W - pad_l - pad_r
    plot_h = H - pad_t - pad_b
    n = len(candles)
    bw = plot_w / n
    def px(i: int) -> float:
        return pad_l + bw * i + bw / 2
    def py(v: float) -> float:
        return pad_t + (hi - v) / (hi - lo) * plot_h
    closes = [c["close"] for c in candles]
    ma20 = _sma(closes, 20)
    ma60 = _sma(closes, 60)
    up, dn = "#26a69a", "#ef5350"
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="system-ui,Segoe UI,Roboto,sans-serif">',
        f'<rect width="{W}" height="{H}" fill="#0b0f14"/>',
    ]
    # 网格
    for g in range(5):
        gy = pad_t + plot_h * g / 4
        parts.append(f'<line x1="{pad_l}" y1="{gy:.1f}" x2="{W - pad_r}" y2="{gy:.1f}" stroke="#1c2530" stroke-width="1"/>')
    # MA 线
    for series, color, name in ((ma20, "#fbbf24", "MA20"), (ma60, "#60a5fa", "MA60")):
        pts = []
        for i, v in enumerate(series):
            if v is not None:
                pts.append(f"{px(i):.1f},{py(v):.1f}")
        if len(pts) > 1:
            parts.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="1.5" opacity="0.9"/>')
    # K 线
    for i, c in enumerate(candles):
        x = px(i)
        color = up if c["close"] >= c["open"] else dn
        parts.append(f'<line x1="{x:.1f}" y1="{py(c["high"]):.1f}" x2="{x:.1f}" y2="{py(c["low"]):.1f}" stroke="{color}" stroke-width="1"/>')
        body_h = max(1.2, abs(py(c["open"]) - py(c["close"])))
        top = min(py(c["open"]), py(c["close"]))
        parts.append(f'<rect x="{x - max(1.0, bw * 0.32):.1f}" y="{top:.1f}" width="{max(2.0, bw * 0.64):.1f}" height="{body_h:.1f}" fill="{color}" rx="1"/>')
    # 价格标签
    parts.append(f'<text x="{pad_l}" y="{H - 6}" fill="#8b98a9" font-size="11">{_f(hi - pad_price, 2)}</text>')
    parts.append(f'<text x="{W - pad_r}" y="{H - 6}" text-anchor="end" fill="#8b98a9" font-size="11">{_f(lo + pad_price, 2)}</text>')
    parts.append('</svg>')
    out = ASSETS / f"{slug}.svg"
    out.write_text("\n".join(parts), encoding="utf-8")
    return out


def render_pair_svg(a: Dict[str, Any], b: Dict[str, Any], slug: str) -> Path:
    W, H, pad_l, pad_r, pad_t, pad_b = 760, 420, 8, 8, 12, 24
    plot_w, plot_h = W - pad_l - pad_r, H - pad_t - pad_b
    n = min(len(a["candles"]), len(b["candles"]), 90)
    ca, cb = a["candles"][-n:], b["candles"][-n:]
    base_a = ca[0]["close"]
    base_b = cb[0]["close"]
    na = [c["close"] / base_a * 100 for c in ca]
    nb = [c["close"] / base_b * 100 for c in cb]
    lo = min(min(na), min(nb)) * 0.995
    hi = max(max(na), max(nb)) * 1.005
    bw = plot_w / n
    def px(i: int) -> float:
        return pad_l + bw * i + bw / 2
    def py(v: float) -> float:
        return pad_t + (hi - v) / (hi - lo) * plot_h
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="system-ui,Segoe UI,Roboto,sans-serif">',
        f'<rect width="{W}" height="{H}" fill="#0b0f14"/>',
    ]
    for g in range(5):
        gy = pad_t + plot_h * g / 4
        parts.append(f'<line x1="{pad_l}" y1="{gy:.1f}" x2="{W - pad_r}" y2="{gy:.1f}" stroke="#1c2530" stroke-width="1"/>')
    for series, color, name in ((na, "#fbbf24", a["symbol"]), (nb, "#60a5fa", b["symbol"])):
        pts = " ".join(f"{px(i):.1f},{py(v):.1f}" for i, v in enumerate(series))
        parts.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2"/>')
    parts.append(f'<text x="{pad_l}" y="{H - 6}" fill="#fbbf24" font-size="12">{a["symbol"]}</text>')
    parts.append(f'<text x="{W - pad_r}" y="{H - 6}" text-anchor="end" fill="#60a5fa" font-size="12">{b["symbol"]}</text>')
    parts.append('</svg>')
    out = ASSETS / f"{slug}.svg"
    out.write_text("\n".join(parts), encoding="utf-8")
    return out


CSS = """
:root{--bg:#0b0f14;--card:#131a22;--line:#1c2530;--fg:#e6edf3;--muted:#8b98a9;--gold:#fbbf24;--blue:#60a5fa;--up:#26a69a;--down:#ef5350}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--fg);font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;line-height:1.7;padding:0 16px 48px}
.wrap{max-width:860px;margin:0 auto}
header{display:flex;align-items:center;justify-content:space-between;padding:18px 0;border-bottom:1px solid var(--line)}
.logo{font-weight:700;color:var(--gold);text-decoration:none}
nav a{color:var(--muted);text-decoration:none;margin-left:18px;font-size:14px}
nav a:hover{color:var(--fg)}
h1{font-size:30px;margin:26px 0 6px;line-height:1.3}
.sub{color:var(--muted);font-size:15px;margin-bottom:18px}
.meta{color:var(--muted);font-size:13px;margin-bottom:22px}
.chart{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px;margin:18px 0}
.chart img{width:100%;height:auto;display:block}
h2{font-size:21px;margin:30px 0 10px;color:var(--gold)}
p{margin:10px 0;color:#c9d4df}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px;margin:18px 0}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px}
.card b{color:var(--gold);font-size:20px;display:block}
.card span{color:var(--muted);font-size:13px}
table{width:100%;border-collapse:collapse;margin:14px 0;font-size:14px}
th,td{text-align:left;padding:9px 12px;border-bottom:1px solid var(--line)}
th{color:var(--muted);font-weight:600}
.up{color:var(--up)}.down{color:var(--down)}
.cta{background:linear-gradient(135deg,#fbbf24,#f59e0b);color:#0b0f14;font-weight:700;display:inline-block;padding:13px 26px;border-radius:10px;text-decoration:none;margin:10px 0}
.cta:hover{opacity:.92}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.disc{font-size:12px;color:var(--muted);margin-top:26px;border-top:1px solid var(--line);padding-top:14px}
ul{padding-left:20px;margin:10px 0}
li{margin:6px 0;color:#c9d4df}
@media(max-width:600px){.grid2{grid-template-columns:1fr}h1{font-size:24px}}
"""


def page_shell(title: str, desc: str, body: str, canonical: str, jsonld: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{APP_URL}/seo/{canonical}">
<meta property="og:type" content="website">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{APP_URL}/seo/{canonical}">
<meta name="robots" content="index,follow">
<style>{CSS}</style>
<script type="application/ld+json">{jsonld}</script>
</head>
<body>
<div class="wrap">
<header>
<a class="logo" href="{APP_URL}">AI24X Markets</a>
<nav>
<a href="{APP_URL}/seo/">Guides</a>
<a href="{APP_URL}/app.html">Charts</a>
<a href="{APP_URL}/pricing.html">Pricing</a>
</nav>
</header>
{body}
<p class="disc">{DISCLAIMER}</p>
</div>
</body>
</html>"""


def stock_faq(sym: str, name: str, st: Dict[str, Any]) -> str:
    return json.dumps(
        {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": f"What does the chart of {name} ({sym}) show?",
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": (
                            f"As of {st['asof']}, {sym} closed at {_f(st['last'])}. {trend_phrase(st).capitalize()}. "
                            f"{st['macd_note']}. {rsi_phrase(st['rsi'])}."
                        ),
                    },
                },
                {
                    "@type": "Question",
                    "name": f"What is {sym} price position relative to its 60-day range?",
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": (
                            f"{sym} sits at approximately {_f(st['pos60'], 0)}% of its 60-bar high-low range, "
                            f"with recent reference support near {_f(st['support'])} and reference resistance near {_f(st['resistance'])}."
                        ),
                    },
                },
                {
                    "@type": "Question",
                    "name": "Is AI24X Markets a stock recommendation service?",
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": "No. AI24X Markets is an educational charting tool. It describes technical state such as moving averages, MACD and RSI, and does not provide recommendations. {DISCLAIMER}".format(
                            DISCLAIMER=DISCLAIMER
                        ),
                    },
                },
            ],
        },
        ensure_ascii=False,
    )


def gen_stock_page(cfg: Dict[str, str], data: Dict[str, Any], api_base: str) -> str:
    sym, name = cfg["sym"], cfg["name"]
    st = compute_stats(data)
    slug = sym.lower()
    chart = render_candle_svg(data, slug)
    up_down = "up" if (st["day_chg"] or 0) >= 0 else "down"
    trend = trend_phrase(st).capitalize()
    rsi = rsi_phrase(st["rsi"])
    ai_summary = (
        f"Technical Snapshot: {sym} closed at {_f(st['last'])} on the latest daily bar "
        f"(change {_f(st['day_chg'])}%). {trend}. {st['macd_note']}. {rsi}. "
        f"The price sits at {_f(st['pos60'], 0)}% of its 60-bar range. {st['vol_note'].capitalize()}."
    )
    compliant_assert(ai_summary, slug)
    others = "".join(
        f'<a href="{o["sym"].lower()}.html">{o["sym"]}</a>&nbsp;·&nbsp;'
        for o in STOCKS
        if o["sym"] != sym
    )
    body = f"""
<h1>{name} ({sym}) Chart and Technical Snapshot</h1>
<p class="sub">{cfg['blurb']} — daily chart with 20-day and 60-day moving averages.</p>
<p class="meta">Data as of {st['asof']} · aggregated market data · educational content</p>
<div class="chart"><img src="assets/{slug}.svg" alt="{name} ({sym}) daily candlestick chart with MA20 and MA60" width="760" height="420"></div>
<div class="cards">
<div class="card"><b>{_f(st['last'])}</b><span>last close</span></div>
<div class="card"><b class="{up_down}">{_f(st['day_chg'])}%</b><span>change vs prior bar</span></div>
<div class="card"><b>{_f(st['chg5'])}%</b><span>5-bar change</span></div>
<div class="card"><b>{_f(st['chg20'])}%</b><span>20-bar change</span></div>
<div class="card"><b>{_f(st['ma20'])}</b><span>20-day average</span></div>
<div class="card"><b>{_f(st['ma60'])}</b><span>60-day average</span></div>
<div class="card"><b>{_f(st['rsi'], 0)}</b><span>RSI-14</span></div>
<div class="card"><b>{_f(st['pos60'], 0)}%</b><span>60-bar range position</span></div>
</div>
<h2>Technical Snapshot</h2>
<p>{ai_summary}</p>
<h2>Reference Levels</h2>
<table>
<tr><th>Metric</th><th>Value</th></tr>
<tr><td>Recent reference support</td><td>{_f(st['support'])}</td></tr>
<tr><td>Recent reference resistance</td><td>{_f(st['resistance'])}</td></tr>
<tr><td>60-bar range low / high</td><td>{_f(st['range_low'])} / {_f(st['range_high'])}</td></tr>
<tr><td>MA5 / MA10 / MA20 / MA60</td><td>{_f(st['ma5'])} / {_f(st['ma10'])} / {_f(st['ma20'])} / {_f(st['ma60'])}</td></tr>
</table>
<h2>Read It Yourself</h2>
<p>Open {sym} in the interactive AI24X Markets charting workbench — add indicators, switch periods, and get the AI technical-health brief.</p>
<a class="cta" href="{APP_URL}/app.html?symbol={sym}">Explore {sym} free</a>
<h2>More Charts</h2>
<p>{others}<a href="index.html">All guides</a></p>
"""
    title = f"{name} ({sym}) Chart and Technical Snapshot"
    desc = f"{name} ({sym}) daily chart with moving averages, MACD, RSI and range position. Read a descriptive technical snapshot of {sym} on AI24X Markets."
    return page_shell(title, desc, body, f"{slug}.html", stock_faq(sym, name, st))


def gen_pair_page(a: str, b: str, label: str, blurb: str, da: Dict[str, Any], db: Dict[str, Any]) -> str:
    slug = f"{a.lower()}-vs-{b.lower()}"
    chart = render_pair_svg(da, db, slug)
    sa, sb = compute_stats(da), compute_stats(db)
    chg_a20, chg_b20 = sa["chg20"] or 0, sb["chg20"] or 0
    chg_a60, chg_b60 = sa["chg60"] or 0, sb["chg60"] or 0
    lead20 = a if chg_a20 >= chg_b20 else b
    lead60 = a if chg_a60 >= chg_b60 else b
    summary = (
        f"Over the last 20 bars, {a} changed {_f(chg_a20)}% and {b} changed {_f(chg_b20)}%; "
        f"over 60 bars, {a} changed {_f(chg_a60)}% and {b} changed {_f(chg_b60)}%. "
        f"{a} sits at {_f(sa['pos60'], 0)}% of its 60-bar range and {b} at {_f(sb['pos60'], 0)}%. "
        f"{a}: {rsi_phrase(sa['rsi'])}. {b}: {rsi_phrase(sb['rsi'])}."
    )
    compliant_assert(summary, slug)
    body = f"""
<h1>{label}</h1>
<p class="sub">{blurb} — normalized 100-index comparison of the last 90 daily bars.</p>
<p class="meta">Data as of {sa['asof']} · educational content</p>
<div class="chart"><img src="assets/{slug}.svg" alt="{label} normalized performance chart" width="760" height="420"></div>
<div class="cards">
<div class="card"><b>{_f(chg_a20)}%</b><span>{a} 20-bar change</span></div>
<div class="card"><b>{_f(chg_b20)}%</b><span>{b} 20-bar change</span></div>
<div class="card"><b>{_f(chg_a60)}%</b><span>{a} 60-bar change</span></div>
<div class="card"><b>{_f(chg_b60)}%</b><span>{b} 60-bar change</span></div>
</div>
<h2>Comparison Snapshot</h2>
<p>{summary}</p>
<p>Over the measured window, {lead20} recorded the higher 20-bar change and {lead60} the higher 60-bar change. Past performance is not a prediction of future results.</p>
<h2>Compare Them Yourself</h2>
<p>Open both tickers side by side in the interactive workbench and apply moving averages, MACD and RSI.</p>
<a class="cta" href="{APP_URL}/app.html?symbol={a}">Open {a} in charts</a>
<h2>More Guides</h2>
<p><a href="index.html">All guides</a></p>
"""
    title = f"{label} — Historical Performance Comparison"
    desc = f"Compare {a} and {b}: 20-bar and 60-bar changes, range position and RSI. A descriptive, educational comparison on AI24X Markets."
    jd = json.dumps(
        {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": f"How do {a} and {b} compare over 60 bars?",
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": f"{a} changed {_f(chg_a60)}% and {b} changed {_f(chg_b60)}% over the last 60 daily bars as of {sa['asof']}.",
                    },
                }
            ],
        },
        ensure_ascii=False,
    )
    return page_shell(title, desc, body, f"{slug}.html", jd)


def gen_tutorial_page(cfg: Dict[str, str], data: Dict[str, Any]) -> str:
    slug = cfg["slug"]
    st = compute_stats(data)
    sample = data["symbol"]
    if slug == "rsi-indicator-guide":
        h2s = ("What the RSI describes", "How to read RSI zones")
        paras = [
            "The Relative Strength Index (RSI-14) measures the size of recent gains against recent losses over 14 bars, scaled to a 0-100 range. It describes how stretched a price move has been, not where the price is going next.",
            f"As of {st['asof']}, {sample} shows {rsi_phrase(st['rsi'])}. Elevated readings near 70 describe a stretched advance; readings near 30 describe a stretched decline. RSI is a descriptive oscillator and can stay in a zone for extended periods.",
            "In the AI24X Markets workbench you can view RSI under the latest daily bar and watch how it responds as price moves relative to its averages.",
        ]
    elif slug == "macd-indicator-guide":
        h2s = ("How MACD is built", "Golden and dead crosses")
        paras = [
            "MACD tracks the gap between a 12-bar and a 26-bar exponential average of price (the DIF line) and its own 9-bar average (the DEA line). The histogram shows the distance between DIF and DEA, doubled.",
            f"As of {st['asof']}, {sample} shows: {st['macd_note']}. A golden cross describes DIF moving above DEA; a dead cross describes DIF moving below DEA. Both are descriptive events, not predictions.",
            "Open any ticker and scroll to the MACD panel below the candles to see DIF, DEA and the histogram together.",
        ]
    elif slug == "moving-averages-guide":
        h2s = ("What moving averages show", "Reading structure")
        paras = [
            "A moving average is the average close over a fixed window. The 20-day average describes the near-term trend; the 60-day average describes the medium-term trend.",
            f"As of {st['asof']}, {sample} closed at {_f(st['last'])} with a 20-day average of {_f(st['ma20'])} and a 60-day average of {_f(st['ma60'])}. {trend_phrase(st).capitalize()}.",
            "When short averages sit above longer averages the structure is often described as stacked; when they cross, it marks a change in the relationship between short and long momentum.",
        ]
    elif slug == "support-resistance-guide":
        h2s = ("What support and resistance mean", "Reference levels from data")
        paras = [
            "Support and resistance are reference areas where price has previously reversed or paused. They are descriptions of historical behavior, not guaranteed levels.",
            f"As of {st['asof']}, {sample} has a recent reference support near {_f(st['support'])} and reference resistance near {_f(st['resistance'])}, with a 60-bar range from {_f(st['range_low'])} to {_f(st['range_high'])}.",
            "In the workbench, horizontal reference lines can be drawn on recent swing highs and lows to study how price interacts with those areas.",
        ]
    else:
        h2s = ("What volume adds to price", "Reading the volume bar")
        paras = [
            "Volume counts how many shares changed hands in a bar. Comparing the latest bar with its 20-bar average shows whether participation is elevated, average, or light.",
            f"As of {st['asof']}, {sample} shows {st['vol_note']}. Moves that occur with elevated volume describe stronger participation than moves on light volume.",
            "Scroll to the volume panel below the candles in the workbench to compare each bar's volume with the 20-day average.",
        ]
    body = f"""
<h1>{cfg['title']}</h1>
<p class="sub">{cfg['desc']}</p>
<p class="meta">Educational guide · uses {sample} daily data as of {st['asof']}</p>
<h2>{h2s[0]}</h2>
<p>{paras[0]}</p>
<h2>{h2s[1]}</h2>
<p>{paras[1]}</p>
<p>{paras[2]}</p>
<h2>See It Live</h2>
<p>Open any US ticker in the interactive workbench to view the {cfg['title'].lower()} alongside price.</p>
<a class="cta" href="{APP_URL}/app.html?symbol={sample}">Open the free workbench</a>
<h2>Related Guides</h2>
<p><a href="index.html">All guides</a></p>
"""
    title = cfg["title"]
    desc = cfg["desc"]
    jd = json.dumps(
        {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": f"Is {cfg['title']} investment advice?",
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": "No. This guide explains how a technical indicator is calculated and read. AI24X Markets is an educational charting tool and does not provide recommendations.",
                    },
                }
            ],
        },
        ensure_ascii=False,
    )
    return page_shell(title, desc, body, f"{slug}.html", jd)


def gen_index_page(pages: List[Tuple[str, str, str]]) -> str:
    stock_links = "".join(
        f'<li><a href="{o["sym"].lower()}.html">{o["name"]} ({o["sym"]})</a> — {o["blurb"]}</li>'
        for o in STOCKS
    )
    pair_links = "".join(
        f'<li><a href="{a.lower()}-vs-{b.lower()}.html">{c}</a> — {d}</li>'
        for a, b, c, d in INDEX_PAIRS
    )
    tut_links = "".join(
        f'<li><a href="{t["slug"]}.html">{t["title"]}</a> — {t["desc"]}</li>' for t in TUTORIALS
    )
    body = f"""
<h1>AI24X Markets · Charts and Technical Guides</h1>
<p class="sub">Free, educational charting for US equities and ETFs. Every page is a descriptive technical snapshot — no recommendations, ever.</p>
<h2>Popular US Stocks</h2>
<ul>{stock_links}</ul>
<h2>Index and ETF Comparisons</h2>
<ul>{pair_links}</ul>
<h2>Indicator Guides</h2>
<ul>{tut_links}</ul>
<h2>Try the Workbench</h2>
<p>Open any symbol in the interactive chart with moving averages, MACD, RSI and the AI technical-health brief.</p>
<a class="cta" href="{APP_URL}/app.html">Open charts free</a>
"""
    return page_shell(
        "AI24X Markets — Charts and Technical Guides",
        "Free educational US stock and ETF charts with moving averages, MACD and RSI, plus descriptive technical snapshots and indicator guides.",
        body,
        "index.html",
        "{}",
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://127.0.0.1:18012")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    WEB.mkdir(parents=True, exist_ok=True)
    ASSETS.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    pages = []
    for cfg in STOCKS:
        data = load_kline(cfg["sym"], args.api)
        if data is None:
            print(f"[warn] no data for {cfg['sym']} — skip")
            continue
        html = gen_stock_page(cfg, data, args.api)
        fp = WEB / f"{cfg['sym'].lower()}.html"
        fp.write_text(html, encoding="utf-8")
        pages.append(fp.name)
        print(f"[ok] {fp.name} (asof {compute_stats(data)['asof']})")
    for a, b, label, blurb in INDEX_PAIRS:
        da, db = load_kline(a, args.api), load_kline(b, args.api)
        if not da or not db:
            print(f"[warn] missing data for {a} or {b} — skip pair")
            continue
        fp = WEB / f"{a.lower()}-vs-{b.lower()}.html"
        fp.write_text(gen_pair_page(a, b, label, blurb, da, db), encoding="utf-8")
        pages.append(fp.name)
        print(f"[ok] {fp.name}")
    sample_data = load_kline("AAPL", args.api)
    for t in TUTORIALS:
        if not sample_data:
            print(f"[warn] no sample data for tutorial {t['slug']} — skip")
            continue
        fp = WEB / f"{t['slug']}.html"
        fp.write_text(gen_tutorial_page(t, sample_data), encoding="utf-8")
        pages.append(fp.name)
        print(f"[ok] {fp.name}")
    idx = WEB / "index.html"
    idx.write_text(gen_index_page(pages), encoding="utf-8")
    print(f"generated {len(pages)} pages + index into {WEB} (date {today})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
