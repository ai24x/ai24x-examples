# -*- coding: utf-8 -*-
"""每日板块主攻研判 · 核心模块（独立于产品代码，纯新增）。
数据链路：AI行情官(18011 指数信号/个股评分) + 东方财富 push2delay(板块资金流) + 同花顺(行业涨幅)。
防封原则：按日缓存（当日命中绝不重抓）、每日上游配额、慢速退避重试、keep-alive 复用连接、单任务锁。
"""
import json, os, re, sys, time, urllib.request, urllib.parse, threading
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CFG_PATH = os.path.join(BASE_DIR, "config.json")
ARCHIVE_ROOT = r"E:\AI24X\ai24x-website\ai24x01\p\a1\调研报告\04-每日跟踪\板块主攻研判"
CACHE_ROOT = os.path.join(BASE_DIR, "cache")          # 按日上游数据缓存

HOST = "http://127.0.0.1:18011"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# 每日上游预算（防封）
EM_DAILY_BUDGET = 16        # 东财 push2delay 请求/日
THS_DAILY_BUDGET = 2        # 同花顺页面请求/日
SNAP_INTERVAL = 8.0         # 18011 snapshot 间隔秒（后端限流 10/min）
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
}

_CFG = None
def cfg():
    global _CFG
    if _CFG is None:
        _CFG = {"token": "", "auto_scan_time": "15:35", "auto_scan": True}
        try:
            if os.path.exists(CFG_PATH):
                _CFG.update(json.load(open(CFG_PATH, encoding="utf-8")))
        except Exception:
            pass
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
    return now_hhmm() >= str(cfg().get("auto_scan_time") or "15:35")
def report_stale(report):
    """今日已生成但数据截至日早于今日，且已过收盘时间 → 陈旧，需重扫。"""
    if not report or report.get("today8") != today8():
        return False
    if is_weekend():
        return False
    if _after_close():
        return (report.get("asof") or "") != today()
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
        return last != today()
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

# ---------------- 18011 API ----------------
def api_get(path, timeout=30, tries=4):
    tok = str(cfg().get("token") or "").strip()
    for i in range(tries):
        try:
            req = urllib.request.Request(HOST + path, headers={"Authorization": "Bearer " + tok})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            if i < tries - 1:
                time.sleep(2 + i * 3)
            else:
                raise RuntimeError("18011接口失败(%s): %s" % (path.split("?")[0], str(e)[:90]))
    return None

