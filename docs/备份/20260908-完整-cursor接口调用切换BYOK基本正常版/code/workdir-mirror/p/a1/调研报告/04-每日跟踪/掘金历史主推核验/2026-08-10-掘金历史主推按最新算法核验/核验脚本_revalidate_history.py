# -*- coding: utf-8 -*-
"""掘金历史主推核验（只读调研，不改任何产品代码）：
按最新算法（bj_screener.run_scan 同款 analyze/bearish_check/评分）重新体检历史主推，
数据统一取自本地 18011 /api/kline（与产品同链路，含同花顺兜底），截至 2026-08-10 收盘。
"""
import asyncio, json, io, os, re, sys, time, urllib.parse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, r"E:\AI24X\ai24x-website\ai24x01\p\a1\api\server")

import httpx
from app import bj_screener as bs
from app.scoring import score_candles
from app.signals import candles_from_tencent_like_pack

ARCHIVE_DIR = r"E:\AI24X\ai24x-website\ai24x01\p\a1\api\server\data\bj_archive"
KLINE_API = "http://127.0.0.1:18011/api/kline"
ASOF = "2026-08-10"

def load_archives():
    out = []
    for fn in sorted(os.listdir(ARCHIVE_DIR)):
        if not re.match(r"^\d{4}-\d{2}-\d{2}", fn) or not fn.endswith(".json"):
            continue
        try:
            j = json.load(open(os.path.join(ARCHIVE_DIR, fn), encoding="utf-8-sig"))
        except Exception as e:
            print("SKIP(unreadable):", fn, e)
            continue
        picks = j.get("picks") or []
        if isinstance(picks, dict):
            items = []
            for mk, mv in picks.items():
                items.extend(mv if isinstance(mv, list) else [])
        else:
            items = picks
        market_code = str(j.get("market_code") or (j.get("market") if isinstance(j.get("market"), str) else "bj") or "bj").lower()
        for it in items:
            if not isinstance(it, dict):
                continue
            code = str(it.get("code") or "")
            if not re.fullmatch(r"\d{6}", code):
                continue
            out.append({
                "file": fn,
                "date": str(j.get("date") or ""),
                "asof": str(j.get("asof") or ""),
                "market": market_code,
                "code": code,
                "name": str(it.get("name") or ""),
                "price": bs._num(it.get("price")),
                "lastDate": str(it.get("lastDate") or ""),
                "tier": str(it.get("tier") or ""),
                "pickRole": str(it.get("pickRole") or it.get("pick_role") or ""),
                "score": bs._num(it.get("score")),
                "pos": bs._num(it.get("pos")),
                "chg5": bs._num(it.get("chg5")),
                "chg10": bs._num(it.get("chg10")),
                "chg20": bs._num(it.get("chg20")),
                "chg60": bs._num(it.get("chg60")),
                "turnover": bs._num(it.get("turnover")),
                "mcap": bs._num(it.get("mcap")),
                "floatMcap": bs._num(it.get("floatMcap")),
                "pe": bs._num(it.get("pe")),
                "pb": bs._num(it.get("pb")),
                "fundIn": bs._num(it.get("fundIn")),
                "ind": str(it.get("ind") or ""),
                "hot": bool(it.get("hot")),
                "hotName": str(it.get("hotName") or ""),
                "levels": it.get("levels") or {},
                "patterns": it.get("patterns") or {},
                "risks": it.get("risks") or [],
                "risk_free": bool(it.get("risk_free")),
            })
    return out

def unique_picks(entries):
    by_code = {}
    for e in entries:
        c = e["code"]
        if c not in by_code:
            e2 = dict(e)
            e2["appearances"] = 1
            by_code[c] = e2
        else:
            by_code[c]["appearances"] += 1
            # 记录最后一次出现（更新 tier/score/pos）
            by_code[c].update({k: e[k] for k in ("tier", "pickRole", "score", "pos", "chg5", "chg10", "chg20", "chg60", "price", "lastDate")})
            if e.get("risk_free"):
                by_code[c]["risk_free"] = True
    return list(by_code.values())

