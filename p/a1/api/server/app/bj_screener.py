# -*- coding: utf-8 -*-
"""
北证掘金 VIP 扫描器（服务端版，算法不暴露到前端）。

由独立页 web/bj/index.html v1.1 算法搬移而来，产品化后的差异：
- 全部形态算法 / 评分 / 主线判断在服务端执行，前端只展示接口返回结果；
- VIP 专属：路由层拦截非 VIP，本模块不再重复鉴权；
- 主线反推：不再只依赖板块 5 日涨幅榜，改为“先看哪些北证标的在底部异动，
  再按行业聚合反推热门主线板块”，与东财板块榜交叉验证；
- 数据源：K线统一走 fetch_tx_kline（VIP 付费源优先 paid_first，
  TuShare 配置后自动生效，未配置时回落腾讯/东财/新浪），与 /api/kline 同策略。

仅供研究参考，不构成投资建议。
"""
from __future__ import annotations

import asyncio
import json
import math
import os
import re
import time
from typing import Any

import httpx

from .providers import fetch_em_suggest, fetch_tx_kline, market_data_status

EM_HOSTS = ["https://push2delay.eastmoney.com", "https://push2.eastmoney.com"]
EM_LIST_FIELDS = "f12,f14,f2,f3,f5,f6,f8,f9,f10,f20,f21,f23,f62,f100"
_UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

DEFAULT_CFG: dict[str, Any] = {
    "mcapMin": 5.0,      # 市值下限（亿）
    "mcapMax": 40.0,     # 市值上限（亿）
    "amountMin": 3000.0, # 最低成交额（万）
    "posMax": 30.0,      # 60日位置上限 %
    "max5d": 20.0, "max10d": 30.0, "max20d": 30.0, "max60d": 45.0,
    "aiMin": 60.0, "topN": 5, "cap": 60, "aiTop": 12, "aiOk": True,
    "kw": "", "minSurge": 4.0, "surgeVol": 1.8, "surgeDays": 15,
    "mainline": "score", "hotPct": 4.0, "hotN": 12,
    "turnMin": 2.0, "turnMax": 20.0, "useFund": True,
    # 全市场（沪深京）参数：板块先行两阶段筛选
    "mcapMinAll": 15.0, "mcapMaxAll": 200.0, "amountMinAll": 8000.0,
    "hotBoards": 20, "memberCap": 800, "allBackupN": 4,
    # 主线龙头层（板块确认后放宽市值/位置约束）与补涨卡位层
    "leaderBoards": 3, "leaderPerBoard": 3, "leaderMcapMax": 5000.0,
    "catchupMcapMin": 50.0, "catchupMcapMax": 300.0,
    "catchupChg5Max": 15.0, "catchupPosMax": 0.40,
}

# 扫描结果缓存：同自然日重复请求直接返回（force=1 强制重扫）
_SCAN_CACHE: dict[str, tuple[float, dict]] = {}

# 扫描历史持久化：当日无合格标的（如盘前数据未更新）时回退展示最近一次有结果的扫描
_HIST_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "data", "bj_scan_history.json"
)


# 板块 secid 解析缓存（板块名 → 东财 90.BKxxxx，24h）
_BOARD_SECID_CACHE: dict[str, tuple[float, str]] = {}
_BOARD_SECID_TTL = 24 * 3600

# 当日扫描结果磁盘持久化：进程重启后仍可复用，减少上游请求
_DAILY_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "data", "bj_scan_daily.json"
)

# K线当日磁盘缓存目录（按交易日存储，带 30 分钟有效期）
_KLINE_CACHE_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "data", "bj_kline_cache"
)
_KLINE_TTL = 30 * 60

# 历史归档目录：每日一档，保留最近 90 天
_ARCHIVE_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "data", "bj_archive"
)
_ARCHIVE_KEEP_DAYS = 90

# 强制重扫最小间隔（秒）：防止高频重扫打爆上游行情源
_FORCE_MIN_INTERVAL = 120.0
_LAST_FULL_SCAN_TS: float = 0.0

# 非 VIP“异动板块”视图独立缓存（当日）
_BOARDS_CACHE: dict[str, tuple[float, dict]] = {}


def _load_history() -> dict[str, Any]:
    try:
        if not os.path.exists(_HIST_PATH):
            return {}
        with open(_HIST_PATH, "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _save_history(key: str, payload: dict[str, Any]) -> None:
    try:
        hist = _load_history()
        hist[str(key)] = payload
        while len(hist) > 12:
            hist.pop(next(iter(hist)))
        os.makedirs(os.path.dirname(_HIST_PATH), exist_ok=True)
        tmp = _HIST_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(hist, f, ensure_ascii=False)
        os.replace(tmp, _HIST_PATH)
    except Exception:
        pass


def _latest_history(market: str = "bj") -> dict[str, Any] | None:
    """返回最近一次有标的（picks 非空）的扫描结果（按市场隔离）。"""
    hist = _load_history()
    prefix = str(market or "bj") + ":"
    for key in reversed(list(hist.keys())):
        # 兼容旧版无市场前缀的归档
        if key.startswith(prefix) or ":" not in key:
            v = hist.get(key)
            if isinstance(v, dict) and v.get("picks"):
                return v
    return None


# ---------------- 持久化与缓存工具 ----------------

def _load_json_file(path: str, default: Any) -> Any:
    try:
        if not os.path.exists(path):
            return default
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save_json_file(path: str, obj: Any) -> None:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception:
        pass


def _load_daily_scan_cache() -> None:
    """启动时加载当日扫描结果磁盘缓存到内存。"""
    try:
        d = _load_json_file(_DAILY_PATH, {})
        if not isinstance(d, dict):
            return
        for k, v in d.items():
            if not (isinstance(k, str) and isinstance(v, dict)):
                continue
            ts = float(v.get("ts") or 0)
            payload = v.get("payload")
            if isinstance(payload, dict):
                _SCAN_CACHE[k] = (ts, payload)
    except Exception:
        pass


def _persist_daily_scan_cache() -> None:
    out: dict[str, Any] = {}
    for k, (ts, payload) in _SCAN_CACHE.items():
        out[k] = {"ts": ts, "payload": payload}
    _save_json_file(_DAILY_PATH, out)


# K线当日磁盘缓存（减少对腾讯/东财/付费源的重复请求）
_KLINE_DAILY: dict[str, Any] = {"date": "", "data": {}, "ts": {}}


def _kline_cache_path(date8: str) -> str:
    return os.path.join(_KLINE_CACHE_DIR, str(date8) + ".json")


def _kline_cache_get(date8: str, code: str) -> list[list[Any]] | None:
    global _KLINE_DAILY
    if _KLINE_DAILY.get("date") != date8:
        _KLINE_DAILY = {
            "date": date8,
            "data": _load_json_file(_kline_cache_path(date8), {}),
            "ts": {},
        }
    rows = _KLINE_DAILY["data"].get(code)
    ts = float(_KLINE_DAILY.get("ts", {}).get(code) or 0)
    if isinstance(rows, list) and rows and (time.time() - ts) < _KLINE_TTL:
        return rows
    return None


def _kline_cache_put(date8: str, code: str, rows: list[list[Any]]) -> None:
    global _KLINE_DAILY
    if _KLINE_DAILY.get("date") != date8:
        _KLINE_DAILY = {
            "date": date8,
            "data": _load_json_file(_kline_cache_path(date8), {}),
            "ts": {},
        }
    _KLINE_DAILY["data"][code] = rows
    _KLINE_DAILY["ts"][code] = time.time()


def _kline_cache_flush() -> None:
    try:
        if _KLINE_DAILY.get("data"):
            _save_json_file(_kline_cache_path(str(_KLINE_DAILY["date"])), _KLINE_DAILY["data"])
    except Exception:
        pass


# ---------------- 历史归档 ----------------

def _archive_path(market: str, date_key: str) -> str:
    return os.path.join(_ARCHIVE_DIR, f"{date_key}-{str(market or 'bj')}.json")


def _save_archive(market: str, date_key: str, payload: dict[str, Any]) -> None:
    """每日归档（含同日多版本保护）：已有主版本时改存 {date}-{market}-{HHMM}.json，避免 force 重扫覆盖历史。"""
    try:
        if not _MULTI_ARCH_RE.match(str(date_key or "")):
            main = _archive_path(market, date_key)
            if os.path.exists(main):
                now = time.strftime("%H%M", time.localtime())
                date_key = f"{str(date_key)} ({now[:2]}:{now[2:]})"
        target = _multi_archive_path(market, date_key) or _archive_path(market, date_key)
        _save_json_file(target, payload)
        try:
            if os.path.isdir(_ARCHIVE_DIR):
                names = sorted(n for n in os.listdir(_ARCHIVE_DIR) if n.endswith(".json"))
                if len(names) > _ARCHIVE_KEEP_DAYS:
                    for nm in names[: len(names) - _ARCHIVE_KEEP_DAYS]:
                        try:
                            os.remove(os.path.join(_ARCHIVE_DIR, nm))
                        except Exception:
                            pass
        except Exception:
            pass
    except Exception:
        pass


_MULTI_ARCH_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}) \((\d{2}):(\d{2})\)$")


def _multi_archive_path(market: str, date_key: str) -> str | None:
    """同日多版本归档：date_key 形如 "2026-08-07 (15:27)"，文件名为 {date}-{market}-{HHMM}.json。"""
    m = _MULTI_ARCH_RE.match(str(date_key or ""))
    if not m:
        return None
    return os.path.join(_ARCHIVE_DIR, f"{m.group(1)}-{str(market or 'bj')}-{m.group(2)}{m.group(3)}.json")


def load_archive(market: str, date_key: str) -> dict[str, Any] | None:
    market = str(market or "bj")
    mp = _multi_archive_path(market, date_key)
    if mp:
        d = _load_json_file(mp, None)
        if isinstance(d, dict):
            return d
        m = _MULTI_ARCH_RE.match(str(date_key or ""))
        if m:
            date_key = m.group(1)
    d = _load_json_file(_archive_path(market, date_key), None)
    if not isinstance(d, dict) and market == "bj":
        # 兼容旧版无市场后缀的归档
        d = _load_json_file(os.path.join(_ARCHIVE_DIR, f"{date_key}.json"), None)
    return d if isinstance(d, dict) else None




def archive_summary(market: str = "bj") -> list[dict[str, Any]]:
    """最近归档日期摘要（含主推代码/名称），供历史归档选择器使用（按市场隔离）。"""
    market = str(market or "bj")
    out: list[dict[str, Any]] = []
    try:
        if not os.path.isdir(_ARCHIVE_DIR):
            return out
        names = sorted((n for n in os.listdir(_ARCHIVE_DIR) if n.endswith(".json")), reverse=True)
        seen: set[str] = set()
        for nm in names[:_ARCHIVE_KEEP_DAYS]:
            stem = nm[:-5]
            is_all_new = stem.endswith("-all")
            is_bj_new = stem.endswith("-bj")
            # 同日多版本：{date}-{market}-{HHMM}.json → date_key 显示为 "2026-08-07 (15:27)"
            mm = re.match(r"^(\d{4}-\d{2}-\d{2})-(all|bj)-(\d{4})$", stem)
            if mm:
                if market == "all":
                    if mm.group(2) != "all":
                        continue
                else:
                    if mm.group(2) != "bj":
                        continue
                date_key = f"{mm.group(1)} ({mm.group(3)[:2]}:{mm.group(3)[2:]})"
                is_all_new = mm.group(2) == "all"
                is_bj_new = mm.group(2) == "bj"
            elif market == "all":
                if not is_all_new:
                    continue
                date_key = stem[:-4]
            else:
                if is_all_new:
                    continue
                date_key = stem[:-3] if is_bj_new else stem
            if date_key in seen:
                # 新版带市场后缀文件优先（与打开时 load_archive 读取的文件一致）
                if is_bj_new or is_all_new:
                    out = [x for x in out if x.get("date") != date_key]
                else:
                    continue
            seen.add(date_key)
            d = _load_json_file(os.path.join(_ARCHIVE_DIR, nm), None)
            if not isinstance(d, dict):
                continue
            picks = d.get("picks") or []
            out.append({
                "date": date_key,
                "asof": d.get("asof") or str(nm[:-5]),
                "total": d.get("total"),
                "fine": d.get("fine"),
                "picks": [
                    {
                        "code": p.get("code"), "name": p.get("name"),
                        "tier": p.get("tier") or "normal",
                        "final": p.get("final"), "price": p.get("price"), "pct": p.get("pct"),
                    }
                    for p in picks[:4] if isinstance(p, dict)
                ],
            })
    except Exception:
        pass
    return out