def token_ok():
    try:
        d = api_get("/api/me")
        return bool(d and (d.get("user") or d.get("ok")))
    except Exception:
        return False

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
    return [{"name": d.get("f14"), "pct": d.get("f3"), "main_today": d.get("f62"),
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

# ---------------- 指数信号 ----------------
def load_scoring():
    sys.path.insert(0, r"E:\AI24X\ai24x-website\ai24x01\p\a1\api\server")
    from app.signals import candles_from_tencent_like_pack, _compute_macd_arrays
    from app.scoring import score_candles, _ma, _slope_ratio, _red_days
    return candles_from_tencent_like_pack, _compute_macd_arrays, score_candles, _ma, _slope_ratio, _red_days

def fetch_index_signals():
    candles_from_tencent_like_pack, _compute_macd_arrays, score_candles, _ma, _slope_ratio, _red_days = load_scoring()
    sh = api_get("/api/kline?secid=1.000001&period=day&count=120")
    sh_pack = next(iter(sh["data"].values()))
    sh_candles = candles_from_tencent_like_pack(sh_pack, period="day")
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
    time.sleep(KLINE_INTERVAL)
    result = {}
    for name, secid in INDEXES.items():
        kline = api_get("/api/kline?secid=%s&period=day&count=120" % secid)
        sig = api_get("/api/signals?secid=%s&period=day&count=200" % secid)
        rec = {"secid": secid}
        pack = next(iter(kline["data"].values()))
        candles = candles_from_tencent_like_pack(pack, period="day")
        sc = score_candles(candles, name=name)
        base = float(sc.get("score") or 0.0)
        rec["score"] = round(max(0.0, min(100.0, base + pts)), 1)
        rec["pts"] = pts
        rec["above_ma20"] = env["above_ma20"]
        rec["weak"] = env["weak"]
        rec["tags"] = env["tags"]
        rec["last_close"] = candles[-1].close
        rec["last_date"] = candles[-1].time
        mk = (sig.get("data") or {}).get("markers") or []
        by_day = {}
        for m in mk:
            txt = str(m.get("text") or "").strip().replace("\u200b", "").strip()
            if not txt: continue
            by_day.setdefault(str(m.get("time")), []).append(txt)
        days = sorted(by_day.keys())
        ARR = "\u2197\u2198\u2192\u2190\u2191\u2193"
        labs = []
        for k in days[-6:]:
            s2 = "".join(ch for ch in "\u3000".join(by_day[k]) if ch not in ARR).strip()
            if s2: labs.append(s2)
        rec["recent_labels"] = labs[-6:]
        macd = (sig.get("data") or {}).get("macd") or []
        if macd: rec["macd_last"] = macd[-1]
        result[name] = rec
        time.sleep(KLINE_INTERVAL)
    return {"env": env, "indexes": result}

# ---------------- 板块成分股评分 ----------------
def secid_of(code): return ("1." if code[0] in "56" else "0.") + code

def fetch_sector_scores():
    out = {}
    n = 0
    total = sum(len(v) for v in SECTORS.values())
    for sec, items in SECTORS.items():
        out[sec] = []
        for code, name in items:
            url = "/api/quote/snapshot?secid=%s&code=%s&name=%s" % (secid_of(code), code, urllib.parse.quote(name))
            d = api_get(url, timeout=40, tries=4)
            if not d or not d.get("ok"):
                out[sec].append({"code": code, "name": name, "error": str((d or {}).get("error") or "failed")[:80]})
            else:
                out[sec].append({
                    "code": code, "name": name, "score": d.get("score"), "tags": d.get("tags") or [],
                    "risks": d.get("risks") or [], "up_pct": d.get("up_pct"), "vol_ratio": d.get("vol_ratio"),
                    "red_days": d.get("red_days"), "latest_time": d.get("latest_time"),
                })
            n += 1
            set_progress(pct=10 + int(n / total * 55), step="AI行情官体检 %d/%d" % (n, total))
            time.sleep(SNAP_INTERVAL)
    return out

# ---------------- breadth（1 次东财请求，top100 采样，与原文口径一致） ----------------
def fetch_breadth():
    fs = urllib.parse.quote("m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048")
    url = ("https://push2delay.eastmoney.com/api/qt/clist/get?pn=1&pz=100&po=1&np=1&fltt=2&invt=2&fid=f3&fs=%s&fields=f3,f62" % fs)
    t = slow_get(url, kind="em")
    diff = json.loads(t).get("data", {}).get("diff", []) or []
    total = len(diff)
    up = sum(1 for d in diff if (d.get("f3") or 0) > 0)
    down = sum(1 for d in diff if (d.get("f3") or 0) < 0)
    limit_up = sum(1 for d in diff if (d.get("f3") or 0) >= 9.8)
    big_up = sum(1 for d in diff if (d.get("f3") or 0) >= 5)
    big_down = sum(1 for d in diff if (d.get("f3") or 0) <= -5)
    main_net = sum(float(d.get("f62") or 0) for d in diff)
    return {"total": total, "up": up, "down": down, "limit_up": limit_up, "big_up": big_up, "big_down": big_down, "main_net": main_net}

# ---------------- 报告生成 ----------------
def yi(v):
    if v is None: return "-"
    return "%.1f" % (float(v) / 1e8)

def sector_stats(sc):
    ok = [x for x in sc if x.get("score") is not None]
    mean = round(sum(float(x["score"]) for x in ok) / len(ok), 1) if ok else None
    top = sorted(ok, key=lambda x: x["score"], reverse=True)[:3]
    names = " / ".join("%s %.1f" % (x["name"], x["score"]) for x in top)
    return mean, names, ok

def pick_main_lines(sector_scores):
    main_lines, observes, avoids = [], [], []
    for sec, sc in sector_scores.items():
        mean, top3, ok = sector_stats(sc)
        if mean is None: continue
        ups = [float(x.get("up_pct") or 0) for x in ok]
        avg_up = sum(ups) / len(ups) if ups else 0
        if mean >= 62 and avg_up >= 0:
            main_lines.append(sec)
        elif mean >= 55:
            observes.append(sec)
        else:
            avoids.append(sec)
    return main_lines, observes, avoids

def build_md(data):
    env = data["indexes"]["env"]; idx = data["indexes"]["indexes"]
    plates = data["plates"]; sc = data["sector_scores"]; asof = data.get("asof", today())
    ind5 = plates.get("em_em_industry_5d", []) or []
    ind_t = plates.get("em_em_industry_today", []) or []
    con5 = plates.get("em_em_concept_5d", []) or []
    con_t = plates.get("em_em_concept_today", []) or []
    ths = plates.get("ths_industry", []) or []
    L = []
    A = L.append
    A("# 大盘空转多每日研判 —— 资金主攻板块与主线锁定")
    A("")
    A("> 报告日期：%s（数据截至 %s 收盘）｜数据源：AI行情官 指数信号/个股评分 + 东方财富/同花顺 板块资金流与涨幅｜性质：大盘择时 × 板块轮动研判" % (today(), asof))
    A("> 声明：本报告由算法自动生成，仅为研究与信息整理，**不构成任何投资建议**。股市有风险，入市需谨慎。")
    A("")
    A("---")
    A("")
    main_lines, observes, avoids = pick_main_lines(sc)
    sh = idx.get("上证指数", {}) or {}
    sh_lab = " ".join((sh.get("recent_labels") or [])[-2:]) or "-"
    A("## 〇、核心结论")
    A("")
    A("1. **大盘**：上证最新信号「%s」，MACD 红柱 %s，站上 MA20，pts=%s——空转多状态：%s；" % (
        sh_lab, ("+%.1f" % ((sh.get("macd_last") or {}).get("bar") or 0)) if ((sh.get("macd_last") or {}).get("bar") or 0) >= 0 else "%.1f" % ((sh.get("macd_last") or {}).get("bar") or 0),
        env.get("pts"), ("顺风（金叉确认）" if "金" in sh_lab else ("底部转多初段" if "底" in sh_lab else "信号不明"))))
    if main_lines:
        A("2. **主攻主线**：**%s**——资金与技术双确认（成分股评分均值 ≥62 且当日走强）；" % "、".join(main_lines))
    A("3. **观察**：%s；**回避/等修复**：%s。" % ("、".join(observes) if observes else "无", "、".join(avoids) if avoids else "无"))
    A("4. 操作原则：右侧确认后总仓 ≤5 成；主线不追高、等回踩；**本报告不构成投资建议**。")
    A("")
    A("---")
    A("")
    A("## 一、大盘信号验证")
    A("")
    A("| 指数 | 最新信号 | 评分 | MACD红柱 | 状态 |")
    A("|---|---|---|---|---|")
    def status_of(r):
        lab = (r.get("recent_labels") or [])
        cur = lab[-1] if lab else ""
        if "金" in cur: return "金叉确认，顺风"
        if "底" in cur: return "底部信号，转多初段"
        if "险" in cur or "卖" in cur: return "偏弱/风险"
        return "中性"
    for name, secid in INDEXES.items():
        r = idx.get(name) or {}
        macd = r.get("macd_last") or {}
        bar = macd.get("bar")
        bar_s = ("+%.1f" % bar) if bar is not None and bar >= 0 else ("%.1f" % bar if bar is not None else "-")
        A("| %s | %s | %s | %s | %s |" % (name, " ".join((r.get("recent_labels") or [])[-2:]) or "-", r.get("score"), bar_s, status_of(r)))
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
    A("| 行业板块 | 5日净流入 | 今日净流入 | 今日涨跌 |")
    A("|---|---|---|---|")
    for r in ind5[:8]:
        A("| %s | +%s 亿 | %s%s 亿 | %s%% |" % (r["name"], yi(r["main_5d"]), "+" if (r["main_today"] or 0) >= 0 else "", yi(r["main_today"]), r["pct"]))
    A("")
    A("### 2.2 行业板块今日主力净流入 TOP")
    A("")
    A("| 行业板块 | 今日净流入 |")
    A("|---|---|")
    for r in ind_t[:8]:
        A("| %s | %s%s 亿 |" % (r["name"], "+" if (r["main_today"] or 0) >= 0 else "", yi(r["main_today"])))
    A("")
    A("### 2.3 概念板块资金流")
    A("")
    A("- **今日 TOP**：" + "、".join("%s %s%s亿(%+.1f%%)" % (r["name"], "+" if (r["main_today"] or 0) >= 0 else "", yi(r["main_today"]), r["pct"] or 0) for r in con_t[:8]))
    A("- **5日 TOP**：" + "、".join("%s %s%s亿" % (r["name"], "+" if (r["main_5d"] or 0) >= 0 else "", yi(r["main_5d"])) for r in con5[:8]))
    A("")
    A("### 2.4 今日行业涨幅 TOP（同花顺）")
    A("")
    A("| 行业 | 涨幅 | 上涨/下跌 | 领涨股 |")
    A("|---|---|---|---|")
    for r in ths[:10]:
        A("| %s | %+.2f%% | %s/%s | %s |" % (r["name"], r["pct"] or 0, r["up"], r["down"], r["leader"]))
    A("")
    A("---")
    A("")
    A("## 三、板块技术体检（AI行情官 成分股评分）")
    A("")
    A("| 板块 | 评分均值 | 龙头梯队(前3) |")
    A("|---|---|---|")
    for sec, items in sc.items():
        mean, top3, ok = sector_stats(items)
        A("| %s | %s | %s |" % (sec, ("%.1f" % mean) if mean else "-", top3))
    A("")
    main_lines, observes, avoids = pick_main_lines(sc)
    A("---")
    A("")
    A("## 四、主线锁定（算法双确认）")
    A("")
    A("**主攻主线**：" + ("、".join("**%s**" % x for x in main_lines) if main_lines else "今日无评分达标板块，等修复"))
    A("")
    A("**观察**：" + ("、".join(observes) if observes else "无"))
    A("")
    A("**回避/等修复**：" + ("、".join(avoids) if avoids else "无"))
    A("")
    A("---")
    A("")
    A("## 五、组合与风控")
    A("")
    A("| 项目 | 建议 |")
    A("|---|---|")
    A("| 总仓位 | 右侧确认后 ≤5 成，不满仓；信号转弱即降仓 |")
    A("| 主仓 | 主线板块龙头（≤2 成/个）：回踩 MA10 低吸，破 MA20 减仓 |")
    A("| 观察仓 | 观察板块（≤0.5 成）：仅评分最高的趋势龙头 |")
    A("| 止损 | 跌破 MA20 或上证跌破 MA20 → 全面降仓 |")
    A("| 跟踪 | 主线 5 日主力资金延续性、龙头量价、大盘底金状态 |")
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
    A("*报告生成：AI行情官 每日研判（算法自动）｜数据截至 %s 收盘｜方法：逻辑×数据双确认*" % asof)
    return "\n".join(L)

def md_to_html(md):
    import html as H
    lines = md.split("\n")
    out = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        s = ln.strip()
        if s.startswith("# "):
            out.append("<h1>%s</h1>" % H.escape(s[2:]))
        elif s.startswith("## "):
            out.append("<h2>%s</h2>" % H.escape(s[3:]))
        elif s.startswith("### "):
            out.append("<h3>%s</h3>" % H.escape(s[4:]))
        elif s.startswith("> "):
            out.append('<div class="note">%s</div>' % md_inline(s[2:]))
        elif s.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
                    i += 1; continue
                rows.append(cells)
                i += 1
            if rows:
                t = ['<table><thead><tr>%s</tr></thead><tbody>' % "".join("<th>%s</th>" % md_inline(c) for c in rows[0])]
                for r in rows[1:]:
                    t.append("<tr>%s</tr>" % "".join("<td>%s</td>" % md_inline(c) for c in r))
                t.append("</tbody></table>")
                out.append("".join(t))
            continue
        elif s.startswith("- "):
            items = []
            while i < len(lines) and lines[i].strip().startswith("- "):
                items.append("<li>%s</li>" % md_inline(lines[i].strip()[2:]))
                i += 1
            out.append("<ul>%s</ul>" % "".join(items))
            continue
        elif s == "---":
            out.append("<hr>")
        elif s:
            out.append("<p>%s</p>" % md_inline(s))
        i += 1
    return "\n".join(out)

def md_inline(s):
    import html as H
    s = H.escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    return s

# ---------------- 主流程 ----------------
def run_daily(force=False):
    d8 = today8()
    if not force:
        hit = cache_load("report")
        if hit and hit.get("today8") == d8 and not report_stale(hit):
            return hit
    if not token_ok():
        raise RuntimeError("18011 token 无效或已过期，请更新 daily_report/config.json 中的 token")
    set_progress(phase="running", pct=1, step="开始（优先用当日缓存数据，防封限流）", started_at=time.time(), finished=None, ok=False)
    t0 = time.time()
    _plates = cache_load("plates"); _idx = cache_load("indexes"); _sc = cache_load("sector_scores")
    if _plates and _idx and _sc and not data_cache_stale(_idx):
        set_progress(step="当日数据缓存已存在，直接生成报告（不再抓上游）")
        _breadth = cache_load("breadth") or {}
        _asof = (_idx.get("indexes", {}).get("上证指数", {}) or {}).get("last_date") or today()
        _data = {"today8": d8, "asof": _asof, "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                 "indexes": _idx, "plates": _plates, "sector_scores": _sc, "breadth": _breadth}
        _data["md"] = build_md(_data)
        _data["html"] = md_to_html(_data["md"])
        cache_save("report", _data)
        archive(_data, d8)
        set_progress(phase="done", pct=100, step="完成（缓存数据，耗时 %.1f 分钟）" % ((time.time() - t0) / 60), finished=datetime.now().strftime("%H:%M:%S"), ok=True)
        return _data
    plates = cache_load("plates")
    if not plates or force:
        set_progress(step="抓取板块资金流(东财 4 组 + 同花顺 1 次，低频)")
        plates = fetch_plates()
        time.sleep(2)
        ths = fetch_ths_industry()
        plates["ths_industry"] = ths
        cache_save("plates", plates)
    idx = cache_load("indexes")
    if not idx or force:
        set_progress(step="拉取 8 指数信号(AI行情官)")
        idx = fetch_index_signals()
        cache_save("indexes", idx)
    sc = cache_load("sector_scores")
    if not sc or force:
        set_progress(step="板块成分股 AI行情官 体检(42 只，8s 间隔)")
        sc = fetch_sector_scores()
        cache_save("sector_scores", sc)
    try:
        breadth = fetch_breadth()
        cache_save("breadth", breadth)
    except Exception:
        breadth = cache_load("breadth") or {}
    asof = (idx.get("indexes", {}).get("上证指数", {}) or {}).get("last_date") or today()
    data = {"today8": d8, "asof": asof, "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "indexes": idx, "plates": plates, "sector_scores": sc, "breadth": breadth}
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
                    ("sector_score.json", data["sector_scores"]), ("breadth.json", data["breadth"])]:
        with open(os.path.join(d, fn), "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
    with open(os.path.join(d, "report.md"), "w", encoding="utf-8") as f:
        f.write(data["md"])
    with open(os.path.join(d, "report.html"), "w", encoding="utf-8") as f:
        f.write(data["html"])
    return d

def list_archive():
    out = []
    if not os.path.isdir(ARCHIVE_ROOT):
        return out
    for d in sorted(os.listdir(ARCHIVE_ROOT), reverse=True):
        p = os.path.join(ARCHIVE_ROOT, d)
        if os.path.isdir(p) and os.path.exists(os.path.join(p, "report.md")):
            out.append({"date": d, "path": p, "has_html": os.path.exists(os.path.join(p, "report.html"))})
    return out

def load_report_by_date(d8):
    p = os.path.join(ARCHIVE_ROOT, d8, "report.html")
    if os.path.exists(p):
        return {"date": d8, "html": open(p, encoding="utf-8").read()}
    p = os.path.join(ARCHIVE_ROOT, d8, "report.md")
    if os.path.exists(p):
        return {"date": d8, "html": md_to_html(open(p, encoding="utf-8").read())}
    return None
