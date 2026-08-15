# -*- coding: utf-8 -*-
"""每日板块主攻研判（已并入 AI行情官 18011 产品后端，VIP 分层）。

- 大盘信号 + 资金面：公开（未登录/免费用户可看）
- 板块技术体检 + 主线锁定：VIP 专属
- 评分/指数信号：内部直算（fetch_tx_kline + score_candles/build_signals_v3），
  不扣 150 次/日查询配额、不 HTTP 自调、不走游客通道
- 鉴权：登录会话（Authorization: Bearer <localStorage.ai24x_a_token>），不再依赖静态 token
- 上游防封：按日缓存 + 每日预算 + 慢速退避 + keep-alive（沿用原独立服务参数，
  K线走腾讯主源，避开东财 push2his 节流通道）
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from . import db
from .auth import get_current_user_id, get_optional_user_id
from .providers import fetch_tx_kline, market_data_status
from .scoring import score_candles, _ma, _slope_ratio, _red_days
from .signals import build_signals_v3, candles_from_tencent_like_pack, _compute_macd_arrays
from .ths_fuyao import build_sentiment as _ths_build_sentiment

router = APIRouter()

# 仓库相对路径（本地/副脑03 通用，03 仅 C 盘无 E 盘）：__file__ = .../p/a1/api/server/app/daily_report.py
_A1_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
BASE_DIR = os.path.join(_A1_ROOT, "daily_report")
CFG_PATH = os.path.join(BASE_DIR, "config.json")
CACHE_ROOT = os.path.join(BASE_DIR, "cache")          # 按日上游数据缓存（沿用原独立服务目录）
ARCHIVE_ROOT = os.path.join(_A1_ROOT, "调研报告", "04-每日跟踪", "板块主攻研判")

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# 每日上游预算（防封，沿用原独立服务参数）
EM_DAILY_BUDGET = 16        # 东财 push2delay 请求/日
THS_DAILY_BUDGET = 2        # 同花顺页面请求/日
KLINE_INTERVAL = 1.6

INDEXES = {
    "上证指数": "1.000001", "深证成指": "0.399001", "创业板指": "0.399006",
    "科创50": "1.000688", "北证50": "0.899050", "沪深300": "1.000300",
    "中证500": "1.000905", "中证1000": "1.000852",
}

SECTORS = {
    "PCB": [("002463","沪电股份"),("002916","深南电路"),("600183","生益科技"),("300476","胜宏科技"),("603228","景旺电子"),("002938","鹏鼎控股")],
    "煤炭": [("601088","中国神华"),("601225","陕西煤业"),("600188","兖矿能源"),("601898","中煤能源"),("601699","潞安环能"),("600546","山煤国际")],
    "有色": [("600111","北方稀土"),("601899","紫金矿业"),("601600","中国铝业"),("000807","云铝股份"),("000933","神火股份"),("603993","洛阳钼业")],
    "通信光模块CPO": [("300308","中际旭创"),("300502","新易盛"),("300394","天孚通信"),("002281","光迅科技"),("600487","亨通光电"),("600522","中天科技")],
    "创新药CXO": [("603259","药明康德"),("300347","泰格医药"),("002821","凯莱英"),("300759","康龙化成"),("300363","博腾股份"),("300558","贝达药业")],
    "半导体": [("688981","中芯国际"),("002371","北方华创"),("603501","韦尔股份"),("603986","兆易创新"),("688008","澜起科技"),("688256","寒武纪")],
    "AI服务器算力": [("000977","浪潮信息"),("603019","中科曙光"),("601138","工业富联"),("000938","紫光股份"),("688158","优刻得"),("603629","利通电子")],
    "证券": [("600030","中信证券"),("300059","东方财富"),("300033","同花顺"),("300803","指南针"),("601688","华泰证券"),("601377","兴业证券")],
    "军工": [("600760","中航沈飞"),("600893","航发动力"),("000768","中航西飞"),("600038","中直股份"),("000738","航发控制"),("300034","钢研高纳")],
    "机器人": [("002747","埃斯顿"),("300124","汇川技术"),("688017","绿的谐波"),("002472","双环传动"),("603728","鸣志电器"),("300024","机器人")],
    "光伏设备": [("300724","捷佳伟创"),("300751","迈为股份"),("300316","晶盛机电"),("688516","奥特维"),("300776","帝尔激光"),("603185","上机数控")],
    "锂电池": [("300750","宁德时代"),("300014","亿纬锂能"),("002074","国轩高科"),("300207","欣旺达"),("002709","天赐材料"),("300769","德方纳米")],
    "汽车整车": [("002594","比亚迪"),("601633","长城汽车"),("000625","长安汽车"),("601127","赛力斯"),("600418","江淮汽车"),("600733","北汽蓝谷")],
    "白酒消费": [("600519","贵州茅台"),("000858","五粮液"),("600809","山西汾酒"),("000568","泸州老窖"),("000596","古井贡酒"),("600702","舍得酒业")],
    "电力": [("600900","长江电力"),("601985","中国核电"),("600886","国投电力"),("600674","川投能源"),("600027","华电国际"),("600011","华能国际")],
    "机械设备": [("600031","三一重工"),("000157","中联重科"),("000425","徐工机械"),("601100","恒立液压"),("000338","潍柴动力"),("002008","大族激光")],
}

# 板块 -> 东财资金榜板块名别名（主线资金确认用；not_in 排除同名歧义，如"电力设备"是光伏/风电设备而非电力运营）
SECTOR_BOARD_ALIASES = {
    "PCB": ["印制电路板", "PCB"],
    "煤炭": ["煤炭开采", "焦煤", "动力煤", "煤炭"],
    "有色": ["工业金属", "小金属", "有色金属", "能源金属", "贵金属", "稀土"],
    "通信光模块CPO": ["通信设备", "通信网络设备", "光通信", "光模块", "CPO", "通信技术"],
    "创新药CXO": ["创新药", "化学制药", "医疗服务", "生物制品", "CXO", "医药生物"],
    "半导体": ["半导体", "芯片", "集成电路", "数字芯片", "存储芯片", "电子化学品"],
    "AI服务器算力": ["算力", "AI服务器", "数据中心", "东数西算", "云计算", "液冷", "IDC"],
    "证券": ["证券", "券商"],
    "军工": ["航天航空", "船舶制造", "军工", "大飞机", "航母"],
    "机器人": ["机器人", "减速器", "工业母机", "人形机器人"],
    "光伏设备": ["光伏设备", "光伏", "钙钛矿", "HJT电池"],
    "锂电池": ["锂电池", "锂电", "固态电池", "动力电池", "电池"],
    "汽车整车": ["汽车整车", "乘用车", "新能源车", "智能汽车"],
    "白酒消费": ["白酒", "酿酒", "食品饮料", "啤酒", "乳业"],
    "电力": ["电力行业", "绿色电力", "绿电", "核电", "火电", "水电", "风电"],
    "机械设备": ["机械设备", "工程机械", "通用设备", "专用设备", "其他专用设备"],
}
SECTOR_BOARD_NOTIN = {
    "电力": ["设备"],            # 排除"电力设备"（光伏/风电设备属新能源，非电力运营）
    "汽车整车": ["零部件", "芯片"],  # 排除"汽车零部件""汽车芯片"（属电子/机械）
}

_CFG = None
def cfg():
    global _CFG
    if _CFG is None:
        _CFG = {"auto_scan_time": "15:03", "auto_scan": True}
        try:
            if os.path.exists(CFG_PATH):
                _CFG.update(json.load(open(CFG_PATH, encoding="utf-8")))
        except Exception:
            pass
        _CFG.pop("token", None)
    return _CFG

def today8(): return datetime.now().strftime("%Y%m%d")
def today(): return datetime.now().strftime("%Y-%m-%d")
HOLIDAYS = set(str(x).strip() for x in [
    "2026-01-01","2026-02-16","2026-02-17","2026-02-18","2026-02-19","2026-02-20",
    "2026-04-06","2026-05-01","2026-06-19","2026-09-25","2026-10-01","2026-10-02",
    "2026-10-05","2026-10-06","2026-10-07","2026-10-08",
] if str(x).strip())
def is_weekend():
    return datetime.now().weekday() >= 5
def now_hhmm():
    return datetime.now().strftime("%H:%M")
def _after_close():
    return now_hhmm() >= str(cfg().get("auto_scan_time") or "15:03")

def _today_close_epoch() -> float:
    """今日收盘时刻（auto_scan_time）的 epoch；解析失败返回 0。"""
    try:
        t = str(cfg().get("auto_scan_time") or "15:03").strip()
        hh, mm = t.split(":")
        return datetime.now().replace(hour=int(hh), minute=int(mm), second=0, microsecond=0).timestamp()
    except Exception:
        return 0.0
def report_stale(report):
    """今日已生成但数据截至日早于今日，且已过收盘时间 → 陈旧，需重扫。"""
    if not report or report.get("today8") != today8():
        return False
    if is_weekend():
        return False
    if _after_close():
        if (report.get("asof") or "") != today():
            return True
        ga = str(report.get("generated_at") or "")
        try:
            gt = datetime.strptime(ga, "%Y-%m-%d %H:%M:%S").timestamp()
        except Exception:
            gt = 0.0
        return gt < _today_close_epoch()
    return False
def data_cache_stale(idx):
    """当日数据缓存是否已过期（收盘后要求上证 last_date == 今天）。"""
    if not idx:
        return True
    last = ((idx.get("indexes") or {}).get("上证指数") or {}).get("last_date") or ""
    if not last:
        return True
    if is_weekend():
        return False
    if _after_close():
        if last != today():
            return True
        ts = float(idx.get("_ts") or 0)
        return ts < _today_close_epoch()
    return False
def is_trading_day():
    return (not is_weekend()) and (today() not in HOLIDAYS)

# ---------------- 进度 ----------------
_PROGRESS = {"phase": "idle", "pct": 0, "step": "", "done": 0, "total": 0, "started_at": 0, "finished": None, "ok": False}
_LOCK = threading.Lock()
def set_progress(**kw):
    with _LOCK:
        _PROGRESS.update(kw)
def get_progress(): return dict(_PROGRESS)

# ---------------- 扫描任务锁 ----------------
_RUNNING = {"busy": False, "last_start": 0.0, "thread": None, "last_done": 0.0, "last_ok": None, "last_error": ""}

def _start_scan(force: bool, is_vip: bool):
    with _LOCK:
        if _RUNNING["busy"]:
            raise HTTPException(status_code=409, detail="已有扫描任务进行中")
        _RUNNING["busy"] = True
        _RUNNING["last_start"] = time.time()
    def worker():
        try:
            run_daily(force=force, is_vip=is_vip)
        except Exception as e:
            set_progress(phase="error", pct=0, step="失败: %s" % str(e)[:120], ok=False)
        finally:
            with _LOCK:
                _RUNNING["busy"] = False
                _RUNNING["last_done"] = time.time()
                _RUNNING["last_ok"] = bool(_PROGRESS.get("ok"))
                _RUNNING["last_error"] = "" if _PROGRESS.get("ok") else str(_PROGRESS.get("step") or "")[:160]
    t = threading.Thread(target=worker, daemon=True)
    _RUNNING["thread"] = t
    t.start()


def _busy() -> bool:
    """扫描忙判断；线程卡死超时（>30 分钟）自动复位，避免前端进度条永远转。"""
    with _LOCK:
        if _RUNNING["busy"] and time.time() - _RUNNING["last_start"] > 1800:
            _RUNNING["busy"] = False
            _RUNNING["last_error"] = "扫描超时（>30 分钟），已自动复位，请重试"
        return _RUNNING["busy"]


_AUTO_FAIL_COOLDOWN = 600  # 自动生成失败后冷却 10 分钟，避免无限重扫打上游
def _auto_blocked() -> bool:
    with _LOCK:
        if _RUNNING.get("last_ok") is False and _RUNNING.get("last_done"):
            if time.time() - _RUNNING["last_done"] < _AUTO_FAIL_COOLDOWN:
                return True
    return False


# ---------------- 慢速 HTTP（防封核心） ----------------
_EM_COUNT = {"n": 0, "day": ""}
_THS_COUNT = {"n": 0, "day": ""}

def _check_budget(kind):
    d = today8()
    if kind == "em":
        if _EM_COUNT["day"] != d:
            _EM_COUNT["n"] = 0; _EM_COUNT["day"] = d
        if _EM_COUNT["n"] >= EM_DAILY_BUDGET:
            raise RuntimeError("东财上游今日预算已用尽(%d次)，自动停止抓取防封" % EM_DAILY_BUDGET)
    elif kind == "ths":
        if _THS_COUNT["day"] != d:
            _THS_COUNT["n"] = 0; _THS_COUNT["day"] = d
        if _THS_COUNT["n"] >= THS_DAILY_BUDGET:
            raise RuntimeError("同花顺上游今日预算已用尽(%d次)" % THS_DAILY_BUDGET)

def slow_get(url, referer="https://quote.eastmoney.com/", kind="em", tries=3, timeout=20, encoding="utf-8"):
    _check_budget(kind)
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": referer})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
            if kind == "em": _EM_COUNT["n"] += 1
            elif kind == "ths": _THS_COUNT["n"] += 1
            return raw.decode(encoding, "ignore")
        except Exception as e:
            last = e
            time.sleep(4 + i * 4)   # 慢速退避，不连发
    raise RuntimeError("上游请求失败(%s): %s" % (kind, str(last)[:100]))

# ---------------- 本地缓存（按日） ----------------
def cache_path(name):
    return os.path.join(CACHE_ROOT, today8(), name)
def cache_save(name, obj):
    p = cache_path(name); os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
def cache_load(name):
    p = cache_path(name)
    if os.path.exists(p):
        try:
            return json.load(open(p, encoding="utf-8"))
        except Exception:
            return None
    return None

# ---------------- 东财板块资金流 ----------------
EM_FIELDS = "f12,f14,f2,f3,f62,f164,f184,f104,f105"
def em_clist(fs, fid, pz=30):
    url = ("https://push2delay.eastmoney.com/api/qt/clist/get?pn=1&pz=%d&po=1&np=1&fltt=2&invt=2&fid=%s&fs=%s&fields=%s"
           % (pz, fid, urllib.parse.quote(fs), EM_FIELDS))
    t = slow_get(url, kind="em")
    try:
        diff = json.loads(t).get("data", {}).get("diff", []) or []
    except Exception:
        return []
    return [{"name": d.get("f14"), "code": d.get("f12"), "pct": d.get("f3"), "main_today": d.get("f62"),
             "main_5d": d.get("f164"), "main_ratio": d.get("f184"), "up": d.get("f104"), "down": d.get("f105")} for d in diff]

def fetch_plates():
    out = {}
    for key, fs, fid in [
        ("em_em_industry_today", "m:90+t:2+f:!50", "f62"),
        ("em_em_industry_5d", "m:90+t:2+f:!50", "f164"),
        ("em_em_concept_today", "m:90+t:3+f:!50", "f62"),
        ("em_em_concept_5d", "m:90+t:3+f:!50", "f164"),
    ]:
        out[key] = em_clist(fs, fid)
        time.sleep(1.2)
    return out

# ---------------- 同花顺行业涨幅 ----------------
def parse_ths_table(html):
    rows = []
    body = html[html.find("<tbody"):] if "<tbody" in html else html
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", body, re.S):
        tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if len(tds) < 10:
            continue
        m = re.search(r"/code/(\d+)/\"[^>]*>([^<]+)</a>", tds[1])
        if not m:
            continue
        code, name = m.group(1), m.group(2).strip()
        pct = re.sub(r"<[^>]+>", "", tds[2]).strip()
        up = re.sub(r"<[^>]+>", "", tds[6]).strip()
        down = re.sub(r"<[^>]+>", "", tds[7]).strip()
        lm = re.search(r"stockpage\.10jqka\.com\.cn/\d+/\"[^>]*>([^<]+)</a>", tds[9])
        leader = lm.group(1).strip() if lm else ""
        try: pctf = float(pct)
        except Exception: pctf = None
        rows.append({"code": code, "name": name, "pct": pctf, "up": up, "down": down, "leader": leader})
    return rows

def fetch_ths_industry():
    h = slow_get("http://q.10jqka.com.cn/thshy/", referer="http://q.10jqka.com.cn/", kind="ths", encoding="gbk")
    return parse_ths_table(h)

# ---------------- 指数信号（内部直算，不扣配额） ----------------
def _provider_profile(is_vip):
    md = market_data_status()
    base_pri = str((md.get("paid") or {}).get("priority") or "").strip().lower()
    if not base_pri:
        base_pri = "tencent,eastmoney,sina,paid"
    vip_only = bool((md.get("paid") or {}).get("vip_only"))
    allow_paid = bool(is_vip or not vip_only)
    priority_override = base_pri if allow_paid else ",".join(
        [x for x in base_pri.split(",") if x.strip() and x.strip() != "paid"]
    )
    # 用独立 variant 命名空间，避免与用户实时查询的 in-flight/cache key 撞车
    return "daily", priority_override, allow_paid

async def _tx_kline(secid, count=120, variant="daily", priority_override=None, allow_paid=True, timeout=10.0):
    payload = await fetch_tx_kline(
        secid, "day", count=count, timeout=timeout,
        variant=variant, priority_override=priority_override, allow_paid=allow_paid,
    )
    if not isinstance(payload, dict) or int(payload.get("code") or 0) != 0:
        raise RuntimeError("kline failed(%s): %s" % (secid, str((payload or {}).get("msg") or "")[:80]))
    data = payload.get("data")
    if not isinstance(data, dict) or not data:
        raise RuntimeError("kline empty(%s)" % secid)
    pack = next(iter(data.values()))
    candles = candles_from_tencent_like_pack(pack, period="day")
    if len(candles) < 60:
        raise RuntimeError("kline insufficient history(%s)" % secid)
    return candles

async def _fetch_index_signals(is_vip):
    variant, priority_override, allow_paid = _provider_profile(is_vip)
    sh_candles = await _tx_kline("1.000001", 120, variant, priority_override, allow_paid)
    closes = [float(c.close) for c in sh_candles]
    dif, dea, bar, golden, dead = _compute_macd_arrays(closes)
    ma5 = _ma(closes, 5); ma10 = _ma(closes, 10); ma20 = _ma(closes, 20)
    rd = _red_days(bar)
    ma_bull = ma5[-1] > ma10[-1] > ma20[-1]
    ma20_up = _slope_ratio(ma20, 5) > 0.001
    above_ma20 = closes[-1] > ma20[-1]
    weak = (not above_ma20) and (not ma20_up)
    pts = 3.0 if rd >= 1 else 0.0
    if ma_bull: pts += 3.0
    if above_ma20 and ma20_up: pts += 2.0
    if weak: pts -= 3.0
    pts = round(max(-3.0, min(8.0, pts)), 1)
    env_tags = ["大盘MACD翻红·第%d天" % rd if rd >= 1 else "大盘MACD绿柱"]
    env_tags.append("大盘均线多头" if ma_bull else ("大盘站上MA20" if above_ma20 else "大盘跌破MA20"))
    env = {"pts": pts, "red_days": rd, "above_ma20": above_ma20, "weak": weak, "tags": env_tags}
    result = {}
    for name, secid in INDEXES.items():
        try:
            candles = await _tx_kline(secid, 120, variant, priority_override, allow_paid)
            sc = score_candles(candles, name=name)
            base = float(sc.get("score") or 0.0)
            rec = {"secid": secid, "score": round(max(0.0, min(100.0, base + pts)), 1), "pts": pts,
                   "above_ma20": env["above_ma20"], "weak": env["weak"], "tags": env["tags"],
                   "last_close": candles[-1].close, "last_date": candles[-1].time}
            sig = build_signals_v3(candles, cache_key="%s_day" % secid)
            mk = (sig or {}).get("markers") or []
            by_day = {}
            for m in mk:
                txt = str(m.get("text") or "").strip().replace("\u200b", "").strip()
                if not txt: continue
                by_day.setdefault(str(m.get("time") or ""), []).append(txt)
            days = sorted(by_day.keys())
            ARR = "\u2197\u2198\u2192\u2190\u2191\u2193"
            labs = []
            for k in days[-6:]:
                s2 = "".join(ch for ch in "\u3000".join(by_day[k]) if ch not in ARR).strip()
                if s2: labs.append(s2)
            rec["recent_labels"] = labs[-6:]
            macd = (sig or {}).get("macd") or []
            if macd: rec["macd_last"] = macd[-1]
            result[name] = rec
            await asyncio.sleep(0.5)
        except Exception as e:
            result[name] = {"secid": secid, "error": str(e)[:80]}
    return {"env": env, "indexes": result}

# ---------------- 板块成分股评分（内部直算，不扣配额） ----------------
def secid_of(code): return ("1." if code[0] in "56" else "0.") + code


def _board_confirm_flags(candles, code):
    """从日K轻量判定板块情绪：10日内涨停 / 15日内底部放量异动（供主线锁定确认，零额外上游成本）。"""
    try:
        closes = [float(c.close) for c in candles]
        highs = [float(c.high) for c in candles]
        lows = [float(c.low) for c in candles]
        vols = [float(c.vol or 0.0) for c in candles]
        n = len(closes)
        if n < 25:
            return False, False
        c6 = str(code).zfill(6)
        th = 19.5 if c6.startswith(("30", "68")) else (29.5 if c6.startswith(("8", "43", "92")) else 9.5)
        zt = False
        for i in range(max(1, n - 10), n):
            if closes[i - 1] > 0 and (closes[i] / closes[i - 1] - 1) * 100 >= th - 0.5:
                zt = True
                break
        lo60 = min(lows[max(0, n - 60):])
        hi60 = max(highs[max(0, n - 60):])
        surge = False
        for i in range(max(1, n - 15), n):
            _win = vols[max(0, i - 20):i]
            v20 = sum(_win) / max(1, len(_win))
            if v20 > 0 and vols[i] >= 1.8 * v20 and closes[i - 1] > 0:
                _pct = (closes[i] / closes[i - 1] - 1) * 100
                _pos = (closes[i] - lo60) / (hi60 - lo60) if hi60 > lo60 else 1.0
                if _pct >= 4 and _pos <= 0.5:
                    surge = True
                    break
        return zt, surge
    except Exception:
        return False, False


def _sector_fund_flow(sec, plates):
    """板块资金共振：从东财行业/概念资金榜（5日/今日主力净流入）匹配本板块。

    返回 (5日主力净流入, 今日主力净流入)，单位元；无匹配返回 (None, None)。
    仅用于主线资金确认，不新增任何上游请求。
    """
    if not plates:
        return None, None
    aliases = SECTOR_BOARD_ALIASES.get(sec) or [sec]
    not_in = SECTOR_BOARD_NOTIN.get(sec) or []
    best5 = best_t = None
    for r in (plates.get("em_em_industry_5d") or []) + (plates.get("em_em_concept_5d") or []):
        nm = str(r.get("name") or "")
        if any(a and a in nm for a in aliases) and not any(x and x in nm for x in not_in):
            try:
                v = float(r.get("main_5d") or 0)
                if best5 is None or v > best5:
                    best5 = v
            except Exception:
                pass
    for r in (plates.get("em_em_industry_today") or []) + (plates.get("em_em_concept_today") or []):
        nm = str(r.get("name") or "")
        if any(a and a in nm for a in aliases) and not any(x and x in nm for x in not_in):
            try:
                v = float(r.get("main_today") or 0)
                if best_t is None or v > best_t:
                    best_t = v
            except Exception:
                pass
    return best5, best_t


async def _fetch_sector_scores(is_vip):
    variant, priority_override, allow_paid = _provider_profile(is_vip)
    out = {}
    n = 0
    total = sum(len(v) for v in SECTORS.values())
    for sec, items in SECTORS.items():
        out[sec] = []
        for code, name in items:
            try:
                candles = await _tx_kline(secid_of(code), 120, variant, priority_override, allow_paid, timeout=8.0)
                res = score_candles(candles, name=name)
                _zt, _surge = _board_confirm_flags(candles, code)
                out[sec].append({
                    "code": code, "name": name, "score": res.get("score"), "tags": res.get("tags") or [],
                    "risks": res.get("risks") or [], "up_pct": res.get("up_pct"), "vol_ratio": res.get("vol_ratio"),
                    "red_days": res.get("red_days"), "latest_time": res.get("latest_time"),
                    "zt": _zt, "surge": _surge,
                })
            except Exception as e:
                out[sec].append({"code": code, "name": name, "error": str(e)[:80]})
            n += 1
            set_progress(pct=10 + int(n / total * 55), step="AI行情官体检 %d/%d（内部直算，不扣查次）" % (n, total))
            await asyncio.sleep(0.6)
    return out

async def _fetch_internal(is_vip, idx_needed=True, sc_needed=True):
    result = {}
    if idx_needed:
        try:
            set_progress(step="内部直算：8 指数信号（腾讯K线，不扣查次）")
            result["indexes"] = await _fetch_index_signals(is_vip)
        except Exception:
            result["indexes"] = None
    if sc_needed:
        try:
            set_progress(step="内部直算：%d 只成分股评分（腾讯K线，不扣查次）" % sum(len(v) for v in SECTORS.values()))
            result["sector_scores"] = await _fetch_sector_scores(is_vip)
        except Exception:
            result["sector_scores"] = None
    return result

# ---------------- breadth（涨跌家数 + 涨停/跌停池 + 两市主力净流入，共 4 次低频请求） ----------------
def _breadth_date():
    """最近一个交易日（YYYYMMDD），供涨跌分布/涨停池做日期参数。"""
    if is_trading_day():
        return today8()
    d = datetime.now() - timedelta(days=1)
    for _ in range(10):
        ds = d.strftime("%Y%m%d")
        if d.weekday() < 5 and ds not in HOLIDAYS:
            return ds
        d -= timedelta(days=1)
    return today8()


def fetch_breadth():
    """沪深A股市场宽度：
    - 涨跌家数/平盘：中证全指(000985) f104/f105/f106
    - 主力净流入合计：上证指数 + 深证成指 f62 之和
    - 涨停/跌停：东财涨停池/跌停池（全市场，含 10/20/30cm）
    - 涨幅>=5% / 跌幅<=-5%：涨跌分布 fenbu 桶统计
    全部低频（每日预算内），任一失败降级不影响整份报告。
    """
    up = down = flat = total = 0
    main_net = 0.0
    try:
        secids = urllib.parse.quote("1.000985,1.000001,0.399001")
        u1 = ("https://push2.eastmoney.com/api/qt/ulist.np/get?fltt=2&invt=2"
              "&fields=f12,f14,f104,f105,f106,f62&secids=%s" % secids)
        rows = json.loads(slow_get(u1, kind="em", tries=2)).get("data", {}).get("diff", []) or []
        by = {str(r.get("f12")): r for r in rows}
        zz = by.get("000985") or {}
        up = int(zz.get("f104") or 0)
        down = int(zz.get("f105") or 0)
        flat = int(zz.get("f106") or 0)
        total = up + down + flat
        main_net = float((by.get("000001") or {}).get("f62") or 0) + float((by.get("399001") or {}).get("f62") or 0)
    except Exception:
        pass
    limit_up = limit_down = big_up = big_down = 0
    bdate = _breadth_date()
    ut = "7eea3edcaed734bea9cbfc24409ed989"
    try:
        tz = slow_get("https://push2ex.eastmoney.com/getTopicZTPool?ut=%s&dpt=wz.ztzt&Pageindex=0&pagesize=500&sort=fbt:asc&date=%s" % (ut, bdate), kind="em", tries=2)
        limit_up = len(json.loads(tz).get("data", {}).get("pool", []) or [])
    except Exception:
        pass
    try:
        td = slow_get("https://push2ex.eastmoney.com/getTopicDTPool?ut=%s&dpt=wz.ztzt&Pageindex=0&pagesize=500&sort=fbt:asc&date=%s" % (ut, bdate), kind="em", tries=2)
        limit_down = len(json.loads(td).get("data", {}).get("pool", []) or [])
    except Exception:
        pass
    try:
        t3 = slow_get("https://push2ex.eastmoney.com/getTopicZDFenBu?ut=%s&dpt=wz.ztzt&Pageindex=0&pagesize=500&sort=fbt:asc&date=%s" % (ut, bdate), kind="em", tries=2)
        fenbu = json.loads(t3).get("data", {}).get("fenbu", []) or []
        buckets = {}
        for o in fenbu:
            for k, v in o.items():
                try:
                    buckets[int(k)] = int(v or 0)
                except Exception:
                    pass
        big_up = sum(v for k, v in buckets.items() if k > 0 and k >= 5)
        big_down = sum(v for k, v in buckets.items() if k < 0 and k <= -5)
        if not total:
            total = sum(buckets.values())
            up = sum(v for k, v in buckets.items() if k > 0)
            down = sum(v for k, v in buckets.items() if k < 0)
            flat = buckets.get(0, 0)
    except Exception:
        pass
    return {"total": total, "up": up, "down": down, "flat": flat,
            "limit_up": limit_up, "limit_down": limit_down,
            "big_up": big_up, "big_down": big_down, "main_net": main_net}


# ---------------- 报告生成 ----------------
def yi(v):
    if v is None: return "-"
    return "%.1f" % (float(v) / 1e8)

def _stock_link(code, name):
    return "[%s](%s)" % (name, "/demo.html?secid=%s&code=%s&name=%s" % (secid_of(code), code, urllib.parse.quote(name)))

def sector_stats(sc):
    ok = [x for x in sc if x.get("score") is not None]
    mean = round(sum(float(x["score"]) for x in ok) / len(ok), 1) if ok else None
    top = sorted(ok, key=lambda x: x["score"], reverse=True)[:3]
    names = " / ".join("%s %.1f" % (_stock_link(x["code"], x["name"]), x["score"]) for x in top)
    return mean, names, ok

def pick_main_lines(sector_scores, prev_mainlines=None, plates=None):
    """主线锁定（资金×技术双确认 + 延续约束，防“一天一个想法”也防“一条线霸榜”）：
    - 技术关：成分股评分均值≥62（或板块内有涨停/异动情绪确认时均值≥58）；
    - 资金关：当日平均涨幅≥0，或 5日主力净流入≥15亿 且 今日净流入>0 / 今日净流入≥50亿（资金主攻）；
    - 昨日主线：均值≥62 且回调≤-1.0%，或 均值≥58 且资金仍主攻 → 延续；均值≥55 → 观察，不直接退潮；
    - 新晋主线：技术+资金双确认；每日新晋最多 2 个（有历史主线时），其余先入观察次日确认；
    - 资金强但技术未修复（均值50~62）→ 观察（等修复确认），避免漏掉正在启动的轮动板块。
    """
    prev = {str(x) for x in (prev_mainlines or [])}
    main_lines, observes, avoids = [], [], []
    info = {}
    for sec, sc in sector_scores.items():
        mean, top3, ok = sector_stats(sc)
        if mean is None:
            continue
        ups = [float(x.get("up_pct") or 0) for x in ok]
        avg_up = sum(ups) / len(ups) if ups else 0
        # 情绪确认：板块内有涨停或≥2只放量异动成分 → 均值≥58 即可升主线（捕捉新主线启动）
        n_zt = sum(1 for x in ok if x.get("zt"))
        n_surge = sum(1 for x in ok if x.get("surge"))
        confirmed = n_zt >= 1 or n_surge >= 2
        fund5, fund_t = _sector_fund_flow(sec, plates)
        fund_ok = bool((fund5 is not None and fund5 >= 15e8 and fund_t is not None and fund_t > 0)
                       or (fund_t is not None and fund_t >= 50e8))
        info[sec] = {"mean": mean, "avg_up": avg_up, "fund5": fund5, "fund_t": fund_t,
                     "fund_ok": fund_ok, "confirmed": confirmed}
        if sec in prev:
            # 昨日主线：均值≥62 且回调≤-1.0%（可小幅回踩），或 资金仍主攻（均值≥58 且 资金共振）→ 延续；
            # 回调偏深、资金离场、情绪转弱 → 观察/回避，防止"一条线霸榜"（10日内涨停是滞后证据，不续命）
            if (mean >= 62 and avg_up >= -1.0) or (mean >= 58 and fund_ok):
                main_lines.append(sec)
            elif mean >= 55:
                observes.append(sec)
            else:
                avoids.append(sec)
        else:
            # 新晋：技术+资金双确认，或情绪确认启动
            if (mean >= 62 and avg_up >= 0) or (confirmed and mean >= 58) or (fund_ok and mean >= 62 and avg_up >= -0.5):
                main_lines.append(sec)
            elif mean >= 55 or (fund_ok and mean >= 50):
                observes.append(sec)
            else:
                avoids.append(sec)
    if prev and len(main_lines) > 0:
        # 每日新晋最多 2 个：超出部分先入观察，次日确认再升主线
        new_ones = [s for s in main_lines if s not in prev]
        if len(new_ones) > 2:
            new_sorted = sorted(new_ones, key=lambda s: -float(info[s]["mean"]))
            for s in new_sorted[2:]:
                main_lines.remove(s)
                if s not in observes:
                    observes.append(s)
    # 主次排序：评分均值优先，5日主力净流入次之
    main_lines.sort(key=lambda s: (-float(info[s]["mean"]), -(info[s]["fund5"] or 0)))
    observes.sort(key=lambda s: -float(info[s]["mean"]))
    avoids.sort(key=lambda s: -float(info[s]["mean"]))
    return main_lines, observes[:3], avoids[:3]

def _prev_mainlines():
    """上一归档日的主线（用于连续性对比）。优先读归档 mainlines.json（当日实际口径），旧归档回退按 sector_score 重算。"""
    try:
        arch = sorted([x for x in os.listdir(ARCHIVE_ROOT) if os.path.isdir(os.path.join(ARCHIVE_ROOT, x))], reverse=True)
        for d in arch:
            if d == today8():
                continue
            mj = os.path.join(ARCHIVE_ROOT, d, "mainlines.json")
            if os.path.exists(mj):
                obj = json.load(open(mj, encoding="utf-8"))
                ml = obj.get("mainlines") or []
                if ml:
                    return {"date": d, "mainlines": ml}
            p = os.path.join(ARCHIVE_ROOT, d, "sector_score.json")
            if os.path.exists(p):
                sc = json.load(open(p, encoding="utf-8"))
                ml, obs, av = pick_main_lines(sc)
                if ml:
                    return {"date": d, "mainlines": ml}
    except Exception:
        pass
    return None

def build_md(data, vip=True):
    env = data["indexes"]["env"]; idx = data["indexes"]["indexes"]
    plates = data["plates"]; sc = data["sector_scores"]; asof = data.get("asof", today())
    ind5 = plates.get("em_em_industry_5d", []) or []
    ind_t = plates.get("em_em_industry_today", []) or []
    con5 = plates.get("em_em_concept_5d", []) or []
    con_t = plates.get("em_em_concept_today", []) or []
    ths = plates.get("ths_industry", []) or []
    L = []
    A = L.append

    def tier_note(i):
        if i == 0:
            return "⭐ 王者"
        if i <= 2:
            return "重点"
        return "备选"

    def _plate_cell(name, code, note):
        nm = str(name or "").strip()
        cd = str(code or "").strip()
        if cd.startswith("BK") and nm:
            return "[%s](/demo.html?secid=90.%s&name=%s) `%s` **%s**" % (nm, cd, urllib.parse.quote(nm), cd, note)
        return "%s **%s**" % (nm, note)
    A("# 大盘研判 —— 资金主攻板块与主线锁定")
    A("")
    A("> 报告日期：%s（数据截至 %s 收盘）｜数据源：AI行情官 指数信号/个股评分 + 东方财富/同花顺 板块资金流与涨幅｜性质：大盘择时 × 板块轮动研判" % (today(), asof))
    A("> 声明：本报告由算法自动生成，仅为研究与信息整理，**不构成任何投资建议**。股市有风险，入市需谨慎。")
    A("")
    A("---")
    A("")
    _prev_ml = (data.get("prev_mainlines") or {}).get("mainlines") or []
    main_lines, observes, avoids = pick_main_lines(sc, _prev_ml, plates)
    data["mainlines"] = main_lines
    data["observes"] = observes
    sh = idx.get("上证指数", {}) or {}
    sh_lab = " ".join((sh.get("recent_labels") or [])[-2:]) or "-"
    A("## ⭐ 〇、核心结论")
    A("")
    A("1. **大盘**：上证最新信号「%s」，MACD 红柱 %s，站上 MA20，pts=%s——空转多状态：%s；" % (
        sh_lab, ("+%.1f" % ((sh.get("macd_last") or {}).get("bar") or 0)) if ((sh.get("macd_last") or {}).get("bar") or 0) >= 0 else "%.1f" % ((sh.get("macd_last") or {}).get("bar") or 0),
        env.get("pts"), ("顺风（金叉确认）" if "金" in sh_lab else ("底部转多初段" if "底" in sh_lab else "信号不明"))))
    if main_lines and vip:
        A("2. **主攻主线**：**%s**——资金与技术双确认（成分股评分均值 ≥62 且当日走强）；" % "、".join(main_lines))
    elif not vip:
        A("2. **主攻主线（VIP 专属）**：开通 VIP 后解锁板块技术体检与主线锁定。")
    if vip:
        A("3. **观察**：%s；**回避/等修复**：%s。" % ("、".join(observes) if observes else "无", "、".join(avoids) if avoids else "无"))
    else:
        A("3. **观察/回避（VIP 专属）**：板块技术体检与主线锁定为 VIP 权益，开通后自动解锁。")
    A("4. 风险提示：注意控制仓位风险、避免盲目追高；**本报告不构成投资建议**。")
    weak_flag = bool(env.get("weak")) or float(env.get("pts") or 0) <= 0
    mkt_lab = "顺风·金叉确认" if "金" in sh_lab else ("底部转多" if "底" in sh_lab else "信号不明")
    A("")
    A("> ⚡ **今日速览**：大盘【%s】｜主攻【%s】｜观察【%s】｜风险【%s】｜节奏【关注回踩企稳、防追高】" % (
        mkt_lab,
        "、".join("**%s**" % x for x in main_lines) if main_lines else "今日无达标板块",
        "、".join(observes) if observes else "无",
        "从严控制" if weak_flag else "注意控制"))
    if weak_flag:
        A("> ⚠️ **环境警示**：大盘环境转弱（跌破MA20 / MACD绿柱），主线多为超跌反弹，注意从严控制仓位，等重新站上 MA20 再观察。")
    elif env.get("pts") is not None and float(env.get("pts")) >= 3:
        A("> ✅ **环境顺风**：大盘 MACD 翻红且站上 MA20，关注主线回踩企稳形态；注意不追高、破位风险。")
    A("")
    A("---")
    A("")
    A("## 一、大盘信号验证")
    A("")
    A("| 排名 | 指数 | 最新信号 | 评分 | MACD红柱 | 状态 |")
    A("|---|---|---|---|---|")
    def status_of(r):
        lab = (r.get("recent_labels") or [])
        cur = lab[-1] if lab else ""
        if "金" in cur: return "金叉确认，顺风"
        if "底" in cur: return "底部信号，转多初段"
        if "险" in cur or "卖" in cur: return "偏弱/风险"
        return "中性"
    def _num(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return -1.0
    _ranked = sorted(INDEXES.items(), key=lambda kv: _num((idx.get(kv[0]) or {}).get("score")), reverse=True)
    for i, (name, secid) in enumerate(_ranked):
        r = idx.get(name) or {}
        macd = r.get("macd_last") or {}
        bar = macd.get("bar")
        bar_s = ("+%.1f" % bar) if bar is not None and bar >= 0 else ("%.1f" % bar if bar is not None else "-")
        A("| %d | [%s](/demo.html?secid=%s&name=%s) | %s | %s | %s | %s |" % (i + 1, name, secid, urllib.parse.quote(name), " ".join((r.get("recent_labels") or [])[-2:]) or "-", r.get("score"), bar_s, status_of(r)))
    A("")
    A("> 大盘环境：%s（%s，pts=%s）；上证收盘 %s。" % (
        env.get("tags")[0] if env.get("tags") else "-", env.get("tags")[1] if len(env.get("tags", [])) > 1 else "", env.get("pts"), idx.get("上证指数", {}).get("last_close")))
    A("")
    A("---")
    A("")
    A("## 二、资金面：谁在真正主攻")
    A("")
    A("### 2.1 行业板块 5 日主力净流入 TOP")
    A("")
    A("| 排名 | 板块 | 5日净流入 | 今日净流入 | 今日涨跌 |")
    A("|---|---|---|---|---|")
    for i, r in enumerate(ind5[:8]):
        A("| %d | %s | +%s 亿 | %s%s 亿 | %s%% |" % (i + 1, _plate_cell(r.get("name"), r.get("code"), tier_note(i)), yi(r["main_5d"]), "+" if (r["main_today"] or 0) >= 0 else "", yi(r["main_today"]), r["pct"]))
    A("")
    A("### 2.2 行业板块今日主力净流入 TOP")
    A("")
    A("| 排名 | 板块 | 今日净流入 |")
    A("|---|---|---|")
    for i, r in enumerate(ind_t[:8]):
        A("| %d | %s | %s%s 亿 |" % (i + 1, _plate_cell(r.get("name"), r.get("code"), tier_note(i)), "+" if (r["main_today"] or 0) >= 0 else "", yi(r["main_today"])))
    A("")
    A("### 2.3 概念板块资金流")
    A("")
    A("**今日净流入 TOP**")
    A("")
    A("| 排名 | 概念板块 | 今日净流入 | 今日涨跌 |")
    A("|---|---|---|---|")
    for i, r in enumerate(con_t[:8]):
        A("| %d | %s | %s%s 亿 | %+.1f%% |" % (i + 1, _plate_cell(r.get("name"), r.get("code"), tier_note(i)), "+" if (r["main_today"] or 0) >= 0 else "", yi(r["main_today"]), r["pct"] or 0))
    A("")
    A("**5日净流入 TOP**")
    A("")
    A("| 排名 | 概念板块 | 5日净流入 |")
    A("|---|---|---|")
    for i, r in enumerate(con5[:8]):
        A("| %d | %s | %s%s 亿 |" % (i + 1, _plate_cell(r.get("name"), r.get("code"), tier_note(i)), "+" if (r["main_5d"] or 0) >= 0 else "", yi(r["main_5d"])))
    A("")
    A("### 2.4 今日行业涨幅 TOP（同花顺）")
    A("")
    A("| 排名 | 行业 | 涨幅 | 上涨/下跌 | 领涨股 |")
    A("|---|---|---|---|---|")
    for i, r in enumerate(ths[:10]):
        A("| %d | %s **%s** | %+.2f%% | %s/%s | %s |" % (i + 1, r["name"], tier_note(i), r["pct"] or 0, r["up"], r["down"], r["leader"]))
    A("")
    br = data.get("breadth") or {}
    if br.get("total"):
        A("### 2.5 市场宽度（沪深A股口径 + 全市场涨跌停池）")
        A("")
        A("| 项目 | 数值 |")
        A("|---|---|")
        A("| 上涨 / 下跌 / 平盘 | %s / %s / %s |" % (br.get("up"), br.get("down"), br.get("flat")))
        A("| 涨停 / 跌停 | %s / %s |" % (br.get("limit_up"), br.get("limit_down")))
        A("| 涨幅≥5%% / ≤-5%% | %s / %s |" % (br.get("big_up"), br.get("big_down")))
        A("| 主力净流入合计 | %s%s 亿 |" % ("+" if (br.get("main_net") or 0) >= 0 else "", yi(br.get("main_net"))))
        A("")
    ts = data.get("ths_sentiment") or {}
    if ts.get("ok") and (ts.get("limit_up") or ts.get("hot") or ts.get("hot_money")):
        A("### 2.6 市场情绪（同花顺 · 交叉验证）")
        A("")
        A("> 涨停/连板/热榜/龙虎榜来自同花顺金融数据API，与东财涨跌停池互相印证；两源口径略有差异，仅供参考。")
        A("")
        lu = ts.get("limit_up") or {}
        if lu.get("count") is not None:
            A("| 项目 | 数值 |")
            A("|---|---|")
            A("| 涨停家数（同花顺） | %s 家 |" % lu.get("count"))
            A("| 最高连板 | %s |" % ("%s 连板 · %s" % (lu.get("max_lianban"), lu.get("max_name")) if lu.get("max_lianban") else "-"))
            A("")
        ld = ts.get("ladder") or {}
        if ld.get("rows"):
            _board_lab = {"two_board": "2连板", "three_board": "3连板", "four_board": "4连板",
                          "five_board": "5连板", "six_board": "6连板", "seven_over": "7板+"}
            rows2 = [r for r in ld["rows"] if r.get("count")]
            if rows2:
                A("**连板梯队（%s）**" % (ld.get("date") or ""))
                A("")
                A("| 板位 | 家数 | 代表 |")
                A("|---|---|---|")
                for r in rows2:
                    A("| %s | %s | %s |" % (_board_lab.get(r.get("board"), r.get("board")), r.get("count"), "、".join(r.get("names") or [])[:36]))
                A("")
        hm = ts.get("hot_money") or []
        if hm:
            A("**龙虎榜游资净买入 TOP**")
            A("")
            A("| 游资 | 净买入 | 主要标的 |")
            A("|---|---|---|")
            for i, r in enumerate(hm[:5]):
                A("| %d. %s | %s%s 亿 | %s |" % (i + 1, r.get("name"), "+" if (r.get("buying") or 0) >= 0 else "", ("%.1f" % (abs(r.get("buying") or 0) / 1e8)), "、".join(r.get("stocks") or [])))
            A("")
        hot = ts.get("hot") or []
        if hot:
            A("**同花顺热股榜 TOP5**")
            A("")
            A("| 排名 | 股票 | 热度 |")
            A("|---|---|---|")
            for i, r in enumerate(hot[:5]):
                A("| %d | %s（%s） | %s |" % (i + 1, r.get("name"), r.get("ticker"), r.get("heat")))
            A("")
    if not vip:
        A("---")
        A("")
        A("## ⭐ 三、板块技术体检（VIP 专属）")
        A("")
        A("> 板块成分股 AI行情官 评分与龙头梯队为 **VIP 专属**，开通 VIP 后自动解锁。")
        A("")
        A("## ⭐ 四、主线锁定（VIP 专属）")
        A("")
        A("> 主线锁定算法（板块评分均值≥62 且当日走强 → 主线）为 **VIP 专属**，开通 VIP 后自动解锁。")
        A("")
    else:
        A("---")
        A("")
        A("## ⭐ 三、板块技术体检（AI行情官 成分股评分）")
        A("")
        A("| 板块 | 评分均值 | 龙头梯队(前3) |")
        A("|---|---|---|")
        for sec, items in sc.items():
            mean, top3, ok = sector_stats(items)
            A("| %s | %s | %s |" % (sec, ("%.1f" % mean) if mean else "-", top3))
        A("")
        main_lines, observes, avoids = pick_main_lines(sc, (data.get("prev_mainlines") or {}).get("mainlines") or [], plates)
        A("---")
        A("")
        A("## ⭐ 四、主线锁定（算法双确认）")
        A("")
        A("**主攻主线**：" + ("、".join("**%s**" % x for x in main_lines) if main_lines else "今日无评分达标板块，等修复"))
        A("")
        A("**观察**：" + ("、".join(observes) if observes else "无"))
        A("")
        A("**回避/等修复**：" + ("、".join(avoids) if avoids else "无"))
        A("")
        A("板块级主线以本页为准；个股筛选与异动观察请前往「复盘」页查看对应标的。")
        prev = data.get("prev_mainlines") or {}
        if prev.get("mainlines"):
            pml = prev["mainlines"]
            cont = [x for x in main_lines if x in pml]
            newm = [x for x in main_lines if x not in pml]
            gone = [x for x in pml if x not in main_lines]
            gone_obs = [x for x in gone if x in observes]
            gone_av = [x for x in gone if x not in observes]
            A("")
            _cont_parts = ["延续 %s" % ("、".join(cont) if cont else "无"),
                           "新增 %s" % ("、".join(newm) if newm else "无")]
            if gone_obs:
                _cont_parts.append("回调观察 %s" % "、".join(gone_obs))
            if gone_av:
                _cont_parts.append("退潮 %s" % "、".join(gone_av))
            A("**主线连续性**（对比 %s）：%s。" % (prev.get("date") or "-", "；".join(_cont_parts)))
        A("")
    A("---")
    A("")
    A("## ⭐ 五、组合与风控")
    A("")
    A("| 项目 | 建议 |")
    A("|---|---|")
    A("| 仓位提示 | 注意控制仓位风险、不满仓操作 |")
    A("| 主线观察 | 关注主线板块代表股回踩企稳形态与主力资金延续性 |")
    A("| 观察板块 | 仅关注评分最高的代表股，控制参与比例 |")
    A("| 风险信号 | 跌破 MA20 或上证跌破 MA20 → 注意整体风险 |")
    A("| 跟踪 | 主线 5 日主力资金延续性、代表股量价、大盘底金状态 |")
    A("")
    A("---")
    A("")
    A("## 六、风险提示")
    A("")
    A("1. 板块资金流、涨幅与评分为公开数据统计，可能存在口径与滞后差异；")
    A("2. 个股单日大涨后追高风险大，优先等回踩企稳；")
    A("3. AI行情官 评分反映历史量价状态，不代表未来走势；")
    A("4. **本报告为算法自动生成，不构成投资建议**，据此操作风险自负。")
    A("")
    A("---")
    A("")
    A("*报告生成：AI行情官 大盘研判（算法自动）｜数据截至 %s 收盘｜方法：逻辑×数据双确认*" % asof)
    return "\n".join(L)

def md_to_html(md):
    import html as H
    lines = md.split("\n")
    blocks = []
    cur = None
    i = 0
    FOLD_KW = ("资金面",)  # 复盘精简：资金面明细默认折叠，避免信息过载
    while i < len(lines):
        ln = lines[i]
        s = ln.strip()
        if s.startswith("# "):
            if cur: blocks.append(cur); cur = None
            blocks.append({"title": None, "fold": False, "html": ["<h1>%s</h1>" % H.escape(s[2:])]})
        elif s.startswith("## "):
            if cur: blocks.append(cur)
            title = s[3:]
            cur = {"title": title, "fold": any(kw in title for kw in FOLD_KW), "html": []}
        else:
            if cur is None:
                cur = {"title": None, "fold": False, "html": []}
            if s.startswith("### "):
                cur["html"].append("<h3>%s</h3>" % H.escape(s[4:]))
            elif s.startswith("> "):
                c = s[2:].lstrip()
                cls = "note"
                if c.startswith("⚡"): cls = "note core"
                elif c.startswith("✅"): cls = "note good"
                elif c.startswith("⚠"): cls = "note bad"
                cur["html"].append('<div class="%s">%s</div>' % (cls, md_inline(c)))
            elif s.startswith("|"):
                rows = []
                while i < len(lines) and lines[i].strip().startswith("|"):
                    cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                    if all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
                        i += 1; continue
                    rows.append(cells)
                    i += 1
                if rows:
                    is_rank = str(rows[0][0]).strip() in ("排名", "#")
                    def _cell(tag, c, idx):
                        cls = ""
                        if is_rank and idx == 0: cls = ' class="col-rank"'
                        elif is_rank and idx == 1: cls = ' class="col-name"'
                        return "<%s%s>%s</%s>" % (tag, cls, md_inline(c), tag)
                    t = ['<table><thead><tr>%s</tr></thead><tbody>' % "".join(_cell("th", c, i) for i, c in enumerate(rows[0]))]
                    for r in rows[1:]:
                        t.append("<tr>%s</tr>" % "".join(_cell("td", c, i) for i, c in enumerate(r)))
                    t.append("</tbody></table>")
                    cur["html"].append("".join(t))
            elif s.startswith("- "):
                items = []
                while i < len(lines) and lines[i].strip().startswith("- "):
                    items.append("<li>%s</li>" % md_inline(lines[i].strip()[2:]))
                    i += 1
                cur["html"].append("<ul>%s</ul>" % "".join(items))
            elif s == "---":
                cur["html"].append("<hr>")
            elif s:
                if "**主攻主线" in s:
                    cur["html"].append('<div class="mainline">%s</div>' % md_inline(s))
                else:
                    cur["html"].append("<p>%s</p>" % md_inline(s))
        i += 1
    if cur: blocks.append(cur)

    def _key(title):
        if not title: return -1
        if "核心结论" in title: return 0
        if "主线锁定" in title: return 1
        if "组合与风控" in title: return 2
        return 3

    pre = [b for b in blocks if b.get("title") is None]
    core = [b for b in blocks if _key(b.get("title")) in (0, 1, 2)]
    rest = [b for b in blocks if b.get("title") is not None and _key(b.get("title")) not in (0, 1, 2)]
    blocks = pre + core + rest

    # 重排后重新编号（〇保留，其余按 一~六 顺延）
    CN = ["一", "二", "三", "四", "五", "六", "七"]
    num = 0
    for b in blocks:
        t = b.get("title")
        if not t or "核心结论" in t: continue
        m = re.match(r"^([⭐\s]*)([一二三四五六七八九十]+)、(.*)$", t)
        if m and num < len(CN):
            t = m.group(1) + CN[num] + "、" + m.group(3)
            num += 1
        b["title"] = t

    out = []
    for b in blocks:
        title = b.get("title")
        if title is None:
            # 标题区（报告标题+日期/声明）下的分隔线冗余，去掉，仅保留章节间分隔
            for _h in b["html"]:
                if _h == "<hr>":
                    continue
                out.append(_h)
            continue
        esc_title = H.escape(title)
        if b.get("fold"):
            out.append('<details class="fold"><summary>%s（点击展开明细）</summary>' % esc_title)
            out.extend(b["html"])
            out.append("</details>")
            continue
        cls = ""
        if "主线锁定" in title:
            cls = ' class="h2-core h2-main"'
        elif "组合与风控" in title:
            cls = ' class="h2-core h2-risk"'
        out.append("<h2%s>%s</h2>" % (cls, esc_title))
        out.extend(b["html"])
    return "\n".join(out)

def md_inline(s):
    import html as H
    s = H.escape(s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2" target="_blank" rel="noopener">\1</a>', s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub("\u0060(.+?)\u0060", r"<code>\1</code>", s)
    return s

# ---------------- 同花顺情绪面 ----------------
def fetch_ths_sentiment(asof):
    """情绪面：涨停/连板/热榜/飙升/异动/龙虎榜游资（同花顺，失败回退当日缓存）。"""
    try:
        return asyncio.run(_ths_build_sentiment(asof))
    except Exception:
        return cache_load("ths_sentiment") or {}


def run_daily(force=False, is_vip=True):
    d8 = today8()
    if not force:
        hit = cache_load("report")
        if hit and hit.get("today8") == d8 and not report_stale(hit):
            return hit
    set_progress(phase="running", pct=1, step="开始（优先用当日缓存数据，防封限流）", started_at=time.time(), finished=None, ok=False)
    t0 = time.time()
    _plates = cache_load("plates"); _idx = cache_load("indexes"); _sc = cache_load("sector_scores")
    if _plates and _idx and _sc and not data_cache_stale(_idx):
        set_progress(step="当日数据缓存已存在，直接生成报告（不再抓上游）")
        _breadth = cache_load("breadth") or {}
        _asof = (_idx.get("indexes", {}).get("上证指数", {}) or {}).get("last_date") or today()
        _ths = cache_load("ths_sentiment")
        if not _ths or not (_ths.get("limit_up") or {}).get("count"):
            # 情绪缓存缺失/为空：补一次（内部按日缓存，上游成本极低）
            try:
                _ths = fetch_ths_sentiment(_asof)
                cache_save("ths_sentiment", _ths)
            except Exception:
                _ths = _ths or {}
        _data = {"today8": d8, "asof": _asof, "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                 "indexes": _idx, "plates": _plates, "sector_scores": _sc, "breadth": _breadth,
                 "ths_sentiment": _ths}
        _data["prev_mainlines"] = _prev_mainlines()
        _data["md"] = build_md(_data)
        _data["html"] = md_to_html(_data["md"])
        cache_save("report", _data)
        archive(_data, d8)
        set_progress(phase="done", pct=100, step="完成（缓存数据，耗时 %.1f 分钟）" % ((time.time() - t0) / 60), finished=datetime.now().strftime("%H:%M:%S"), ok=True)
        return _data
    idx = cache_load("indexes")
    sc = cache_load("sector_scores")
    stale = data_cache_stale(idx)   # 收盘后昨日/盘中缓存 → 需重拉当日最终数据（修复主线错版）
    scan_warn = ""
    plates = cache_load("plates")
    if not plates or force or stale:
        set_progress(step="抓取板块资金流(东财 4 组 + 同花顺 1 次，低频)")
        try:
            plates = fetch_plates()
            time.sleep(2)
            ths = fetch_ths_industry()
            plates["ths_industry"] = ths
            cache_save("plates", plates)
        except Exception as e:
            plates = cache_load("plates") or {}
            scan_warn = "板块资金流重拉失败(%s)，沿用旧缓存" % str(e)[:80]
    if (not idx or force or stale) or (not sc or force or stale):
        set_progress(step="内部直算：指数信号 + 成分股评分（腾讯K线，不扣查次）")
        try:
            got = asyncio.run(_fetch_internal(is_vip, idx_needed=(not idx or force or stale), sc_needed=(not sc or force or stale)))
        except Exception as e:
            got = {}
            scan_warn = "指数/评分重拉失败(%s)，沿用旧缓存" % str(e)[:80]
        if got.get("indexes"):
            idx = got["indexes"]; idx["_ts"] = time.time(); cache_save("indexes", idx)
        if got.get("sector_scores"):
            sc = got["sector_scores"]; cache_save("sector_scores", sc)
    try:
        breadth = fetch_breadth()
        cache_save("breadth", breadth)
    except Exception:
        breadth = cache_load("breadth") or {}
    set_progress(step="同花顺情绪面：涨停/连板/热榜/龙虎榜游资（限流低频）")
    asof = (idx.get("indexes", {}).get("上证指数", {}) or {}).get("last_date") or today()
    try:
        ths_sentiment = fetch_ths_sentiment(asof)
        cache_save("ths_sentiment", ths_sentiment)
    except Exception:
        ths_sentiment = cache_load("ths_sentiment") or {}
    data = {"today8": d8, "asof": asof, "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "indexes": idx, "plates": plates, "sector_scores": sc, "breadth": breadth,
            "ths_sentiment": ths_sentiment, "warn": scan_warn or ""}
    data["prev_mainlines"] = _prev_mainlines()
    data["md"] = build_md(data)
    data["html"] = md_to_html(data["md"])
    cache_save("report", data)
    archive(data, d8)
    set_progress(phase="done", pct=100, step="完成，耗时 %.1f 分钟" % ((time.time() - t0) / 60), finished=datetime.now().strftime("%H:%M:%S"), ok=True)
    return data

def archive(data, d8):
    d = os.path.join(ARCHIVE_ROOT, d8)
    os.makedirs(d, exist_ok=True)
    for fn, obj in [("index_signal.json", data["indexes"]), ("plate_data.json", data["plates"]),
                    ("sector_score.json", data["sector_scores"]), ("breadth.json", data["breadth"]),
                    ("ths_sentiment.json", data.get("ths_sentiment") or {})]:
        with open(os.path.join(d, fn), "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
    with open(os.path.join(d, "report.md"), "w", encoding="utf-8") as f:
        f.write(data["md"])
    with open(os.path.join(d, "report.html"), "w", encoding="utf-8") as f:
        f.write(data["html"])
    with open(os.path.join(d, "mainlines.json"), "w", encoding="utf-8") as f:
        json.dump({"date": d8, "mainlines": data.get("mainlines") or [], "observes": data.get("observes") or []},
                  f, ensure_ascii=False, indent=2)
    return d

def list_archive():
    out = []
    if not os.path.isdir(ARCHIVE_ROOT):
        return out
    for d in sorted(os.listdir(ARCHIVE_ROOT), reverse=True):
        p = os.path.join(ARCHIVE_ROOT, d)
        if os.path.isdir(p) and os.path.exists(os.path.join(p, "report.md")):
            out.append({"date": d, "has_html": os.path.exists(os.path.join(p, "report.html"))})
    return out

def load_report_by_date(d8):
    # 优先用 report.md 实时渲染（模板升级自动生效），缺失再回退已生成的 report.html
    pm = os.path.join(ARCHIVE_ROOT, d8, "report.md")
    if os.path.exists(pm):
        md = open(pm, encoding="utf-8").read()
        out = {"date": d8, "html": md_to_html(md), "md": md}
    else:
        p = os.path.join(ARCHIVE_ROOT, d8, "report.html")
        if not os.path.exists(p):
            return None
        out = {"date": d8, "html": open(p, encoding="utf-8").read(), "md": ""}
    ps = os.path.join(ARCHIVE_ROOT, d8, "ths_sentiment.json")
    if os.path.exists(ps):
        try:
            out["ths_sentiment"] = json.load(open(ps, encoding="utf-8"))
        except Exception:
            pass
    return out

def _sentiment_public_lines(sentiment, header="### 2.6 市场情绪（免费公开）"):
    """公开版市场情绪小节（涨停池/连板梯队/热股TOP5），数据异常时返回空。"""
    try:
        lim = sentiment.get("limit_up") or {}
        ladder = sentiment.get("ladder") or {}
        hot = sentiment.get("hot") or []
        cnt = int(lim.get("count") or 0)
        if not cnt:
            return []
        out = ["", header, ""]
        out.append("> 涨停池 **" + str(cnt) + "** 家 · 最高连板 **" + str(lim.get("max_lianban") or 0) + "** 板（" + str(lim.get("max_name") or "-") + "）")
        seal = lim.get("seal_money_top") or []
        if seal:
            out.append("> 封单TOP5：" + "、".join(str(x.get("name") or "") for x in seal[:5]))
        lrows = ladder.get("rows") or []
        lab = {"two_board": "2连板", "three_board": "3连板", "four_board": "4连板",
               "five_board": "5连板", "six_board": "6连板", "seven_over": "7板以上"}
        parts = []
        for r in lrows:
            if not (r or {}).get("count"):
                continue
            nm = "、".join(str(x) for x in (r.get("names") or [])[:3])
            parts.append(str(lab.get(r.get("board"), r.get("board"))) + " " + str(r.get("count")) + "家" + ("（" + nm + "）" if nm else ""))
        if parts:
            out.append("> 连板梯队：" + "；".join(parts))
        if hot:
            out.append("> 热股TOP5：" + "、".join(str(x.get("name") or "") for x in hot[:5]))
        out.append("")
        out.append("> 以上为市场情绪统计（同花顺交叉验证），**不构成投资建议**。")
        return out
    except Exception:
        return []


def public_md(full_md, sentiment=None):
    """非 VIP：把完整报告降级为“大盘+市场宽度”公开版（风控）。
    隐藏板块资金流TOP、市场情绪与个股、今日速览/操作建议、板块体检、主线锁定；
    免费版仅保留大盘信号与市场宽度纯统计，避免荐股导向内容。"""
    out = []
    skip = False
    inserted = set()
    in_s2 = False
    for ln in (full_md or "").split("\n"):
        s = ln.strip()

        def _h2(kw):
            return s.startswith("## ") and kw in s

        if _h2("三、板块技术体检"):
            skip = True
            if "s3" not in inserted:
                inserted.add("s3")
                out.append("## 三、板块技术体检（VIP 专属）")
                out.append("")
                out.append("> 板块资金流、板块成分 AI行情官 评分与龙头梯队为 **VIP 专属**，开通 VIP 后自动解锁。")
                out.append("")
            continue
        if _h2("四、主线锁定"):
            skip = True
            if "s4" not in inserted:
                inserted.add("s4")
                out.append("## 四、主线锁定（VIP 专属）")
                out.append("")
                out.append("> 主线锁定算法（板块评分均值≥62 且当日走强 → 主线）为 **VIP 专属**，开通 VIP 后自动解锁。")
                out.append("")
            continue
        if _h2("五、组合与风控"):
            skip = True
            if "s5" not in inserted:
                inserted.add("s5")
                out.append("## 五、组合与风控（VIP 专属）")
                out.append("")
                out.append("> 风险提示与观察要点为 **VIP 专属**，开通 VIP 后自动解锁。")
                out.append("")
            continue
        # 二、资金面：仅保留 2.5 市场宽度（纯统计），隐藏 2.1~2.4 板块资金流TOP 与 2.6 市场情绪个股
        if _h2("二、资金面"):
            in_s2 = True
            out.append("## 二、市场宽度（免费公开）")
            out.append("")
            out.append("> 板块资金流排行、市场情绪与个股信息为 **VIP 专属**；免费版仅保留大盘信号与市场宽度统计。")
            out.append("")
            continue
        if in_s2:
            if s.startswith("### 2.5 "):
                in_s2 = False
            elif s.startswith("### "):
                continue  # 2.1~2.4 板块资金流TOP 跳过
            else:
                continue
        if s.startswith("### 2.6 "):
            # 免费公开版：原 VIP 情绪小节位置替换为公开市场情绪统计
            _s6 = _sentiment_public_lines(sentiment)
            if _s6:
                out.extend(_s6)
            skip = True
            continue
        # 今日速览（含大盘/主攻/观察/风险/节奏）→ 隐藏
        if s.startswith("> ⚡ "):
            continue
        # 环境警示/顺风：保留大盘事实，去掉“低吸/破位即撤”类操作建议
        if s.startswith("> ⚠️ **环境警示**"):
            out.append("> ⚠️ **大盘环境**：跌破 MA20 / MACD 绿柱（转弱），注意控制仓位。")
            continue
        if s.startswith("> ✅ **环境顺风**"):
            out.append("> ✅ **大盘环境**：MACD 翻红且站上 MA20（顺风）。")
            continue
        # 核心结论：非 VIP 隐藏主攻/观察板块与操作原则，仅留声明
        if s.startswith("2. **主攻主线**"):
            out.append("2. **主攻主线（VIP 专属）**：开通 VIP 后解锁板块技术体检与主线锁定。")
            continue
        if s.startswith("3. **观察**"):
            out.append("3. **观察/回避（VIP 专属）**：板块技术体检与主线锁定为 VIP 权益，开通后自动解锁。")
            continue
        if s.startswith("4. 操作原则"):
            out.append("4. 本报告由算法基于公开行情自动生成，仅供研究与信息整理，**不构成投资建议**；股市有风险，入市需谨慎。")
            continue
        if skip and s.startswith("## "):
            skip = False
        if not skip:
            out.append(ln)
    base = "\n".join(out)
    # 兜底：报告模板不含 2.6 小节时（如旧归档），以附录追加，避免情绪缺失
    if sentiment and "市场情绪（免费公开）" not in base:
        _sx = _sentiment_public_lines(sentiment, header="## 附、市场情绪（免费公开）")
        if _sx:
            base = base + "\n" + "\n".join(_sx)
    return base

# ---------------- 鉴权/权限 ----------------
def _vip_of(user_id):
    """返回 (is_vip, plan)。未登录/免费/匿名均视为非 VIP。"""
    if user_id is None:
        return False, "anon"
    try:
        db.downgrade_expired_vip_plan(int(user_id))
        quota = db.get_quota_status(int(user_id))
        plan = str(quota.get("plan") or "anon").strip().lower()
        return plan not in ("", "free", "anon"), plan
    except Exception:
        return False, "anon"

# ---------------- 路由（并入 18011，前缀 /api/report） ----------------
@router.get("/api/report/status")
def status(user_id: Optional[int] = Depends(get_optional_user_id)):
    is_vip, _plan = _vip_of(user_id)
    report = cache_load("report")
    has_today = bool(report and (report.get("today8") == today8() or str(report.get("generated_at") or "").startswith(today())))
    needs_refresh = bool(report and report_stale(report))
    return {
        "ok": True,
        "today": today(),
        "today8": today8(),
        "is_weekend": is_weekend(),
        "is_trading_day": is_trading_day(),
        "logged_in": user_id is not None,
        "vip": is_vip,
        "has_today": has_today,
        "needs_refresh": needs_refresh,
        "asof": (report or {}).get("asof"),
        "generated_at": (report or {}).get("generated_at"),
        "running": _busy(),
        "progress": get_progress(),
        "last_done": _RUNNING.get("last_done") or 0,
        "last_error": _RUNNING.get("last_error") or "",
        "auto_blocked": _auto_blocked(),
        "auto_scan_time": cfg().get("auto_scan_time"),
        "auto_scan": bool(cfg().get("auto_scan", True)),
        "history": list_archive(),
        "service_ok": True,
    }

@router.get("/api/report/progress")
def progress():
    return {"ok": True, "running": _busy(), "progress": get_progress()}

@router.post("/api/report/scan")
def scan(force: int = 0, user_id: int = Depends(get_current_user_id)):
    is_vip, _plan = _vip_of(user_id)
    if not is_vip:
        raise HTTPException(status_code=403, detail="每日研判自动生成为 VIP 专属功能，开通 VIP 后即可使用")
    if not force:
        hit = cache_load("report")
        if hit and hit.get("today8") == today8() and not report_stale(hit):
            return {"ok": True, "msg": "今日报告已生成，无需重复扫描（如需重扫请用强制模式）", "cached": True}
    if not force and _auto_blocked():
        return {"ok": False, "msg": "上次自动生成失败（%s），为避免重复占用上游预算，请 %d 分钟后重试" % (_RUNNING.get("last_error") or "未知错误", _AUTO_FAIL_COOLDOWN // 60)}
    if is_weekend() and not force:
        return {"ok": False, "msg": "今天是周末，非交易日，不自动扫描（可 force=1 强制）"}
    _start_scan(bool(force), is_vip)
    return {"ok": True, "msg": "扫描已启动"}

@router.get("/api/report/today")
def today_report(user_id: Optional[int] = Depends(get_optional_user_id)):
    is_vip, _plan = _vip_of(user_id)
    report = cache_load("report")
    if not report:
        return {"ok": False, "msg": "今日报告尚未生成"}
    if is_vip:
        md = report.get("md", "")
        html = md_to_html(md) if md else report.get("html", "")
    else:
        md = public_md(report.get("md", ""), report.get("ths_sentiment"))
        html = md_to_html(md)
    return {"ok": True, "asof": report.get("asof"), "generated_at": report.get("generated_at"),
            "html": html, "md": md, "vip": is_vip}

@router.get("/api/report/history")
def history(user_id: Optional[int] = Depends(get_optional_user_id)):
    return {"ok": True, "items": list_archive()}

class CfgIn(BaseModel):
    auto_scan: bool = True
    auto_scan_time: str = "15:03"

@router.get("/api/report/config")
def get_cfg(user_id: Optional[int] = Depends(get_optional_user_id)):
    c = dict(cfg())
    c.pop("token", None)
    return {"ok": True, "config": c}

@router.post("/api/report/config")
def set_cfg(body: CfgIn, user_id: int = Depends(get_current_user_id)):
    is_vip, _plan = _vip_of(user_id)
    if not is_vip:
        raise HTTPException(status_code=403, detail="该设置为 VIP 专属，开通 VIP 后即可使用")
    c = dict(cfg())
    c["auto_scan"] = bool(body.auto_scan)
    if body.auto_scan_time:
        c["auto_scan_time"] = body.auto_scan_time.strip()
    c.pop("token", None)
    with open(CFG_PATH, "w", encoding="utf-8") as f:
        json.dump(c, f, ensure_ascii=False, indent=2)
    global _CFG
    _CFG = c
    return {"ok": True}

@router.get("/api/report/{date8}")
def by_date(date8: str, user_id: Optional[int] = Depends(get_optional_user_id)):
    is_vip, _plan = _vip_of(user_id)
    d = load_report_by_date(date8)
    if not d:
        raise HTTPException(status_code=404, detail="未找到该日期报告")
    if not is_vip:
        md = public_md(d.get("md", ""), d.get("ths_sentiment"))
        d = {"date": d.get("date") or date8, "html": md_to_html(md), "md": md}
    return {"ok": True, **d, "vip": is_vip}
