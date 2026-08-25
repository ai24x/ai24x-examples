# -*- coding: utf-8 -*-
"""单测：analyze() 对近一周有涨停的标的应标 ztWeek；无涨停不标。"""
import asyncio, json, os, sys

API = "http://127.0.0.1:18011"

def secid_for(code):
    c = str(code)
    return ("1." if c.startswith(("60", "68", "90", "43", "83", "87", "88", "92")) else "0.") + c

async def login_once() -> str:
    import httpx
    for _try in range(5):
        async with httpx.AsyncClient(timeout=30) as cli:
            lr = await cli.post(API + "/api/auth/login", json={"phone": "18968701913", "password": "iamlei"})
            if lr.status_code == 200:
                return lr.json().get("token", "")
            if lr.status_code == 429:
                await asyncio.sleep(8)
                continue
            raise RuntimeError("login failed: %s %s" % (lr.status_code, lr.text[:200]))
    return ""


async def get_bars(code, token):
    import httpx
    async with httpx.AsyncClient(timeout=60) as cli:
        r = await cli.get(API + "/api/kline", params={"secid": secid_for(code), "period": "day", "count": 400},
                          headers={"Authorization": "Bearer " + token})
        j = r.json()
        for _k, _v in (j.get("data") or {}).items():
            if isinstance(_v, dict) and _v.get("qfqday"):
                return _v["qfqday"]
    return None

def main():
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "api", "server"))
    from app.bj_screener import analyze, DEFAULT_CFG
    cases = [
        # (code, asof, 预期是否有 ztWeek)
        ("601699", "2026-08-11", True),   # 潞安环能：08-06 涨停，08-11 距涨停 3 个交易日 → 近一周有涨停
        ("601699", "2026-08-18", False),  # 潞安环能：距涨停 8 个交易日 > 5 → 不标 ztWeek（ztPullback 仍可标）
        ("000823", "2026-08-18", False),  # 超声电子：replay pick，无涨停形态
        ("601015", "2026-08-21", True),   # 陕西黑猫：08-21 归档 firstBoardRight + lq=normal
    ]
    bars_by_code = {}
    token = asyncio.run(login_once())
    if not token:
        print("LOGIN FAILED (rate limited); abort")
        return 1
    for code, asof, _exp in cases:
        bars = asyncio.run(get_bars(code, token))
        if bars:
            bars_by_code[(code, asof)] = [b for b in bars if str(b[0]) <= asof]
    for code, asof, exp in cases:
        bars = bars_by_code.get((code, asof))
        if not bars:
            print(code, "NO BARS")
            continue
        cand = {
            "code": code, "name": code, "price": float(bars[-1][2]), "mcap": 80e8,
            "amount": 3e8, "turnover": 5.0, "pe": 12.0, "pb": 1.5, "volRatio": 1.1,
            "fund": 1e7, "fundIn": 1e7, "ind": "煤炭", "indCnt": 10,
            "hot": False, "hotName": "", "kwHits": [], "concepts": [],
        }
        out = analyze(bars, cand, dict(DEFAULT_CFG), market="hs")
        pp = out.get("patterns") or {}
        got = bool(pp.get("ztWeek"))
        mark = "OK " if got == exp else "FAIL"
        print("%s %s asof=%s  ztWeek=%s(expect %s)  keys=%s" % (
            mark, code, asof, got, exp,
            sorted(k for k in pp if pp[k])))
    return 0

raise SystemExit(main())
