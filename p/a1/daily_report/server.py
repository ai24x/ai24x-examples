# -*- coding: utf-8 -*-
"""每日板块主攻研判 · 本地服务（端口 18013，独立于产品代码）。
页面 http://127.0.0.1:18001/daily/ 调本服务。
"""
import os, sys, threading, time, json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import daily_report_core as core

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="AI行情官 每日板块研判服务", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_RUNNING = {"busy": False, "last_start": 0.0, "thread": None}
_LOCK = threading.Lock()

def _start_scan(force: bool):
    with _LOCK:
        if _RUNNING["busy"]:
            raise HTTPException(status_code=409, detail="已有扫描任务进行中")
        _RUNNING["busy"] = True
        _RUNNING["last_start"] = time.time()
    def worker():
        try:
            core.run_daily(force=force)
        except Exception as e:
            core.set_progress(phase="error", pct=0, step="失败: %s" % str(e)[:120], ok=False)
        finally:
            with _LOCK:
                _RUNNING["busy"] = False
    t = threading.Thread(target=worker, daemon=True)
    _RUNNING["thread"] = t
    t.start()

@app.get("/api/report/status")
def status():
    today = core.today()
    report = core.cache_load("report")
    has_today = bool(report and (report.get("today8") == core.today8() or str(report.get("generated_at") or "").startswith(core.today())))
    needs_refresh = bool(report and core.report_stale(report))
    history = core.list_archive()
    return {
        "ok": True,
        "today": today,
        "today8": core.today8(),
        "is_weekend": core.is_weekend(),
        "is_trading_day": core.is_trading_day(),
        "token_ok": core.token_ok(),
        "has_today": has_today,
        "needs_refresh": needs_refresh,
        "asof": (report or {}).get("asof"),
        "generated_at": (report or {}).get("generated_at"),
        "running": bool(_RUNNING["busy"]),
        "progress": core.get_progress(),
        "auto_scan_time": core.cfg().get("auto_scan_time"),
        "auto_scan": bool(core.cfg().get("auto_scan", True)),
        "history": history,
        "service_ok": True,
    }

@app.get("/api/report/progress")
def progress():
    return {"ok": True, "running": bool(_RUNNING["busy"]), "progress": core.get_progress()}

@app.post("/api/report/scan")
def scan(force: int = 0):
    if not force:
        hit = core.cache_load("report")
        if hit and hit.get("today8") == core.today8() and not core.report_stale(hit):
            return {"ok": True, "msg": "今日报告已生成，无需重复扫描（如需重扫请用强制模式）", "cached": True}
    if core.is_weekend() and not force:
        return {"ok": False, "msg": "今天是周末，非交易日，不自动扫描（可 force=1 强制）"}
    if not core.token_ok():
        raise HTTPException(status_code=400, detail="18011 token 无效或已过期，请更新 daily_report/config.json 中的 token")
    _start_scan(bool(force))
    return {"ok": True, "msg": "扫描已启动"}

@app.get("/api/report/today")
def today_report():
    report = core.cache_load("report")
    if not report:
        return {"ok": False, "msg": "今日报告尚未生成"}
    return {"ok": True, "asof": report.get("asof"), "generated_at": report.get("generated_at"),
            "html": report.get("html", ""), "md": report.get("md", "")}

@app.get("/api/report/history")
def history():
    return {"ok": True, "items": core.list_archive()}

@app.get("/api/report/{date8}")
def by_date(date8: str):
    d = core.load_report_by_date(date8)
    if not d:
        raise HTTPException(status_code=404, detail="未找到该日期报告")
    return {"ok": True, **d}

class CfgIn(BaseModel):
    token: str = ""
    auto_scan: bool = True
    auto_scan_time: str = "15:35"

@app.get("/api/report/config")
def get_cfg():
    c = dict(core.cfg())
    c.pop("token", None)
    return {"ok": True, "config": c}

@app.post("/api/report/config")
def set_cfg(body: CfgIn):
    p = core.CFG_PATH
    c = dict(core.cfg())
    if body.token:
        c["token"] = body.token.strip()
    c["auto_scan"] = bool(body.auto_scan)
    if body.auto_scan_time:
        c["auto_scan_time"] = body.auto_scan_time.strip()
    with open(p, "w", encoding="utf-8") as f:
        json.dump(c, f, ensure_ascii=False, indent=2)
    core._CFG = c
    return {"ok": True}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=18013)