def tx_symbol(code):
    if code.startswith(("92", "89")) or code.startswith(("43", "83", "87", "88")):
        return "bj" + code
    if code.startswith("6"):
        return "sh" + code
    return "sz" + code

async def fetch_funds(cl, codes):
    """东财 ulist 一次请求拿全部代码 今日/5日 主力净流入(元)。"""
    secids = ",".join(em_secid(c) for c in codes)
    out = {}
    try:
        r = await cl.get("https://push2delay.eastmoney.com/api/qt/ulist.np/get", params={
            "secids": secids, "fields": "f12,f14,f2,f3,f6,f8,f9,f10,f20,f21,f23,f62,f164",
            "fltt": 2, "invt": 2, "np": 1})
        j = r.json()
        for d in ((j.get("data") or {}).get("diff") or []):
            code = str(d.get("f12") or "")
            if code:
                out[code] = {"fund": bs._num(d.get("f62")), "fund5": bs._num(d.get("f164"))}
    except Exception as e:
        print("funds EXC", type(e).__name__, str(e)[:100])
    return out

def em_secid(code):
    if code.startswith(("92", "89")) or code.startswith(("43", "83", "87", "88")):
        return "0." + code
    if code.startswith("6"):
        return "1." + code
    return "0." + code

def build_cfg(market):
    cfg = dict(bs.DEFAULT_CFG)
    if market == "all":
        cfg["mcapMin"] = float(cfg.get("mcapMinAll") or 15.0)
        cfg["mcapMax"] = float(cfg.get("mcapMaxAll") or 200.0)
        cfg["amountMin"] = float(cfg.get("amountMinAll") or 8000.0)
        cfg["posMax"] = 35.0
        cfg["max5d"] = 25.0
        cfg["max10d"] = 40.0
        cfg["max20d"] = 40.0
        cfg["max60d"] = 60.0
        cfg["scoreMin"] = 44.0
    return cfg

def fine_filter_check(a, cand, cfg):
    p = a.get("patterns") or {}
    sv = float(a.get("score") or 0)
    sm = float(cfg.get("scoreMin") or 50)
    if p.get("surgeStart") or p.get("pullback") or p.get("ztPullback"):
        must_start = sv >= sm - 4
    elif p.get("baseUp") or p.get("tightBurst"):
        must_start = sv >= sm + 2
    else:
        must_start = sv >= sm + 12 and (bool(p.get("leaderOk")) or bool(a.get("ma_bull3")) or a.get("volHealth") == 1)
    turn = bs._num(cand.get("turnover"))
    checks = {
        "pos": a.get("pos", 99) <= float(cfg["posMax"]) / 100,
        "chg5": a.get("chg5", 999) <= float(cfg["max5d"]),
        "chg10": a.get("chg10", 999) <= float(cfg["max10d"]),
        "chg20": a.get("chg20", 999) <= float(cfg["max20d"]),
        "chg60": a.get("chg60", 999) <= float(cfg["max60d"]),
        "turn": float(cfg["turnMin"]) <= turn <= float(cfg["turnMax"]),
        "volShrink": not a.get("volShrink"),
        "newHighWeak": not a.get("newHighWeak"),
        "atHighWeak": not a.get("atHighWeak"),
        "amp20": not (a.get("amp20") and float(a.get("amp20") or 0) < 3),
        "must_start": must_start,
    }
    fails = []
    if a.get("pos", 99) > float(cfg["posMax"]) / 100:
        fails.append("位置%.0f%%>上限%.0f%%" % (a.get("pos", 0) * 100, cfg["posMax"]))
    if a.get("chg5", 999) > float(cfg["max5d"]):
        fails.append("5日%.1f%%>%.0f%%" % (a.get("chg5", 0), cfg["max5d"]))
    if a.get("chg10", 999) > float(cfg["max10d"]):
        fails.append("10日%.1f%%>%.0f%%" % (a.get("chg10", 0), cfg["max10d"]))
    if a.get("chg20", 999) > float(cfg["max20d"]):
        fails.append("20日%.1f%%>%.0f%%" % (a.get("chg20", 0), cfg["max20d"]))
    if a.get("chg60", 999) > float(cfg["max60d"]):
        fails.append("60日%.1f%%>%.0f%%" % (a.get("chg60", 0), cfg["max60d"]))
    if not (float(cfg["turnMin"]) <= turn <= float(cfg["turnMax"])):
        fails.append("换手%.1f%%超区间[%.0f,%.0f]" % (turn, cfg["turnMin"], cfg["turnMax"]))
    if a.get("volShrink"):
        fails.append("持续缩量")
    if a.get("newHighWeak"):
        fails.append("无量新高")
    if a.get("atHighWeak"):
        fails.append("贴前高缩量")
    if a.get("amp20") and float(a.get("amp20") or 0) < 3:
        fails.append("20日振幅过窄")
    if not must_start:
        fails.append("启动形态不达标(评分%.0f<门槛%.0f)" % (sv, sm))
    return all(checks.values()), fails