def _apply_stale_fallback(result: dict[str, Any], market: str = "bj") -> dict[str, Any]:
    """今日无合格标的时，回退展示上一交易日结果并打 stale 标记。"""
    if result.get("picks"):
        return result
    stale = _latest_history(market)
    if not stale:
        return result
    result["stale"] = True
    result["stale_from"] = stale.get("asof") or stale.get("date") or ""
    result["picks"] = stale.get("picks") or []
    result["runners"] = stale.get("runners") or []
    if not result.get("mainlines"):
        result["mainlines"] = stale.get("mainlines") or []
    return result


def _num(v: Any, d: float = 0.0) -> float:
    try:
        n = float(v)
        return n if math.isfinite(n) else d
    except Exception:
        return d


# ---------------- 数据源 ----------------

async def _em_get_json(path: str, params: dict[str, Any]) -> dict[str, Any] | None:
    last_err: Exception | None = None
    for host in EM_HOSTS:
        try:
            async with httpx.AsyncClient(timeout=12.0, headers=_UA) as cli:
                r = await cli.get(host + path, params=params)
                if r.status_code != 200:
                    continue
                j = r.json()
                if isinstance(j, dict):
                    return j
        except Exception as e:  # noqa: BLE001
            last_err = e
            continue
    if last_err is not None:
        raise last_err
    return None


async def fetch_bj_list() -> dict[str, Any]:
    """东财北证全市场列表（fid=f6 按成交额排序；单页最多 100 行，自动翻页取全量）。"""
    total = 0
    rows: list[dict[str, Any]] = []
    for pn in range(1, 8):
        params = {
            "pn": pn, "pz": 100, "po": 1, "np": 1, "fltt": 2, "invt": 2,
            "fid": "f6", "fs": "m:0+t:81+s:2048", "fields": EM_LIST_FIELDS,
        }
        try:
            j = await _em_get_json("/api/qt/clist/get", params) or {}
        except Exception:
            break
        data = j.get("data") or {}
        if not total:
            total = int(_num(data.get("total"), 0))
        diff = data.get("diff") or []
        if not isinstance(diff, list) or not diff:
            break
        rows.extend(diff)
        if total and len(rows) >= total:
            break
        if len(diff) < 100:
            break
    return {"total": total, "rows": rows[:total] if total else rows}


async def fetch_hot_sectors(cfg: dict[str, Any]) -> dict[str, Any]:
    """东财行业/概念板块 5 日涨幅榜（f109），用于与“主线反推”交叉验证。"""
    by_name: dict[str, float] = {}
    hot_list: list[dict[str, Any]] = []
    for t in (2, 3):  # 行业 / 概念
        params = {
            "pn": 1, "pz": 60, "po": 1, "np": 1, "fltt": 2, "invt": 2,
            "fid": "f109", "fs": f"m:90+t:{t}", "fields": "f12,f14,f109",
        }
        try:
            j = await _em_get_json("/api/qt/clist/get", params) or {}
        except Exception:
            continue
        data = j.get("data") or {}
        diff = data.get("diff") or []
        if not isinstance(diff, list):
            continue
        cnt = 0
        for r in diff:
            p5 = _num(r.get("f109"))
            if p5 >= float(cfg.get("hotPct", 4)) and cnt < int(cfg.get("hotN", 12)):
                nm = str(r.get("f14") or "").strip()
                if nm and nm not in by_name:
                    by_name[nm] = p5
                    hot_list.append({"name": nm, "p5": round(p5, 2)})
                    cnt += 1
    return {"byName": by_name, "list": hot_list}


# ---------------- 形态算法（服务端，与 web/bj 个人页同口径） ----------------

def _ema(arr: list[float], n: int) -> list[float]:
    out: list[float] = []
    k = 2 / (n + 1)
    prev: float | None = None
    for v in arr:
        if prev is None:
            prev = v
        else:
            prev = v * k + prev * (1 - k)
        out.append(prev)
    return out


def _ma_at(arr: list[float], p: int, i: int) -> float:
    if i + 1 < p or i < 0:
        return float("nan")
    return sum(arr[i + 1 - p: i + 1]) / p


def _norm_name(s: str) -> str:
    return re.sub(r"(板块|概念|行业|指数|及器件|及材料|及服务|产业链)$", "", str(s or ""))


def board_hit(ind: str, hot: dict[str, Any]) -> str:
    if not ind or ind == "-":
        return ""
    by_name = hot.get("byName") or {}
    if not by_name:
        return ""
    n = _norm_name(ind)
    if n in by_name or ind in by_name:
        return n if n in by_name else ind
    if len(n) >= 2:
        for nm in by_name:
            m = _norm_name(nm)
            if len(m) >= 2 and (m in n or n in m or n[:2] == m[:2]):
                return nm
    return ""


def coarse(row: dict[str, Any], cfg: dict[str, Any], hot: dict[str, Any]) -> dict[str, Any] | None:
    code = str(row.get("f12") or "")
    name = str(row.get("f14") or "")
    if not re.fullmatch(r"\d{6}", code):
        return None
    if re.search(r"ST|退", name):
        return None
    mcap = _num(row.get("f20"))
    amount = _num(row.get("f6"))
    if not (float(cfg["mcapMin"]) * 1e8 <= mcap <= float(cfg["mcapMax"]) * 1e8):
        return None
    if amount < float(cfg["amountMin"]) * 1e4:
        return None
    if _num(row.get("f3")) > 20:  # 当日已大涨直接排除
        return None
    ind = str(row.get("f100") or "").strip()
    hn = board_hit(ind, hot)
    kh: list[str] = []
    kw = str(cfg.get("kw") or "").strip()
    if kw:
        for k in re.split(r"[,，]", kw):
            k = k.strip()
            if k and k in name:
                kh.append(k)
    return {
        "code": code, "name": name,
        "price": _num(row.get("f2")), "pct": _num(row.get("f3")),
        "amount": amount, "mcap": mcap, "floatMcap": _num(row.get("f21")),
        "turnover": _num(row.get("f8")), "pe": _num(row.get("f9")),
        "pb": _num(row.get("f23")), "volRatio": _num(row.get("f10")),
        "fund": _num(row.get("f62")), "fundIn": _num(row.get("f62")), "ind": ind, "indCnt": 0,
        "hot": bool(hn), "hotName": hn, "kwHits": kh,
        "A": None, "snap": None, "final": None, "revHit": False, "revName": "",
    }


# ---------------- 全市场：板块先行两阶段抓取 ----------------

