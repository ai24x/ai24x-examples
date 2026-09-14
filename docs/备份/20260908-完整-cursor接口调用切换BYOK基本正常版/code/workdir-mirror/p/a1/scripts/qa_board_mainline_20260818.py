# -*- coding: utf-8 -*-
"""2026-08-18 板块排名与主线判定优化 回放验收单测（P0-1/P0-2 + P1-1~P1-5）。

覆盖：
  1. P0-1 煤炭案例回放（2 涨停 + 今日 f62>0 → 命中条件 b 仍升主线）；构造「1 涨停+资金弱」→ 入观察；
  2. P0-2/P1-1 reverse_mainline 桶名归一化（煤炭开采/焦煤/煤化工 → 单桶煤炭）+ 命中率/形态加权排序；
  3. P1-2 A _macd_reds_from_report("20260818") >= 3 只，数据源标注「复盘样本」；
  4. P1-3 pb_view 复盘样本兜底（含 潞安环能/至纯科技 基础过滤 + 复盘样本补齐）；
  5. P1-4 _attach_ml_why（煤炭 key 位 ml_src=new + ml_why 含「新晋主线」）；
  6. P1-5 _board_rank_funds kc 代表股按市场过滤（30/688）。
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "api", "server"))

from app import bj_screener as bs
from app import daily_report as dr

_A1 = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
_ARCH = os.path.join(_A1, "调研报告", "04-每日跟踪", "板块主攻研判", "20260818")


def load_arch(name):
    with open(os.path.join(_ARCH, name), encoding="utf-8") as f:
        return json.load(f)


# ---------------- 1. P0-1 新晋主线资金/量能二次确认 ----------------
sc = load_arch("sector_score.json")
plates = load_arch("plate_data.json")
# 合并掘金侧真实资金（08-18 复盘后掘金对主线板块做了 ulist 真实资金回填：
# 煤炭 今日 f62=+0.95亿 / 5日 f164=+2.8亿），保证「煤炭案例回放」资金数据齐全。
hs_arch0 = json.load(open(os.path.join(_A1, "api", "server", "data", "bj_archive", "2026-08-18-hs.json"), encoding="utf-8"))
plates = dict(plates)
for _k in ("em_em_industry_today", "em_em_industry_5d"):
    plates[_k] = list(plates.get(_k) or [])
for _b in (hs_arch0.get("board_rank") or []):
    _bn = str(_b.get("name") or "")
    if _bn == "煤炭":
        plates["em_em_industry_today"].append({"name": "煤炭行业", "main_today": _b.get("f62"), "main_5d": _b.get("f164")})
        plates["em_em_industry_5d"].append({"name": "煤炭行业", "main_today": _b.get("f62"), "main_5d": _b.get("f164")})
prev_mainlines = ["AI服务器算力", "通信光模块CPO"]
ml, obs, av = dr.pick_main_lines(sc, prev_mainlines=prev_mainlines, plates=plates)
print("[P0-1] 20260818 回放 主线:", ml)
print("[P0-1] 20260818 回放 观察:", obs)
assert "煤炭" in ml, f"煤炭应仍升主线（2涨停+f62>0 命中条件 b），实际主线={ml}"
assert "半导体" not in ml or len(ml) <= 3, f"主线上限 3 条，实际={ml}"

# 构造「1 涨停 + 资金弱」：top5 高分、1 涨停、今日 f62 小、5日 f164 小 → 应入观察
weak_sc = {
    "测试板块": [
        {"code": "600000", "name": "A", "score": 70, "up_pct": 2.0, "zt": True, "surge": False,
         "tags": ["MACD翻红·第2天", "位置30%"], "risks": [], "red_days": 2},
        {"code": "600001", "name": "B", "score": 66, "up_pct": 1.0, "zt": False, "surge": False,
         "tags": ["MACD翻红·第2天", "位置30%"], "risks": [], "red_days": 2},
        {"code": "600002", "name": "C", "score": 62, "up_pct": 0.5, "zt": False, "surge": False,
         "tags": ["位置30%"], "risks": [], "red_days": 0},
        {"code": "600003", "name": "D", "score": 60, "up_pct": 0.0, "zt": False, "surge": False,
         "tags": ["位置30%"], "risks": [], "red_days": 0},
        {"code": "600004", "name": "E", "score": 58, "up_pct": -0.5, "zt": False, "surge": False,
         "tags": ["位置30%"], "risks": [], "red_days": 0},
        {"code": "600005", "name": "F", "score": 55, "up_pct": -1.0, "zt": False, "surge": False,
         "tags": ["位置30%"], "risks": [], "red_days": 0},
    ],
}
weak_plates = {
    "em_em_industry_5d": [{"name": "测试板块", "main_5d": 2.8e8}],
    "em_em_industry_today": [{"name": "测试板块", "main_today": 0.95e8}],
    "em_em_concept_5d": [], "em_em_concept_today": [],
}
ml2, obs2, av2 = dr.pick_main_lines(weak_sc, prev_mainlines=None, plates=weak_plates)
print("[P0-1] 构造「1涨停+资金弱」→ 主线:", ml2, "观察:", obs2)
assert "测试板块" not in ml2, "1 涨停+资金弱 不应升主线"
assert "测试板块" in obs2, "1 涨停+资金弱 应入观察"

# 资金缺失（None）不得当通过：top5 高 + 2 涨停但 plates=None → 应降级观察
ml3, obs3, av3 = dr.pick_main_lines(weak_sc, prev_mainlines=None, plates=None)
print("[P0-1] 资金缺失（plates=None）→ 主线:", ml3, "观察:", obs3)
assert "测试板块" not in ml3, "资金缺失不得当通过"
assert "测试板块" in obs3, "资金缺失应入观察"

# ---------------- 2. P0-2/P1-1 北证桶名归一化 + 命中率/形态加权 ----------------
def mk_cand(code, name, concepts, ind, pattern):
    return {
        "code": code, "name": name, "concepts": concepts or [], "ind": ind,
        "amount": 1.0e8, "A": {"patterns": {pattern: True}},
    }

cands = [
    mk_cand("920001", "煤A", ["煤炭开采"], "煤炭开采", "surgeStart"),
    mk_cand("920002", "煤B", ["焦煤"], "焦煤", "pullback2"),
    mk_cand("920003", "煤C", ["煤炭"], "煤炭", "ztPullback"),
    mk_cand("920004", "煤D", ["煤化工"], "煤化工", "firstBoardRight"),
    mk_cand("920005", "煤E", ["煤炭开采"], "煤炭开采", "smallYang"),
    mk_cand("920006", "煤F", ["焦煤"], "焦煤", "pullback"),
    mk_cand("920007", "半A", ["半导体"], "半导体", "surgeStart"),
    mk_cand("920008", "半B", ["半导体"], "半导体", "surgeStart"),
]
rev = bs.reverse_mainline(cands, {})
names = [x["name"] for x in rev]
print("[P0-2/P1-1] reverse_mainline 桶:", names)
assert "煤炭" in names, f"煤炭桶应存在，实际={names}"
assert not any(n in ("煤炭开采", "焦煤", "煤化工") for n in names), f"不应拆桶，实际={names}"
coal = next(x for x in rev if x["name"] == "煤炭")
print("[P0-2/P1-1] 煤炭桶: count=%s wcount=%s total_cands=%s hit_rate=%s rank_score=%s" % (
    coal["count"], coal["wcount"], coal["total_cands"], coal["hit_rate"], coal["rank_score"]))
assert coal["count"] == 6, f"煤炭桶异动家数应=6（6只全部命中形态），实际={coal['count']}"
assert coal["total_cands"] == 6, "煤炭桶候选池应=6"
assert coal["hit_rate"] == 1.0, "煤炭桶命中率应=1.0"
sem = next(x for x in rev if x["name"] == "半导体")
assert sem["count"] == 2 and sem["hit_rate"] == 1.0
# 排序：rank_score 相同的 hot 优先、再 amount
assert rev[0]["name"] == "煤炭" or rev[0]["name"] == "半导体", f"排序异常: {names}"

# 命中率区分度：大桶高容量但低命中率 vs 小桶高命中率
cands2 = [
    mk_cand("930001", "大A", ["测试大板块"], "测试大板块", "smallYang"),
    mk_cand("930002", "大B", ["测试大板块"], "测试大板块", None),
    mk_cand("930003", "大C", ["测试大板块"], "测试大板块", None),
    mk_cand("930004", "大D", ["测试大板块"], "测试大板块", None),
    mk_cand("930005", "小A", ["测试小板块"], "测试小板块", "surgeStart"),
    mk_cand("930006", "小B", ["测试小板块"], "测试小板块", "surgeStart"),
]
rev2 = bs.reverse_mainline(cands2, {})
for x in rev2:
    print("[P1-1] 命中率排序:", x["name"], "count=%s total=%s hit=%s rank=%s" % (
        x["count"], x["total_cands"], x["hit_rate"], x["rank_score"]))
assert str(rev2[0]["name"]).startswith("测试小"), "高命中率小板块应排前（1.0×1.5 vs 0.6×1.125）"

# ---------------- 3. P1-2 A MACD 首红复盘样本 ----------------
mr = bs._macd_reds_from_report("20260818", limit=12)
print("[P1-2A] _macd_reds_from_report 20260818:", [(x["name"], x["red_days"], x["pos"], x["src"]) for x in mr])
assert len(mr) >= 3, f"MACD 首红复盘样本应>=3 只，实际={len(mr)}"
assert all(x.get("src") == "复盘样本" for x in mr), "数据源标注应为「复盘样本」"

# ---------------- 4. P1-3 回踩企稳数据源拓宽 ----------------
hs_arch = json.load(open(os.path.join(_A1, "api", "server", "data", "bj_archive", "2026-08-18-hs.json"), encoding="utf-8"))
pb_out = bs.pb_view(hs_arch)
pb_names = [str(x.get("name") or "") for x in (pb_out.get("picks") or []) + (pb_out.get("runners") or [])]
print("[P1-3] pb_view picks+runners:", pb_names)
assert "潞安环能" in pb_names, "回踩企稳应含 潞安环能"
assert "至纯科技" in pb_names, "回踩企稳应含 至纯科技"
assert len(pb_names) > 2, f"回踩企稳应>2 只，实际={len(pb_names)}"

# ---------------- 5. P1-4 主线判定小字透传 ----------------
_info = dr.mainline_judgment(sc, plates)
rank = [
    {"name": "煤炭", "tier": "key", "ml_name": "煤炭"},
    {"name": "AI服务器算力", "tier": "king", "ml_name": "AI服务器算力"},
    {"name": "普通板块", "tier": "backup"},
]
rank2 = bs._attach_ml_why(rank, ["AI服务器算力", "通信光模块CPO", "煤炭"], _info)
coal_b = next(x for x in rank2 if x["name"] == "煤炭")
king_b = next(x for x in rank2 if x["name"] == "AI服务器算力")
print("[P1-4] 煤炭 key 位:", coal_b.get("ml_src"), coal_b.get("ml_why"))
print("[P1-4] AI服务器算力 king 位:", king_b.get("ml_src"), king_b.get("ml_why"))
assert coal_b.get("ml_src") == "new", "煤炭今日新晋 → ml_src=new"
assert "新晋主线" in (coal_b.get("ml_why") or ""), f"ml_why 应含「新晋主线」: {coal_b.get('ml_why')}"
assert king_b.get("ml_src") == "cont", "AI服务器算力昨日延续 → ml_src=cont"
assert "延续主线" in (king_b.get("ml_why") or ""), f"ml_why 应含「延续主线」: {king_b.get('ml_why')}"
_bkp = next(x for x in rank2 if x["name"] == "普通板块")
assert "ml_why" not in _bkp, "backup 不应透传 ml_why"

# ---------------- 6. P1-5 科创代表股按市场过滤 ----------------
boards = [
    {
        "name": "煤炭", "secid": "90.BK0437", "f62": 1e8, "f164": 2.8e8, "p5": -0.76,
        "leaders": [
            {"code": "601088", "name": "中国神华"},
            {"code": "688187", "name": "时代电气"},
            {"code": "300750", "name": "宁德时代"},
        ],
    }
]
br_kc = bs._board_rank_funds(boards, keep_backup=3, mainline_names=["煤炭"], market="kc")
print("[P1-5] kc 榜 leaders:", [(x.get("code"), x.get("name")) for x in (br_kc[0].get("leaders") or [])])
assert all(str(x.get("code") or "").startswith(("30", "688")) for x in (br_kc[0].get("leaders") or [])), "kc 榜 leaders 应只留 30/688"

boards_nokc = [
    {
        "name": "煤炭", "secid": "90.BK0437", "f62": 1e8, "f164": 2.8e8, "p5": -0.76,
        "leaders": [{"code": "601088", "name": "中国神华"}, {"code": "601225", "name": "陕西煤业"}],
    }
]
br_kc2 = bs._board_rank_funds(boards_nokc, keep_backup=3, mainline_names=["煤炭"], market="kc")
print("[P1-5] kc 榜无科创成分 leaders:", br_kc2[0].get("leaders"))
assert br_kc2[0].get("leaders") == [], "kc 榜无 30/688 成分时应置空"

print("\nALL QA PASS")