async def fetch_kline(cl, code):
    sid = em_secid(code)
    url = KLINE_API + "?" + urllib.parse.urlencode({"secid": sid, "count": 130})
    try:
        r = await cl.get(url, timeout=40.0)
        j = r.json()
    except Exception as e:
        return None, "api_exc:" + type(e).__name__, None
    if int(j.get("code") or 0) != 0:
        return None, str(j.get("msg") or "code!=0"), None
    data = j.get("data") or {}
    pack = next(iter(data.values()), None)
    rows = ((pack or {}).get("qfqday") or (pack or {}).get("day") or [])
    src = (j.get("_meta") or {}).get("source") or ""
    return rows, "", src

async def main():
    entries = load_archives()
    picks = unique_picks(entries)
    print("历史主推去重:", len(picks), "只 | 归档条目:", len(entries))
    codes = [p["code"] for p in picks]
    async with httpx.AsyncClient(timeout=15.0, headers={"User-Agent": "Mozilla/5.0"}) as cl:
        # 腾讯实时行情（1 次请求，拿今日 OHLC/换手/市值/PE）
        q = ",".join(tx_symbol(c) for c in codes)
        r = await cl.get("https://qt.gtimg.cn/q=" + q)
        txt = r.content.decode("gbk", errors="replace")
        funds = await fetch_funds(cl, codes)
        quote = {}
        for line in txt.strip().split(";"):
            if "~" not in line:
                continue
            f = line.split("~")
            if len(f) < 50:
                continue
            code = f[2].strip()
            try:
                quote[code] = {
                    "name": f[1], "close": float(f[3]), "prev": float(f[4]),
                    "open": float(f[5]), "high": float(f[33]), "low": float(f[34]),
                    "vol": float(f[36] or f[6]), "amount": float(f[37]) * 1e4,
                    "turn": float(f[38]), "pe": float(f[39]), "pb": float(f[46]),
                    "floatMcap": float(f[44]) * 1e8, "mcap": float(f[45]) * 1e8,
                    "volRatio": float(f[49]) if f[49] else 0.0,
                    "pct": float(f[32]) if f[32] else 0.0,
                }
            except Exception:
                pass
        results = []
        for p in picks:
            code = p["code"]
            cfg = build_cfg(p["market"])
            rows, err, src = await fetch_kline(cl, code)
            qd = quote.get(code)
            cand = {
                "code": code, "name": p["name"], "price": (qd or {}).get("close", p["price"]),
                "pct": (qd or {}).get("pct", 0.0),
                "amount": (qd or {}).get("amount", p.get("amount", 0.0)),
                "mcap": (qd or {}).get("mcap", p.get("mcap", 0.0)),
                "floatMcap": (qd or {}).get("floatMcap", p.get("floatMcap", 0.0)),
                "turnover": (qd or {}).get("turn", p.get("turnover", 0.0)),
                "pe": (qd or {}).get("pe", p.get("pe", 0.0)),
                "pb": (qd or {}).get("pb", p.get("pb", 0.0)),
                "volRatio": (qd or {}).get("volRatio", 0.0),
                "fund": (funds.get(code) or {}).get("fund", 0.0),
                "fundIn": (funds.get(code) or {}).get("fund", 0.0),
                "fund5": (funds.get(code) or {}).get("fund5", 0.0),
                "ind": p["ind"], "indCnt": 0, "hot": p["hot"], "hotName": p["hotName"], "kwHits": [],
            }
            res = {
                "code": code, "name": p["name"], "market": p["market"],
                "appearances": p["appearances"],
                "first_file": p["file"], "first_date": p["date"], "first_asof": p["asof"],
                "first_price": p["price"], "first_tier": p["tier"], "first_pickRole": p["pickRole"],
                "first_score": p["score"], "first_pos": p["pos"],
                "last_tier": p["tier"], "last_score": p["score"], "last_pos": p["pos"],
                "ind": p["ind"], "hotName": p["hotName"],
                "quote": qd,
                "kline_src": src, "kline_error": err, "kline_rows": (len(rows) if rows else 0),
                "last_kline_date": (rows[-1][0] if rows else None),
                "fund_today": (funds.get(code) or {}).get("fund", 0.0),
                "fund5": (funds.get(code) or {}).get("fund5", 0.0),
            }
            if rows and len(rows) >= 61:
                a = bs.analyze(rows, cand, cfg, p["market"])
                bearish = bs.bearish_check(cand, a)
                candles = candles_from_tencent_like_pack({"day": rows}, "day")
                snap = score_candles(candles, name=p["name"])
                pass_fine, fails = fine_filter_check(a, cand, cfg)
                close = float(rows[-1][2])
                stop = bs._num((p.get("levels") or {}).get("stop"))
                ret = (close / p["price"] - 1) * 100 if p["price"] and p["price"] > 0 else None
                hard_bs = [it.get("text") for it in (bearish.get("items") or []) if it.get("level") == "hard"]
                if stop and close < stop:
                    verdict = "已破位·跌破止损"
                    verdict_reason = "收盘%.2f<止损%.2f" % (close, stop)
                elif hard_bs:
                    verdict = "利空硬伤·已出局"
                    verdict_reason = "; ".join(hard_bs)
                elif pass_fine:
                    verdict = "仍达标(今日算法)"
                    verdict_reason = "零风险" if not snap.get("risks") else ("警示:" + "、".join(snap.get("risks")[:3]))
                else:
                    verdict = "已出局(今日算法)"
                    verdict_reason = "；".join(fails[:4])
                res.update({
                    "today_close": close,
                    "today_pct": cand["pct"],
                    "today_score": a.get("score"),
                    "today_snap_score": snap.get("score"),
                    "today_pos": round(float(a.get("pos") or 0), 4),
                    "chg5": round(float(a.get("chg5") or 0), 1),
                    "chg10": round(float(a.get("chg10") or 0), 1),
                    "chg20": round(float(a.get("chg20") or 0), 1),
                    "chg60": round(float(a.get("chg60") or 0), 1),
                    "patterns": a.get("patterns") or {},
                    "risks": a.get("risks") or [],
                    "snap_risks": snap.get("risks") or [],
                    "ma_bull3": a.get("ma_bull3"), "volHealth": a.get("volHealth"),
                    "bearish_level": bearish.get("level"),
                    "bearish_items": bearish.get("items") or [],
                    "stop": stop,
                    "levels_now": a.get("levels") or {},
                    "ret_from_pick": round(ret, 1) if ret is not None else None,
                    "pass_fine": pass_fine,
                    "fails": fails,
                    "verdict": verdict,
                    "verdict_reason": verdict_reason,
                })
            else:
                res["verdict"] = "无法核验"
                res["verdict_reason"] = err or ("K线不足%d根" % (len(rows) if rows else 0))
            results.append(res)
            print("%s %s(%s) %s | close=%s ret=%s%% pos=%s score=%s|snap=%s | %s" % (
                res["verdict"][:12], p["name"], code, p["market"], res.get("today_close"),
                res.get("ret_from_pick"), res.get("today_pos"), res.get("today_score"),
                res.get("today_snap_score"), res.get("verdict_reason", "")[:60]))
    out = {"asof": ASOF, "generated": time.strftime("%Y-%m-%d %H:%M:%S"), "results": results}
    out_path = r"E:\AI24X\ai24x-website\ai24x01\p\a1\api\server\data\revalidate_history_20260810.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("SAVED:", out_path)

asyncio.run(main())