async def fetch_hot_boards_funds(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """东财行业/概念板块资金流榜（今日 f62 / 5日 f164 主力净流入）→ 热门板块池（含 BK secid）。"""
    out: dict[str, dict[str, Any]] = {}
    for fid, limit in (("f62", 16), ("f164", 16)):
        params = {
            "pn": 1, "pz": limit, "po": 1, "np": 1, "fltt": 2, "invt": 2,
            "fid": fid, "fs": "m:90+t:2", "fields": "f12,f14,f62,f164,f184,f3,f109",
        }
        try:
            j = await _em_get_json("/api/qt/clist/get", params) or {}
        except Exception:
            continue
        for r in ((j.get("data") or {}).get("diff") or []):
            nm = str(r.get("f14") or "").strip()
            bk = str(r.get("f12") or "").strip()
            if not nm or not bk.startswith("BK"):
                continue
            e = out.setdefault(nm, {
                "name": nm, "secid": "90." + bk, "f62": 0.0, "f164": 0.0,
                "p5": None, "pct": None, "kind": "industry",
            })
            e["f62"] = max(float(e.get("f62") or 0), _num(r.get("f62")))
            e["f164"] = max(float(e.get("f164") or 0), _num(r.get("f164")))
            if e.get("p5") is None:
                e["p5"] = _num(r.get("f109")) if r.get("f109") is not None else None
            if e.get("pct") is None:
                e["pct"] = _num(r.get("f3")) if r.get("f3") is not None else None
    # 概念板块：5日主力净流入（剔除泛概念，避免“融资融券/昨日涨停”等噪音）
    try:
        j = await _em_get_json("/api/qt/clist/get", {
            "pn": 1, "pz": 14, "po": 1, "np": 1, "fltt": 2, "invt": 2,
            "fid": "f164", "fs": "m:90+t:3", "fields": "f12,f14,f62,f164,f184,f3,f109",
        }) or {}
    except Exception:
        j = {}
    skip_terms = ("融资融券", "昨日", "富时", "标普", "MSCI", "机构重仓", "深股通", "沪股通", "中证", "转债", "ST", "预盈预增", "预亏预减", "转融券", "百元股", "风格", "成分", "样本", "微盘股", "大盘股", "中盘股", "小盘股", "低价股", "高价股", "破净", "活跃")
    for r in ((j.get("data") or {}).get("diff") or []):
        nm = str(r.get("f14") or "").strip()
        bk = str(r.get("f12") or "").strip()
        if not nm or not bk.startswith("BK"):
            continue
        if any(k in nm for k in skip_terms):
            continue
        e = out.setdefault(nm, {
            "name": nm, "secid": "90." + bk, "f62": 0.0, "f164": 0.0,
            "p5": None, "pct": None, "kind": "concept",
        })
        e["f62"] = max(float(e.get("f62") or 0), _num(r.get("f62")))
        e["f164"] = max(float(e.get("f164") or 0), _num(r.get("f164")))
        if e.get("p5") is None:
            e["p5"] = _num(r.get("f109")) if r.get("f109") is not None else None
    items = sorted(out.values(), key=lambda x: -float(x.get("f164") or 0))
    return items[:20]


async def fetch_board_members(
    boards: list[dict[str, Any]], cap: int = 800
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    """对热门板块拉成分股（东财 clist fs=b:BKxxxx），双路合并去重：
    ① fid=f6 成交额头部（板块活跃核心）；② fid=f3 当日涨幅头部
    （捕捉“底部刚走强/异动”但成交额尚未放大的标的）。
    总候选控制在 cap 以内，避免 K线精筛阶段请求过多。
    返回 (rows, leaders)：leaders 为每板块成交额前 3 的成分股（供板块排行展示龙头参考）。
    """
    boards = boards or []
    rows: dict[str, dict[str, Any]] = {}
    leaders: dict[str, list[dict[str, Any]]] = {}
    per = max(20, cap // max(1, len(boards)))
    per_rise = max(10, per // 2)

    def _add_rows(diff: list[Any], board_rows: dict[str, dict[str, Any]]) -> int:
        got = 0
        for r in diff:
            code = str(r.get("f12") or "")
            if not re.fullmatch(r"\d{6}", code):
                continue
            if code not in board_rows:
                board_rows[code] = r
            if code not in rows:
                rows[code] = r
                got += 1
        return got

    for b in boards:
        bname = str(b.get("name") or "").strip()
        bk = str(b.get("secid") or "").replace("90.", "").strip()
        if not bk or not bk.startswith("BK"):
            continue
        board_rows: dict[str, dict[str, Any]] = {}
        # 路1：成交额头部（1~2 页，至 per 只）
        got = 0
        for pn in (1, 2):
            params = {
                "pn": pn, "pz": 200, "po": 1, "np": 1, "fltt": 2, "invt": 2,
                "fid": "f6", "fs": "b:" + bk,
                "fields": "f12,f14,f2,f3,f6,f8,f9,f10,f20,f21,f23,f62,f100,f164",
            }
            try:
                j = await _em_get_json("/api/qt/clist/get", params) or {}
            except Exception:
                break
            data = j.get("data") or {}
            diff = data.get("diff") or []
            if not isinstance(diff, list) or not diff:
                break
            got += _add_rows(diff, board_rows)
            total = int(_num(data.get("total")))
            if len(diff) < 200 or got >= per or len(rows) >= cap:
                break
            await asyncio.sleep(0.12)
        # 路2：当日涨幅头部（1 页，至 per_rise 只）——捕捉底部刚异动、成交额尚未放大者
        if len(rows) < cap:
            try:
                await asyncio.sleep(0.12)
                j2 = await _em_get_json("/api/qt/clist/get", {
                    "pn": 1, "pz": 200, "po": 1, "np": 1, "fltt": 2, "invt": 2,
                    "fid": "f3", "fs": "b:" + bk,
                    "fields": "f12,f14,f2,f3,f6,f8,f9,f10,f20,f21,f23,f62,f100,f164",
                }) or {}
            except Exception:
                j2 = {}
            diff2 = ((j2.get("data") or {}).get("diff") or [])
            if isinstance(diff2, list) and diff2:
                _add_rows(diff2, board_rows)
        if bname and board_rows:
            top = sorted(board_rows.values(), key=lambda x: -_num(x.get("f6")))[:3]
            leaders[bname] = [{
                "code": str(r.get("f12") or ""),
                "name": str(r.get("f14") or ""),
                "pct": _num(r.get("f3")),
                "amount": _num(r.get("f6")),
                "mcap": _num(r.get("f20")),
                "turnover": _num(r.get("f8")),
                "fund": _num(r.get("f62")),
                "fund5": _num(r.get("f164")),
                "_row": r,
            } for r in top]
        if len(rows) >= cap:
            break
    return list(rows.values())[:cap], leaders


async def _collect_candidates(
    cfg: dict[str, Any], market: str
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]] | None, int, list[dict[str, Any]]]:
    """收集候选池：bj=北证全市场；all=板块先行两阶段（资金流榜→成分股粗筛）。返回 (cands, hot, board_pool, total, rows_all)。"""
    if market == "all":
        funds_task = asyncio.create_task(fetch_hot_boards_funds(cfg))
        hot5_task = asyncio.create_task(fetch_hot_sectors(cfg))
        funds = await funds_task
        hot5 = await hot5_task
        by_name: dict[str, float] = dict(hot5.get("byName") or {})
        for b in funds:
            nm = str(b.get("name") or "")
            if nm and nm not in by_name:
                by_name[nm] = float(b.get("p5") or 0)
        hot: dict[str, Any] = {"byName": by_name, "list": hot5.get("list") or []}
        boards = funds[: int(cfg.get("hotBoards") or 12)]
        rows, leaders = await fetch_board_members(boards, int(cfg.get("memberCap") or 400))
        for b in funds:
            nm = str(b.get("name") or "")
            if nm and nm in leaders:
                b["leaders"] = leaders[nm]
        ind_count: dict[str, int] = {}
        for row in rows:
            _ind = str(row.get("f100") or "").strip()
            if _ind:
                ind_count[_ind] = ind_count.get(_ind, 0) + 1
        cands: list[dict[str, Any]] = []
        for row in rows:
            c = coarse(row, cfg, hot)
            if c:
                c["indCnt"] = ind_count.get(c.get("ind") or "", 0)
                cands.append(c)
        return cands, hot, funds, len(rows), rows
    # 北证全市场
    lst_task = asyncio.create_task(fetch_bj_list())
    hot_task = asyncio.create_task(fetch_hot_sectors(cfg))
    lst = await lst_task
    hot = await hot_task
    ind_count = {}
    for row in lst.get("rows") or []:
        _ind = str(row.get("f100") or "").strip()
        if _ind:
            ind_count[_ind] = ind_count.get(_ind, 0) + 1
    cands = []
    for row in lst.get("rows") or []:
        c = coarse(row, cfg, hot)
        if c:
            c["indCnt"] = ind_count.get(c.get("ind") or "", 0)
            cands.append(c)
    return cands, hot, None, int(lst.get("total") or 0), []


def analyze(bars: list[list[Any]], cand: dict[str, Any], cfg: dict[str, Any], market: str = "bj") -> dict[str, Any]:
    n = len(bars)
    o = [float(b[1]) for b in bars]
    c = [float(b[2]) for b in bars]
    h = [float(b[3]) for b in bars]
    l = [float(b[4]) for b in bars]
    v = [float(b[5]) for b in bars]
    e12 = _ema(c, 12)
    e26 = _ema(c, 26)
    dif = [e12[i] - e26[i] for i in range(n)]
    dea = _ema(dif, 9)
    hist = [(dif[i] - dea[i]) * 2 for i in range(n)]
    last = n - 1
    cl = c[last]
    ma5 = _ma_at(c, 5, last)
    ma10 = _ma_at(c, 10, last)
    ma20 = _ma_at(c, 20, last)
    ma60 = _ma_at(c, 60, last)
    ma6 = _ma_at(c, 6, last)
    ma12 = _ma_at(c, 12, last)
    ma20_3 = _ma_at(c, 20, last - 3)
    lo60 = min(l[n - 60:])
    hi60 = max(h[n - 60:])
    pos = (cl - lo60) / (hi60 - lo60) if hi60 > lo60 else 1.0
    chg1 = (cl / c[last - 1] - 1) * 100 if c[last - 1] > 0 else 0.0
    chg5 = (cl / c[last - 5] - 1) * 100 if c[last - 5] > 0 else 0.0
    chg10 = (cl / c[last - 10] - 1) * 100 if c[last - 10] > 0 else 0.0
    chg20 = (cl / c[last - 20] - 1) * 100 if c[last - 20] > 0 else 0.0
    chg60 = (cl / c[last - 60] - 1) * 100 if c[last - 60] > 0 else 0.0
    v20 = sum(v[last - 19: last + 1]) / 20
    vol_ratio = v[last] / v20 if v20 > 0 else 0.0
    v5 = sum(v[last - 4: last + 1]) / 5
    vol5v20 = v5 / v20 if v20 > 0 else 0.0
    up_days = 0
    max_day_pct = 0.0
    for i in range(last - 4, last + 1):
        if c[i] >= o[i]:
            up_days += 1
        p0 = (c[i] / c[i - 1] - 1) * 100 if c[i - 1] > 0 else 0.0
        if p0 > max_day_pct:
            max_day_pct = p0

    # ---- 新增技术因子 ----
    def _rsi_wilder(arr: list[float], period: int = 14) -> float:
        gains: list[float] = []
        losses: list[float] = []
        for i in range(1, len(arr)):
            d = arr[i] - arr[i - 1]
            gains.append(d if d > 0 else 0.0)
            losses.append(-d if d < 0 else 0.0)
        if len(gains) <= period:
            return 50.0
        ag = sum(gains[:period]) / period
        al = sum(losses[:period]) / period
        for i in range(period, len(gains)):
            ag = (ag * (period - 1) + gains[i]) / period
            al = (al * (period - 1) + losses[i]) / period
        if al == 0:
            return 100.0
        return 100 - 100 / (1 + ag / al)

    rsi14 = _rsi_wilder(c)
    sd20 = (sum((c[i] - ma20) ** 2 for i in range(last - 19, last + 1)) / 20) ** 0.5
    boll_up = ma20 + 2 * sd20
    boll_dn = ma20 - 2 * sd20
    boll_pos = (cl - boll_dn) / (boll_up - boll_dn) if boll_up > boll_dn else 0.5
    boll_width = (boll_up - boll_dn) / ma20 * 100 if ma20 else 0.0
    trs: list[float] = []
    for i in range(last - 13, last + 1):
        trs.append(max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])))
    atr = sum(trs) / 14
    atr_pct = atr / cl * 100 if cl else 0.0
    bias6 = (cl - ma6) / ma6 * 100 if ma6 else 0.0
    bias12 = (cl - ma12) / ma12 * 100 if ma12 else 0.0
    ma_bull = bool(ma5 > ma10 > ma20 > ma60)
    ma_bull3 = bool(ma5 > ma10 > ma20)
    gc_days = 0
    for i in range(last, -1, -1):
        if dif[i] > dea[i]:
            gc_days += 1
        else:
            break

    fund = _num(cand.get("fundIn") if cand.get("fundIn") is not None else cand.get("fund"))
    patterns: dict[str, int] = {}
    risks: list[str] = []
    # 底部走多：站上MA20 + MA20上拐 + MA5>MA10 + MACD红柱
    if cl > ma20 and ma20 > ma20_3 and ma5 > ma10 and hist[last] > 0:
        patterns["baseUp"] = 1
    # 异动拉升一小波后回踩企稳
    pulled = False
    for i in range(n - 13, last - 1):
        pcti = (c[i] / c[i - 1] - 1) * 100 if c[i - 1] > 0 else 0.0
        if pcti >= 5 and v[i] >= 1.5 * v20:
            for j in range(i + 1, last + 1):
                ok_pull = (
                    l[j] < h[i]
                    and v[j] < v[i] * 0.9
                    and l[j] >= l[i] * 0.97
                    and cl >= max(c[i], c[j]) * 0.97
                    and cl >= ma10
                )
                if ok_pull:
                    pulled = True
                    break
            if pulled:
                break
    if pulled:
        patterns["pullback"] = 1
    # 一路小阳
    if up_days >= 3 and max_day_pct <= 8 and 0 <= chg5 <= 18:
        patterns["smallYang"] = 1
    # 底部放量异动启动（核心：刚底部异动起来）
    surge_days_ago = 0
    surge_idx = -1
    for i in range(max(1, n - int(cfg["surgeDays"]) - 1), last):
        pcti = (c[i] / c[i - 1] - 1) * 100 if c[i - 1] > 0 else 0.0
        v_ma = 0.0
        cnt_v = 0
        for k in range(i - 20, i):
            if k >= 0:
                v_ma += v[k]
                cnt_v += 1
        v_ma = v_ma / cnt_v if cnt_v else 0.0
        pos_at_i = (c[i] - lo60) / (hi60 - lo60) if hi60 > lo60 else 1.0
        if float(cfg["minSurge"]) <= pcti <= 14 and v[i] >= float(cfg["surgeVol"]) * v_ma and pos_at_i <= 0.5:
            surge_idx = i
    surge_ok = False
    if surge_idx >= 0:
        surge_days_ago = last - surge_idx
        if surge_days_ago <= int(cfg["surgeDays"]) and cl >= ma5 and cl >= c[surge_idx] * 0.97:
            surge_ok = True
    if surge_ok:
        patterns["surgeStart"] = 1
    if surge_idx >= 0 and not surge_ok:
        risks.append("底部异动后未确认企稳")
    # 均线粘合后发散（启动初期）
    spread = (max(ma5, ma10, ma20) - min(ma5, ma10, ma20)) / ma20 * 100 if ma20 else 0.0
    if spread <= 2.5 and ma5 > ma10 and ma10 > ma20 and hist[last] > 0:
        patterns["tightBurst"] = 1
    # 未大幅拉升 + 刚启动约束
    if chg5 <= float(cfg["max5d"]) and chg10 <= float(cfg["max10d"]):
        patterns["notHot"] = 1
    else:
        risks.append(f"涨幅偏大(5日{chg5:.1f}%)")
    if chg20 > float(cfg["max20d"]):
        risks.append(f"20日涨幅过大{chg20:.1f}%")
    if chg60 > float(cfg["max60d"]):
        risks.append(f"60日涨幅过大{chg60:.1f}%")
    if chg5 > float(cfg["max5d"]):
        risks.append(f"5日涨幅过大{chg5:.1f}%")
    if chg10 > float(cfg["max10d"]):
        risks.append(f"10日涨幅过大{chg10:.1f}%")
    has_zt = False
    for i in range(n - 10, last + 1):
        p0 = (c[i] / c[i - 1] - 1) * 100 if c[i - 1] > 0 else 0.0
        if p0 >= 25:
            has_zt = True
    if has_zt:
        risks.append("10日内有涨停/近涨停")
    rr = (h[last] - c[last]) / ((h[last] - l[last]) or 1)
    if (h[last] - cl) / cl >= 0.05 and c[last] < o[last] and rr >= 0.5:
        risks.append("长上影滞涨")
    if last >= 3:
        lj = True
        for i in range(last - 2, last + 1):
            if not (c[i] > c[i - 1] and v[i] < v[i - 1]):
                lj = False
                break
        if lj:
            risks.append("量价背离(3日缩量上涨)")
    if cl < ma20 and not (ma20 > ma20_3):
        risks.append("跌破MA20且趋势下拐")
    if cl < l[last - 1] and c[last] < o[last] and chg1 <= -7:
        risks.append("放量长阴")
    kw_hits = list(cand.get("kwHits") or [])

    # ---- 综合评分（多因子加权，0-100） ----
    sc = 0.0
    # 位置安全边际（0-24）
    if pos <= 0.10:
        sc += 24
    elif pos <= 0.20:
        sc += 20
    elif pos <= 0.30:
        sc += 16
    elif pos <= 0.40:
        sc += 11
    else:
        sc += 5
    # 启动形态（0-37）
    if patterns.get("surgeStart"):
        sc += 10
    if patterns.get("pullback"):
        sc += 8
    if patterns.get("smallYang"):
        sc += 6
    if patterns.get("baseUp"):
        sc += 6
    if patterns.get("tightBurst"):
        sc += 3
    if hist[last] > 0:
        sc += 2
    gc = False
    for i in range(last - 4, last + 1):
        if dif[i] > dea[i] and dif[i - 1] <= dea[i - 1]:
            gc = True
    if gc:
        sc += 2
    # 主线龙头确认（龙头层）：资金回流 + 短期趋势走强 + MACD 不弱；
    # 急跌后强反弹阶段 MA20 往往仍下行，故不要求 MA20 上拐，改为站上或贴近 MA20（>=0.97x）
    leader_ok = bool(
        fund > 0 and chg5 > 0 and cl > ma10
        and cl >= ma20 * 0.97
        and (hist[last] > 0 or gc)
    )
    if leader_ok:
        patterns["leaderOk"] = 1
        sc += 6
    # 均线趋势（0-11）
    if ma_bull:
        sc += 8
    elif ma_bull3:
        sc += 5
    if ma20 > ma20_3:
        sc += 3
    # 量能健康（0-9）
    if 1.1 <= vol5v20 <= 2.5:
        sc += 6
    elif 0.8 <= vol5v20 < 1.1:
        sc += 3
    elif 2.5 < vol5v20 <= 4:
        sc += 2
    if 1.1 <= vol_ratio <= 3:
        sc += 3
    elif vol_ratio > 0.6:
        sc += 1
    # 资金与热度（0-15）
    fund = _num(cand.get("fundIn") if cand.get("fundIn") is not None else cand.get("fund"))
    if cfg.get("useFund") and fund > 0:
        sc += 5
    if cand.get("hot"):
        sc += 6
    if kw_hits:
        sc += 4
    # 估值与市值弹性（0-11）
    pe = _num(cand.get("pe"))
    pb = _num(cand.get("pb"))
    mcap = _num(cand.get("mcap"))
    if 0 < pe <= 30:
        sc += 3
    elif 30 < pe <= 60:
        sc += 2
    if 0 < pb <= 3:
        sc += 2
    mcap_yi = mcap / 1e8
    if 5 <= mcap_yi <= 15:
        sc += 4
    elif 15 < mcap_yi <= 25:
        sc += 3
    elif 25 < mcap_yi <= 40:
        sc += 2
    # 动能质量（0-9）
    if 55 <= rsi14 <= 72:
        sc += 4
    elif 40 <= rsi14 < 55:
        sc += 2
    if 4 <= atr_pct <= 10:
        sc += 3
    elif 1.5 <= atr_pct < 4:
        sc += 2
    if -3 <= bias6 <= 8:
        sc += 2
    # 换手率（0-4）
    turnover = _num(cand.get("turnover"))
    if 3 <= turnover <= 12:
        sc += 4
    elif 12 < turnover <= float(cfg["turnMax"]):
        sc += 2
    elif turnover < float(cfg["turnMin"]):
        risks.append(("换手" + "过低" + f"{turnover:.1f}%"))
    else:
        risks.append(("换手" + "过高" + f"{turnover:.1f}%"))
    # 风险扣分
    sc -= len(risks) * 7
    if not (patterns.get("pullback") or patterns.get("smallYang") or patterns.get("baseUp") or patterns.get("surgeStart")):
        sc -= 8
    # 稀缺性（0-6）：行业独苗 + 流通盘占比低（北证小流通盘弹性高）
    ind_cnt = int(_num(cand.get("indCnt"), 0))
    fcap = _num(cand.get("floatMcap"))
    mcap_now = _num(cand.get("mcap"))
    float_ratio = (fcap / mcap_now) if mcap_now > 0 and fcap > 0 else 1.0
    scarcity = 0
    scar_tags: list[str] = []
    if 0 < ind_cnt <= 2:
        scarcity += 3
        scar_tags.append("行业稀缺" + f"\u00b7{('北证仅' if market == 'bj' else '候选池仅')}{ind_cnt}只")
    if 0 < float_ratio < 0.5:
        scarcity += 3
        scar_tags.append("流通盘稀缺" + f"\u00b7流通占比{float_ratio * 100:.0f}%")
    sc += scarcity
    s1 = min(l[last - 4:])
    s2 = ma20
    p1 = max(h[last - 9:])
    p2 = hi60
    stop = min(s1, s2)
    return {
        "closes": c, "opens": o, "highs": h, "lows": l, "vols": v,
        "ma5": ma5, "ma10": ma10, "ma20": ma20, "ma60": ma60, "ma20_3": ma20_3,
        "dif": dif, "dea": dea, "hist": hist,
        "pos": pos, "chg1": chg1, "chg5": chg5, "chg10": chg10,
        "chg20": chg20, "chg60": chg60, "volRatio": vol_ratio,
        "vol5v20": vol5v20, "upDays": up_days,
        "patterns": patterns, "risks": risks,
        "score": max(0, min(100, int(round(sc)))),
        "surgeDaysAgo": surge_days_ago, "spread": spread,
        "scarcity": scarcity, "scarcityTags": scar_tags, "floatRatio": round(float_ratio, 4),
        "levels": {"s1": s1, "s2": s2, "p1": p1, "p2": p2, "stop": stop},
        "kwHits": kw_hits, "hot": bool(cand.get("hot")),
        "hotName": cand.get("hotName") or "", "fund": fund,
        "ind": cand.get("ind") or "",
        # 新增因子
        "rsi14": rsi14, "boll_pos": boll_pos, "boll_width": boll_width,
        "atr_pct": atr_pct, "bias6": bias6, "bias12": bias12,
        "ma_bull": ma_bull, "ma_bull3": ma_bull3, "gc_days": gc_days,
        "leaderOk": leader_ok,
        "pe": pe, "pb": pb, "mcap": mcap,
    }


