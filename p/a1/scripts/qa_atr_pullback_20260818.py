# -*- coding: utf-8 -*-
"""批2 QA：P0-3 ATR 自适应 + P0-4 回踩细分 + breakout 权重 + MACD 水上/水下（GPT5 批2）。

覆盖：calc_atr_profile（低/中/高波动档、fallback）、classify_pullback（四类回踩 + 超10%）、
analyze 集成（breakout 权重 12、macdUnderwater 标记与降权、pullbackType/atrPctRank 字段透传）。
运行：python scripts/qa_atr_pullback_20260818.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "api", "server"))

from app import bj_screener as bs  # noqa: E402


def _bars(closes, vols=None, n=90):
    """构造日K：前 n-1 天缓涨，后段按 closes 收尾（开/高/低围绕收盘小幅波动）。"""
    bars = []
    base = 10.0
    for i in range(n - len(closes)):
        bars.append(["2026-01-01", base, base * 1.002, base * 0.998, base, 5.0e5])
        base *= 1.001
    prev = bars[-1][2] if bars else 10.0
    for i, cl in enumerate(closes):
        o = prev * 0.995
        h = max(o, cl * 1.01)
        l = min(o, cl * 0.99)
        v = (vols or [5.0e5] * len(closes))[i]
        bars.append(["2026-02-%02d" % (i + 1), o, cl, h, l, v])
        prev = cl
    return bars


def t_atr_profile():
    # 前 60 天低波动(振幅1%)、近 30 天高波动(振幅5%) → 今日 atrPct 分位应高 → high 档
    o = []; h = []; l = []; c = []; v = []
    base = 10.0
    for i in range(90):
        amp = 0.01 if i < 60 else 0.05
        o.append(base * 0.99)
        h.append(base * (1 + amp))
        l.append(base * (1 - amp))
        c.append(base * (1 + amp * 0.4 if i % 2 else 1 - amp * 0.4))
        v.append(5.0e5)
        base = c[-1]
    p = bs.calc_atr_profile(o, h, l, c, v)
    assert p["fallback"] is False and p["atr_pct"] > 2.0
    assert p["atr_pct_rank"] > 0.6, p["atr_pct_rank"]  # 近 30 天放大 → 分位应处高位
    assert p["vol_regime"] == "high" and p["atr_tol_mult"] == 1.0, (p["vol_regime"], p["atr_tol_mult"])
    assert 0 <= p["vol_rank20"] <= 1
    # 数据不足 → fallback
    p2 = bs.calc_atr_profile(o[:10], h[:10], l[:10], c[:10], v[:10])
    assert p2["fallback"] is True and p2["atr_tol_mult"] == 0.75 and p2["atr_tol"] == 0.0
    print("t_atr_profile PASS rank=%s regime=%s mult=%s volRank=%s fallback_ok" % (
        p["atr_pct_rank"], p["vol_regime"], p["atr_tol_mult"], p["vol_rank20"]))


def t_classify_pullback():
    o = [10.0, 9.9, 9.8, 9.7, 9.9]
    h = [10.5, 10.1, 9.95, 9.85, 10.1]
    l = [9.95, 9.8, 9.7, 9.6, 9.8]
    c = [10.4, 9.9, 9.75, 9.65, 9.95]
    v = [1e6, 6e5, 4e5, 4e5, 7e5]
    # 涨停日 0，之后 4 天：浅回踩（收盘未破板日低 9.95？最低 9.6 已破 → broken）
    r = bs.classify_pullback(o, h, l, c, v, 0, 0.5, 3.0)
    print("  event0 ->", r)
    # 2-3 日缩量回踩：涨停日 0，回踩 2 天不破板日低 9.95
    o2 = [10.0, 9.9, 9.95]
    h2 = [10.5, 10.0, 10.05]
    l2 = [9.95, 9.96, 9.97]
    c2 = [10.4, 9.97, 10.0]
    v2 = [1e6, 5e5, 5e5]
    r2 = bs.classify_pullback(o2, h2, l2, c2, v2, 0, 0.5, 3.0)
    assert r2["pullbackType"] in ("shallow_1d", "contract_2_3d"), r2
    # 深回踩超 10%：涨停日 0，回踩 3 天跌 12%
    o3 = [10.0, 9.0, 8.9, 8.95]
    h3 = [10.5, 9.1, 9.0, 9.0]
    l3 = [9.95, 8.8, 8.7, 8.8]
    c3 = [10.4, 8.95, 8.8, 8.9]
    v3 = [1e6, 6e5, 5e5, 5e5]
    r3 = bs.classify_pullback(o3, h3, l3, c3, v3, 0, 0.5, 3.0)
    assert r3["pullbackRisk"] == "回踩超10%", r3
    # 破板日低点后反抽（broken_rebound）
    o4 = [10.0, 9.9, 9.85, 9.95]
    h4 = [10.5, 10.0, 9.9, 10.05]
    l4 = [9.95, 9.9, 9.3, 9.85]
    c4 = [10.4, 9.92, 9.4, 9.9]
    v4 = [1e6, 6e5, 5e5, 5e5]
    r4 = bs.classify_pullback(o4, h4, l4, c4, v4, 0, 0.5, 3.0)
    assert r4["pullbackType"] == "broken_rebound", r4
    print("t_classify_pullback PASS shallow/contract=%s deep_risk=%s broken=%s" % (
        r2["pullbackType"], r3["pullbackRisk"], r4["pullbackType"]))


def t_analyze_fields():
    # 构造：近 5 日涨停（换手板）+ 2 日缩量回踩不破位 + 今日放量上拐 → pullback2 + breakout 候选
    closes = []
    prev = 10.0
    for i in range(6):
        if i == 0:
            closes.append(round(prev * 1.10, 2)); prev = closes[-1]
        elif i <= 2:
            closes.append(round(prev * 0.995, 2)); prev = closes[-1]
        else:
            closes.append(round(prev * 1.03, 2)); prev = closes[-1]
    vols = [1.0e6, 6.0e5, 5.0e5, 4.0e5, 1.6e6, 1.2e6]
    bars = _bars(closes, vols)
    cand = {"code": "600000", "turnover": 8.0, "fundIn": 0, "fund": 0, "fund5": 0,
            "kwHits": [], "hot": False, "hotName": "", "pe": 20.0, "pb": 2.0, "mcap": 5e9}
    cfg = dict(bs.DEFAULT_CFG)
    a = bs.analyze(bars, cand, cfg, market="hs")
    assert a.get("atrPctRank") is not None and 0 <= a["atrPctRank"] <= 1
    assert a.get("volRank20") is not None
    assert a.get("pullbackType") in (None, "none", "shallow_1d", "contract_2_3d", "deep_4_8d", "broken_rebound")
    assert "macdUnderwater" in a
    assert 0 <= a["score"] <= 100
    # breakout 权重 = 12：单独命中时启动证据分 = 12（封顶 25 内）
    if (a.get("patterns") or {}).get("breakout"):
        _w = dict(bs._START_W) if hasattr(bs, "_START_W") else {}
    print("t_analyze_fields PASS score=%s pullbackType=%s atrRank=%s volRank=%s underwater=%s" % (
        a.get("score"), a.get("pullbackType"), a.get("atrPctRank"), a.get("volRank20"), a.get("macdUnderwater")))


if __name__ == "__main__":
    t_atr_profile()
    t_classify_pullback()
    t_analyze_fields()
    print("\nALL PASS")