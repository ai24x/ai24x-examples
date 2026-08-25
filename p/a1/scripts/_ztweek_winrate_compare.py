# -*- coding: utf-8 -*-
"""近一周有涨停 vs 无涨停：历史主推标的 T+1/T+3/T+5 表现对比。
数据源：bj_scan_history.json（所有市场主推） + 本地 18011 /api/kline（不扣配额）。
"""
import asyncio, json, os, re, time, sys
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
HIST = os.path.join(BASE, "..", "api", "server", "data", "bj_scan_history.json")
API = "http://127.0.0.1:18011"

ZT_PATTERNS = ("firstWeek", "firstBoardRight", "ztPullback", "pullback2")

def secid_for(code: str) -> str:
    c = str(code or "").strip()
    if c.startswith(("60", "68", "90")):
        return "1." + c
    if c.startswith(("00", "30", "20")):
        return "0." + c
    if c.startswith(("43", "83", "87", "88", "92")):
        return "1." + c  # 北证走 1. 前缀
    return "1." + c

def collect_jobs():
    jobs, seen = [], set()
    def add(code, asof, p):
        code = str(code or "").strip()
        asof = str(asof or "").strip()
        if not code or not asof or (code, asof) in seen:
            return
        seen.add((code, asof))
        jobs.append((code, asof, p))
    # 1) 历史快照（bj_scan_history.json）
    hist = json.load(open(HIST, encoding="utf-8"))
    for key, payload in hist.items():
        d = str(key).split(":")[-1]
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d) or d < "2026-07-20":
            continue
        for p in (payload.get("picks") or []):
            add(p.get("code"), p.get("lastDate") or p.get("asof"), p)
    # 2) 归档目录（含同日多版本）
    arch = os.path.join(BASE, "..", "api", "server", "data", "bj_archive")
    if os.path.isdir(arch):
        for fn in sorted(os.listdir(arch)):
            if not fn.endswith(".json") or not re.match(r"^\d{4}-\d{2}-\d{2}", fn):
                continue
            if fn in ("archive_index.json", "winrate_cache.json"):
                continue
            try:
                j = json.load(open(os.path.join(arch, fn), encoding="utf-8"))
            except Exception:
                continue
            d = fn[:10]
            if d < "2026-07-20":
                continue
            for p in (j.get("picks") or []):
                add(p.get("code"), p.get("lastDate") or p.get("asof"), p)
    return jobs

async def main():
    jobs = collect_jobs()
    print("jobs:", len(jobs))
    # 登录
    async with __import__("httpx").AsyncClient(timeout=60) as cli:
        lr = await cli.post(API + "/api/auth/login",
                            json={"phone": "18968701913", "password": "iamlei"})
        token = lr.json().get("token", "")
        hdr = {"Authorization": "Bearer " + token}
        rows_map = {}
        fails = {}
        async def get_kline(code):
            try:
                r = await cli.get(API + "/api/kline",
                                  params={"secid": secid_for(code), "period": "day", "count": 400},
                                  headers=hdr)
                j = r.json()
                d0 = (j.get("data") or {})
                for _k, _v in d0.items():
                    if isinstance(_v, dict) and _v.get("qfqday"):
                        return _v["qfqday"]
                fails[code] = str(j)[:120]
            except Exception as e:
                fails[code] = repr(e)
            return None
        t0 = time.time()
        for i, (code, asof, p) in enumerate(jobs):
            rows_map[(code, asof)] = await get_kline(code)
            await asyncio.sleep(2.1)
            if (i + 1) % 10 == 0:
                print("  fetched", i + 1, "/", len(jobs), "elapsed", int(time.time() - t0), "s")
    if fails:
        print("kline fails:", json.dumps(fails, ensure_ascii=False)[:600])
    # 统计
    groups = defaultdict(list)
    n_norows = n_noidx = n_skip = n_done = 0
    for code, asof, p in jobs:
        rows = rows_map.get((code, asof))
        if not rows:
            n_norows += 1
            continue
        dates = [str(r[0]) for r in rows]
        idx = None
        for i, dd in enumerate(dates):
            if dd == asof:
                idx = i
                break
        if idx is None:
            for i in range(len(dates) - 1, -1, -1):
                if dates[i] <= asof:
                    idx = i
                    break
        if idx is None:
            n_noidx += 1
            continue
        if idx >= len(rows) - 1:
            n_skip += 1
            continue
        n_done += 1
        entry = float(p.get("price") or rows[idx][2]) or 1.0
        pp = p.get("patterns") or {}
        zt = bool(any(pp.get(k) for k in ZT_PATTERNS) or p.get("limitQuality"))
        sub = ""
        for k in ZT_PATTERNS:
            if pp.get(k):
                sub = k
                break
        if not sub and p.get("limitQuality"):
            sub = "limit_only"
        def fwd(nn):
            j = idx + nn
            return (float(rows[j][2]) / entry - 1) * 100 if j < len(rows) else None
        f1, f3, f5 = fwd(1), fwd(3), fwd(5)
        hi5 = max(float(r[3]) for r in rows[idx + 1: min(idx + 6, len(rows))])
        stop = 0.0
        m = re.search(r"\d+(?:\.\d+)?", str((p.get("strategy") or {}).get("stop") or ""))
        if m:
            stop = float(m.group())
        stop_hit = (stop > 0 and min(float(r[4]) for r in rows[idx + 1: min(idx + 11, len(rows))]) <= stop)
        rec = {"f1": f1, "f3": f3, "f5": f5, "hi5": hi5, "stop": stop_hit, "final": p.get("final")}
        groups["ztWeek" if zt else "no-zt"].append(rec)
        if sub:
            groups["pat:" + sub].append(rec)
    def stats(items):
        n = len(items)
        if not n:
            return None
        def mean(k):
            vals = [x[k] for x in items if x.get(k) is not None]
            return round(sum(vals) / len(vals), 2) if vals else None
        return {
            "n": n,
            "hit5_rate": round(sum(1 for x in items if x["hi5"] >= 5.0) / n * 100, 1),
            "pos5_rate": round(sum(1 for x in items if (x["f5"] or -999) >= 0) / n * 100, 1),
            "mean_f1": mean("f1"), "mean_f3": mean("f3"), "mean_f5": mean("f5"),
            "stop_rate": round(sum(1 for x in items if x["stop"]) / n * 100, 1),
        }
    print()
    print("debug: no_rows=%d no_idx=%d tracking=%d done=%d" % (n_norows, n_noidx, n_skip, n_done))
    for g in ("ztWeek", "no-zt"):
        print(g, "=>", stats(groups[g]))
    print()
    for k in sorted(groups):
        if k.startswith("pat:"):
            print(k, "=>", stats(groups[k]))

asyncio.run(main())