def bearish_check(cand: dict[str, Any], a: dict[str, Any]) -> dict[str, Any]:
    """利空排查：硬伤直接排除，警示降权。"""
    items: list[dict[str, str]] = []

    def hard(t: str) -> None:
        items.append({"level": "hard", "text": t})

    def warn(t: str) -> None:
        items.append({"level": "warn", "text": t})

    c = a.get("closes") or []
    o = a.get("opens") or []
    h = a.get("highs") or []
    l = a.get("lows") or []
    v = a.get("vols") or []
    n = len(c)
    if n < 61:
        return {"level": "warn", "items": [{"level": "warn", "text": "K线历史不足"}]}
    last = n - 1
    cl = c[last]
    ma20 = a.get("ma20") or 0.0
    ma20_3 = a.get("ma20_3") or ma20
    v20 = sum(v[last - 19: last + 1]) / 20
    # 硬伤
    if cl <= min(l[n - 60:]) * 1.001:
        hard("创60日新低")
    if cl < ma20 and not (ma20 > ma20_3):
        hard("跌破MA20且趋势下拐")
    if (a.get("chg1") or 0) <= -7 and v[last] >= 1.5 * v20:
        hard("放量长阴")
    for i in range(n - 10, last + 1):
        p0 = (c[i] / c[i - 1] - 1) * 100 if c[i - 1] > 0 else 0.0
        if p0 <= -25:
            hard("10日内出现跌停/接近跌停")
            break
    if last >= 3:
        down3 = all(c[i] < c[i - 1] for i in range(last - 2, last + 1))
        chg3 = (c[last] / c[last - 3] - 1) * 100 if c[last - 3] > 0 else 0.0
        if down3 and chg3 <= -10:
            hard("3日连跌且累计超10%")
    # 警示
    pe = _num(cand.get("pe"))
    pb = _num(cand.get("pb"))
    turn = _num(cand.get("turnover"))
    mcap = _num(cand.get("mcap"))
    if pe < 0:
        warn("基本面亏损(PE为负)")
    elif pe > 150:
        warn("估值偏高(PE>150)")
    if pb > 12:
        warn("市净率过高(PB>12)")
    if turn > 20:
        warn("换手过热(>20%)")
    if (a.get("chg5") or 0) > 18:
        warn("5日涨幅过热")
    if mcap < 8e8:
        warn("市值偏小(流动性/退市风险)")
    for r in (a.get("risks") or []):
        if r in ("长上影滞涨", "量价背离(3日缩量上涨)", "底部异动后未确认企稳", "10日内有涨停/近涨停"):
            warn(r)
            break
    level = "hard" if any(it["level"] == "hard" for it in items) else ("warn" if items else "pass")
    return {"level": level, "items": items}


# ---------------- 业绩成长 + 消息面利空排查（fine 池体检） ----------------
_FIN_CACHE: dict[str, tuple[str, dict[str, Any] | None]] = {}
_NEWS_CACHE: dict[str, tuple[str, list[str]]] = {}
# 硬伤消息：直接排除推荐池
_NEWS_HARD = ["立案", "行政处罚", "证监会调查", "监管措施", "退市风险", "实施退市",
              "财务造假", "虚增", "虚构", "造假", "涉嫌", "被查"]
# 警示消息：降权并展示
_NEWS_WARN = ["减持", "解禁", "质押", "冻结", "问询", "关注函", "警示函", "监管函",
              "预亏", "业绩预减", "业绩下滑", "商誉减值", "诉讼", "仲裁", "终止",
              "违规", "通报批评", "公开谴责", "亏损", "担保"]


def _today8() -> str:
    return time.strftime("%Y%m%d", time.localtime())


async def _fetch_financials(code: str) -> dict[str, Any] | None:
    """东财主要财务指标（最新报告期，缺失则回退上一期）。"""
    hit = _FIN_CACHE.get(code)
    if hit and hit[0] == _today8():
        return hit[1]
    url = ("https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_F10_FINANCE_MAINFINADATA"
           "&columns=ALL&filter=(SECUCODE%3D%22" + code + ".BJ%22)"
           "&pageNumber=1&pageSize=4&sortTypes=-1&sortColumns=REPORT_DATE")
    fin: dict[str, Any] | None = None
    try:
        async with httpx.AsyncClient(timeout=12.0, headers=_UA) as cli:
            j = (await cli.get(url)).json()
        rows = ((j.get("result") or {}).get("data")) or []
        if not rows:
            fin = None
        else:
            r = rows[0]
            fin = {
                "report": str(r.get("REPORT_DATE_NAME") or ""),
                "rev": _num(r.get("TOTALOPERATEREVE")),
                "revYoy": _num(r.get("TOTALOPERATEREVETZ")),
                "np": _num(r.get("PARENTNETPROFIT")),
                "npYoy": _num(r.get("PARENTNETPROFITTZ")),
                "kcjNp": _num(r.get("KCFJCXSYJLR")),
                "kcjNpYoy": _num(r.get("KCFJCXSYJLRTZ")),
                "roe": _num(r.get("ROEJQ")),
                "gross": _num(r.get("XSMLL")),
                "eps": _num(r.get("EPSJB")),
                "debt": _num(r.get("ZCFZL")),
                "cashFlow": _num(r.get("NETCASH_OPERATE_PK")),
                "cashPerShare": _num(r.get("MGJYXJJE")),
                "arGrowth": _num(r.get("YSZKZZL")),
            }
            # 最新期营收/净利缺失（如季报未披露）时回退上一期
            if fin["rev"] == 0 and len(rows) > 1:
                r1 = rows[1]
                fin.update({
                    "report": str(r1.get("REPORT_DATE_NAME") or ""),
                    "rev": _num(r1.get("TOTALOPERATEREVE")),
                    "revYoy": _num(r1.get("TOTALOPERATEREVETZ")),
                    "np": _num(r1.get("PARENTNETPROFIT")),
                    "npYoy": _num(r1.get("PARENTNETPROFITTZ")),
                    "kcjNp": _num(r1.get("KCFJCXSYJLR")),
                    "kcjNpYoy": _num(r1.get("KCFJCXSYJLRTZ")),
                    "roe": _num(r1.get("ROEJQ")),
                    "gross": _num(r1.get("XSMLL")),
                    "debt": _num(r1.get("ZCFZL")),
                    "cashFlow": _num(r1.get("NETCASH_OPERATE_PK")),
                    "cashPerShare": _num(r1.get("MGJYXJJE")),
                    "arGrowth": _num(r1.get("YSZKZZL")),
                })
    except Exception:
        fin = None
    _FIN_CACHE[code] = (_today8(), fin)
    return fin


