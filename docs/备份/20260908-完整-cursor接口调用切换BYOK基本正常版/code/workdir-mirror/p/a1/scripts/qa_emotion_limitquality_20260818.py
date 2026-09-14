# -*- coding: utf-8 -*-
"""批1 QA：P0-1 情绪周期 Gate + P0-2 涨停质量分级（GPT5 选股引擎优化）。

覆盖：五类涨停质量、情绪冷启动、risk_off 构造、温度公式（合成 20 日历史）、
apply_emotion_gate 门槛调整、analyze 集成（limitQuality 字段 + 一字板风险）。
运行：python scripts/qa_emotion_limitquality_20260818.py
"""
from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "api", "server"))

from app import bj_screener as bs  # noqa: E402


def t_classify():
    cases = [
        ("one_word", dict(o_=9.98, h_=10.0, l_=9.98, c_=10.0, prev_close=9.0, limit_pct=9.5, turnover=1.2), "one_word"),
        ("t_board", dict(o_=9.98, h_=10.0, l_=9.2, c_=10.0, prev_close=9.0, limit_pct=9.5, turnover=2.0), "t_board"),
        ("turnover_board", dict(o_=9.5, h_=10.0, l_=9.4, c_=10.0, prev_close=9.0, limit_pct=9.5, turnover=8.0), "turnover_board"),
        ("rotten_unseal", dict(o_=9.0, h_=9.99, l_=8.9, c_=9.3, prev_close=9.0, limit_pct=9.5, turnover=9.0), "rotten_board"),
        ("rotten_high_turn", dict(o_=9.5, h_=10.0, l_=9.4, c_=10.0, prev_close=9.0, limit_pct=9.5, turnover=18.0), "rotten_board"),
        ("normal", dict(o_=9.3, h_=10.0, l_=9.2, c_=10.0, prev_close=9.0, limit_pct=9.5, turnover=3.5), "normal"),
    ]
    for name, kw, exp in cases:
        r = bs.classify_limit_quality(**kw)
        assert r["limitQuality"] == exp, "%s -> %s (expect %s)" % (name, r["limitQuality"], exp)
        assert 0 <= r["limitQualityScore"] <= 100
    print("t_classify PASS (6/6)")


def t_cold_start():
    snap = {"date": "20260818", "temperature": 50, "regime": "normal", "confidence": "low",
            "gate_active": False, "intraday": False, "note": "x", "limit_up": 1, "limit_down": 1,
            "zb": 1, "zb_rate": 0.5, "max_lianban": 1, "fb": 1, "promote": 1, "promote_rate": 1.0, "src": "t"}
    assert snap["confidence"] == "low" and snap["gate_active"] is False
    assert bs.apply_emotion_gate(dict(bs.DEFAULT_CFG), snap, "") is None
    print("t_cold_start PASS")


