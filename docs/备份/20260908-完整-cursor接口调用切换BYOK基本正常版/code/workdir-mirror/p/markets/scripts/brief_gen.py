"""AI24X Markets · 每日美股简报生成器（P1，可 cron）。

收盘后运行（交易日 ~05:00 UTC 之后）：拉指数 + 热门标的日线统计，
输出描述性简报 Markdown/HTML 到 p/markets/data/brief/YYYYMMDD/。

合规：全流程为确定性技术描述（无模型调用、无建议性表达），附标准免责。
数据纪律：优先本地 markets API（127.0.0.1:18012），失败回退 data/cache 缓存，
单标的单日只取一次（缓存复用），避免高频访问腾讯/东财。
用法：python brief_gen.py [--api http://127.0.0.1:18012] [--symbols AAPL,NVDA,...]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "api" / "server" / "data" / "cache"
OUT_DIR = ROOT / "data" / "brief"
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
    "Market data is delayed at least 15 minutes. Past performance is not a prediction of future results."
)

INDICES = [
    ("DJI", "Dow Jones Industrial Average"),
    ("INX", "S&P 500"),
    ("IXIC", "Nasdaq Composite"),
]
DEFAULT_SYMBOLS = ["NVDA", "AAPL", "TSLA", "MSFT", "AMZN", "META", "GOOGL", "AMD", "PLTR", "NFLX"]


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


def _rsi(values: List[float], period: int = 14) -> Optional[float]:
    n = len(values)
    if n <= period:
        return None
    gains = losses = 0.0
    for i in range(1, period + 1):
        chg = values[i] - values[i - 1]
        gains += max(chg, 0.0)
        losses += max(-chg, 0.0)
    avg_g, avg_l = gains / period, losses / period
    if avg_l == 0:
        return 100.0 if avg_g > 0 else 50.0
    return 100.0 - 100.0 / (1.0 + avg_g / avg_l)


def load_kline(sym: str, api_base: str, count: int = 260) -> Optional[Dict[str, Any]]:
    rows: Optional[List[List[Any]]] = None
    source = ""
    if api_base:
        try:
            import urllib.request

            url = f"{api_base}/api/kline?symbol={sym}&period=day&count={count}"
            with urllib.request.urlopen(url, timeout=12) as resp:
                j = json.loads(resp.read().decode("utf-8"))
            if j.get("code") == 0 and (j.get("data") or {}).get("candles"):
                rows = j["data"]["candles"]
                source = "api"
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


def stats(data: Dict[str, Any]) -> Dict[str, Any]:
    candles = data["candles"]
    closes = [c["close"] for c in candles]
    last, prev = closes[-1], closes[-2]
    ma20 = _sma(closes, 20)[-1]
    ma60 = _sma(closes, 60)[-1]
    rsi = _rsi(closes)
    vols = [c["vol"] for c in candles]
    avg20 = sum(vols[-21:-1]) / 20.0 if len(vols) >= 21 else 0
    vratio = vols[-1] / avg20 if avg20 else None
    if vratio is None:
        vol_note = "n/a"
    elif vratio >= 1.5:
        vol_note = "elevated"
    elif vratio <= 0.6:
        vol_note = "below average"
    else:
        vol_note = "in line"
    seg = closes[-60:]
    lo, hi = min(seg), max(seg)
    pos = 50.0 if hi == lo else (last - lo) / (hi - lo) * 100.0
    above20 = last > ma20
    above60 = last > ma60
    if above20 and above60:
        trend = "above MA20 and MA60"
    elif above20:
        trend = "above MA20, below MA60"
    elif above60:
        trend = "below MA20, above MA60"
    else:
        trend = "below MA20 and MA60"
    if rsi is None:
        rsi_note = "n/a"
    elif rsi >= 70:
        rsi_note = "elevated"
    elif rsi >= 45:
        rsi_note = "neutral"
    elif rsi >= 30:
        rsi_note = "soft"
    else:
        rsi_note = "oversold"
    return {
        "asof": candles[-1]["date"],
        "last": last,
        "day_chg": _pct(last, prev),
        "chg5": _pct(last, closes[-6]) if len(closes) >= 6 else None,
        "chg20": _pct(last, closes[-21]) if len(closes) >= 21 else None,
        "chg60": _pct(last, closes[-61]) if len(closes) >= 61 else None,
        "ma20": ma20,
        "ma60": ma60,
        "rsi": rsi,
        "rsi_note": rsi_note,
        "pos60": pos,
        "vol_note": vol_note,
        "trend": trend,
    }


def compliant_assert(text: str, what: str) -> None:
    hits = FORBIDDEN_RE.findall(text)
    if hits:
        raise SystemExit(f"COMPLIANCE FAIL on {what}: {sorted(set(h.lower() for h in hits))}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://127.0.0.1:18012")
    ap.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    args = ap.parse_args()
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]

    rows: List[Dict[str, Any]] = []
    for sym, label in INDICES:
        data = load_kline(sym, args.api)
        if not data:
            print(f"[warn] no data for index {sym} — skip")
            continue
        st = stats(data)
        rows.append({"kind": "index", "sym": sym, "label": label, "st": st, "source": data["source"]})
    for sym in symbols:
        data = load_kline(sym, args.api)
        if not data:
            print(f"[warn] no data for {sym} — skip")
            continue
        st = stats(data)
        rows.append({"kind": "stock", "sym": sym, "label": sym, "st": st, "source": data["source"]})

    if not rows:
        print("no data at all — abort")
        return 1
    asof = rows[0]["st"]["asof"]
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_dir = OUT_DIR / day.replace("-", "")
    out_dir.mkdir(parents=True, exist_ok=True)

    idx_lines = ["| Index | Close | Change | 5-bar | 20-bar |"]
    idx_lines.append("|---|---:|---:|---:|---:|")
    stock_lines = [
        "| Symbol | Close | Change | 5-bar | 20-bar | 60-bar | RSI | Trend | Volume |",
        "|---|---:|---:|---:|---:|---:|---:|---|---:|---:|",
    ]
    for r in rows:
        st = r["st"]
        chg = f"{_f(st['day_chg'])}%"
        if r["kind"] == "index":
            idx_lines.append(
                f"| {r['label']} ({r['sym']}) | {_f(st['last'])} | {chg} | {_f(st['chg5'])}% | {_f(st['chg20'])}% |"
            )
        else:
            stock_lines.append(
                f"| {r['sym']} | {_f(st['last'])} | {chg} | {_f(st['chg5'])}% | {_f(st['chg20'])}% | "
                f"{_f(st['chg60'])}% | {_f(st['rsi'], 0)} ({st['rsi_note']}) | {st['trend']} | {st['vol_note']} |"
            )

    snapshot = (
        f"Latest session: {asof} (delayed). Index rows use daily closes; stock rows use daily closes "
        f"with MA20/MA60, RSI-14, 60-bar range position and volume vs 20-bar average as descriptive context."
    )
    md = "\n".join(
        [
            f"# AI24X Markets · Daily US Market Brief — {day}",
            "",
            f"*Data as of {asof} · generated {datetime.now(timezone.utc).isoformat(timespec='seconds')} UTC · educational content*",
            "",
            "## Market Overview",
            "",
            "\n".join(idx_lines),
            "",
            "## Popular Symbols — Technical Snapshot",
            "",
            "\n".join(stock_lines),
            "",
            "## Notes",
            "",
            f"- {snapshot}",
            "- RSI zones: elevated ≥70, neutral 45-69, soft 30-44, oversold <30. These are descriptive labels, not recommendations.",
            "",
            DISCLAIMER,
            "",
        ]
    )
    compliant_assert(md, "brief md")

    def _row_html(r: Dict[str, Any]) -> str:
        st = r["st"]
        cls = "up" if (st["day_chg"] or 0) >= 0 else "down"
        if r["kind"] == "index":
            return (
                f"<tr><td>{r['label']} ({r['sym']})</td><td>{_f(st['last'])}</td>"
                f"<td class='{cls}'>{_f(st['day_chg'])}%</td><td>{_f(st['chg5'])}%</td><td>{_f(st['chg20'])}%</td></tr>"
            )
        return (
            f"<tr><td><a href='{APP_URL}/app.html?symbol={r['sym']}'>{r['sym']}</a></td>"
            f"<td>{_f(st['last'])}</td><td class='{cls}'>{_f(st['day_chg'])}%</td>"
            f"<td>{_f(st['chg5'])}%</td><td>{_f(st['chg20'])}%</td><td>{_f(st['chg60'])}%</td>"
            f"<td>{_f(st['rsi'], 0)} ({st['rsi_note']})</td><td>{st['trend']}</td><td>{st['vol_note']}</td></tr>"
        )
    index_rows = "".join(_row_html(r) for r in rows if r["kind"] == "index")
    stock_rows = "".join(_row_html(r) for r in rows if r["kind"] == "stock")
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI24X Markets · Daily US Market Brief — {day}</title>
<style>
body{{background:#0b0f14;color:#e6edf3;font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;line-height:1.7;max-width:900px;margin:0 auto;padding:16px}}
h1{{color:#fbbf24}}h2{{color:#fbbf24;margin-top:28px}}
table{{width:100%;border-collapse:collapse;font-size:14px;margin:12px 0}}
th,td{{text-align:left;padding:8px 10px;border-bottom:1px solid #1c2530}}
th{{color:#8b98a9}}a{{color:#60a5fa}}.up{{color:#26a69a}}.down{{color:#ef5350}}
.meta,.disc{{color:#8b98a9;font-size:13px}}.disc{{margin-top:28px;border-top:1px solid #1c2530;padding-top:12px}}
</style>
</head>
<body>
<h1>AI24X Markets · Daily US Market Brief</h1>
<p class="meta">Data as of {asof} · generated {datetime.now(timezone.utc).isoformat(timespec='seconds')} UTC · educational content</p>
<h2>Market Overview</h2>
<table><tr><th>Index</th><th>Close</th><th>Change</th><th>5-bar</th><th>20-bar</th></tr>{index_rows}</table>
<h2>Popular Symbols — Technical Snapshot</h2>
<table><tr><th>Symbol</th><th>Close</th><th>Change</th><th>5-bar</th><th>20-bar</th><th>60-bar</th><th>RSI</th><th>Trend</th><th>Volume</th></tr>{stock_rows}</table>
<p>{snapshot}</p>
<p class="disc">{DISCLAIMER}</p>
</body>
</html>"""
    compliant_assert(html, "brief html")

    (out_dir / "brief.md").write_text(md, encoding="utf-8")
    (out_dir / "brief.html").write_text(html, encoding="utf-8")
    print(f"written: {out_dir / 'brief.md'} + brief.html (asof {asof}, {len(rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