async def _fetch_news_ann(code: str) -> list[str]:
    """东财 F10 公告标题（近 30 条），用于负面消息排查。"""
    hit = _NEWS_CACHE.get(code)
    if hit and hit[0] == _today8():
        return hit[1]
    titles: list[str] = []
    try:
        url = ("https://np-anotice-stock.eastmoney.com/api/security/ann?sr=-1&page_size=30&page_index=1"
               "&ann_type=A&client_source=web&stock_list=" + code)
        async with httpx.AsyncClient(timeout=12.0, headers=_UA) as cli:
            j = (await cli.get(url)).json()
        data = j.get("data") or {}
        titles = [str(it.get("title") or "") for it in (data.get("list") or [])]
    except Exception:
        titles = []
    _NEWS_CACHE[code] = (_today8(), titles)
    return titles


def _fin_red_flags(fin: dict[str, Any]) -> list[str]:
    """利润质量红旗（虚构业绩疑云：现金流背离 / 应收异常 / 扣非亏损 / 高增无现金）。"""
    flags: list[str] = []
    np = _num(fin.get("np"))
    cf = fin.get("cashFlow")
    np_yoy = fin.get("npYoy")
    rev_yoy = fin.get("revYoy")
    ar_growth = fin.get("arGrowth")
    kcj = fin.get("kcjNp")
    if np > 0 and cf is not None and cf < np * 0.5:
        flags.append("利润含金量低(经营现金流<净利50%)")
    if np > 0 and kcj is not None and kcj < 0:
        flags.append("扣非净利为负，盈利依赖非经常性损益")
    if rev_yoy and rev_yoy > 0 and ar_growth and ar_growth > rev_yoy * 2:
        flags.append("应收增速远超营收，需核实收入质量")
    if np_yoy and np_yoy > 80 and cf is not None and cf <= 0:
        flags.append("净利高增但经营现金流为负，警惕虚构业绩")
    return flags[:3]


def _growth_score(fin: dict[str, Any]) -> int:
    """业绩利润增长空间（-6 ~ +10）：净利/营收增速 + ROE + 毛利率。"""
    g = 0
    np_yoy = fin.get("npYoy")
    rev_yoy = fin.get("revYoy")
    roe = fin.get("roe")
    gross = fin.get("gross")
    if np_yoy is None or (isinstance(np_yoy, float) and np_yoy == 0 and rev_yoy in (None, 0)):
        return 0
    if np_yoy is not None:
        if np_yoy > 50: g += 4
        elif np_yoy > 20: g += 3
        elif np_yoy > 0: g += 1
        elif np_yoy < -30: g -= 3
        elif np_yoy < 0: g -= 2
    if rev_yoy is not None:
        if rev_yoy > 30: g += 3
        elif rev_yoy > 10: g += 2
        elif rev_yoy > 0: g += 1
        elif rev_yoy < -20: g -= 2
        elif rev_yoy < 0: g -= 1
    if roe is not None:
        if roe > 15: g += 2
        elif roe > 8: g += 1
        elif roe < 0: g -= 1
    if gross is not None and gross > 40: g += 1
    return max(-6, min(10, g))


async def _fundamental_check(c: dict[str, Any]) -> dict[str, Any]:
    """业绩成长 + 消息面体检：红旗 hard 排除；警示降权；成长分加成。"""
    fin = await _fetch_financials(c["code"])
    titles = await _fetch_news_ann(c["code"])
    news_hard = [t for t in titles if any(k in t for k in _NEWS_HARD)][:4]
    news_warn = list(dict.fromkeys(
        t for t in titles if not any(k in t for k in _NEWS_HARD) and any(k in t for k in _NEWS_WARN)
    ))[:5]
    flags = _fin_red_flags(fin) if fin else []
    growth = _growth_score(fin) if fin else 0
    if news_hard:
        level = "hard"
    elif flags or news_warn or growth < 0:
        level = "warn"
    else:
        level = "pass"
    return {
        "level": level,
        "fin": fin,
        "growth": growth,
        "flags": flags,
        "newsHard": news_hard,
        "newsWarn": news_warn,
    }


