# -*- coding: utf-8 -*-
"""markets(18012) 与 a1 共享引擎算法一致性实证对比（只读，不写库）。"""
import importlib, json, sys, types
from pathlib import Path
import urllib.request

API = "http://127.0.0.1:18012"
COUNT = 500  # app.html 默认请求根数

def get(url):
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))

# 1) markets 接口原始结果
sig_resp = get(f"{API}/api/signals?symbol=AAPL&period=day&count={COUNT}")
kl_resp = get(f"{API}/api/kline?symbol=AAPL&period=day&count={COUNT}")
assert sig_resp["code"] == 0 and kl_resp["code"] == 0, (sig_resp.get("msg"), kl_resp.get("msg"))
api_data = sig_resp["data"]

# 2) 用 markets /api/kline 返回的同一批 candles 直接喂共享引擎
rows = kl_resp["data"]["candles"]  # [date, open, close, high, low, volume]

root = Path(__file__).resolve().parents[3]  # ai24x01（脚本位于 p/markets/scripts/）
a1_app = root / "p" / "a1" / "api" / "server" / "app"
assert (a1_app / "signals.py").exists()
pkg = types.ModuleType("a1_engine")
pkg.__path__ = [str(a1_app)]
sys.modules["a1_engine"] = pkg
signals = importlib.import_module("a1_engine.signals")
scoring = importlib.import_module("a1_engine.scoring")

candles = signals.candles_from_tencent_like_pack({"day": rows}, "day")
engine_sig = signals.build_signals_v3(candles, cache_key="")  # 禁用信号锁定缓存，取纯算法基线
engine_score = scoring.score_candles(candles, name="AAPL")

# 3) 对比 markers / macd
def norm_markers(ms):
    out = []
    for m in ms:
        out.append({
            "time": m.get("time"),
            "text": m.get("text", "").replace("\u200b", "").strip(),
            "position": m.get("position"),
            "shape": m.get("shape"),
        })
    return out

def norm_macd(ms):
    out = []
    for m in ms:
        out.append({"time": m.get("time"), "dif": round(float(m.get("dif", 0)), 6),
                    "dea": round(float(m.get("dea", 0)), 6), "bar": round(float(m.get("bar", 0)), 6),
                    "golden_cross": bool(m.get("golden_cross")), "dead_cross": bool(m.get("dead_cross"))})
    return out

a_mk = norm_markers(api_data.get("markers") or [])
e_mk = norm_markers(engine_sig.get("markers") or [])
a_md = norm_macd(api_data.get("macd") or [])
e_md = norm_macd(engine_sig.get("macd") or [])

print("markers api={} engine={} match={}".format(len(a_mk), len(e_mk), a_mk == e_mk))
print("macd    api={} engine={} match={}".format(len(a_md), len(e_md), a_md == e_md))

if a_mk != e_mk:
    for i in range(max(len(a_mk), len(e_mk))):
        am = a_mk[i] if i < len(a_mk) else None
        em = e_mk[i] if i < len(e_mk) else None
        if am != em:
            print("  first diff marker:", i, am, em)
            break
if a_md != e_md:
    for i in range(max(len(a_md), len(e_md))):
        am = a_md[i] if i < len(a_md) else None
        em = e_md[i] if i < len(e_md) else None
        if am != em:
            print("  first diff macd:", i, am, em)
            break

# 4) 对比 score（markets 走 screener.compute_score 包装，核心 score_candles 应一致）
api_score = api_data.get("score") or {}
es = engine_score or {}
print("score api={} engine={} score_match={} ok={}".format(
    api_score.get("score"), es.get("score"),
    round(float(api_score.get("score") or 0), 1) == round(float(es.get("score") or 0), 1),
    es.get("ok")))
print("engine tags:", es.get("tags"))
print("engine risks:", es.get("risks"))

ok = (a_mk == e_mk) and (a_md == e_md) and round(float(api_score.get("score") or 0), 1) == round(float(es.get("score") or 0), 1)
print("PARITY_OK" if ok else "PARITY_FAIL")
sys.exit(0 if ok else 1)
