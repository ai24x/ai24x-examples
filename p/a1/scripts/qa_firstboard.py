# -*- coding: utf-8 -*-
"""P0 刀1 验收单测：首板不再被粗筛删掉 + firstBoardRight 命中且旧 warn 消失。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "api", "server"))

from app import bj_screener as bs

CFG = dict(bs.DEFAULT_CFG)

# ---- coarse：北证 30cm 涨停当天（f3=30）不再被删 ----
row_bj_zt = {
    "f12": "920932", "f14": "测试股", "f2": 15.6, "f3": 30.0, "f6": 90000000.0,
    "f8": 8.0, "f9": 20.0, "f20": 15.0e8, "f21": 8.0e8, "f23": 2.0,
    "f62": 5.0e6, "f100": "软件开发", "f128": "机器人概念,智能制造",
}
c1 = bs.coarse(row_bj_zt, CFG, {})
assert c1 is not None, "coarse: BJ 30cm 涨停当天被误删!"
assert c1["concepts"] == ["机器人概念", "智能制造"], c1["concepts"]

# 异常暴涨（无涨跌停限制新股 f3=45）仍排除
row_bj_boom = dict(row_bj_zt, f3=45.0)
assert bs.coarse(row_bj_boom, CFG, {}) is None, "coarse: 异常暴涨未排除!"

# 科创 20cm 涨停（f3=20）不被删；主板 9.9 不被删
row_kc_zt = dict(row_bj_zt, f12="688001", f3=20.0)
assert bs.coarse(row_kc_zt, CFG, {}) is not None, "coarse: 科创 20cm 涨停被误删!"
row_hs_zt = dict(row_bj_zt, f12="600001", f3=9.9)
assert bs.coarse(row_hs_zt, CFG, {}) is not None, "coarse: 主板 9.9 涨停被误删!"
print("coarse OK: 北证/科创/主板 涨停当天均纳入候选，异常暴涨仍排除")


def mk_bars(base, n_flat, zt_idx, zt_pct, pull_days, today_pct, today_vol_k):
    """构造 K 线：前段平台 → 涨停日 → 回调 N 日 → 今日放量上拐。"""
    bars = []
    px = base
    for i in range(n_flat):
        bars.append([f"2026-01-{i+1:02d}", px, px, px * 1.01, px * 0.99, 100.0])
    # 涨停日
    zc = px * (1 + zt_pct / 100)
    bars.append(["zt", px, zc, zc * 1.01, px, 400.0])
    # 回调日
    c_prev = zc
    for j in range(pull_days):
        cp = c_prev * (1 - 0.03)
        bars.append([f"pull{j}", c_prev * 0.995, cp, c_prev, cp * 0.985, 120.0])
        c_prev = cp
    # 今日放量上拐
    bars.append(["today", c_prev * 0.99, c_prev * (1 + today_pct / 100),
                 c_prev * 1.02, c_prev * 0.98, today_vol_k])
    return bars


# 北证 30cm：昨日涨停 → 今日回调1日后放量上拐（last-zt=1，排除 pb2 干扰）
bars = mk_bars(10.0, 70, 0, 30.0, 1, 4.0, 320.0)
cand = {
    "code": "920932", "name": "测试股", "market": "bj",
    "mcap": 15.0e8, "floatMcap": 8.0e8, "pe": 20.0, "ind": "软件开发",
    "concepts": ["机器人概念"], "indCnt": 5, "fund": 5.0e6, "fund5": 2.0e7,
    "hot": False, "hotName": "", "kwHits": [], "turnover": 8.0, "A": None,
    "snap": None, "final": None, "revHit": False, "revName": "", "pos": 0.2,
}
a = bs.analyze(bars, cand, CFG, "bj")
assert a["patterns"].get("firstBoardRight") == 1, (
    "firstBoardRight 未命中: patterns=%s" % a["patterns"])
assert not any("10日内有涨停" in r or "近涨停" in r for r in a["risks"]), a["risks"]
assert not any("首板失败" in r for r in a["risks"]), a["risks"]
assert a["riskCodes"], a["riskCodes"]
print("firstBoardRight OK: 命中且无旧 warn；score=%s risks=%s" % (a["score"], a["risks"]))

# 涨停后破位（跌破涨停价）→ 首板失败风险保留，且不命中 firstBoardRight
bars2 = mk_bars(10.0, 70, 0, 30.0, 2, -6.0, 150.0)
c2 = dict(cand)
a2 = bs.analyze(bars2, c2, CFG, "bj")
assert any("首板失败" in r for r in a2["risks"]), a2["risks"]
assert not a2["patterns"].get("firstBoardRight"), a2["patterns"]
print("首板失败 OK: 破位风险保留，firstBoardRight 不命中")

# 评分封顶：五主轴总分不超 100 且不重复爆表（构造多因子同命中场景）
bars3 = mk_bars(10.0, 70, 0, 30.0, 3, 5.0, 350.0)
c3 = dict(cand)
a3 = bs.analyze(bars3, c3, CFG, "bj")
assert 0 <= a3["score"] <= 100, a3["score"]
print("评分主轴 OK: score=%s（0-100 封顶）" % a3["score"])
print("ALL TESTS PASSED")