def _pick_fund_out(fund: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(fund, dict):
        return None
    fin = fund.get("fin") if isinstance(fund.get("fin"), dict) else None
    return {
        "level": fund.get("level") or "pass",
        "growth": int(fund.get("growth") or 0),
        "flags": fund.get("flags") or [],
        "newsHard": fund.get("newsHard") or [],
        "newsWarn": fund.get("newsWarn") or [],
        "fin": {
            "report": (fin or {}).get("report") or "",
            "revYoy": (fin or {}).get("revYoy"),
            "npYoy": (fin or {}).get("npYoy"),
            "roe": (fin or {}).get("roe"),
            "gross": (fin or {}).get("gross"),
            "cashPerShare": (fin or {}).get("cashPerShare"),
        } if fin else None,
    }


def build_strategy(pick: dict[str, Any], tier: str, role: str | None = None) -> dict[str, str]:
    """中线波段策略（2~8周）：入场/止损/目标/仓位/条件，规则化生成（龙头/卡位不同打法）。"""
    a = pick.get("A") or {}
    lv = a.get("levels") or {}
    cl = _num(pick.get("price"))
    s1, s2 = lv.get("s1"), lv.get("s2")
    p1, p2 = lv.get("p1"), lv.get("p2")
    stop = lv.get("stop")
    s1 = s1 if s1 and s1 > 0 else cl * 0.95
    s2 = s2 if s2 and s2 > 0 else cl * 0.92
    p1 = p1 if p1 and p1 > cl else cl * 1.08
    p2 = p2 if p2 and p2 > cl else cl * 1.25
    entry_lo = min(s1, s2)
    entry_hi = max(s1, s2)
    if entry_hi - entry_lo < entry_lo * 0.01:
        entry_hi = cl * 0.985
        entry_lo = cl * 0.955
    t2 = p2
    if t2 > cl * 1.45:
        t2 = p1 + (p1 - stop) * 1.5
    pos_share = {"king": "20%", "key": "15%", "normal": "10%"}.get(tier, "10%")
    if role == "leader":
        # 龙头已确认走强：回踩均线分批，趋势打法
        ma5 = _num(a.get("ma5"))
        ma10 = _num(a.get("ma10"))
        if ma5 <= 0:
            ma5 = cl * 0.97
        if ma10 <= 0:
            ma10 = cl * 0.95
        lo, hi = min(ma5, ma10), max(ma5, ma10)
        # 急跌反弹初期均线远离现价：入场带收敛到现价下方 0.5%~5.5%，避免等不到回踩
        hi = min(hi, cl * 0.995)
        lo = max(lo, cl * 0.945)
        if lo >= hi:
            lo, hi = cl * 0.945, cl * 0.99
        stop = max(float(lv.get("stop") or 0), cl * 0.90)
        return {
            "period": "主线龙头 · 趋势波段 2~8周",
            "entry": f"回踩MA5/MA10（{lo:.2f}~{hi:.2f}）分批建仓，强势不回踩可轻仓追突破（现价 {cl:.2f}）",
            "stop": f"{stop:.2f}（收盘跌破MA10或止损价无条件离场）",
            "target1": f"{p1:.2f}（近10日压力）",
            "target2": f"{t2:.2f}" + ("（保守目标）" if t2 < lv.get("p2", 0) else "（60日压力）"),
            "position": f"单票建议仓位 {pos_share}（龙头组合总仓位上限 50%，留机动）",
            "conditions": "加仓：站稳MA10且MACD红柱延续、主力持续净流入；减仓：冲高放量滞涨或跌破MA5；离场：收盘破MA10或单日放量长阴-8%",
        }
    period_txt = {"catchup": "补涨卡位 · 区间波段 2~8周"}.get(role, "中线波段 · 2~8周")
    return {
        "period": period_txt,
        "entry": f"回踩 {entry_lo:.2f}~{entry_hi:.2f} 分批建仓（现价 {cl:.2f}）",
        "stop": f"{stop:.2f}（收盘跌破无条件离场）",
        "target1": f"{p1:.2f}（近10日压力）",
        "target2": f"{t2:.2f}" + ("（保守目标）" if t2 < lv.get("p2", 0) else "（60日压力）"),
        "position": f"单票建议仓位 {pos_share}（波段总仓位上限 60%）",
        "conditions": "加仓：站稳MA20且MACD红柱持续；减仓：放量滞涨或跌破MA5；离场：破止损或单日放量长阴-8%",
    }


async def _market_env(variant: str, priority_override: str, allow_paid: bool) -> dict[str, Any]:
    """大盘环境（上证指数）：MACD 红柱天数 + 均线状态，作为统一加减分。"""
    try:
        payload = await fetch_tx_kline("1.000001", "day", count=120, timeout=6.0, variant=variant, priority_override=priority_override, allow_paid=allow_paid)
        rows = _rows_from_payload(payload)
        if not rows or len(rows) < 61:
            return {}
        a = analyze(rows, {}, DEFAULT_CFG)
        red = bool(a["hist"][-1] > 0)
        above = bool(a["closes"][-1] > a["ma20"])
        ma20_up = bool(a["ma20"] > a["ma20_3"])
        weak = (not above) and (not ma20_up)
        tags: list[str] = []
        if red:
            tags.append(f"上证MACD红柱·第{a['gc_days']}天")
        else:
            tags.append("上证MACD绿柱")
        if a["ma_bull3"]:
            tags.append("上证均线多头")
        elif above:
            tags.append("上证站上MA20")
        else:
            tags.append("上证跌破MA20")
        return {
            "red": red, "red_days": int(a["gc_days"]), "ma_bull3": bool(a["ma_bull3"]),
            "above_ma20": above, "weak": weak, "tags": tags,
            "pos": round(a["pos"] * 100), "asof": str(rows[-1][0]),
        }
    except Exception:
        return {}


# ---------------- 主线反推 ----------------

def reverse_mainline(cands: list[dict[str, Any]], hot: dict[str, Any]) -> list[dict[str, Any]]:
    """先看标的异动 → 反推热门主线板块（按行业聚合异动标的数 / 成交额）。"""
    buckets: dict[str, dict[str, Any]] = {}
    for c in cands:
        a = c.get("A") or {}
        p = a.get("patterns") or {}
        if not (p.get("surgeStart") or p.get("pullback") or p.get("smallYang") or p.get("baseUp")):
            continue
        ind = str(c.get("ind") or "").strip()
        if not ind or ind == "-":
            continue
        b = buckets.setdefault(ind, {"name": ind, "count": 0, "amount": 0.0, "stocks": []})
        b["count"] += 1
        b["amount"] += _num(c.get("amount"))
        if len(b["stocks"]) < 8 and c.get("name"):
            b["stocks"].append(str(c["name"]))
    items = sorted(buckets.values(), key=lambda x: (-x["count"], -x["amount"]))
    for it in items:
        hn = board_hit(it["name"], hot)
        it["hot"] = bool(hn)
        it["hot_name"] = hn
    return items[:12]


# ---------------- 单票快照（AI 综合分 / 风险标签，服务端同口径） ----------------

# ---------------- 板块排行（王者 1 + 辅线 2 + 备选 N） ----------------

def _board_rank(mainlines: list[dict[str, Any]], hot_boards: list[dict[str, Any]], keep_backup: int = 4) -> list[dict[str, Any]]:
    """把主线反推结果排成「王者 1 + 辅线 2 + 备选 N」的板块排行。

    - 王者/辅线来自底部异动主线反推（异动家数优先，板块榜确认次之，成交额兜底）；
    - 主线不足时用东财 5 日涨幅榜补足备选。
    """
    hot_by_name: dict[str, dict[str, Any]] = {}
    for b in (hot_boards or []):
        nm = str(b.get("name") or "").strip()
        if nm:
            hot_by_name[nm] = b

    def entry(it: dict[str, Any], tier: str) -> dict[str, Any]:
        name = str(it.get("name") or "")
        hb = hot_by_name.get(name)
        return {
            "name": name,
            "secid": str(it.get("secid") or ""),
            "count": it.get("count"),
            "amount": it.get("amount"),
            "p5": hb.get("p5") if hb is not None else it.get("p5"),
            "hot": bool(it.get("hot") or hb is not None),
            "hot_name": str(it.get("hot_name") or ""),
            "tier": tier,
        }

    m = sorted(
        (mainlines or []),
        key=lambda x: (-int(x.get("count") or 0), 0 if x.get("hot") else 1, -float(x.get("amount") or 0)),
    )
    if not m:
        return []
    rank: list[dict[str, Any]] = [entry(m[0], "king")]
    used = {str(x.get("name") or "") for x in rank}
    for it in m[1:3]:
        if str(it.get("name") or "") not in used:
            rank.append(entry(it, "key"))
            used.add(str(it.get("name") or ""))
    backups: list[dict[str, Any]] = []
    for it in m[3:]:
        nm = str(it.get("name") or "")
        if nm and nm not in used and nm not in {str(x.get("name") or "") for x in backups}:
            backups.append(it)
    if len(backups) < keep_backup:
        for b in (hot_boards or []):
            nm = str(b.get("name") or "")
            if nm and nm not in used and nm not in {str(x.get("name") or "") for x in backups}:
                backups.append(b)
            if len(backups) >= keep_backup:
                break
    for it in backups[:keep_backup]:
        rank.append(entry(it, "backup"))
    return rank


def _board_rank_funds(boards: list[dict[str, Any]], keep_backup: int = 4) -> list[dict[str, Any]]:
    """全市场板块排行：按 5日主力净流入排序，王者 1 + 辅线 2 + 备选 N。"""
    items = sorted((boards or []), key=lambda x: -float(x.get("f164") or 0))
    tiers = ["king", "key", "key"] + ["backup"] * max(0, keep_backup)
    rank: list[dict[str, Any]] = []
    for i, b in enumerate(items):
        if i >= len(tiers):
            break
        rank.append({
            "name": str(b.get("name") or ""),
            "secid": str(b.get("secid") or ""),
            "count": None,
            "amount": None,
            "f62": float(b.get("f62") or 0),
            "f164": float(b.get("f164") or 0),
            "p5": b.get("p5"),
            "pct": b.get("pct"),
            "hot": True,
            "hot_name": "",
            "kind": str(b.get("kind") or "industry"),
            "leaders": b.get("leaders") or [],
            "tier": tiers[i],
        })
    return rank


# ---------------- 板块 secid（点击跳转 AI行情官） ----------------

async def _resolve_board_secid(name: str) -> str:
    """板块名 → 东财板块 secid（90.BKxxxx），24h 内存缓存，减少上游 suggest 请求。"""
    if not name:
        return ""
    now = time.time()
    hit = _BOARD_SECID_CACHE.get(name)
    if hit and now - hit[0] < _BOARD_SECID_TTL:
        return hit[1]
    secid = ""
    try:
        j = await fetch_em_suggest(name, timeout=6.0, include_plates=True)
        tbl = j.get("QuotationCodeTable") if isinstance(j, dict) else None
        data = (tbl or {}).get("Data") if isinstance(tbl, dict) else None
        if isinstance(data, list):
            for it in data:
                if not isinstance(it, dict):
                    continue
                cls = str(it.get("Classify") or "").strip().upper()
                qid = str(it.get("QuoteID") or "").strip().upper()
                nm = str(it.get("Name") or "").strip()
                if cls == "BK" and qid.startswith("90.BK") and (
                    nm == name or (len(name) >= 2 and (name in nm or nm in name))
                ):
                    secid = qid
                    break
            if not secid:
                for it in data:
                    if not isinstance(it, dict):
                        continue
                    cls = str(it.get("Classify") or "").strip().upper()
                    qid = str(it.get("QuoteID") or "").strip().upper()
                    if cls == "BK" and qid.startswith("90.BK"):
                        secid = qid
                        break
    except Exception:
        secid = ""
    _BOARD_SECID_CACHE[name] = (time.time(), secid)
    return secid


async def _attach_board_secids(mainlines: list[dict[str, Any]], hot_boards: list[dict[str, Any]]) -> None:
    names: list[str] = []
    for it in (mainlines or []):
        n = str(it.get("name") or "").strip()
        if n and n not in names:
            names.append(n)
    for it in (hot_boards or []):
        n = str(it.get("name") or "").strip()
        if n and n not in names:
            names.append(n)
    if not names:
        return
    results = await asyncio.gather(*[_resolve_board_secid(n) for n in names], return_exceptions=True)
    mapping: dict[str, str] = {}
    for n, r in zip(names, results):
        mapping[n] = r if isinstance(r, str) else ""
    for it in (mainlines or []):
        n = str(it.get("name") or "")
        if n in mapping and mapping[n]:
            it["secid"] = mapping[n]
    for it in (hot_boards or []):
        n = str(it.get("name") or "")
        if n in mapping and mapping[n]:
            it["secid"] = mapping[n]


def _rows_from_payload(payload: dict[str, Any]) -> list[list[Any]]:
    data = payload.get("data")
    if not isinstance(data, dict) or not data:
        return []
    pack = next(iter(data.values()))
    if not isinstance(pack, dict):
        return []
    return pack.get("qfqday") or pack.get("day") or pack.get("kline") or []


async def _kline_with_retry(
    code: str,
    variant: str,
    priority_override: str,
    allow_paid: bool,
    tries: int = 2,
    use_cache: bool = True,
) -> list[list[Any]]:
    """拉取个股日 K：带当日磁盘缓存（30 分钟有效）与重试；use_cache=False 强制刷新上游。"""
    date8 = time.strftime("%Y%m%d", time.localtime())
    if use_cache:
        cached = _kline_cache_get(date8, code)
        if cached:
            return cached
    for i in range(tries):
        try:
            payload = await fetch_tx_kline(
                "1." + code, "day", count=170, timeout=8.0,
                variant=variant, priority_override=priority_override, allow_paid=allow_paid,
            )
            rows = _rows_from_payload(payload)
            if rows and len(rows) >= 61:
                if use_cache:
                    _kline_cache_put(date8, code, rows)
                return rows
            return []
        except Exception:
            if i == tries - 1:
                return []
            await asyncio.sleep(1.0 + i)
    return []


async def _fetch_snapshot(secid: str, code: str, name: str, variant: str, priority_override: str, allow_paid: bool) -> dict[str, Any]:
    """单票技术指标快照：与自选评分榜同口径（不含大盘调整）。"""
    from .scoring import score_candles
    from .signals import candles_from_tencent_like_pack

    base: dict[str, Any] = {"secid": secid, "code": str(code or ""), "name": str(name or "")}
    try:
        payload = await fetch_tx_kline(
            secid, "day", count=120, timeout=6.0,
            variant=variant, priority_override=priority_override, allow_paid=allow_paid,
        )
    except Exception as e:
        base["error"] = "fetch:%s" % type(e).__name__
        return base
    if not isinstance(payload, dict) or int(payload.get("code") or 0) != 0:
        base["error"] = str((payload or {}).get("msg") or "kline failed")
        return base
    data = payload.get("data")
    if not isinstance(data, dict) or not data:
        base["error"] = "empty data"
        return base
    pack = next(iter(data.values()))
    candles = candles_from_tencent_like_pack(pack, period="day")
    if len(candles) < 60:
        base["error"] = "insufficient history"
        return base
    res = score_candles(candles, name=base["name"] or base["code"])
    base.update(res)
    return base


# ---------------- 扫描主流程 ----------------

def _reorder(priority: str, paid_first: bool) -> str:
    items: list[str] = []
    for it in (priority or "").split(","):
        it = it.strip()
        if it and it not in items:
            items.append(it)
    if "paid" in items:
        items = [x for x in items if x != "paid"]
        items = (["paid"] + items) if paid_first else (items + ["paid"])
    return ",".join(items)


def _ma_arr(vals: list[float], n: int) -> list[float]:
    out: list[float] = []
    s = 0.0
    for i, v in enumerate(vals):
        s += v
        if i >= n:
            s -= vals[i - n]
        out.append(s / n if i >= n - 1 else float("nan"))
    return out


def _fund_of(c: dict[str, Any]) -> dict[str, Any] | None:
    """Fundamental-check dict only when present; pre-check candidates keep 'fund' as float (net inflow)."""
    f = c.get("fund")
    return f if isinstance(f, dict) else None

def _risk_free(c: dict[str, Any]) -> bool:
    """与 run_scan 零风险池判定完全一致：AI 复核无风险标签 + 利空检查 pass。"""
    snap = c.get("snap") if isinstance(c.get("snap"), dict) else None
    if snap and snap.get("risks"):
        return False
    if not snap and (c.get("A") or {}).get("risks"):
        return False
    if (c.get("bearish") or {}).get("level") != "pass":
        return False
    if (_fund_of(c) or {}).get("level", "pass") != "pass":
        return False
    return True


def _pick_out(c: dict[str, Any]) -> dict[str, Any]:
    a = c.get("A") or {}
    levels = a.get("levels") or {}
    snap = c.get("snap") if isinstance(c.get("snap"), dict) else None
    bearish = c.get("bearish") if isinstance(c.get("bearish"), dict) else {"level": "pass", "items": []}
    snap_risks = list(snap.get("risks") or []) if snap and not snap.get("error") else []
    if snap_risks and bearish.get("level") != "hard":
        seen = {it.get("text") for it in (bearish.get("items") or [])}
        items = list(bearish.get("items") or [])
        for r in snap_risks:
            if r not in seen:
                items.append({"level": "warn", "text": "AI复核\u00b7" + str(r)})
        bearish = {"level": "warn", "items": items}
    risk_free = _risk_free(c)
    chart: dict[str, Any] = {}
    if a:
        chart = {
            "closes": a.get("closes", [])[-60:], "opens": a.get("opens", [])[-60:],
            "highs": a.get("highs", [])[-60:], "lows": a.get("lows", [])[-60:],
            "vols": a.get("vols", [])[-60:],
            "ma5": _ma_arr(a.get("closes", []), 5)[-60:],
            "ma10": _ma_arr(a.get("closes", []), 10)[-60:],
            "ma20": _ma_arr(a.get("closes", []), 20)[-60:],
            "s1": levels.get("s1"), "s2": levels.get("s2"),
            "p1": levels.get("p1"), "p2": levels.get("p2"),
        }
    factors = {
        "rsi14": round(_num(a.get("rsi14")), 1) if a.get("rsi14") is not None else None,
        "boll_pos": round(_num(a.get("boll_pos")), 2) if a.get("boll_pos") is not None else None,
        "atr_pct": round(_num(a.get("atr_pct")), 1) if a.get("atr_pct") is not None else None,
        "bias6": round(_num(a.get("bias6")), 1) if a.get("bias6") is not None else None,
        "ma_bull": bool(a.get("ma_bull")), "gc_days": int(a.get("gc_days") or 0),
        "pe": _num(a.get("pe")), "pb": _num(a.get("pb")), "mcap_yi": round(_num(a.get("mcap")) / 1e8, 1),
    }
    return {
        "rank": c.get("rank"), "code": c.get("code"), "name": c.get("name"),
        "price": c.get("price"), "pct": c.get("pct"), "mcap": c.get("mcap"),
        "amount": c.get("amount"), "turnover": c.get("turnover"),
        "volRatio": c.get("volRatio"), "fundIn": c.get("fundIn"),
        "ind": c.get("ind"), "lastDate": c.get("lastDate"), "final": c.get("final"),
        "tier": c.get("tier") or "normal", "star": bool(c.get("star")),
        "pickRole": str(c.get("pick_role") or ""),
        "strategy": c.get("strategy"),
        "bearish": bearish,
        "risk_free": risk_free,
        "scarcity": {"score": int(_num(a.get("scarcity"))), "tags": a.get("scarcityTags") or [],
                     "floatRatio": a.get("floatRatio")},
        "fund": _pick_fund_out(c.get("fund")),
        "factors": factors,
        "score": (a or {}).get("score"), "pos": (a or {}).get("pos"),
        "chg5": (a or {}).get("chg5"), "chg10": (a or {}).get("chg10"),
        "chg20": (a or {}).get("chg20"), "chg60": (a or {}).get("chg60"),
        "surgeDaysAgo": (a or {}).get("surgeDaysAgo"),
        "patterns": (a or {}).get("patterns") or {}, "risks": (a or {}).get("risks") or [],
        "levels": levels, "kwHits": (a or {}).get("kwHits") or [],
        "hot": bool((a or {}).get("hot")), "hotName": (a or {}).get("hotName") or "",
        "revHit": bool(c.get("revHit")), "revName": c.get("revName") or "",
        "snap": ({"score": snap.get("score"), "risks": snap.get("risks") or [], "tags": snap.get("tags") or []}
                 if snap and not snap.get("error") else None),
        "chart": chart,
    }


def _runner_out(c: dict[str, Any]) -> dict[str, Any]:
    a = c.get("A") or {}
    snap = c.get("snap") if isinstance(c.get("snap"), dict) else None
    risks = list((a or {}).get("risks") or [])
    if snap and snap.get("risks"):
        risks = list(snap["risks"]) + risks
    bearish = c.get("bearish") if isinstance(c.get("bearish"), dict) else {"level": "pass", "items": []}
    btxt = [it.get("text") for it in (bearish.get("items") or [])]
    if btxt:
        risks = btxt + risks
    fund = _fund_of(c)
    if fund:
        for t in (fund.get("newsWarn") or [])[:1]:
            risks.append("消息面·" + str(t)[:22])
        for fl in (fund.get("flags") or [])[:1]:
            risks.append("业绩·" + str(fl)[:18])
        if fund.get("newsHard"):
            risks.append("消息硬伤·" + str(fund["newsHard"][0])[:22])
    return {
        "code": c.get("code"), "name": c.get("name"), "price": c.get("price"),
        "pct": c.get("pct"), "mcap": c.get("mcap"), "amount": c.get("amount"),
        "final": c.get("final"), "score": (a or {}).get("score"),
        "pos": (a or {}).get("pos"), "chg5": (a or {}).get("chg5"),
        "chg20": (a or {}).get("chg20"),
        "risks": risks[:3] or ["排名靠后"],
        "bearish_level": bearish.get("level") or "pass",
        "revName": c.get("revName") or "", "hotName": (a or {}).get("hotName") or "",
    }


def _leader_bearish_adjust(c: dict[str, Any], a: dict[str, Any]) -> bool:
    """龙头层利空判定：允许“历史急跌后资金回流确认”的情形。

    急跌修复期（站上MA10 + 5日转涨 + 当日主力净流入为正）的龙头，
    “10日内曾跌停”“跌破MA20且趋势下拐”等历史硬伤降级为警示保留展示；
    仍创新低 / 放量长阴 / 3日连跌等破位硬伤仍一票否决。
    """
    bh = c.get("bearish") if isinstance(c.get("bearish"), dict) else None
    items = (bh or {}).get("items") or []
    hard_items = [it for it in items if it.get("level") == "hard"]
    if not hard_items:
        return True
    cl = (a.get("closes") or [None])[-1]
    ma10 = a.get("ma10") or 0
    recovering = bool(cl and ma10 and cl > ma10
                     and a.get("chg5", 0) > 0
                     and _num(c.get("fundIn") if c.get("fundIn") is not None else c.get("fund")) > 0)
    if not recovering:
        return False
    allow = {"10日内出现跌停/接近跌停", "跌破MA20且趋势下拐"}
    for it in hard_items:
        if str(it.get("text") or "") not in allow:
            return False
    for it in items:
        if it.get("level") == "hard":
            it["level"] = "warn"
            it["text"] = "已修复·" + str(it.get("text") or "")
    if bh is not None:
        bh["level"] = "warn"
    return True


async def run_scan(
    user_id: int,
    force: bool = False,
    cfg_override: dict[str, Any] | None = None,
    boards_only: bool = False,
    market: str = "bj",
) -> dict[str, Any]:
    """掘金扫描主流程（服务端执行，VIP 路由层已校验）。

    market: bj=北证全市场；all=沪深京“板块先行”两阶段（资金流榜→成分股粗筛→K线精筛）。
    boards_only=True 用于非 VIP 的“板块视图”：缩小候选池、跳过 AI 快照/基本面体检，
    结果独立缓存，仅返回板块与市场概览（不含个股分析）。
    """
    market = str(market or "bj").strip().lower()
    if market not in ("bj", "all"):
        market = "bj"
    cfg = dict(DEFAULT_CFG)
    if market == "all":
        cfg["mcapMin"] = float(cfg.get("mcapMinAll") or 15.0)
        cfg["mcapMax"] = float(cfg.get("mcapMaxAll") or 200.0)
        cfg["amountMin"] = float(cfg.get("amountMinAll") or 8000.0)
    if cfg_override:
        for k, v in cfg_override.items():
            if k in cfg and v is not None:
                cfg[k] = v
    t0 = time.time()
    today8 = time.strftime("%Y%m%d", time.localtime())
    today = time.strftime("%Y-%m-%d", time.localtime())
    use_cache = not force
    boards_key = f"{market}-boards:" + today8
    full_key = f"{market}-scan:" + today8

    if boards_only:
        # 非 VIP：优先复用当日完整扫描（若有），否则做一次轻量板块扫描
        hit = _BOARDS_CACHE.get(boards_key)
        if hit and time.time() - hit[0] < 6 * 3600:
            out = dict(hit[1])
            out["cached"] = True
            out["vip_required"] = True
            return out
        full = _SCAN_CACHE.get(full_key)
        if full and time.time() - full[0] < 12 * 3600:
            out = dict(full[1])
            out["cached"] = True
            out["vip_required"] = True
            out.pop("picks", None)
            out.pop("runners", None)
            _BOARDS_CACHE[boards_key] = (time.time(), out)
            return out
        cfg["cap"] = min(int(cfg.get("cap") or 60), 30)
        cfg["aiOk"] = False
        cfg["aiTop"] = 0
        force = False
    else:
        if not force:
            hit = _SCAN_CACHE.get(full_key)
            if hit and time.time() - hit[0] < 6 * 3600:
                out = dict(hit[1])
                out["cached"] = True
                return _apply_stale_fallback(out, market)
        else:
            global _LAST_FULL_SCAN_TS
            if time.time() - _LAST_FULL_SCAN_TS < _FORCE_MIN_INTERVAL:
                hit = _SCAN_CACHE.get(full_key)
                if hit:
                    out = dict(hit[1])
                    out["cached"] = True
                    out["refresh_locked"] = True
                    return _apply_stale_fallback(out, market)
            _LAST_FULL_SCAN_TS = time.time()

    md = market_data_status()
    base_pri = str((md.get("paid") or {}).get("priority") or "").strip().lower()
    if not base_pri:
        base_pri = "tencent,eastmoney,sina,paid"
    # VIP 路由：一律允许付费源；优先级默认 paid 优先（TuShare 未配置时自动回落公共源）
    paid_first = True
    priority_override = _reorder(base_pri, paid_first=paid_first)
    allow_paid = True
    variant = "vip"

    mkt_task = asyncio.create_task(_market_env(variant, priority_override, allow_paid))
    cands, hot, board_pool, total, rows_all = await _collect_candidates(cfg, market)
    mkt_env = await mkt_task
    cands.sort(key=lambda x: -(x.get("amount") or 0))
    if len(cands) > int(cfg["cap"]):
        cands = cands[: int(cfg["cap"])]

    # 主线龙头候选：全市场下取板块排行前列（5日主力净流入排序）的板块龙头，
    # 放宽市值至 leaderMcapMax、不做“未大幅拉升”硬约束，用 leaderOk 确认形态与资金。
    leader_cands: list[dict[str, Any]] = []
    if market == "all" and board_pool:
        top_boards = sorted(
            board_pool, key=lambda x: -float(x.get("f164") or 0)
        )[: int(cfg.get("leaderBoards") or 3)]
        seen_leader = {str(c.get("code")) for c in cands}
        for bi, b in enumerate(top_boards):
            bname = str(b.get("name") or "").strip()
            for ld in (b.get("leaders") or [])[: int(cfg.get("leaderPerBoard") or 3)]:
                row = ld.get("_row") if isinstance(ld, dict) else None
                if not isinstance(row, dict):
                    continue
                code = str(row.get("f12") or "")
                if not re.fullmatch(r"\d{6}", code) or code in seen_leader:
                    continue
                name = str(row.get("f14") or "").strip()
                if re.search(r"ST|退", name):
                    continue
                mcap = _num(row.get("f20"))
                if not (0 < mcap <= float(cfg.get("leaderMcapMax") or 800.0) * 1e8):
                    continue
                seen_leader.add(code)
                leader_cands.append({
                    "code": code, "name": name,
                    "price": _num(row.get("f2")), "pct": _num(row.get("f3")),
                    "amount": _num(row.get("f6")), "mcap": mcap,
                    "floatMcap": _num(row.get("f21")),
                    "turnover": _num(row.get("f8")), "pe": _num(row.get("f9")),
                    "pb": _num(row.get("f23")), "volRatio": _num(row.get("f10")),
                    "fund": _num(row.get("f62")), "fundIn": _num(row.get("f62")),
                    "fund5": _num(row.get("f164")),
                    "ind": str(row.get("f100") or "").strip(), "indCnt": 0,
                    "hot": True, "hotName": bname, "kwHits": [],
                    "A": None, "snap": None, "final": None,
                    "revHit": True, "revName": bname,
                    "_board": bname, "_board_tier": "king" if bi == 0 else "key",
                })

    # 龙头层专用参数：放宽“未大幅拉升/换手/位置”约束，避免误伤强反弹龙头
    leader_cfg = dict(cfg)
    leader_cfg["max5d"] = 40.0
    leader_cfg["max10d"] = 55.0
    leader_cfg["max20d"] = 60.0
    leader_cfg["max60d"] = 60.0
    leader_cfg["posMax"] = 60.0
    leader_cfg["turnMin"] = 0.5
    leader_cfg["turnMax"] = 40.0

    # K线形态体检：并发 + 起步间隔，温和访问上游（避免触发腾讯熔断影响全产品）
    sem = asyncio.Semaphore(4)

    async def work(c: dict[str, Any], cfg_use: dict[str, Any] | None = None) -> None:
        async with sem:
            bars = await _kline_with_retry(c["code"], variant, priority_override, allow_paid, use_cache=use_cache)
            if not bars:
                return
            c["A"] = analyze(bars, c, cfg_use or cfg, market)
            c["lastDate"] = str(bars[-1][0])
            c["bearish"] = bearish_check(c, c["A"])

    tasks = []
    for c in cands:
        tasks.append(asyncio.create_task(work(c)))
        await asyncio.sleep(0.30)
    for c in leader_cands:
        tasks.append(asyncio.create_task(work(c, leader_cfg)))
        await asyncio.sleep(0.30)
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

    analyzed = [c for c in cands if c.get("A")]
    leader_analyzed = [c for c in leader_cands if c.get("A")]
    # 大盘环境统一加减分
    if mkt_env.get("weak"):
        for c in analyzed:
            c["A"]["score"] = max(0, int(c["A"].get("score") or 0) - 3)
    elif mkt_env.get("red"):
        for c in analyzed:
            c["A"]["score"] = min(100, int(c["A"].get("score") or 0) + 2)
    for c in leader_analyzed:
        a = c.get("A") or {}
        if mkt_env.get("weak"):
            a["score"] = max(0, int(a.get("score") or 0) - 3)
        elif mkt_env.get("red"):
            a["score"] = min(100, int(a.get("score") or 0) + 2)

    rev_mainlines = reverse_mainline(analyzed, hot)
    rev_names = {it["name"] for it in rev_mainlines[:8]}

    # 精筛 + 利空硬伤排除 + 主线反推加分
    fine: list[dict[str, Any]] = []
    hard_rejected = 0
    for c in analyzed:
        a = c["A"]
        bearish = c.get("bearish") or {}
        if bearish.get("level") == "hard":
            hard_rejected += 1
            continue
        if str(c.get("ind") or "") in rev_names:
            c["revHit"] = True
            c["revName"] = str(c.get("ind") or "")
        p = a.get("patterns") or {}
        must_start = bool(
            p.get("surgeStart") or p.get("smallYang")
            or (p.get("baseUp") and (a.get("vol5v20", 0) >= 1.15 or a.get("volRatio", 0) >= 1.2))
        )
        line_ok = cfg.get("mainline") != "must" or bool(
            c.get("hot") or (c.get("kwHits") and len(c["kwHits"]) > 0)
            or (a.get("chg5", 0) >= 8 and c.get("amount", 0) >= 5e7 and a.get("volRatio", 0) >= 1.2)
        )
        if (
            a.get("pos", 99) <= float(cfg["posMax"]) / 100
            and a.get("chg5", 999) <= float(cfg["max5d"])
            and a.get("chg10", 999) <= float(cfg["max10d"])
            and a.get("chg20", 999) <= float(cfg["max20d"])
            and a.get("chg60", 999) <= float(cfg["max60d"])
            and float(cfg["turnMin"]) <= _num(c.get("turnover")) <= float(cfg["turnMax"])
            and must_start and line_ok and a.get("score", 0) >= 50
        ):
            if c["revHit"]:
                a["score"] = min(100, int(a["score"]) + 6)
            fine.append(c)

    fine.sort(key=lambda x: -int(x["A"].get("score") or 0))
    finals = fine[: int(cfg["aiTop"])]

    sem2 = asyncio.Semaphore(3)

    async def snap_work(c: dict[str, Any], leader_mode: bool = False) -> None:
        async with sem2:
            try:
                snap = await _fetch_snapshot("1." + c["code"], c["code"], c["name"], variant, priority_override, allow_paid)
            except Exception:
                snap = {"error": "fetch"}
            c["snap"] = snap
            try:
                c["fund"] = await _fundamental_check(c)
            except Exception:
                c["fund"] = None
            if isinstance(snap, dict) and not snap.get("error"):
                s = _num(snap.get("score"))
                if leader_mode:
                    # 龙头层：AI 复核风险以警示展示，不按 8 分/条同权扣分
                    c["final"] = int(round(int(c["A"]["score"]) * 0.55 + s * 0.45))
                else:
                    c["final"] = int(round(int(c["A"]["score"]) * 0.55 + s * 0.45 - len(snap.get("risks") or []) * 8))
            else:
                c["final"] = int(c["A"]["score"])

    if cfg.get("aiOk") and finals:
        await asyncio.gather(*[snap_work(c) for c in finals], return_exceptions=True)

    def _post_adjust(c: dict[str, Any]) -> bool:
        """利空/业绩/消息警示降权；返回 False 表示硬伤剔除（已计入 hard_rejected）。"""
        if c.get("final") is None:
            c["final"] = int((c.get("A") or {}).get("score") or 0)
        fund = _fund_of(c)
        if fund and fund.get("level") == "hard":
            return False
        # 利空警示扣分（硬伤已排除）
        warn_n = sum(1 for it in ((c.get("bearish") or {}).get("items") or []) if it.get("level") == "warn")
        if warn_n:
            c["final"] = max(0, int(c["final"]) - warn_n * 3)
        # 业绩红旗 + 消息面警示降权（-2/条）
        if fund:
            fwarn = len(fund.get("flags") or []) + min(len(fund.get("newsWarn") or []), 2)
            if fwarn:
                c["final"] = max(0, int(c["final"]) - fwarn * 2)
            g = int(fund.get("growth") or 0)
            if g:
                c["final"] = max(0, min(100, int(c["final"]) + g))
        return True

    ok_fine: list[dict[str, Any]] = []
    for c in fine:
        if not _post_adjust(c):
            hard_rejected += 1
            continue
        ok_fine.append(c)
    fine = ok_fine

    def risk_of(c: dict[str, Any]) -> bool:
        snap = c.get("snap") if isinstance(c.get("snap"), dict) else None
        if snap and snap.get("risks"):
            return True
        if not snap and (c.get("A") or {}).get("risks"):
            return True
        return False

    zero_risk = [
        c for c in fine
        if not risk_of(c)
        and (c.get("bearish") or {}).get("level") == "pass"
        and (_fund_of(c) or {}).get("level", "pass") == "pass"
    ]
    warned = [c for c in fine if c not in zero_risk]
    zero_risk.sort(key=lambda x: -int(x.get("final") or 0))
    warned.sort(key=lambda x: -int(x.get("final") or 0))
    pool = zero_risk + warned

    all_sorted = sorted(fine, key=lambda x: -int(x.get("final") or 0))

    picks: list[dict[str, Any]] = []
    if market == "all":
        # 全市场主推分层：主线龙头 2 + 板块内补涨卡位 1
        # 龙头层：板块排行前列（王者/重点板块）龙头，leaderOk 确认形态与资金；
        # 不要求“未大幅拉升”，但 20 日涨幅超 max60d 仍排除（避免极端追高）。
        leader_pool: list[dict[str, Any]] = []
        for c in leader_analyzed:
            a = c.get("A") or {}
            if not (a.get("patterns") or {}).get("leaderOk"):
                continue
            if not _leader_bearish_adjust(c, a):
                continue
            if a.get("chg20", 0) > float(cfg["max60d"]):
                continue
            if c.get("_board_tier") == "king":
                a["score"] = min(100, int(a.get("score") or 0) + 4)
            leader_pool.append(c)
        leader_pool.sort(key=lambda x: -int((x.get("A") or {}).get("score") or 0))
        leader_pre = leader_pool[: int(cfg.get("leaderBoards") or 3) * int(cfg.get("leaderPerBoard") or 3)]
        if cfg.get("aiOk") and leader_pre:
            await asyncio.gather(*[snap_work(c, True) for c in leader_pre], return_exceptions=True)
        leader_final: list[dict[str, Any]] = []
        for c in leader_pre:
            if not _post_adjust(c):
                continue
            # 板块资金榜确认 + 龙头辨识度加分
            c["final"] = min(100, int(c.get("final") or 0) + 10)
            leader_final.append(c)
        leader_final.sort(key=lambda x: -int(x.get("final") or 0))

        # 卡位层：板块内补涨（位置<40%、5日涨幅<15%、50-300亿、当日主力净流入为正）
        catchup_pool = [
            c for c in all_sorted
            if _num(c.get("mcap")) >= float(cfg.get("catchupMcapMin") or 50.0) * 1e8
            and _num(c.get("mcap")) <= float(cfg.get("catchupMcapMax") or 300.0) * 1e8
            and (c.get("A") or {}).get("chg5", 999) <= float(cfg.get("catchupChg5Max") or 15.0)
            and (c.get("A") or {}).get("pos", 99) <= float(cfg.get("catchupPosMax") or 0.40)
            and _num(c.get("fundIn")) > 0
        ]
        catchup_pool.sort(key=lambda x: -int(x.get("final") or 0))

        for c in leader_final[:2]:
            c["tier"] = "king" if not picks else "key"
            c["star"] = not bool(picks)
            c["pick_role"] = "leader"
            picks.append(c)
        if len(picks) < 3 and catchup_pool:
            c = catchup_pool[0]
            c["tier"] = "key"
            c["star"] = False
            c["pick_role"] = "catchup"
            picks.append(c)
        if len(picks) < 4:
            used = {str(c.get("code")) for c in picks}
            for c in all_sorted:
                if str(c.get("code")) in used:
                    continue
                c["tier"] = "key"
                c["star"] = False
                c["pick_role"] = "catchup"
                picks.append(c)
                used.add(str(c.get("code")))
                if len(picks) >= 4:
                    break

    if not picks:
        # 北证 / 龙头不足兜底：王者(1⭐) + 重点(2)
        # 王者优先经零风险池最高分（final>=58）；若无，退而求其次取全池第一名
        king: dict[str, Any] | None = None
        if zero_risk:
            z0 = zero_risk[0]
            if int(z0.get("final") or 0) >= 58:
                king = z0
        if king is None and all_sorted:
            for cand in all_sorted:
                if _num((cand.get("A") or {}).get("pe")) > 0:
                    king = cand
                    break
            if king is None:
                king = all_sorted[0]
        rest = [c for c in pool if c is not king]
        keys = rest[:3]
        if king:
            king["tier"] = "king"
            king["star"] = True
            picks.append(king)
        for c in keys:
            c["tier"] = "key"
            c["star"] = False
            picks.append(c)
    # 主推统一 4 只：主线龙头 2 + 补涨卡位 2（2×2 排版；数据不足时按 3→2 递减，宁缺毋滥）
    if len(picks) > 4:
        picks = picks[:4]
    for c in picks:
        c["strategy"] = build_strategy(c, c.get("tier") or "normal", c.get("pick_role"))
    for i, c in enumerate(picks):
        c["rank"] = i + 1

    picked = {str(c.get("code")) for c in picks}
    runners = [c for c in all_sorted if str(c.get("code")) not in picked][:10]

    asof = picks[0].get("lastDate") if picks else (today or "")
    pick_out = [_pick_out(c) for c in picks]
    run_out = [_runner_out(c) for c in runners]
    # 板块 secid 解析（供前端点击跳转 AI行情官对应板块）
    try:
        await _attach_board_secids(rev_mainlines[:10], hot.get("list") or [])
    except Exception:
        pass
    if market == "all":
        board_rank = _board_rank_funds(board_pool or [], int(cfg.get("allBackupN") or 4))
    else:
        board_rank = _board_rank(rev_mainlines[:10], hot.get("list") or [])

    result: dict[str, Any] = {
        "ok": True, "cached": False, "date": today, "asof": asof,
        "market_code": market,
        "total": total, "scanned": len(cands), "fine": len(fine),
        "hard_rejected": hard_rejected,
        "generated_ts": int(time.time()), "elapsed_s": round(time.time() - t0, 1),
        "market": mkt_env,
        "hot_boards": hot.get("list") or [],
        "mainlines": rev_mainlines[:10],
        "board_rank": board_rank,
        "picks": pick_out,
        "runners": run_out,
    }
    _kline_cache_flush()
    if boards_only:
        result["vip_required"] = True
        result.pop("picks", None)
        result.pop("runners", None)
        _BOARDS_CACHE[boards_key] = (time.time(), result)
        return result
    # 有结果则持久化：供今日无合格标的回退展示 + 历史归档回看
    if pick_out:
        hist_payload: dict[str, Any] = {
            "date": today, "asof": asof, "market_code": market,
            "total": result["total"], "scanned": result["scanned"],
            "fine": result["fine"], "hard_rejected": hard_rejected,
            "generated_ts": result["generated_ts"], "elapsed_s": result["elapsed_s"],
            "market": mkt_env, "hot_boards": hot.get("list") or [],
            "mainlines": rev_mainlines[:10], "board_rank": board_rank,
            "picks": pick_out, "runners": run_out,
        }
        _save_history(f"{market}:{str(today)}", hist_payload)
        _save_archive(market, str(today), hist_payload)
    _SCAN_CACHE[full_key] = (time.time(), result)
    _BOARDS_CACHE.pop(boards_key, None)
    _persist_daily_scan_cache()
    return _apply_stale_fallback(result, market)


# 进程启动即加载当日扫描结果磁盘缓存（减少重启后的上游请求）
_load_daily_scan_cache()