def t_gate_adj():
    fake = {"gate_active": True, "regime": "risk_off", "note": "t"}
    cfg = dict(bs.DEFAULT_CFG)
    adj = bs.apply_emotion_gate(cfg, fake, "")
    assert adj is not None
    assert abs(adj["scoreMin"] - (cfg["scoreMin"] + 5)) < 0.01
    assert adj["cap"] == max(20, cfg["cap"] // 2)
    adj_pb = bs.apply_emotion_gate(cfg, fake, "pb")
    assert adj_pb["scoreMin"] == cfg["scoreMin"] + 8
    assert bs.apply_emotion_gate(cfg, {"gate_active": False, "regime": "normal"}, "pb") is None
    print("t_gate_adj PASS")


def t_temperature_formula():
    """合成 20 日历史：当前涨停/连板处近 20 日低位 → 温度偏冷（risk_off）；高位 → 偏热。"""
    days = [{"date": "202607%02d" % (i + 1), "limit_up": 60 + i * 3, "limit_down": 2 + i * 0.4,
             "zb_rate": 0.10 + i * 0.02, "max_lianban": 3 + i * 0.3,
             "promote_rate": 0.30 + i * 0.02, "fb_codes": []} for i in range(20)]
    pu = bs._pct_rank([float(x["limit_up"]) for x in days], 40)
    pd_ = bs._pct_rank([float(x["limit_down"]) for x in days], 1)
    pzb = bs._pct_rank([float(x["zb_rate"]) for x in days], 0.40)
    plb = bs._pct_rank([float(x["max_lianban"]) for x in days], 2)
    pjg = bs._pct_rank([float(x["promote_rate"]) for x in days], 0.20)
    temp = int(max(0, min(100, round(25 * pu + 20 * (1 - pd_) + 20 * (1 - pzb) + 20 * plb + 15 * pjg))))
    assert temp < 30, "低位样本温度应偏冷，got %s" % temp
    days_hot = [{"date": "202607%02d" % (i + 1), "limit_up": 60 + i * 3, "limit_down": 2 + i * 0.4,
                 "zb_rate": 0.10 + i * 0.02, "max_lianban": 3 + i * 0.3,
                 "promote_rate": 0.30 + i * 0.02, "fb_codes": []} for i in range(20)]
    pu2 = bs._pct_rank([float(x["limit_up"]) for x in days_hot], 130)
    pd2 = bs._pct_rank([float(x["limit_down"]) for x in days_hot], 0)
    pzb2 = bs._pct_rank([float(x["zb_rate"]) for x in days_hot], 0.05)
    plb2 = bs._pct_rank([float(x["max_lianban"]) for x in days_hot], 10)
    pjg2 = bs._pct_rank([float(x["promote_rate"]) for x in days_hot], 0.80)
    temp_hot = int(max(0, min(100, round(25 * pu2 + 20 * (1 - pd2) + 20 * (1 - pzb2) + 20 * plb2 + 15 * pjg2))))
    assert temp_hot >= 70, "高位样本温度应偏高，got %s" % temp_hot
    print("t_temperature_formula PASS (cold=%s hot=%s)" % (temp, temp_hot))


def t_analyze_integration():
    """构造：近 5 日一字板涨停 + 回调不破位 + 今日放量上拐 → 涨停质量字段 + 一字板风险。"""
    bars = []
    close = 10.0
    for i in range(80):
        if i == 75:
            prev = close
            limit_px = round(prev * 1.0995, 2)
            bars.append(["2026-08-12", limit_px, limit_px, limit_px, limit_px, 1.0e6])
            close = limit_px
        elif i == 76:
            bars.append(["2026-08-13", close * 0.99, close * 0.995, close * 0.985, close * 0.99, 5.0e5])
            close = close * 0.995
        elif i == 77:
            bars.append(["2026-08-14", close * 0.995, close * 1.005, close * 0.99, close * 0.995, 6.0e5])
            close = close * 1.005
        elif i == 78:
            bars.append(["2026-08-17", close * 1.0, close * 1.008, close * 0.995, close * 1.0, 7.0e5])
            close = close * 1.008
        elif i == 79:
            bars.append(["2026-08-18", close * 1.005, close * 1.02, close * 1.0, close * 1.005, 1.2e6])
        else:
            bars.append(["2026-08-01", close, close * 1.002, close * 0.998, close * 1.0, 5.0e5])
    cand = {"code": "600000", "turnover": 1.5, "fundIn": 0, "fund": 0, "fund5": 0,
            "kwHits": [], "hot": False, "hotName": "", "pe": 20.0, "pb": 2.0, "mcap": 5e9}
    cfg = dict(bs.DEFAULT_CFG)
    a = bs.analyze(bars, cand, cfg, market="hs")
    assert a["limitQuality"] == "one_word", a.get("limitQuality")
    assert "一字板·不可交易强度" in (a.get("risks") or [])
    assert (a.get("patterns") or {}).get("firstBoardRight") or (a.get("patterns") or {}).get("pullback2")
    assert 0 <= a["score"] <= 100
    print("t_analyze_integration PASS score=%s lq=%s" % (a.get("score"), a.get("limitQuality")))


if __name__ == "__main__":
    t_classify()
    t_cold_start()
    t_gate_adj()
    t_temperature_formula()
    t_analyze_integration()

    async def _snap():
        s = await bs.compute_emotion_snapshot()
        assert s.get("confidence") == "low"
        return s
    snap = asyncio.run(_snap())
    print("t_real_snapshot PASS temp=%s regime=%s up=%s down=%s zb=%s maxlb=%s promote=%s" % (
        snap.get("temperature"), snap.get("regime"), snap.get("limit_up"),
        snap.get("limit_down"), snap.get("zb"), snap.get("max_lianban"), snap.get("promote")))
    print("\nALL PASS")