# -*- coding: utf-8 -*-
"""本地数据源通道质量测试 - 单轮"""
import asyncio, csv, json, os, sys, time, re
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
SRV = os.path.join(HERE, "..", "api", "server")
for p in (SRV, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

import httpx
from app import providers
from app.providers import (
    TX_FQ, secid_to_tencent_symbol, secid_to_sina_symbol, _strip_js_wrapper,
    fetch_ths_fuyao_kline, fetch_tushare_kline, fetch_sina_kline,
    fetch_em_plate_kline, fetch_em_stock_kline, fetch_em_index_kline,
    _tencent_payload_has_rows, _payload_missing_today,
    _PLATE_CACHE, _PLATE_RECON_CACHE, _KLINE_CACHE,
)

_KLINE_CACHE.clear()
_PLATE_CACHE.clear()
_PLATE_RECON_CACHE.clear()

TARGETS = [
    ("1.600519", "GZMT"),
    ("0.000001", "PAYH"),
    ("0.300750", "NDSD"),
    ("1.688111", "JSBG"),
    ("1.920932", "KDZK"),
    ("1.000001", "SHZHI"),
    ("0.399001", "SZCHENG"),
    ("0.899050", "BJ50"),
    ("90.BK1340", "PCB_BK"),
    ("90.BK1250", "MT_BK"),
]
THS_PLATES = [
    ("884092.TI", "PCB_THS"),
    ("881105.TI", "MT_THS"),
    ("885959.TI", "PCB_GN_THS"),
]

OUT_DIR = os.path.join(HERE, "..", "api", "server", "data", "channels_test")
os.makedirs(OUT_DIR, exist_ok=True)
ROWS = []

def rows_of(payload, secid):
    try:
        d = (payload or {}).get("data") or {}
        sym = secid_to_tencent_symbol(str(secid).strip())
        for k in (sym, sym.upper()):
            v = d.get(k)
            if isinstance(v, dict):
                for kk in ("qfqday", "day"):
                    if v.get(kk):
                        return v[kk]
        for v in d.values():
            if isinstance(v, dict):
                for kk in ("qfqday", "day"):
                    if v.get(kk):
                        return v[kk]
    except Exception:
        pass
    return []

def last_date(rows):
    try:
        return str(rows[-1][0]) if rows else ""
    except Exception:
        return ""

def add(round_name, src, secid, name, payload, status, ms, rows):
    missing = ""
    try:
        if payload is not None and _tencent_payload_has_rows(payload):
            missing = "1" if _payload_missing_today(payload) else "0"
    except Exception:
        missing = ""
    ROWS.append({
        "round": round_name, "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": src, "secid": secid, "name": name,
        "status": status, "ms": round(ms, 1), "rows": int(len(rows or [])),
        "last_date": last_date(rows), "missing_today": missing,
    })

async def test_tencent(round_name, secid, name):
    sid = str(secid).strip()
    if re.fullmatch(r"0\.89\d{4}", sid) or re.fullmatch(r"90\.BK\d+", sid, re.I):
        add(round_name, "tencent", secid, name, None, "n/a", 0.0, [])
        return
    sym = secid_to_tencent_symbol(sid)
    params = {"param": f"{sym},day,2000-01-01,2099-12-31,130,qfq", "_var": "1"}
    t0 = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(TX_FQ, params=params)
            r.raise_for_status()
            j = json.loads(_strip_js_wrapper(r.text))
        ms = (time.perf_counter() - t0) * 1000
        rows = rows_of(j, sid)
        if rows:
            add(round_name, "tencent", secid, name, j, "ok", ms, rows)
        else:
            add(round_name, "tencent", secid, name, j, "empty", ms, [])
    except Exception as e:
        add(round_name, "tencent", secid, name, None, f"err:{type(e).__name__}", (time.perf_counter() - t0) * 1000, [])

async def test_ths(round_name, secid, name):
    t0 = time.perf_counter()
    try:
        fb = await fetch_ths_fuyao_kline(secid, "day", count=130, timeout=10.0)
        ms = (time.perf_counter() - t0) * 1000
        if fb is None:
            add(round_name, "ths", secid, name, None, "none", ms, [])
        elif _tencent_payload_has_rows(fb):
            add(round_name, "ths", secid, name, fb, "ok", ms, rows_of(fb, secid))
        else:
            add(round_name, "ths", secid, name, fb, f"code:{fb.get('code')}", ms, [])
    except Exception as e:
        add(round_name, "ths", secid, name, None, f"err:{type(e).__name__}", (time.perf_counter() - t0) * 1000, [])

async def test_ths_plate(round_name, thscode, name):
    try:
        from app.ths_fuyao import fuyao_config
    except Exception:
        add(round_name, "ths_plate", thscode, name, None, "err:import", 0.0, [])
        return
    cfg = fuyao_config()
    key = str(cfg.get("api_key") or "")
    if not key:
        add(round_name, "ths_plate", thscode, name, None, "no_key", 0.0, [])
        return
    base = str(cfg.get("base_url") or "").rstrip("/") or "https://fuyao.aicubes.cn"
    now_ms = int(time.time() * 1000)
    params = {"thscode": thscode, "interval": "1d", "start": now_ms - 200 * 86400 * 1000, "end": now_ms, "adjust": "none"}
    headers = {"X-api-key": key, "User-Agent": "ai24x/1.0"}
    t0 = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
            r = await client.get(base + "/api/a-share-index/prices/historical", params=params)
            data = r.json()
        ms = (time.perf_counter() - t0) * 1000
        items = (data.get("data") or {}).get("item") or []
        if data.get("code") == 0 and items:
            payload = {"code": 0, "data": {thscode: {"qfqday": [[datetime.fromtimestamp(int(it.get("date_ms") or 0) / 1000).strftime("%Y-%m-%d"), it["open_price"], it["close_price"], it["high_price"], it["low_price"], str(int(it.get("volume") or 0) / 100)] for it in items]}}}
            add(round_name, "ths_plate", thscode, name, payload, "ok", ms, rows_of(payload, thscode))
        else:
            add(round_name, "ths_plate", thscode, name, data, f"code:{data.get('code')}", ms, [])
    except Exception as e:
        add(round_name, "ths_plate", thscode, name, None, f"err:{type(e).__name__}", (time.perf_counter() - t0) * 1000, [])

async def test_tushare(round_name, secid, name):
    t0 = time.perf_counter()
    try:
        fb = await fetch_tushare_kline(secid, "day", count=130, timeout=15.0)
        ms = (time.perf_counter() - t0) * 1000
        if _tencent_payload_has_rows(fb):
            add(round_name, "tushare", secid, name, fb, "ok", ms, rows_of(fb, secid))
        else:
            add(round_name, "tushare", secid, name, fb, f"code:{fb.get('code')}", ms, [])
    except Exception as e:
        add(round_name, "tushare", secid, name, None, f"err:{type(e).__name__}", (time.perf_counter() - t0) * 1000, [])

async def test_tushare_ths(round_name, thscode, name):
    sid = "ths:" + thscode.split(".")[0]
    await test_tushare(round_name, sid, name + "_ts")

async def test_sina(round_name, secid, name):
    sid = str(secid).strip()
    if re.fullmatch(r"90\.BK\d+", sid, re.I):
        add(round_name, "sina", secid, name, None, "n/a", 0.0, [])
        return
    t0 = time.perf_counter()
    try:
        fb = await fetch_sina_kline(secid, "day", count=130, timeout=10.0)
        ms = (time.perf_counter() - t0) * 1000
        if _tencent_payload_has_rows(fb):
            add(round_name, "sina", secid, name, fb, "ok", ms, rows_of(fb, secid))
        else:
            add(round_name, "sina", secid, name, fb, f"code:{fb.get('code')}", ms, [])
    except Exception as e:
        add(round_name, "sina", secid, name, None, f"err:{type(e).__name__}", (time.perf_counter() - t0) * 1000, [])

async def test_em(round_name, secid, name):
    sid = str(secid).strip()
    t0 = time.perf_counter()
    try:
        if re.fullmatch(r"90\.BK\d+", sid, re.I):
            fb = await fetch_em_plate_kline(sid, "day", count=130, timeout=15.0)
        elif sid in ("1.000001", "1.000300", "1.000688", "1.000852"):
            fb = await fetch_em_index_kline(sid, "day", count=130, timeout=15.0)
        elif re.fullmatch(r"[01]\.\d{6}", sid):
            fb = await fetch_em_stock_kline(sid, "day", count=130, timeout=15.0)
        else:
            add(round_name, "eastmoney", secid, name, None, "n/a", 0.0, [])
            return
        ms = (time.perf_counter() - t0) * 1000
        if _tencent_payload_has_rows(fb):
            add(round_name, "eastmoney", secid, name, fb, "ok", ms, rows_of(fb, sid))
        else:
            msg = str(fb.get("msg") or "")[:80]
            add(round_name, "eastmoney", secid, name, fb, f"code:{fb.get('code')}:{msg}", ms, [])
    except Exception as e:
        add(round_name, "eastmoney", secid, name, None, f"err:{type(e).__name__}", (time.perf_counter() - t0) * 1000, [])

async def run_round(round_name):
    print(f"=== round {round_name} start ===")
    tasks = []
    for secid, name in TARGETS:
        tasks.append(test_tencent(round_name, secid, name))
        tasks.append(test_ths(round_name, secid, name))
        tasks.append(test_tushare(round_name, secid, name))
        tasks.append(test_sina(round_name, secid, name))
        tasks.append(test_em(round_name, secid, name))
    for ths_code, name in THS_PLATES:
        tasks.append(test_ths_plate(round_name, ths_code, name))
        tasks.append(test_tushare_ths(round_name, ths_code, name))
    await asyncio.gather(*tasks)
    csv_path = os.path.join(OUT_DIR, f"channels_{round_name}.csv")
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(ROWS[0].keys()) if ROWS else ["round"])
        w.writeheader()
        for r in ROWS:
            w.writerow(r)
    print(f"saved {csv_path} rows={len(ROWS)}")
    agg = {}
    for r in ROWS:
        a = agg.setdefault(r["source"], {"n": 0, "ok": 0, "ms": [], "rows": [], "missing": 0, "fails": []})
        a["n"] += 1
        if r["status"] == "ok":
            a["ok"] += 1
            a["ms"].append(r["ms"])
            a["rows"].append(r["rows"])
            if r["missing_today"] == "1":
                a["missing"] += 1
        else:
            a["fails"].append(f"{r['secid']}:{r['status']}")
    print(f"{'source':<12}{'ok/n':<8}{'ok%':<7}{'avg_ms':<9}{'p50':<8}{'avg_rows':<9}{'missing':<8}detail")
    for k, a in agg.items():
        oks = sorted(a["ms"])
        p50 = oks[len(oks)//2] if oks else 0
        avg = round(sum(a["ms"])/len(a["ms"]), 1) if a["ms"] else 0
        avg_rows = round(sum(a["rows"])/len(a["rows"]), 1) if a["rows"] else 0
        okr = round(100*a["ok"]/max(1,a["n"]), 1)
        fails = ",".join(a["fails"][:4])
        print(f"{k:<12}{str(a['ok'])+'/'+str(a['n']):<8}{okr:<8}{avg:<9}{p50:<8}{avg_rows:<9}{a['missing']:<8}{fails}")

if __name__ == "__main__":
    round_name = sys.argv[1] if len(sys.argv) > 1 else "r1"
    asyncio.run(run_round(round_name))
    print("DONE")
