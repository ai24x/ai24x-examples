# -*- coding: utf-8 -*-
"""QA 2026-08-25：规则技术简报（key_levels + 趋势倾向 + 合规词）单元测试。"""
import math
import sys
from types import SimpleNamespace

sys.path.insert(0, r"E:\AI24X\ai24x-website\ai24x01\p\markets\api\server")

from app.ai_brief import _FORBIDDEN_RE, _rule_brief, _trend_bias  # noqa: E402
from app.key_levels import compute_key_levels  # noqa: E402

results = []


def log(name, ok, detail=""):
    results.append((name, ok, detail))
    print(("PASS" if ok else "FAIL") + " | " + name + (" | " + detail if detail else ""))


def make_candles(n=300, uptrend=True, base=100.0):
    out = []
    for i in range(n):
        drift = 0.12 if uptrend else -0.12
        price = base * (1 + drift * i / 10) if uptrend else base * (1 + drift * i / 8)
        c = price
        h = c * 1.012
        l = c * 0.988
        v = 1_000_000 + (i % 7) * 10_000
        out.append(SimpleNamespace(close=c, high=h, low=l, vol=v, time=f"2026-01-{i%28+1:02d}"))
    return out


def stats_for(candles):
    closes = [float(c.close) for c in candles]
    last = closes[-1]
    return {
        "symbol": "AAPL",
        "period": "day",
        "asof": str(candles[-1].time),
        "last_close": last,
        "day_change_pct": 0.5,
        "pos_60d_pct": 55.0,
        "ma20": sum(closes[-20:]) / 20,
        "ma60": sum(closes[-60:]) / 60,
        "rsi14": 52.0,
        "volume": "volume ~1.2x the 20-day average (moderately above)",
    }


def test_key_levels():
    up = make_candles(uptrend=True)
    lv = compute_key_levels(up)
    ok = lv["ok"] and lv["support"] is not None and lv["resistance"] is not None
    log("关键位计算 ok", ok, str({k: lv[k] for k in ("support", "resistance", "atr", "atr_pct", "pos_52w_pct")}))
    log("支撑 <= 现价", lv["support"] <= up[-1].close)
    log("阻力 >= 现价", lv["resistance"] >= up[-1].close)
    log("ATR > 0", lv["atr"] is not None and lv["atr"] > 0)
    log("52周位置 0-100", lv["pos_52w_pct"] is not None and 0 <= lv["pos_52w_pct"] <= 100)
    log("距离支撑为负(在下方)", lv["dist_support_pct"] <= 0)
    log("距离阻力为正(在上方)", lv["dist_resistance_pct"] >= 0)
    short = make_candles(10)
    lv2 = compute_key_levels(short)
    log("数据不足返回 ok=False", lv2["ok"] is False and lv2["atr"] is None)


def test_trend_bias():
    up = [100 + i * 0.4 for i in range(120)]
    down = [200 - i * 0.4 for i in range(120)]
    log("多头排列识别", "aligned higher" in _trend_bias(up), _trend_bias(up))
    log("空头排列识别", "aligned lower" in _trend_bias(down), _trend_bias(down))
    log("数据不足返回 unavailable", "unavailable" in _trend_bias(up[:10]))


def test_rule_brief():
    candles = make_candles(uptrend=True)
    closes = [float(c.close) for c in candles]
    stats = stats_for(candles)
    levels = compute_key_levels(candles)
    score = {
        "score": 68.0,
        "summary": "Moderate uptrend",
        "risks": ["RSI overbought", "Price-volume divergence"],
    }
    macd_note = "MACD DIF is above DEA; histogram expanding"
    brief = _rule_brief("AAPL", stats, macd_note, score, levels, closes)
    log("简报含 3 大段落", all(s in brief for s in ("Technical Snapshot:", "Technical Reference Levels:", "Risk Notes:", "Education:")), "")
    log("简报含支撑/阻力数值", ("Near support:" in brief) and ("Near resistance:" in brief))
    log("简报含 ATR", "ATR-14:" in brief)
    log("简报含风险标签", "RSI overbought" in brief and "Price-volume divergence" in brief)
    log("简报含免责声明", "not investment advice" in brief and "delayed at least 15 minutes" in brief)
    hits = _FORBIDDEN_RE.findall(brief)
    log("简报无合规禁词", not hits, str(set(hits)) if hits else "")


def main():
    test_key_levels()
    test_trend_bias()
    test_rule_brief()
    failed = [r for r in results if not r[1]]
    print("TOTAL=" + str(len(results)) + " PASS=" + str(len(results) - len(failed)) + " FAIL=" + str(len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
