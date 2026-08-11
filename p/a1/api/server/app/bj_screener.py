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
from .ths_fuyao import fetch_special as ths_fetch_special

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
    "aiMin": 60.0, "topN": 5, "cap": 60, "aiTop": 8, "aiOk": True,
    "kw": "", "minSurge": 4.0, "surgeVol": 1.8, "surgeDays": 15,
    "mainline": "score", "hotPct": 4.0, "hotN": 12, "mainlineMemberCap": 60,
    "turnMin": 2.0, "turnMax": 20.0, "useFund": True,
    "scoreMin": 46.0,
    # 全市场（沪深京）参数：板块先行两阶段筛选
    "mcapMinAll": 15.0, "mcapMaxAll": 200.0, "amountMinAll": 8000.0,
    "hotBoards": 16, "memberCap": 800, "allBackupN": 4,
    # 主线龙头层（板块确认后放宽市值/位置约束）与补涨卡位层
    "leaderBoards": 3, "leaderPerBoard": 3, "leaderMcapMax": 5000.0,
    "catchupMcapMin": 50.0, "catchupMcapMax": 300.0,
    "catchupChg5Max": 15.0, "catchupPosMax": 0.40,
}

# 扫描结果缓存：同自然日重复请求直接返回（force=1 强制重扫）
_SCAN_CACHE: dict[str, tuple[float, dict]] = {}
# 扫描进度（供前端进度条轮询）：key = market，单进程内最新一次扫描的进度快照
_SCAN_PROGRESS: dict[str, dict[str, Any]] = {}

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

# 归档版本索引（全部保留版本，含同日多版本）：供程序/后续功能调用，不参与页面展示
_ARCHIVE_INDEX_PATH = os.path.join(_ARCHIVE_DIR, "archive_index.json")

# 归档文件名白名单：仅 "YYYY-MM-DD..." 才算归档，排除 winrate_cache 等内部缓存文件
_ARCH_FILE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")

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

def _prev_day_picks(market: str = "bj") -> tuple[str, list[dict[str, Any]]]:
    """上一交易日主推（按市场隔离）：取 date != 今天 且 picks 非空的最新一条。
    用于“昨日主推→今日状态”追踪与延续加分，避免每日推新导致用户追着换股。"""
    try:
        hist = _load_history()
        prefix = str(market or "bj") + ":"
        today = time.strftime("%Y-%m-%d", time.localtime())
        for key in reversed(list(hist.keys())):
            if not (key.startswith(prefix) or ":" not in key):
                continue
            v = hist.get(key)
            if isinstance(v, dict) and v.get("picks") and str(v.get("date") or "") != today:
                return str(v.get("date") or v.get("asof") or ""), v.get("picks") or []
    except Exception:
        pass
    return "", []


def _archive_board_rank_days(market: str, limit: int = 8) -> list[set[str]]:
    """近 N 个归档日的板块名集合（按日期倒序去重），用于计算板块连续上榜天数。"""
    try:
        if not os.path.isdir(_ARCHIVE_DIR):
            return []
        out: list[tuple[str, set[str]]] = []
        for fn in sorted(os.listdir(_ARCHIVE_DIR), reverse=True):
            if not fn.endswith(".json") or not _ARCH_FILE_RE.match(fn):
                continue
            try:
                j = json.load(open(os.path.join(_ARCHIVE_DIR, fn), encoding="utf-8"))
            except Exception:
                continue
            if str(j.get("market_code") or j.get("market") or "") != market:
                continue
            dt = str(j.get("date") or "")
            if not dt or dt in {x[0] for x in out}:
                continue
            nms = {str(b.get("name") or "") for b in (j.get("board_rank") or []) if b and b.get("name")}
            if nms:
                out.append((dt, nms))
            if len(out) >= limit:
                break
        return [s for _, s in out]
    except Exception:
        return []


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


def _kline_cache_load(date8: str) -> tuple[dict[str, Any], dict[str, float]]:
    obj = _load_json_file(_kline_cache_path(date8), {}) or {}
    if isinstance(obj, dict) and isinstance(obj.get("data"), dict):
        return obj["data"], obj.get("ts") or {}
    # 旧格式：{code: rows}
    return obj, {}


def _kline_cache_get(date8: str, code: str) -> list[list[Any]] | None:
    global _KLINE_DAILY
    if _KLINE_DAILY.get("date") != date8:
        data, ts = _kline_cache_load(date8)
        _KLINE_DAILY = {"date": date8, "data": data, "ts": ts}
    rows = _KLINE_DAILY["data"].get(code)
    ts = float(_KLINE_DAILY.get("ts", {}).get(code) or 0)
    if isinstance(rows, list) and rows and (time.time() - ts) < _KLINE_TTL:
        return rows
    return None


def _kline_cache_put(date8: str, code: str, rows: list[list[Any]]) -> None:
    global _KLINE_DAILY
    if _KLINE_DAILY.get("date") != date8:
        data, ts = _kline_cache_load(date8)
        _KLINE_DAILY = {"date": date8, "data": data, "ts": ts}
    _KLINE_DAILY["data"][code] = rows
    _KLINE_DAILY["ts"][code] = time.time()


def _kline_cache_flush() -> None:
    try:
        if _KLINE_DAILY.get("data"):
            _save_json_file(
                _kline_cache_path(str(_KLINE_DAILY["date"])),
                {"data": _KLINE_DAILY["data"], "ts": _KLINE_DAILY.get("ts") or {}},
            )
    except Exception:
        pass


def _winrate_cache_path() -> str:
    return os.path.join(_ARCHIVE_DIR, "winrate_cache.json")


_WINRATE_CACHE: dict[str, Any] = {}


def _winrate_cache_load() -> dict[str, Any]:
    if not _WINRATE_CACHE:
        _WINRATE_CACHE.update(_load_json_file(_winrate_cache_path(), {}) or {})
    return _WINRATE_CACHE


async def compute_winrate(days: int = 14, variant: str = "vip", priority_override: str = "", allow_paid: bool = True) -> dict[str, Any]:
    """实测战绩：回溯最近 N 天主推的 5日/10日 达标率与止损率（VIP 可验证胜率）。"""
    days = max(1, min(int(days or 14), 30))
    cache = _winrate_cache_load()
    today8 = _today8()
    if cache.get("asof") == today8 and cache.get("ok"):
        return cache
    hist = _load_history() or {}
    cutoff = time.time() - days * 86400
    jobs: list[tuple[str, str, dict[str, Any]]] = []
    seen: set[tuple[str, str]] = set()
    for key, payload in hist.items():
        d = str(key).split(":")[-1]
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
            continue
        try:
            ts = time.mktime(time.strptime(d, "%Y-%m-%d"))
        except Exception:
            continue
        if ts < cutoff:
            continue
        for p in (payload.get("picks") or []):
            code = str(p.get("code") or "")
            asof = str(p.get("lastDate") or p.get("asof") or "")
            if not code or not asof or (code, asof) in seen:
                continue
            seen.add((code, asof))
            jobs.append((code, asof, p))
    jobs = jobs[:30]
    results: list[dict[str, Any]] = []
    for code, asof, p in jobs:
        try:
            rows = await _kline_with_retry(code, variant, priority_override, allow_paid, use_cache=True)
        except Exception:
            continue
        if not rows:
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
        if idx is None or idx >= len(rows) - 1:
            results.append({"code": code, "asof": asof, "name": str(p.get("name") or ""), "state": "tracking", "fwd5": None, "fwd10": None, "stop_hit": None})
            continue
        entry = float(p.get("price") or rows[idx][2]) or 1.0
        hi5 = max(float(r[3]) for r in rows[idx + 1: min(idx + 6, len(rows))])
        fwd5 = (hi5 / entry - 1) * 100
        fwd10 = None
        stop_hit = None
        if idx + 10 < len(rows):
            fwd10 = (float(rows[idx + 10][2]) / entry - 1) * 100
            stop = float((p.get("levels") or {}).get("stop") or 0)
            if stop > 0:
                stop_hit = min(float(r[4]) for r in rows[idx + 1: idx + 11]) <= stop
        results.append({
            "code": code, "asof": asof, "name": str(p.get("name") or ""),
            "tier": str(p.get("tier") or "normal"), "role": str(p.get("pickRole") or ""),
            "final": p.get("final"), "state": "done",
            "fwd5": round(fwd5, 1), "fwd10": round(fwd10, 1) if fwd10 is not None else None,
            "stop_hit": stop_hit,
        })
    done = [r for r in results if r.get("state") == "done" and r.get("fwd5") is not None]
    n = len(done)
    hit5 = sum(1 for r in done if r["fwd5"] >= 5.0)
    pos5 = sum(1 for r in done if r["fwd5"] >= 0)
    stop_n = sum(1 for r in done if r.get("stop_hit"))
    tracking = sum(1 for r in results if r.get("state") == "tracking")
    by_tier: dict[str, dict[str, Any]] = {}
    for r in done:
        k = r.get("tier") or "normal"
        b = by_tier.setdefault(k, {"n": 0, "hit": 0})
        b["n"] += 1
        if r["fwd5"] >= 5.0:
            b["hit"] += 1
    out = {
        "ok": True, "asof": today8, "n": n, "tracking": tracking,
        "hit5_rate": round(hit5 / n * 100, 1) if n else None,
        "pos5_rate": round(pos5 / n * 100, 1) if n else None,
        "stop_rate": round(stop_n / n * 100, 1) if n else None,
        "hit_def": "5日内最高涨幅≥5%计为达标",
        "by_tier": by_tier,
        "recent": results[-12:],
    }
    cache.update(out)
    try:
        _save_json_file(_winrate_cache_path(), cache)
    except Exception:
        pass
    return out


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
                names = sorted(n for n in os.listdir(_ARCHIVE_DIR) if n.endswith(".json") and _ARCH_FILE_RE.match(n))
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
    _rebuild_archive_index()


_MULTI_ARCH_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}) \((\d{2}):(\d{2})\)$")


def _multi_archive_path(market: str, date_key: str) -> str | None:
    """同日多版本归档：date_key 形如 "2026-08-07 (15:27)"，文件名为 {date}-{market}-{HHMM}.json。"""
    m = _MULTI_ARCH_RE.match(str(date_key or ""))
    if not m:
        return None
    return os.path.join(_ARCHIVE_DIR, f"{m.group(1)}-{str(market or 'bj')}-{m.group(2)}{m.group(3)}.json")


def _rebuild_archive_index() -> None:
    """重建归档版本索引（archive_index.json）：列出全部保留的历史版本文件摘要。

    展示层（archive_summary）只取「每日最终版」；本索引保留所有版本（含同日多版本、
    旧版无市场后缀），供程序/后续功能调用。备份目录在子目录，不会被扫入。
    """
    try:
        if not os.path.isdir(_ARCHIVE_DIR):
            return
        idx: list[dict[str, Any]] = []
        for nm in os.listdir(_ARCHIVE_DIR):
            if not (nm.endswith(".json") and _ARCH_FILE_RE.match(nm)):
                continue
            fp = os.path.join(_ARCHIVE_DIR, nm)
            try:
                d = _load_json_file(fp, None)
                if not isinstance(d, dict):
                    continue
                mt = os.path.getmtime(fp)
            except Exception:
                continue
            stem = nm[:-5]
            mm = re.match(r"^(\d{4}-\d{2}-\d{2})-(all|bj)(?:-(\d{4}))?$", stem)
            if mm:
                market = mm.group(2)
                date_key = mm.group(1)
                if mm.group(3):
                    date_key = f"{mm.group(1)} ({mm.group(3)[:2]}:{mm.group(3)[2:]})"
            else:
                market = "bj"  # 旧版无市场后缀 → 北证
                date_key = stem
            idx.append({
                "file": nm,
                "market": market,
                "date": date_key,
                "day": date_key.split(" (", 1)[0],
                "asof": d.get("asof") or date_key,
                "generated_ts": d.get("generated_ts"),
                "mtime": round(mt, 3),
                "total": d.get("total"),
                "fine": d.get("fine"),
                "picks": [
                    {"code": p.get("code"), "name": p.get("name"),
                     "tier": p.get("tier") or "normal", "star": bool(p.get("star")),
                     "final": p.get("final")}
                    for p in (d.get("picks") or []) if isinstance(p, dict)
                ],
            })
        idx.sort(key=lambda x: (str(x.get("day") or ""), str(x.get("date") or "")), reverse=True)
        _save_json_file(_ARCHIVE_INDEX_PATH, {"updated_ts": int(time.time()), "n": len(idx), "items": idx})
    except Exception:
        pass


def archive_versions(market: str = "") -> dict[str, Any]:
    """归档版本索引（全部保留版本，含同日多版本），供程序调用；market 空=全部，all/bj 过滤。"""
    try:
        d = _load_json_file(_ARCHIVE_INDEX_PATH, None)
    except Exception:
        d = None
    if not isinstance(d, dict):
        _rebuild_archive_index()
        d = _load_json_file(_ARCHIVE_INDEX_PATH, None) or {}
    items = d.get("items") or []
    market = str(market or "").strip().lower()
    if market in ("all", "bj"):
        items = [it for it in items if it.get("market") == market]
    out = dict(d)
    out["items"] = items
    return out


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
    """历史归档选择器（按市场隔离）：优先以 bj_scan_history.json 索引为准。

    索引 = 每次扫描保存的「当日最终快照」，与 stale 回退 / 昨日跟踪同源，全站口径一致；
    避免按归档文件名倒序误选早盘临时版/旧主版本（如 08-10 北证 11:44 版 57/54 压过
    16:09 收盘版 68/60）。索引缺失的旧日期（如 2026-08-06 无市场前缀）回退扫描归档文件。
    同日多版本文件一律保留在磁盘，详情打开仍可寻址。
    """
    market = str(market or "bj")
    out: list[dict[str, Any]] = []
    try:
        hist = _load_history()
        items: list[dict[str, Any]] = []
        for k, v in hist.items():
            if not isinstance(v, dict):
                continue
            if ":" in k:
                mk, dk = k.split(":", 1)
            else:
                mk, dk = "bj", k  # 旧版无市场前缀 → 按北证
            if mk != market:
                continue
            picks = v.get("picks") or []
            items.append({
                "date": dk,
                "asof": v.get("asof") or dk,
                "total": v.get("total"),
                "fine": v.get("fine"),
                "picks": [
                    {
                        "code": p.get("code"), "name": p.get("name"),
                        "tier": p.get("tier") or "normal",
                        "final": p.get("final"), "price": p.get("price"), "pct": p.get("pct"),
                    }
                    for p in picks[:4] if isinstance(p, dict)
                ],
            })
        items.sort(key=lambda x: str(x.get("date") or ""), reverse=True)
        out.extend(items[:_ARCHIVE_KEEP_DAYS])
    except Exception:
        pass
    if out:
        return out
    # 索引为空时的兜底：按归档文件 mtime 取每日最新一份
    try:
        if not os.path.isdir(_ARCHIVE_DIR):
            return out
        by_day: dict[str, tuple[float, str]] = {}
        for nm in os.listdir(_ARCHIVE_DIR):
            if not (nm.endswith(".json") and _ARCH_FILE_RE.match(nm)):
                continue
            mm0 = re.match(r"^(\d{4}-\d{2}-\d{2})", nm)
            if not mm0:
                continue
            day = mm0.group(1)
            fp = os.path.join(_ARCHIVE_DIR, nm)
            try:
                mt = os.path.getmtime(fp)
            except Exception:
                continue
            if day not in by_day or mt > by_day[day][0]:
                by_day[day] = (mt, nm)
        for day in sorted(by_day, reverse=True)[:_ARCHIVE_KEEP_DAYS]:
            _, nm = by_day[day]
            stem = nm[:-5]
            mm = re.match(r"^(\d{4}-\d{2}-\d{2})-(all|bj)-(\d{4})$", stem)
            if mm:
                if mm.group(2) != market:
                    continue
                date_key = f"{mm.group(1)} ({mm.group(3)[:2]}:{mm.group(3)[2:]})"
            else:
                if market == "all":
                    if not stem.endswith("-all"):
                        continue
                    date_key = stem[:-4]
                else:
                    if stem.endswith("-all"):
                        continue
                    date_key = stem[:-3] if stem.endswith("-bj") else stem
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
    """今日无合格标的时，回退展示上一交易日结果并打 stale 标记。

    不原地修改 result：先浅拷贝再合并，避免污染 _SCAN_CACHE / 磁盘缓存——
    否则缓存里只剩昨日归档数据，今日真实扫描结果（fine/runner/未达主推线原因）无法核对。
    """
    if result.get("picks"):
        return result
    stale = _latest_history(market)
    if not stale:
        return result
    out = dict(result)
    out["stale"] = True
    out["stale_from"] = stale.get("asof") or stale.get("date") or ""
    out["picks"] = stale.get("picks") or []
    out["runners"] = stale.get("runners") or []
    if not out.get("mainlines"):
        out["mainlines"] = stale.get("mainlines") or []
    # 今日扫描透明度：即使回退展示上一交易日，也保留今日扫描结论供前端说明（避免“空算法”疑虑）
    _tf: dict[str, Any] = {"fine": int(result.get("fine") or 0), "hard": int(result.get("hard_rejected") or 0)}
    _top = (result.get("runners") or [])[:1]
    if _top:
        _t0 = _top[0]
        _tf["top"] = {
            "code": _t0.get("code"), "name": _t0.get("name"),
            "final": _t0.get("final"), "score": _t0.get("score"),
            "risks": _t0.get("risks") or [],
        }
    out["today_fine"] = _tf
    return out


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
    turn = _num(row.get("f8"))
    if not (float(cfg.get("turnMin") or 0) <= turn <= float(cfg.get("turnMax") or 100)):
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
            "pn": 1, "pz": 10, "po": 1, "np": 1, "fltt": 2, "invt": 2,
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
    # ---- 新增安全因子（第一批：量能/乖离/位置/蓄势/资金）----
    # 持续缩量阴跌：5日均量 < 0.5×20日均量 且 今日收阴
    vol_shrink = bool(v5 < 0.5 * v20 and cl < o[last])
    # 价格创20日新高但量能不足前高量50%（无量新高）
    hi20 = max(h[last - 19: last + 1]) if n >= 20 else max(h)
    hi20_idx = last
    for _i in range(last, -1, -1):
        if h[_i] >= hi20:
            hi20_idx = _i
            break
    new_high_weak = bool(
        n >= 20 and hi20_idx < last and cl >= hi20 * 0.995
        and v[last] < 0.5 * (v[hi20_idx] or v20)
    )
    # 贴前高且缩量（突破失败风险）
    at_high_weak = bool(hi60 > 0 and cl >= hi60 * 0.98 and v[last] < v20)
    # 涨放量/跌缩量健康度（近10日）
    up_vol = down_vol = 0.0
    up_cnt = down_cnt = 0
    for _i in range(max(1, last - 9), last + 1):
        if c[_i] >= o[_i]:
            up_vol += v[_i]; up_cnt += 1
        else:
            down_vol += v[_i]; down_cnt += 1
    vol_health = 0
    if up_cnt >= 3 and down_cnt >= 2:
        _ua = up_vol / up_cnt
        _da = down_vol / down_cnt
        if _da > 0 and _ua >= 1.3 * _da:
            vol_health = 1
        elif _ua > 0 and _da >= 1.3 * _ua:
            vol_health = -1
    # 乖离：现价偏离 MA5 / MA20
    bias_ma5 = (cl - ma5) / ma5 * 100 if ma5 else 0.0
    bias_ma20 = (cl - ma20) / ma20 * 100 if ma20 else 0.0
    bias_over = bool(bias_ma5 > 8 or bias_ma20 > 15)
    # 平台蓄势：近30日小振幅（<=4%）天数
    plateau_days = 0
    for _i in range(max(0, last - 30), last + 1):
        _pc = c[_i - 1] if _i > 0 and c[_i - 1] > 0 else cl
        if _pc > 0 and (h[_i] - l[_i]) / _pc * 100 <= 4:
            plateau_days += 1
    # 20日振幅
    amp20 = (max(h[last - 19: last + 1]) - min(l[last - 19: last + 1])) / cl * 100 if cl and n >= 20 else 0.0
    # 关键位（供赔率与止损计算）
    s1 = min(l[last - 4:])
    s2 = ma20
    p1 = max(h[last - 9:])
    p2 = hi60
    stop = min(s1, s2)
    # 收盘承接：当日振幅内收盘位置（有承接才易续涨）
    _rng = h[last] - l[last]
    close_pos = (cl - l[last]) / _rng if _rng > 0 else 0.5
    # 赔率：目标1 vs 止损距离（决定可操作性）
    odds1 = (p1 - cl) / (cl - stop) if cl > stop > 0 else 0.0
    odds2 = (p2 - cl) / (cl - stop) if cl > stop > 0 else 0.0
    odds_use = max(odds1, odds2)  # 双目标取优（10日/60日压力），避免突破新高后误判无空间
    # 资金持续流入近似：近4日连续3日收阳且量能不萎缩
    fund_streak = False
    if last >= 4:
        fund_streak = bool(
            c[last] > c[last - 1] and v[last] >= v[last - 1]
            and c[last - 1] > c[last - 2] and v[last - 1] >= v[last - 2]
            and c[last - 2] > c[last - 3] and v[last - 2] >= v[last - 3]
        )
    patterns: dict[str, int] = {}
    risks: list[str] = []
    if close_pos < 0.35:
        risks.append("收盘偏弱(承接不足)")
    if 0 < odds_use < 1.2:
        risks.append(f"赔率不足(双目标{odds_use:.1f}×止损)")
    # 底部走多：站上MA20 + MA20上拐 + MA5>MA10 + MACD红柱
    if cl > ma20 and ma20 > ma20_3 and ma5 > ma10 and hist[last] > 0:
        patterns["baseUp"] = 1
    # 异动拉升后回踩企稳（分市场阈值：北证30cm用大阳标准，沪深用涨停/大阳标准）
    pulled = False
    pull_surge_pct = 0.0
    surge_min = 10.0 if market == "bj" else 7.0
    surge_vol = 2.0 if market == "bj" else 1.5
    for i in range(n - 13, last - 1):
        pcti = (c[i] / c[i - 1] - 1) * 100 if c[i - 1] > 0 else 0.0
        if pcti >= surge_min and v[i] >= surge_vol * v20:
            for j in range(i + 1, last + 1):
                ok_pull = (
                    l[j] < h[i]
                    and v[j] < v[i] * 0.75
                    and (last - j) <= 3
                    and l[j] >= l[i] * 0.97
                    and cl >= max(c[i], c[j]) * 0.97
                    and cl >= ma10
                )
                if ok_pull:
                    pulled = True
                    pull_surge_pct = pcti
                    break
            if pulled:
                break
    if pulled:
        patterns["pullback"] = 1
        if pull_surge_pct >= (20.0 if market == "bj" else 9.5):
            patterns["ztPullback"] = 1  # 涨停级回踩：最强低吸形态
    # 一路小阳
    if up_days >= 3 and max_day_pct <= 8 and 0 <= chg5 <= 18:
        patterns["smallYang"] = 1
    # 底部放量异动启动（核心：刚底部异动起来）
    ms_min = max(float(cfg["minSurge"]), 10.0 if market == "bj" else 7.0)
    sv_min = max(float(cfg["surgeVol"]), 2.0 if market == "bj" else 1.5)
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
        if ms_min <= pcti <= 14 and v[i] >= sv_min * v_ma and pos_at_i <= 0.5:
            surge_idx = i
    surge_ok = False
    if surge_idx >= 0:
        surge_days_ago = last - surge_idx
        if surge_days_ago <= int(cfg["surgeDays"]) and cl >= ma5 and cl >= c[surge_idx] * 0.97:
            surge_ok = True
    if surge_ok:
        patterns["surgeStart"] = 1
        if surge_days_ago > 7:
            patterns.pop("surgeStart", None)
            risks.append("异动过时(>7日未再启动)")
    if surge_idx >= 0 and not surge_ok:
        risks.append("底部异动后未确认企稳")
    # 均线粘合后发散（启动初期）
    spread = (max(ma5, ma10, ma20) - min(ma5, ma10, ma20)) / ma20 * 100 if ma20 else 0.0
    if spread <= 2.5 and ma5 > ma10 and ma10 > ma20 and hist[last] > 0:
        patterns["tightBurst"] = 1
    # 未大幅拉升 + 刚启动约束
    if chg5 <= float(cfg["max5d"]) and chg10 <= float(cfg["max10d"]):
        patterns["notHot"] = 1
    if chg5 > float(cfg["max5d"]):
        risks.append(f"5日涨幅偏大{chg5:.1f}%")
    if chg10 > float(cfg["max10d"]):
        risks.append(f"10日涨幅偏大{chg10:.1f}%")
    if chg20 > float(cfg["max20d"]):
        risks.append(f"20日涨幅过大{chg20:.1f}%")
    if chg60 > float(cfg["max60d"]):
        risks.append(f"60日涨幅过大{chg60:.1f}%")
    has_zt = False
    zt_day = -1
    zt_th = 25.0 if market == "bj" else 9.5
    for i in range(n - 10, last + 1):
        p0 = (c[i] / c[i - 1] - 1) * 100 if c[i - 1] > 0 else 0.0
        if p0 >= zt_th:
            has_zt = True
            zt_day = i
    if has_zt and not pulled:
        if zt_day >= 0 and cl < c[zt_day] * 0.985:
            risks.append("首板失败(跌破涨停价)")
        else:
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
    if vol_shrink:
        risks.append("持续缩量阴跌")
    if new_high_weak:
        risks.append("无量新高")
    if at_high_weak:
        risks.append("贴前高缩量")
    if bias_over:
        risks.append(f"乖离偏大(MA5 {bias_ma5:.0f}%)")
    if amp20 and amp20 < 3:
        risks.append("20日振幅过低(死水)")
    if amp20 and amp20 > 35:
        risks.append("20日振幅过大(偏疯)")
    if vol_health == -1:
        risks.append("跌放量出货嫌疑")
    kw_hits = list(cand.get("kwHits") or [])

    # ---- 综合评分（潜力框架：空间×驱动×时机−风险，0-100） ----
    sc = 0.0
    # ① 空间（0-36）：位置 + 距前高空间 + 市值弹性 + 稀缺性
    if pos <= 0.10:
        sc += 20
    elif pos <= 0.20:
        sc += 16
    elif pos <= 0.30:
        sc += 12
    elif pos <= 0.40:
        sc += 8
    else:
        sc += 2
    room = (hi60 - cl) / hi60 * 100 if hi60 > 0 else 0.0
    if 5 <= room <= 25:
        sc += 10
    elif 25 < room <= 45:
        sc += 7
    elif 2 <= room < 5:
        sc += 6
    elif room > 45:
        sc += 4
    else:
        sc += 1  # 贴前高(<2%)：空间被压
    pe = _num(cand.get("pe"))
    pb = _num(cand.get("pb"))
    mcap = _num(cand.get("mcap"))
    mcap_yi = mcap / 1e8
    if 5 <= mcap_yi <= 15:
        sc += 6
    elif 15 < mcap_yi <= 25:
        sc += 4
    elif 25 < mcap_yi <= 40:
        sc += 3
    # 稀缺性（0-6）：行业独苗 + 流通盘占比低（小流通盘弹性高）
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
    # ② 驱动（0-35）：启动证据 + 资金 + 量能 + 热度
    if patterns.get("ztPullback"):
        sc += 8
    if patterns.get("pullback"):
        sc += 12
    if patterns.get("surgeStart"):
        sc += 10
    if patterns.get("smallYang"):
        sc += 3  # 吸筹辅助确认（不单独构成启动证据）
    if cfg.get("useFund") and fund > 0:
        sc += 5
    if cfg.get("useFund") and _num(cand.get("fund5")) > 0:
        sc += 3
    if cand.get("hot"):
        sc += 4
    if kw_hits:
        sc += 2
    if vol_health == 1:
        sc += 3
    if fund_streak:
        sc += 2
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
    # ③ 时机（0-23）：走多确认 + 均线 + MACD + 动能 + 蓄势
    if patterns.get("baseUp"):
        sc += 6
    if patterns.get("tightBurst"):
        sc += 4
    if hist[last] > 0:
        sc += 2
    gc = False
    for i in range(last - 4, last + 1):
        if dif[i] > dea[i] and dif[i - 1] <= dea[i - 1]:
            gc = True
    if gc:
        sc += 2
    if ma_bull:
        sc += 6
    elif ma_bull3:
        sc += 4
    if ma20 > ma20_3:
        sc += 2
    # 主线龙头确认：资金回流 + 短期趋势走强 + MACD 不弱
    leader_ok = bool(
        fund > 0 and chg5 > 0 and cl > ma10
        and cl >= ma20 * 0.97
        and (hist[last] > 0 or gc)
    )
    if leader_ok:
        patterns["leaderOk"] = 1
        sc += 4
    if 55 <= rsi14 <= 72:
        sc += 2
    elif 40 <= rsi14 < 55:
        sc += 1
    if 4 <= atr_pct <= 10:
        sc += 2
    elif 1.5 <= atr_pct < 4:
        sc += 1
    if -3 <= bias6 <= 8:
        sc += 1
    if plateau_days >= 20:
        sc += 2
    elif plateau_days and plateau_days < 5:
        sc -= 2
    # 收盘承接 + 赔率
    if close_pos >= 0.60:
        sc += 3
    if odds_use >= 2.0:
        sc += 3
    elif odds_use >= 1.5:
        sc += 1
    elif 0 < odds_use < 1.2:
        sc -= 2
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
    # ④ 风险扣分（hard×8 / warn×3）
    warn_risk_hints = ("5日涨幅偏大", "10日涨幅偏大", "20日涨幅过大", "60日涨幅过大",
                       "赔率不足", "收盘偏弱(承接不足)", "异动过时(>7日未再启动)",
                       "换手过低", "换手过高", "乖离偏大", "20日振幅过大(偏疯)", "跌放量出货嫌疑")
    n_hard_risk = n_warn_risk = 0
    for _r in risks:
        if _r == "10日内有涨停/近涨停" or _r.startswith(warn_risk_hints):
            n_warn_risk += 1
        else:
            n_hard_risk += 1
    sc -= n_hard_risk * 8 + n_warn_risk * 3
    # ⑤ 无启动确认（小阳不算）：异动/回踩/走多一个都没有 → 强扣
    if not (patterns.get("pullback") or patterns.get("surgeStart") or patterns.get("baseUp")):
        sc -= 6
    # ⑥ 动量修正
    if bias_over:
        sc -= 4
    if amp20 and amp20 > 35:
        sc -= 3
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
        "closePos": round(close_pos, 2), "odds1": round(odds1, 2), "odds2": round(odds2, 2), "oddsUse": round(odds_use, 2),
        "kwHits": kw_hits, "hot": bool(cand.get("hot")),
        "hotName": cand.get("hotName") or "", "fund": fund,
        "ind": cand.get("ind") or "",
        # 新增因子
        "rsi14": rsi14, "boll_pos": boll_pos, "boll_width": boll_width,
        "atr_pct": atr_pct, "bias6": bias6, "bias12": bias12,
        "ma_bull": ma_bull, "ma_bull3": ma_bull3, "gc_days": gc_days,
        "leaderOk": leader_ok,
        "pe": pe, "pb": pb, "mcap": mcap,
        # 第一批安全因子
        "volShrink": vol_shrink, "newHighWeak": new_high_weak, "atHighWeak": at_high_weak,
        "volHealth": vol_health, "biasMa5": round(bias_ma5, 1), "biasMa20": round(bias_ma20, 1),
        "biasOver": bias_over, "plateauDays": plateau_days, "amp20": round(amp20, 1),
        "fundStreak": fund_streak,
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
        warn("跌破MA20且趋势下拐")
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
# 业绩预告方向（公告标题级）：预亏/预减=硬伤排除，预增/预盈=加分
_EARN_NEG = ["预亏", "预减", "预降", "大幅下滑", "业绩下滑"]
_EARN_POS = ["预增", "预盈", "大幅增长", "同比大幅增长", "大幅上升"]

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
    suffix = "BJ" if _is_bj_code(code) else ("SH" if str(code).startswith("6") else "SZ")
    url = ("https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_F10_FINANCE_MAINFINADATA"
           "&columns=ALL&filter=(SECUCODE%3D%22" + code + "." + suffix + "%22)"
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


# ---------------- 分时尾盘强度 + 龙虎榜（第二档：盘中承接/游资席位验证） ----------------
_MINUTE_CACHE: dict[str, tuple[str, list[Any]]] = {}
_LHB_CACHE: dict[str, tuple[str, dict[str, Any]]] = {}

_LHB_MAP_LOCK = asyncio.Lock()


def _ths_trading_days(n: int = 4) -> list[str]:
    """近 n 个交易日（跳过周末）YYYY-MM-DD，新→旧。"""
    out: list[str] = []
    d = time.localtime()
    while len(out) < n:
        ts = time.mktime(d)
        if time.localtime(ts).tm_wday < 5:
            out.append(time.strftime("%Y-%m-%d", d))
        d = time.localtime(ts - 86400)
    return out


def _is_bj_code(code: str) -> bool:
    return bool(re.fullmatch(r"(?:920\d{3}|(?:43|83|87|88|89)\d{4})", str(code)))


async def _fetch_minute(code: str) -> list[list[Any]] | None:
    """腾讯当日分时（日缓存）：[HHMM, price, cumVol, cumAmt?]，北证/沪深通用。"""
    hit = _MINUTE_CACHE.get(code)
    if hit and hit[0] == _today8():
        return hit[1]
    prefix = "bj" if _is_bj_code(code) else ("sh" if str(code).startswith("6") else "sz")
    arr: list[list[Any]] = []
    try:
        url = f"https://ifzq.gtimg.cn/appstock/app/minute/query?code={prefix}{code}"
        async with httpx.AsyncClient(timeout=10.0, headers=_UA) as cli:
            j = (await cli.get(url)).json()
        d = ((j.get("data") or {}).get(prefix + str(code)) or {})
        arr = ((d.get("data") or {}).get("data")) or []
    except Exception:
        arr = []
    if arr:
        _MINUTE_CACHE[code] = (_today8(), arr)
    return arr or None


def _tail_strength(arr: list[list[Any]] | None) -> dict[str, Any]:
    """尾盘承接强度：最后30分钟涨幅 + 尾盘量占比（收盘后=14:30-15:00，盘中=截至当前最后30分钟）。"""
    if not arr or len(arr) < 20:
        return {}
    try:
        rows: list[tuple[int, float, float]] = []
        for r in arr:
            parts = str(r).split()
            if len(parts) >= 3 and len(parts[0]) == 4:
                rows.append((int(parts[0][:2]) * 60 + int(parts[0][2:]), float(parts[1]), float(parts[2])))
        if len(rows) < 20:
            return {}
        last_t, last_p, last_v = rows[-1]
        t30, t60 = last_t - 30, last_t - 60
        p30 = p60 = None
        v30 = None
        for t, p, v in rows:
            if t <= t60:
                p60 = p
            if t <= t30:
                p30, v30 = p, v
        if p30 is None or p30 <= 0 or last_p <= 0:
            return {}
        tail_pct = (last_p / p30 - 1) * 100
        half_pct = (last_p / p60 - 1) * 100 if p60 and p60 > 0 else None
        tail_vol = (last_v - v30) / last_v * 100 if last_v > 0 and v30 is not None else None
        return {
            "tailPct": round(tail_pct, 2),
            "tailVol": round(tail_vol, 1) if tail_vol is not None else None,
            "halfPct": round(half_pct, 2) if half_pct is not None else None,
            "n": len(rows),
        }
    except Exception:
        return {}


async def _fetch_lhb_map(days: int = 6) -> dict[str, Any]:
    """近 N 日龙虎榜明细（日缓存）：{code: {name, dates, reasons, net, buy, sell}}。"""
    hit = _LHB_CACHE.get("map")
    if hit and hit[0] == _today8():
        return hit[1]
    out: dict[str, Any] = {}
    try:
        since = time.strftime("%Y-%m-%d", time.localtime(time.time() - max(2, days) * 86400))
        url = ("https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_DAILYBILLBOARD_DETAILSNEW"
               "&columns=SECURITY_CODE,SECURITY_NAME_ABBR,TRADE_DATE,EXPLANATION,BILLBOARD_NET_AMT,BILLBOARD_BUY_AMT,BILLBOARD_SELL_AMT"
               "&filter=(TRADE_DATE%3E%3D%27" + since + "%27)&pageNumber=1&pageSize=500&sortTypes=-1&sortColumns=TRADE_DATE")
        async with httpx.AsyncClient(timeout=12.0, headers=_UA) as cli:
            j = (await cli.get(url)).json()
        rows = ((j.get("result") or {}).get("data")) or []
        for r in rows:
            code = str(r.get("SECURITY_CODE") or "")
            if not code:
                continue
            e = out.setdefault(code, {
                "name": str(r.get("SECURITY_NAME_ABBR") or ""),
                "dates": [], "reasons": [], "net": 0.0, "buy": 0.0, "sell": 0.0,
            })
            e["dates"].append(str(r.get("TRADE_DATE"))[:10])
            e["reasons"].append(str(r.get("EXPLANATION") or ""))
            e["net"] += float(r.get("BILLBOARD_NET_AMT") or 0)
            e["buy"] += float(r.get("BILLBOARD_BUY_AMT") or 0)
            e["sell"] += float(r.get("BILLBOARD_SELL_AMT") or 0)
        _LHB_CACHE["map"] = (_today8(), out)
    except Exception:
        pass
    return out


async def _fetch_ths_lhb_map(days: int = 4) -> dict[str, Any]:
    """同花顺龙虎榜（日缓存+锁）：{code: {name, dates, reasons, net, buy, sell,
    hotRank, concepts, moneyTypes}}。board_type=all/org/hot_money × 近 N 个交易日；
    失败静默降级返回 {}，由东财版兜底。"""
    hit = _LHB_CACHE.get("ths_map")
    if hit and hit[0] == _today8():
        return hit[1]
    async with _LHB_MAP_LOCK:
        hit = _LHB_CACHE.get("ths_map")
        if hit and hit[0] == _today8():
            return hit[1]
        out: dict[str, Any] = {}
        try:
            for date_s in _ths_trading_days(days):
                for bt in ("all", "org", "hot_money"):
                    r = await ths_fetch_special(
                        "dragon-tiger-list", {"board_type": bt, "date": date_s})
                    item = r.get("item") if isinstance(r, dict) else None
                    if not isinstance(item, dict):
                        continue
                    for it in item.get("stock_items") or []:
                        raw = str(it.get("ticker") or it.get("thscode") or "").strip()
                        code = re.sub(r"\D", "", raw)[-6:]
                        if len(code) != 6:
                            continue
                        e = out.setdefault(code, {
                            "name": str(it.get("name") or ""),
                            "dates": [], "reasons": [], "net": 0.0,
                            "buy": 0.0, "sell": 0.0,
                            "hotRank": 0, "concepts": [], "moneyTypes": [],
                        })
                        if date_s not in e["dates"]:
                            e["dates"].append(date_s)
                        lr = str(it.get("limit_reason") or "").strip()
                        if lr and lr not in e["reasons"]:
                            e["reasons"].append(lr)
                        e["net"] += float(it.get("net_value") or 0)
                        e["buy"] += float(it.get("buy_value") or 0)
                        e["sell"] += float(it.get("sell_value") or 0)
                        hr = int(it.get("hot_rank") or 0)
                        if hr and (e["hotRank"] == 0 or hr < e["hotRank"]):
                            e["hotRank"] = hr
                        for cc in it.get("concept_list") or []:
                            cn = str(cc.get("name") or "").strip()
                            if cn and cn not in e["concepts"]:
                                e["concepts"].append(cn)
                        if bt not in e["moneyTypes"]:
                            e["moneyTypes"].append(bt)
            for e in out.values():
                e["dates"].sort(reverse=True)
                e["concepts"] = e["concepts"][:5]
            _LHB_CACHE["ths_map"] = (_today8(), out)
        except Exception:
            pass
        return out


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
    fin_task = asyncio.create_task(_fetch_financials(c["code"]))
    news_task = asyncio.create_task(_fetch_news_ann(c["code"]))
    fin = await fin_task
    titles = await news_task
    news_hard = [t for t in titles if any(k in t for k in _NEWS_HARD)][:4]
    news_warn = list(dict.fromkeys(
        t for t in titles if not any(k in t for k in _NEWS_HARD) and any(k in t for k in _NEWS_WARN)
    ))[:5]
    # 业绩预告方向（公告标题级）：预亏/预减=硬伤，预增/预盈=加分
    earn_neg = list(dict.fromkeys(t for t in titles if any(k in t for k in _EARN_NEG)))[:2]
    earn_pos = list(dict.fromkeys(t for t in titles if any(k in t for k in _EARN_POS)))[:2]
    flags = _fin_red_flags(fin) if fin else []
    growth = _growth_score(fin) if fin else 0
    if news_hard or earn_neg:
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
        "earnNeg": earn_neg,
        "earnPos": earn_pos,
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
        "earnNeg": fund.get("earnNeg") or [],
        "earnPos": fund.get("earnPos") or [],
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
            "rules": "次日不追高：高开>5%或冲高回落破分时均线→放弃/减半；回踩须缩量（量≤启动日70%）分批低吸；单日放量长阴-8%无条件离场",
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
        "rules": "次日不追高：高开>5%或冲高回落破分时均线→放弃/减半；回踩须缩量（量≤启动日70%）分批低吸；单日放量长阴-8%无条件离场",
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
        # 中证1000（小盘风险偏好，掘金主战场）同步确认
        weak1000 = False
        red1000 = False
        try:
            payload2 = await fetch_tx_kline("1.000852", "day", count=120, timeout=6.0, variant=variant, priority_override=priority_override, allow_paid=allow_paid)
            rows2 = _rows_from_payload(payload2)
            if rows2 and len(rows2) >= 61:
                a2 = analyze(rows2, {}, DEFAULT_CFG)
                red1000 = bool(a2["hist"][-1] > 0)
                weak1000 = bool(not (a2["closes"][-1] > a2["ma20"]) and not (a2["ma20"] > a2["ma20_3"]))
        except Exception:
            pass
        if (weak and not red) or (weak and weak1000):
            regime = "defensive"
        elif red and above and not weak1000:
            regime = "attack"
        else:
            regime = "stable"
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
        if weak1000:
            tags.append("中证1000走弱")
        elif red1000:
            tags.append("中证1000转强")
        return {
            "red": red, "red_days": int(a["gc_days"]), "ma_bull3": bool(a["ma_bull3"]),
            "above_ma20": above, "weak": weak, "weak1000": weak1000,
            "regime": regime, "tags": tags,
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


def _board_rank_funds(boards: list[dict[str, Any]], keep_backup: int = 4, mainline_names: list[str] | None = None) -> list[dict[str, Any]]:
    """全市场板块排行：复盘主线板块优先（资金+技术双确认），其余按 5日主力净流入排序，王者 1 + 辅线 2 + 备选 N。"""
    items = sorted((boards or []), key=lambda x: -float(x.get("f164") or 0))
    _ml: set[str] = set()
    if mainline_names:
        _ml = {str(n).replace(" ", "") for n in mainline_names if str(n).strip()}
        if _ml:
            items.sort(key=lambda x: (
                0 if (str(x.get("name") or "").replace(" ", "") in _ml) else 1,
                -float(x.get("f164") or 0),
            ))
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
            "mainline": bool(b.get("mainline") or (str(b.get("name") or "").replace(" ", "") in _ml)) if _ml else bool(b.get("mainline")),
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
    # 优先复用当日 K 线磁盘缓存（精筛阶段已拉过），避免快照阶段重复请求上游
    try:
        rows = _kline_cache_get(time.strftime("%Y%m%d", time.localtime()), str(code or "")) if code else None
        if rows and len(rows) >= 60:
            candles = candles_from_tencent_like_pack({"day": rows}, "day")
            if len(candles) >= 60:
                res = score_candles(candles, name=base["name"] or base["code"])
                base.update(res)
                return base
    except Exception:
        pass
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
    _raw_bars = c.get("_bars") or []
    if a:
        chart = {
            "closes": a.get("closes", [])[-60:], "opens": a.get("opens", [])[-60:],
            "highs": a.get("highs", [])[-60:], "lows": a.get("lows", [])[-60:],
            "vols": a.get("vols", [])[-60:],
            "dates": [str(b[0]) for b in _raw_bars[-60:]] or [],
            "ma5": _ma_arr(a.get("closes", []), 5)[-60:],
            "ma10": _ma_arr(a.get("closes", []), 10)[-60:],
            "ma20": _ma_arr(a.get("closes", []), 20)[-60:],
            "ma14": _ma_arr(a.get("closes", []), 14)[-60:],
            "ma28": _ma_arr(a.get("closes", []), 28)[-60:],
            "ma57": _ma_arr(a.get("closes", []), 57)[-60:],
            "s1": levels.get("s1"), "s2": levels.get("s2"),
            "p1": levels.get("p1"), "p2": levels.get("p2"),
        }
        if len(_raw_bars) >= 61:
            try:
                from .signals import candles_from_tencent_like_pack, build_signals_v3
                _candles = candles_from_tencent_like_pack({"day": _raw_bars}, "day")
                if len(_candles) >= 61:
                    _sig = build_signals_v3(_candles, cache_key="bjpick_%s" % c.get("code"))
                    _mk = _sig.get("markers") or []
                    _last_dates = {str(b[0]) for b in _raw_bars[-60:]}
                    chart["signals"] = [
                        {k: m.get(k) for k in ("time", "position", "color", "shape", "text", "size")}
                        for m in _mk if str(m.get("time") or "") in _last_dates
                    ]
            except Exception:
                chart["signals"] = []
    factors = {
        "rsi14": round(_num(a.get("rsi14")), 1) if a.get("rsi14") is not None else None,
        "boll_pos": round(_num(a.get("boll_pos")), 2) if a.get("boll_pos") is not None else None,
        "atr_pct": round(_num(a.get("atr_pct")), 1) if a.get("atr_pct") is not None else None,
        "bias6": round(_num(a.get("bias6")), 1) if a.get("bias6") is not None else None,
        "ma_bull": bool(a.get("ma_bull")), "gc_days": int(a.get("gc_days") or 0),
        "closePos": a.get("closePos"), "odds1": a.get("odds1"), "oddsUse": a.get("oddsUse"),
        "pe": _num(a.get("pe")), "pb": _num(a.get("pb")), "mcap_yi": round(_num(a.get("mcap")) / 1e8, 1),
    }
    return {
        "rank": c.get("rank"), "code": c.get("code"), "name": c.get("name"),
        "price": c.get("price"), "pct": c.get("pct"), "mcap": c.get("mcap"),
        "amount": c.get("amount"), "turnover": c.get("turnover"),
        "volRatio": c.get("volRatio"), "fundIn": c.get("fundIn"),
        "ind": c.get("ind"), "lastDate": c.get("lastDate"), "final": c.get("final"),
        "tier": c.get("tier") or "normal", "star": bool(c.get("star")),
        "cont": bool(c.get("cont")), "contPrevDate": c.get("contPrevDate") or "",
        "contPrevTier": c.get("contPrevTier") or "",
        "pickRole": str(c.get("pick_role") or ""),
        "relaxed": bool(c.get("relaxed")),
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
        "tail": c.get("tail") or {},
        "lhb": c.get("lhb"),
        "patterns": (a or {}).get("patterns") or {}, "risks": (a or {}).get("risks") or [],
        "levels": levels, "kwHits": (a or {}).get("kwHits") or [],
        "hot": bool((a or {}).get("hot")), "hotName": (a or {}).get("hotName") or "",
        "revHit": bool(c.get("revHit")), "revName": c.get("revName") or "",
        "boardLeader": bool(c.get("boardLeader")),
        "mainHit": bool(c.get("mainHit")), "mainName": c.get("mainName") or "",
        "volHealth": (a or {}).get("volHealth"), "fundStreak": bool((a or {}).get("fundStreak")),
        "plateauDays": (a or {}).get("plateauDays"), "biasOver": bool((a or {}).get("biasOver")),
        "amp20": (a or {}).get("amp20"),
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
        "mainHit": bool(c.get("mainHit")), "mainName": c.get("mainName") or "",
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


def scan_progress(market: str) -> dict[str, Any]:
    """返回指定市场最近一次扫描的进度（前端进度条轮询用）。"""
    p = _SCAN_PROGRESS.get(str(market or "bj").strip().lower())
    if not p:
        return {"ok": True, "running": False, "phase": "idle", "pct": 0,
                "done": 0, "total": 0, "msg": "", "ts": 0}
    return {"ok": True, **p}


def mark_scan_failed(market: str, msg: str = "扫描失败") -> None:
    """扫描异常时把进度复位为 done，避免前端进度条卡住。"""
    m = str(market or "bj").strip().lower()
    _SCAN_PROGRESS[m] = {"phase": "done", "pct": 100, "done": 0, "total": 0,
                         "msg": msg, "running": False, "ts": time.time()}


def _today_off_market() -> bool:
    """非交易日（周末/法定休市）：掘金不重复扫描，直接展示最近归档。"""
    try:
        from .daily_report import HOLIDAYS as _holidays, is_weekend as _is_weekend
        return bool(_is_weekend()) or (time.strftime("%Y-%m-%d") in _holidays)
    except Exception:
        return time.localtime().tm_wday >= 5


def _market_closed() -> bool:
    """交易日 15:03 后视为收盘，可更新今日数据；盘中（15:03 前）默认展示上一交易日归档。"""
    return int(time.strftime("%H%M", time.localtime())) >= 1503


# 复盘主线 → 东财板块 secid（主线成分补进掘金候选池用；未知板块回落 suggest 解析）
_MAINLINE_BOARD_MAP: dict[str, list[str]] = {
    "PCB": ["90.BK0877", "90.BK1340"],
    "创新药CXO": ["90.BK1600", "90.BK0899"],
    "通信光模块CPO": ["90.BK1128", "90.BK1136"],
    "煤炭": ["90.BK0437", "90.BK1250", "90.BK1493", "90.BK1494"],
    "半导体": ["90.BK1036", "90.BK1325"],
}


async def _collect_mainline_cands(cfg: dict[str, Any], names: list[str], hot: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    """主线板块全成分补进候选池（含板块名归属）：主线不在资金热度榜时，其低风险成分也要有机会进主推。"""
    out: list[dict[str, Any]] = []
    leaders_by_name: dict[str, list[dict[str, Any]]] = {}
    seen: set[str] = set()
    cap_total = int(cfg.get("mainlineMemberCap") or 40)
    for n in names:
        secids = list(_MAINLINE_BOARD_MAP.get(n) or [])
        if not secids:
            try:
                s = await _resolve_board_secid(n)
            except Exception:
                s = ""
            if s:
                secids = [s]
        boards = [{"name": n, "secid": sid} for sid in secids]
        if not boards:
            continue
        try:
            rows, _ld = await fetch_board_members(boards, 400)
            if _ld:
                leaders_by_name[n] = _ld.get(n) or []
        except Exception:
            rows = []
        for r in rows:
            code = str(r.get("f12") or "")
            if code in seen:
                continue
            c = coarse(r, cfg, hot)
            if not c:
                continue
            seen.add(code)
            c["mainline"] = True
            c["mainlineName"] = n
            out.append(c)
    out.sort(key=lambda x: (x.get("mcap") or 0, -(x.get("amount") or 0)))
    return out[:cap_total], leaders_by_name


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
    board_rank: list[dict[str, Any]] = []  # 北证路径无板块榜，预置空表防 UnboundLocalError
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
    if cfg_override:
        for k, v in cfg_override.items():
            if k in cfg and v is not None:
                cfg[k] = v
    t0 = time.time()
    today8 = time.strftime("%Y%m%d", time.localtime())
    today = time.strftime("%Y-%m-%d", time.localtime())
    # K线磁盘缓存 30 分钟 TTL 自动保鲜；force 仍会刷新 clist/快照/基本面
    use_cache = True
    boards_key = f"{market}-boards:" + today8
    full_key = f"{market}-scan:" + today8

    def _strip_conclusions(o: dict) -> dict:
        """非 VIP 板块视图：隐藏主线锁定结论（mainline 标记 + 主线列表），仅保留排行数据。
        重建 dict/list，不原地修改共享缓存对象。"""
        o = dict(o)
        o["board_rank"] = [dict(_b) for _b in (o.get("board_rank") or []) if isinstance(_b, dict)]
        for _br in o["board_rank"]:
            _br.pop("mainline", None)
        o["mainlines"] = []
        o.pop("prev_track", None)
        o.pop("prev_date", None)
        return o

    _SCAN_PROGRESS[market] = {"phase": "init", "pct": 1, "done": 0, "total": 0,
                              "msg": "准备启动扫描…", "running": True, "ts": time.time()}

    def _set_prog(phase: str, pct: float, msg: str, done: int = 0, total: int = 0) -> None:
        _SCAN_PROGRESS[market] = {"phase": phase, "pct": int(max(0, min(100, pct))),
                                  "done": done, "total": total, "msg": msg,
                                  "running": True, "ts": time.time()}

    def _mark_cached(msg: str) -> None:
        _SCAN_PROGRESS[market] = {"phase": "done", "pct": 100, "done": 0, "total": 0,
                                  "msg": msg, "running": False, "ts": time.time()}

    if boards_only:
        # 非 VIP：优先复用当日完整扫描（若有），否则做一次轻量板块扫描
        hit = _BOARDS_CACHE.get(boards_key)
        if hit and time.time() - hit[0] < 6 * 3600:
            out = dict(hit[1])
            out["cached"] = True
            out["vip_required"] = True
            out = _strip_conclusions(out)
            _mark_cached("已加载今日板块缓存")
            return out
        full = _SCAN_CACHE.get(full_key)
        if full and time.time() - full[0] < 12 * 3600:
            out = dict(full[1])
            out["cached"] = True
            out["vip_required"] = True
            out.pop("picks", None)
            out.pop("runners", None)
            out = _strip_conclusions(out)
            _BOARDS_CACHE[boards_key] = (time.time(), out)
            _mark_cached("已加载今日缓存")
            return out

        # 非交易日或盘中（未到 15:03）：直接展示最近归档板块视图，避免盘中半成品
        if _today_off_market() or not _market_closed():
            stale = _latest_history(market)
            if stale:
                out = dict(stale)
                out["cached"] = True
                out["stale"] = True
                out["vip_required"] = True
                out["stale_from"] = stale.get("asof") or stale.get("date") or ""
                out["market_code"] = market
                out["intraday"] = True
                out["date"] = stale.get("date") or stale.get("asof") or ""
                out.pop("picks", None)
                out.pop("runners", None)
                out = _strip_conclusions(out)
                _BOARDS_CACHE[boards_key] = (time.time(), out)
                _mark_cached("盘中/非交易日：展示最近归档板块视图")
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
                _mark_cached("已加载今日扫描缓存")
                return _apply_stale_fallback(out, market)
            # 非交易日（周末/休市）：不重复扫描，直接展示最近归档，节省上游与系统资源
            if _today_off_market():
                stale = _latest_history(market)
                if stale:
                    out = dict(stale)
                    out["cached"] = True
                    out["stale"] = True
                    out["stale_from"] = stale.get("asof") or stale.get("date") or ""
                    out["market_code"] = market
                    out["off_market"] = True
                    out["date"] = stale.get("date") or stale.get("asof") or ""
                    _mark_cached("非交易日：直接展示最近交易日归档（可点「重新扫描」强制刷新）")
                    return out
            # 交易日盘中（未到 15:03 收盘）：今日数据尚未生成，展示上一交易日归档
            if not _market_closed():
                stale = _latest_history(market)
                if stale:
                    out = dict(stale)
                    out["cached"] = True
                    out["stale"] = True
                    out["stale_from"] = stale.get("asof") or stale.get("date") or ""
                    out["market_code"] = market
                    out["intraday"] = True
                    out["date"] = stale.get("date") or stale.get("asof") or ""
                    _mark_cached("盘中未收盘：展示上一交易日归档（15:03 后自动更新今日）")
                    return out
        else:
            global _LAST_FULL_SCAN_TS
            if time.time() - _LAST_FULL_SCAN_TS < _FORCE_MIN_INTERVAL:
                hit = _SCAN_CACHE.get(full_key)
                if hit:
                    out = dict(hit[1])
                    out["cached"] = True
                    out["refresh_locked"] = True
                    _mark_cached("已加载今日扫描缓存")
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

    _set_prog("collect", 6, "拉取板块资金榜与成分股…")
    mkt_task = asyncio.create_task(_market_env(variant, priority_override, allow_paid))
    cands, hot, board_pool, total, rows_all = await _collect_candidates(cfg, market)
    mkt_env = await mkt_task
    _set_prog("kline", 18, "开始K线形态体检…")
    # 复盘主线（资金+技术双确认）：先读主线，把主线板块成分补进候选池（主线小票优先主推）
    _dml = _daily_mainlines()
    _dml_names = (_dml or {}).get("names") or []
    _dml_date = (_dml or {}).get("date") or ""
    _dml_src = (_dml or {}).get("src") or ""
    _ml_leaders: dict[str, list[dict[str, Any]]] = {}
    if market == "all" and _dml_names and not boards_only:
        _ml_cands, _ml_leaders = await _collect_mainline_cands(cfg, _dml_names, hot)
        _have = {str(c.get("code")): c for c in cands}
        for _c in _ml_cands:
            _code = str(_c.get("code"))
            if _code in _have:
                _have[_code]["mainline"] = True
                _have[_code]["mainlineName"] = _c.get("mainlineName") or _have[_code].get("mainlineName") or ""
            else:
                cands.append(_c)
    cands.sort(key=lambda x: -(x.get("amount") or 0))
    if len(cands) > int(cfg["cap"]):
        _trunc = cands[: int(cfg["cap"])]
        _ml_extra = [_c for _c in cands[int(cfg["cap"]):] if _c.get("mainline")]
        _trunc.extend(_ml_extra[: int(cfg.get("mainlineMemberCap") or 40)])
        cands = _trunc

    # 主线龙头候选：全市场下取板块排行前列（5日主力净流入排序）的板块龙头，
    # 放宽市值至 leaderMcapMax、不做“未大幅拉升”硬约束，用 leaderOk 确认形态与资金。
    leader_cands: list[dict[str, Any]] = []
    if market == "all" and (board_pool or _ml_leaders):
        seen_leader = {str(c.get("code")) for c in cands}
        # ① 复盘主线板块龙头优先入龙头层（资金+技术双确认）；主线无合格龙头再走资金热度兜底
        for _mn in (_dml_names or []):
            _b0 = next((b for b in (board_pool or []) if str(b.get("name") or "").strip() == _mn), None)
            _lds = (_ml_leaders or {}).get(_mn) or (_b0 or {}).get("leaders") or []
            for _ld in (_lds or [])[: int(cfg.get("leaderPerBoard") or 3)]:
                _row = _ld.get("_row") if isinstance(_ld, dict) else None
                code = str((_row or {}).get("f12") or _ld.get("code") or "")
                if not re.fullmatch(r"\d{6}", code) or code in seen_leader:
                    continue
                name = str((_row or {}).get("f14") or _ld.get("name") or "").strip()
                if re.search(r"ST|退", name):
                    continue
                mcap = _num((_row or {}).get("f20") or _ld.get("mcap") or 0)
                if mcap and not (0 < mcap <= float(cfg.get("leaderMcapMax") or 800.0) * 1e8):
                    continue
                seen_leader.add(code)
                leader_cands.append({
                    "code": code, "name": name,
                    "price": _num((_row or {}).get("f2") or _ld.get("price") or 0),
                    "pct": _num((_row or {}).get("f3") if (_row or {}).get("f3") is not None else _ld.get("pct") or 0),
                    "amount": _num((_row or {}).get("f6") or _ld.get("amount") or 0),
                    "mcap": mcap,
                    "floatMcap": _num((_row or {}).get("f21") or 0),
                    "turnover": _num((_row or {}).get("f8") or _ld.get("turnover") or 0),
                    "pe": _num((_row or {}).get("f9") or 0),
                    "pb": _num((_row or {}).get("f23") or 0),
                    "volRatio": _num((_row or {}).get("f10") or 0),
                    "fund": _num((_row or {}).get("f62") or _ld.get("fund") or 0),
                    "fundIn": _num((_row or {}).get("f62") or _ld.get("fund") or 0),
                    "fund5": _num((_row or {}).get("f164") or _ld.get("fund5") or 0),
                    "ind": str((_row or {}).get("f100") or "").strip(), "indCnt": 0,
                    "hot": True, "hotName": _mn, "kwHits": [],
                    "A": None, "snap": None, "final": None,
                    "revHit": True, "revName": _mn,
                    "mainline": True, "mainlineName": _mn,
                    "_board": _mn, "_board_tier": "king",
                })
        # ② 资金热度兜底：主线龙头不足时按 5日主力净流入补足
        top_boards = sorted(
            board_pool, key=lambda x: -float(x.get("f164") or 0)
        )[: int(cfg.get("leaderBoards") or 3)]
        for bi, b in enumerate(top_boards):
            bname = str(b.get("name") or "").strip()
            if _dml_names and bname in _dml_names:
                continue  # 主线板块已在 ① 处理
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
    prog_kline = {"n": 0}
    kline_total = len(cands) + len(leader_cands)
    _set_prog("kline", 18, f"K线形态体检 0/{kline_total}…", 0, kline_total)
    sem = asyncio.Semaphore(6)

    async def work(c: dict[str, Any], cfg_use: dict[str, Any] | None = None) -> None:
        async with sem:
            bars = await _kline_with_retry(c["code"], variant, priority_override, allow_paid, use_cache=use_cache)
            if not bars:
                return
            c["A"] = analyze(bars, c, cfg_use or cfg, market)
            c["_bars"] = bars
            c["lastDate"] = str(bars[-1][0])
            c["bearish"] = bearish_check(c, c["A"])
            prog_kline["n"] += 1
            if kline_total:
                _set_prog("kline", 18 + prog_kline["n"] / kline_total * 52,
                          f"K线形态体检 {prog_kline['n']}/{kline_total}…", prog_kline["n"], kline_total)

    tasks = []
    for c in cands:
        tasks.append(asyncio.create_task(work(c)))
        await asyncio.sleep(0.10)
    for c in leader_cands:
        tasks.append(asyncio.create_task(work(c, leader_cfg)))
        await asyncio.sleep(0.10)
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

    analyzed = [c for c in cands if c.get("A")]
    leader_analyzed = [c for c in leader_cands if c.get("A")]
    # 大盘环境统一加减分（攻/守模式：防守 -5 / 强攻 +3 / 稳健按红柱 +2）
    regime = str(mkt_env.get("regime") or "stable")
    _regime_delta = {"defensive": -5, "attack": 3, "stable": 2 if mkt_env.get("red") else 0}.get(regime, 0)
    for c in analyzed:
        c["A"]["score"] = max(0, min(100, int(c["A"].get("score") or 0) + _regime_delta))
    for c in leader_analyzed:
        a = c.get("A") or {}
        a["score"] = max(0, min(100, int(a.get("score") or 0) + _regime_delta))
    defensive_mode = regime == "defensive"

    # 行情风格初算（streak 计算后重算覆盖）：电风扇只做回踩低吸、趋势双线、震荡稳健
    style = _detect_style(regime, _dml_names, board_rank)
    style_mode = str(style.get("mode") or "chop") if style else "chop"

    # 板块龙头确认（成分池标的命中热度板块前3龙头 → 主推优先，加分）
    _board_leader_codes: set[str] = set()
    for _bp in (board_pool or []):
        for _ld in (_bp.get("leaders") or []):
            _c0 = str(_ld.get("code") or "")
            if _c0:
                _board_leader_codes.add(_c0)
    for _c in analyzed:
        if str(_c.get("code") or "") in _board_leader_codes:
            _c["boardLeader"] = True
            _c["A"]["score"] = min(100, int(_c["A"].get("score") or 0) + 2)

    rev_mainlines = reverse_mainline(analyzed, hot)
    rev_names = {it["name"] for it in rev_mainlines[:8]}

    # 复盘主线板块成分标记：主线板块内的标的优先主推（资金+技术双确认）
    _mlm = _mainline_members(_dml_names) if _dml_names else None
    if _mlm and _mlm.get("all"):
        _ml_codes = _mlm["all"]
        _ml_by_name = _mlm["by_name"]
        for _c in analyzed + leader_analyzed:
            _code = str(_c.get("code") or "")
            if _code in _ml_codes or _c.get("mainline"):
                _c["mainHit"] = True
                _c["mainName"] = _c.get("mainlineName") or next(
                    (n for n, codes in _ml_by_name.items() if _code in codes), ""
                )

    # 复盘主线板块补齐板块榜：主线不在资金热度池时也入榜（技术双确认优先于资金热度）
    if market == "all" and _dml_names:
        try:
            from .daily_report import SECTORS
            _have = {str(b.get("name") or "") for b in (board_pool or [])}
            for _mn in _dml_names:
                if _mn in _have:
                    continue
                _members = SECTORS.get(_mn) or []
                _secid = ""
                try:
                    _secid = (_MAINLINE_BOARD_MAP.get(_mn) or [""])[0] if _MAINLINE_BOARD_MAP.get(_mn) else await _resolve_board_secid(_mn)
                except Exception:
                    _secid = ""
                # 龙头带真实行情：优先复用主线成分拉取时已获得的 leaders，否则单板块补拉（1~2 次 clist）
                _ml_lds = (_ml_leaders or {}).get(_mn) or []
                if not _ml_lds and _secid:
                    try:
                        _r2, _ld2 = await fetch_board_members([{"name": _mn, "secid": _secid}], cap=20)
                        _ml_lds = _ld2.get(_mn) or []
                    except Exception:
                        _ml_lds = []
                if not _ml_lds:
                    _ml_lds = [
                        {"code": _c, "name": _n, "pct": None, "amount": 0.0,
                         "mcap": 0.0, "turnover": 0.0, "fund": 0.0, "fund5": 0.0, "_row": {}}
                        for _c, _n in _members[:3]
                    ]
                board_pool.append({
                    "name": _mn, "secid": _secid, "f164": 0.0, "f62": 0.0,
                    "p5": None, "pct": None, "hot": True, "mainline": True,
                    "leaders": _ml_lds,
                })
        except Exception:
            pass

    # 精筛 + 利空硬伤排除 + 主线反推加分
    # 严格档：位置/5日/换手/评分门槛从严（宁缺毋滥）；严格档空出时启用「放宽兜底档」，
    # 仅放宽 位置+5%、5日+5%、换手≥1.5%、scoreMin-2、启动门槛（sm+12→sm+8，baseUp 类 sm+2→sm+0），
    # 硬伤排除、主线硬约束、形态否决项全部保留，避免“空算法”。
    hard_rejected = 0
    for c in analyzed:
        if (c.get("bearish") or {}).get("level") == "hard":
            hard_rejected += 1

    def _fine_pass(cands: list[dict[str, Any]], relaxed: bool) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        _sm = float(cfg.get("scoreMin") or 50) - (2 if relaxed else 0)
        _pos_max = (float(cfg["posMax"]) + (5 if relaxed else 0)) / 100
        _chg5_max = float(cfg["max5d"]) + (5 if relaxed else 0)
        _turn_min = 1.5 if relaxed else float(cfg["turnMin"])
        _sm_plain = float(cfg.get("scoreMin") or 50) + (8 if relaxed else 12)
        _sm_base = float(cfg.get("scoreMin") or 50) + (0 if relaxed else 2)
        for c in cands:
            if (c.get("bearish") or {}).get("level") == "hard":
                continue
            a = c["A"]
            if str(c.get("ind") or "") in rev_names:
                c["revHit"] = True
                c["revName"] = str(c.get("ind") or "")
            p = a.get("patterns") or {}
            _sv = float(a.get("score") or 0)
            if p.get("surgeStart") or p.get("pullback") or p.get("ztPullback"):
                must_start = _sv >= _sm - 4
            elif p.get("baseUp") or p.get("tightBurst"):
                must_start = _sv >= _sm_base
            else:
                must_start = _sv >= _sm_plain and (
                    bool(p.get("leaderOk")) or bool(a.get("ma_bull3")) or a.get("volHealth") == 1
                )
            line_ok = cfg.get("mainline") != "must" or bool(
                c.get("hot") or (c.get("kwHits") and len(c["kwHits"]) > 0)
                or (a.get("chg5", 0) >= 8 and c.get("amount", 0) >= 5e7 and a.get("volRatio", 0) >= 1.2)
            )
            if (
                a.get("pos", 99) <= _pos_max
                and a.get("chg5", 999) <= _chg5_max
                and a.get("chg10", 999) <= float(cfg["max10d"])
                and a.get("chg20", 999) <= float(cfg["max20d"])
                and a.get("chg60", 999) <= float(cfg["max60d"])
                and _turn_min <= _num(c.get("turnover")) <= float(cfg["turnMax"])
                and not a.get("volShrink")
                and not a.get("newHighWeak")
                and not a.get("atHighWeak")
                and not (a.get("amp20") and float(a.get("amp20") or 0) < 3)
                and must_start and line_ok
            ):
                if c.get("mainHit"):
                    a["score"] = min(100, int(a["score"]) + 4)
                if c["revHit"]:
                    a["score"] = min(100, int(a["score"]) + 3)
                out.append(c)
        return out

    fine = _fine_pass(analyzed, False)
    relaxed_used = bool(not fine)
    if relaxed_used:
        fine = _fine_pass(analyzed, True)

    fine.sort(key=lambda x: (0 if x.get("mainHit") else 1, -int(x["A"].get("score") or 0)))
    finals = fine[: int(cfg["aiTop"])]

    prog_snap = {"n": 0}
    snap_total = 0
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
            # 再上一档：分时尾盘强度 + 龙虎榜（仅 finals/picks 级，量小可控）
            try:
                c["tail"] = _tail_strength(await _fetch_minute(c["code"]))
            except Exception:
                c["tail"] = {}
            try:
                _lhb = await _fetch_ths_lhb_map()
                _lhbe = _lhb.get(c["code"])
                _src = "ths"
                if not _lhbe:
                    _lhbe = (await _fetch_lhb_map()).get(c["code"])
                    _src = "em"
                if _lhbe:
                    c["lhb"] = {
                        "src": _src,
                        "dates": list(dict.fromkeys(_lhbe.get("dates") or []))[:3],
                        "reasons": list(dict.fromkeys(_lhbe.get("reasons") or []))[:2],
                        "net": round(float(_lhbe.get("net") or 0), 0),
                        "buy": round(float(_lhbe.get("buy") or 0), 0),
                        "sell": round(float(_lhbe.get("sell") or 0), 0),
                        "hotRank": int(_lhbe.get("hotRank") or 0),
                        "concepts": (_lhbe.get("concepts") or [])[:3],
                        "moneyTypes": list(_lhbe.get("moneyTypes") or []),
                    }
            except Exception:
                pass
            prog_snap["n"] += 1
            if snap_total:
                _set_prog("snapshot", 72 + prog_snap["n"] / snap_total * 22,
                          f"AI技术复核与利空排查 {prog_snap['n']}/{snap_total}…", prog_snap["n"], snap_total)
            if isinstance(snap, dict) and not snap.get("error"):
                s = _num(snap.get("score"))
                if leader_mode:
                    # 龙头层：AI 复核风险以警示展示，不按 8 分/条同权扣分
                    c["final"] = int(round(int(c["A"]["score"]) * 0.70 + s * 0.30))
                else:
                    c["final"] = int(round(int(c["A"]["score"]) * 0.70 + s * 0.30 - len(snap.get("risks") or []) * 8))
            else:
                c["final"] = int(c["A"]["score"])

    if cfg.get("aiOk") and finals:
        snap_total += len(finals)
        _set_prog("snapshot", 72, "AI技术复核与利空排查…", 0, snap_total)
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
        # 尾盘承接：强尾盘加分 / 尾盘走弱降权
        tail = c.get("tail") or {}
        tail_pct = _num(tail.get("tailPct"))
        if tail_pct >= 0.5:
            c["final"] = min(100, int(c["final"]) + 2)
        elif tail_pct <= -0.8:
            c["final"] = max(0, int(c["final"]) - 4)
        # 龙虎榜：净买入加分 / 净卖出降权；游资净买额外加分；热榜前20关注度加分
        lhb = c.get("lhb")
        if isinstance(lhb, dict):
            lhb_net = _num(lhb.get("net"))
            if lhb_net > 0:
                c["final"] = min(100, int(c["final"]) + 2)
            elif lhb_net < 0:
                c["final"] = max(0, int(c["final"]) - 3)
            if lhb_net > 0 and "hot_money" in (lhb.get("moneyTypes") or []):
                c["final"] = min(100, int(c["final"]) + 2)
            hr = int(lhb.get("hotRank") or 0)
            if hr and hr <= 20:
                c["final"] = min(100, int(c["final"]) + 1)
        # 业绩预告加分（预增/预盈）
        if fund:
            if fund.get("earnPos"):
                c["final"] = min(100, int(c["final"]) + 3)
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

    # ---- 昨日主推延续机制：昨日 picks 今日仍达标 → 延续加分；并记录状态供前端追踪 ----
    prev_date_s, prev_picks_raw = _prev_day_picks(market)
    prev_by_code: dict[str, dict[str, Any]] = {}
    for _p in prev_picks_raw:
        _c0 = str(_p.get("code") or "")
        if _c0:
            prev_by_code[_c0] = _p
    analyzed_by_code = {str(c.get("code")): c for c in analyzed}
    hard_codes: set[str] = set()
    for c in analyzed:
        if (c.get("bearish") or {}).get("level") == "hard":
            hard_codes.add(str(c.get("code")))
        _f0 = _fund_of(c)
        if _f0 and _f0.get("level") == "hard":
            hard_codes.add(str(c.get("code")))
    fine_codes = {str(c.get("code")) for c in fine}
    for c in fine:
        _c0 = str(c.get("code") or "")
        if _c0 in prev_by_code:
            c["cont"] = True
            c["contPrevDate"] = prev_date_s
            c["contPrevTier"] = str((prev_by_code[_c0] or {}).get("tier") or "")
            c["final"] = min(100, int(c.get("final") or 0) + 3)

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
    zero_risk.sort(key=lambda x: (0 if x.get("mainHit") else 1, -int(x.get("final") or 0)))
    warned.sort(key=lambda x: (0 if x.get("mainHit") else 1, -int(x.get("final") or 0)))
    pool = zero_risk + warned

    all_sorted = sorted(fine, key=lambda x: (0 if x.get("mainHit") else 1, -int(x.get("final") or 0)))
    # 电风扇风格：回踩企稳优先（低吸为主，不追热度）
    if style_mode == "fan":
        all_sorted.sort(key=lambda x: (0 if (x.get("revHit") or x.get("mainHit")) else 1, 0 if x.get("revHit") else 1, -int(x.get("final") or 0)))

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
                a["score"] = min(100, int(a.get("score") or 0) + 2)
            leader_pool.append(c)
        leader_pool.sort(key=lambda x: -int((x.get("A") or {}).get("score") or 0))
        leader_pre = leader_pool[: int(cfg.get("leaderBoards") or 3) * int(cfg.get("leaderPerBoard") or 3)]
        if cfg.get("aiOk") and leader_pre:
            snap_total += len(leader_pre)
            _set_prog("snapshot", 72, "AI技术复核与利空排查…", 0, snap_total)
            await asyncio.gather(*[snap_work(c, True) for c in leader_pre], return_exceptions=True)
        leader_final: list[dict[str, Any]] = []
        for c in leader_pre:
            if not _post_adjust(c):
                continue
            # 板块资金榜确认 + 龙头辨识度加分
            c["final"] = min(100, int(c.get("final") or 0) + 10)
            leader_final.append(c)
        # 龙头层分数下限（宁缺毋滥）：防守档 62，其余 56
        _lead_min = 62 if defensive_mode else 56
        leader_final = [c for c in leader_final if int(c.get("final") or 0) >= _lead_min]
        leader_final.sort(key=lambda x: (0 if x.get("mainHit") else 1, -int(x.get("final") or 0)))

        # 龙头层只占“王者”1 位：主线龙头优先；无主线龙头才用资金热度龙头兜底；空则交给卡位/兜底层
        _main_leaders = [c for c in leader_final if c.get("mainHit")]
        _lead_src = (_main_leaders or leader_final)[:1]
        for c in _lead_src:
            c["tier"] = "king"
            c["star"] = True
            c["pick_role"] = "leader"
            picks.append(c)
        # 卡位层（主线优先）：all_sorted 已按 mainHit 优先排序——
        # 主线命中 final≥60 即占位；非主线补涨需低风险约束（位置<40%、5日<15%、50-300亿、主力净流入为正）且 final≥62。
        if len(picks) < 2:  # 主推收敛：王者1⭐ + 重点1
            used = {str(c.get("code")) for c in picks}
            ind_used: dict[str, int] = {}
            for c in picks:
                _ik = str(c.get("ind") or "-")
                ind_used[_ik] = ind_used.get(_ik, 0) + 1
            for c in all_sorted:
                if str(c.get("code")) in used:
                    continue
                _f = int(c.get("final") or 0)
                if c.get("mainHit"):
                    if _f < (62 if defensive_mode else 56):
                        continue
                else:
                    if _f < (62 if defensive_mode else 58):
                        continue
                    if style_mode == "fan" and not (c.get("revHit") or c.get("mainHit")):
                        continue  # 电风扇：只做回踩/主线低吸，不追纯热度
                    # 补涨卡位必须有板块共振（反推/热门/板块龙头任一），避免孤军奋战
                    if not (c.get("revHit") or c.get("hot") or c.get("boardLeader")):
                        continue
                    if not (_num(c.get("mcap")) >= float(cfg.get("catchupMcapMin") or 50.0) * 1e8
                            and _num(c.get("mcap")) <= float(cfg.get("catchupMcapMax") or 300.0) * 1e8
                            and (c.get("A") or {}).get("chg5", 999) <= float(cfg.get("catchupChg5Max") or 15.0)
                            and (c.get("A") or {}).get("pos", 99) <= float(cfg.get("catchupPosMax") or 0.40)
                            and _num(c.get("fundIn")) > 0):
                        continue
                _ik = str(c.get("ind") or "-")
                if ind_used.get(_ik, 0) >= 2:
                    continue  # 同行业主推最多 2 只，防板块拥挤
                c["tier"] = "key"
                c["star"] = False
                c["pick_role"] = "catchup"
                picks.append(c)
                used.add(str(c.get("code")))
                ind_used[_ik] = ind_used.get(_ik, 0) + 1
                if len(picks) >= 2:
                    break

    if not picks:
        # 北证 / 龙头不足兜底：王者(1⭐) + 重点(最多3)
        # 宁缺毋滥：与主线标准一致 final>=62（all_sorted 已按主线命中优先排序）
        king: dict[str, Any] | None = None
        if zero_risk:
            z0 = zero_risk[0]
            if int(z0.get("final") or 0) >= (62 if defensive_mode else 56):
                if not defensive_mode or (z0.get("mainHit") or z0.get("revHit") or z0.get("hot") or z0.get("boardLeader")):
                    king = z0
        if king is None and all_sorted:
            for cand in all_sorted:
                if int(cand.get("final") or 0) >= (62 if defensive_mode else 56) and _num((cand.get("A") or {}).get("pe")) > 0:
                    if not defensive_mode or (cand.get("mainHit") or cand.get("revHit") or cand.get("hot") or cand.get("boardLeader")):
                        king = cand
                        break
            if king is None:
                for cand in all_sorted:
                    if int(cand.get("final") or 0) >= (62 if defensive_mode else 56):
                        if not defensive_mode or (cand.get("mainHit") or cand.get("revHit") or cand.get("hot") or cand.get("boardLeader")):
                            king = cand
                            break
        rest = [c for c in pool if c is not king and int(c.get("final") or 0) >= (62 if defensive_mode else 56)]
        keys = rest[:1]  # 主推收敛：王者 1⭐ + 重点 1，共 2 只
        if king:
            king["tier"] = "king"
            king["star"] = True
            picks.append(king)
        for c in keys:
            c["tier"] = "key"
            c["star"] = False
            picks.append(c)
    # 主推 2×2 排版：足 4 只显示 4 只；不足 4 只只显示 2 只（3 只砍为 2 只，避免缺一格）；1 只补足到 2 只
    if len(picks) > 2:
        picks = picks[:2]  # 主推收敛：王者 1⭐ + 重点 1，最多 2 只
    # 主推仅 1 只时，从备选池补 1 只到 2 只（final>=50 优先、>=40 兜底），避免单卡孤悬
    if len(picks) == 1 and all_sorted:
        _used = {str(c.get("code")) for c in picks}
        for _bk in all_sorted:
            if str(_bk.get("code")) in _used:
                continue
            if int(_bk.get("final") or 0) >= 40:
                _bk["tier"] = "key"
                _bk["star"] = False
                _bk["pick_role"] = "backup"
                picks.append(_bk)
                break
    for c in picks:
        if relaxed_used and c.get("pick_role") != "leader":
            c["relaxed"] = True
        c["strategy"] = build_strategy(c, c.get("tier") or "normal", c.get("pick_role"))
    # 电风扇风格：策略纪律追加“只做回踩低吸、不追涨”
    if style_mode == "fan":
        for _c in picks:
            _st = _c.get("strategy") or {}
            _extra = "电风扇行情：只做回踩低吸，不追当日大涨，破位即撤。"
            _st["rules"] = ((_st.get("rules") or "") + "；" if _st.get("rules") else "") + _extra
            _c["strategy"] = _st
    for i, c in enumerate(picks):
        c["rank"] = i + 1

    picked = {str(c.get("code")) for c in picks}
    # 昨日主推 → 今日状态追踪（持有/延续/止盈观察/离场），防“每天推新、用户追着换股”
    cand_codes = {str(c.get("code")) for c in cands}
    prev_track: list[dict[str, Any]] = []
    for _p in prev_picks_raw:
        _c0 = str(_p.get("code") or "")
        if not _c0:
            continue
        _rec: dict[str, Any] = {"code": _c0, "name": _p.get("name") or "",
                                "tier": _p.get("tier") or "", "star": bool(_p.get("star")),
                                "status": "今日暂无数据", "tag": "muted"}
        _cur = analyzed_by_code.get(_c0)
        if _c0 in hard_codes:
            _rec["status"] = "离场（利空/硬伤排查）"; _rec["tag"] = "bad"
        elif _c0 in picked:
            _rec["status"] = "延续持有（今日入选主推）"; _rec["tag"] = "ok"
        elif _c0 in fine_codes:
            _rec["status"] = "延续关注（仍达标，未入主推）"; _rec["tag"] = "ok"
        elif _cur:
            _a0 = _cur.get("A") or {}
            if (float(_a0.get("pos") or 99) > float(cfg["posMax"]) / 100
                    or float(_a0.get("chg5") or 999) > float(cfg["max5d"])
                    or float(_a0.get("chg10") or 999) > float(cfg["max10d"])):
                _rec["status"] = "涨幅过热（止盈观察）"; _rec["tag"] = "warn"
            elif _a0.get("volShrink"):
                _rec["status"] = "缩量走弱（观望）"; _rec["tag"] = "warn"
            else:
                _rec["status"] = "条件不满足（观望）"; _rec["tag"] = "muted"
        else:
            if _c0 in cand_codes:
                _rec["status"] = "候选池内待精筛（观察）"; _rec["tag"] = "muted"
            else:
                _rec["status"] = "今日未进候选池（排序/条件变化，谨慎）"; _rec["tag"] = "warn"
        prev_track.append(_rec)
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
        board_rank = _board_rank_funds(board_pool or [], int(cfg.get("allBackupN") or 4), mainline_names=_dml_names or None)
    else:
        board_rank = _board_rank(rev_mainlines[:10], hot.get("list") or [])
    # 北证板块排行龙头：从已分析的候选按行业聚合 top3（成交额），零上游成本
    if market == "bj":
        try:
            _by_ind: dict[str, list[dict[str, Any]]] = {}
            for _c in analyzed:
                _ik = str(_c.get("ind") or "").strip()
                if not _ik or _ik == "-":
                    continue
                _by_ind.setdefault(_ik, []).append({
                    "code": str(_c.get("code") or ""),
                    "name": str(_c.get("name") or ""),
                    "pct": _c.get("pct"),
                    "amount": _num(_c.get("amount")),
                    "mcap": _num(_c.get("mcap")),
                    "turnover": _num(_c.get("turnover")),
                    "fund": _num(_c.get("fundIn")),
                    "fund5": _num(_c.get("fund5")),
                })
            for _b in (board_rank or []):
                _bn = str(_b.get("name") or "")
                _lds3 = sorted(_by_ind.get(_bn) or [], key=lambda x: -float(x.get("amount") or 0))[:3]
                if _lds3:
                    _b["leaders"] = _lds3
        except Exception:
            pass
    # 板块连续上榜天数（回溯归档，>=2 表示延续热点，抑制单日异动跳变）
    try:
        _br_days = _archive_board_rank_days(market, 8)
        for _b in (board_rank or []):
            _nm = str(_b.get("name") or "")
            _stk = 0
            for _day_nms in _br_days:
                if _nm in _day_nms:
                    _stk += 1
                else:
                    break
            _b["streak"] = _stk
    except Exception:
        pass

    result_mainlines = rev_mainlines[:10]
    if _dml_names:
        result_mainlines = [{"name": n, "src": "daily"} for n in _dml_names]
    # 行情风格终算（含板块持续性 streak）：覆盖初算
    style = _detect_style(regime, _dml_names, board_rank)
    style_mode = str(style.get("mode") or "chop") if style else "chop"
    result: dict[str, Any] = {
        "ok": True, "cached": False, "date": today, "asof": asof,
        "market_code": market,
        "total": total, "scanned": len(cands), "fine": len(fine),
        "hard_rejected": hard_rejected,
        "relaxed": relaxed_used,
        "generated_ts": int(time.time()), "elapsed_s": round(time.time() - t0, 1),
        "market": mkt_env,
        "regime": regime,
        "style": style,
        "mainline_from": _dml_src or ("daily" if _dml_names else "fallback"),
        "mainline_date": _dml_date,
        "hot_boards": hot.get("list") or [],
        "mainlines": result_mainlines,
        "mainline_hit": sorted({str(c.get("mainName") or c.get("mainlineName") or "") for c in picks if c.get("mainHit") and (c.get("mainName") or c.get("mainlineName"))}),
        "mainline_gap": bool(picks) and not any(c.get("mainHit") for c in picks),
        "board_rank": board_rank,
        "picks": pick_out,
        "runners": run_out,
        "prev_date": prev_date_s,
        "prev_track": prev_track,
    }
    _kline_cache_flush()
    _SCAN_PROGRESS[market] = {"phase": "done", "pct": 100, "done": 0, "total": 0,
                              "msg": "扫描完成", "running": False, "ts": time.time()}
    if boards_only:
        result["vip_required"] = True
        result.pop("picks", None)
        result.pop("runners", None)
        # 非 VIP：隐藏主线锁定结论（mainline 标记 + 主线列表），仅保留板块排行数据
        result = _strip_conclusions(result)
        _BOARDS_CACHE[boards_key] = (time.time(), result)
        return result
    # 有结果则持久化：供今日无合格标的回退展示 + 历史归档回看
    if pick_out:
        hist_payload: dict[str, Any] = {
            "date": today, "asof": asof, "market_code": market,
            "total": result["total"], "scanned": result["scanned"],
            "fine": result["fine"], "hard_rejected": hard_rejected,
            "generated_ts": result["generated_ts"], "elapsed_s": result["elapsed_s"],
            "market": mkt_env, "regime": regime, "style": style, "hot_boards": hot.get("list") or [],
            "mainlines": result_mainlines,
            "mainline_hit": sorted({str(c.get("mainName") or c.get("mainlineName") or "") for c in picks if c.get("mainHit") and (c.get("mainName") or c.get("mainlineName"))}),
            "mainline_gap": bool(picks) and not any(c.get("mainHit") for c in picks),
            "board_rank": board_rank,
            "picks": pick_out, "runners": run_out,
        }
        _save_history(f"{market}:{str(today)}", hist_payload)
        _save_archive(market, str(today), hist_payload)
    _SCAN_CACHE[full_key] = (time.time(), result)
    _BOARDS_CACHE.pop(boards_key, None)
    _persist_daily_scan_cache()
    return _apply_stale_fallback(result, market)


# 并发去重：同 market 非 force 时共享一份扫描，避免多用户同时触发重复全量扫描（浪费资源/触发上游封 IP）
_SCAN_LOCKS: dict[str, asyncio.Lock] = {}

# 运行中的扫描任务（同市场复用，防重复全量扫描；/start 接口后台任务注册于此）
_RUNNING_SCAN: dict[str, asyncio.Task] = {}


async def run_scan_dedup(
    user_id: int,
    force: bool = False,
    cfg_override: dict[str, Any] | None = None,
    boards_only: bool = False,
    market: str = "bj",
) -> dict[str, Any]:
    """掘金扫描并发去重包装：
    - 同市场已有扫描在跑 → 等待复用该任务结果（force 也复用，避免重复全量扫描浪费上游预算）；
    - force=True 无任务在跑 → 启动新扫描（后台/同步皆可）；
    - force=False → 优先今日缓存，无缓存才扫描。"""
    market = str(market or "bj").strip().lower()
    if market not in ("bj", "all"):
        market = "bj"
    today8 = time.strftime("%Y%m%d", time.localtime())
    full_key = f"{market}-scan:" + today8
    running = _RUNNING_SCAN.get(market)
    if running is not None and not running.done():
        try:
            await running
        except Exception:
            pass
        hit = _SCAN_CACHE.get(full_key)
        if hit and time.time() - hit[0] < 6 * 3600:
            out = dict(hit[1])
            out["cached"] = True
            _SCAN_PROGRESS[market] = {"phase": "done", "pct": 100, "done": 0, "total": 0,
                                      "msg": "已加载今日扫描缓存", "running": False, "ts": time.time()}
            return _apply_stale_fallback(out, market)
        return await run_scan(user_id, force=False, cfg_override=cfg_override, boards_only=boards_only, market=market)

    if force:
        async def _wrap_scan() -> dict[str, Any]:
            try:
                return await run_scan(user_id, force=True, cfg_override=cfg_override, boards_only=boards_only, market=market)
            finally:
                _RUNNING_SCAN.pop(market, None)
        t = asyncio.ensure_future(_wrap_scan())
        _RUNNING_SCAN[market] = t
        return await t

    lock = _SCAN_LOCKS.setdefault(market, asyncio.Lock())
    async with lock:
        hit = _SCAN_CACHE.get(full_key)
        if hit and time.time() - hit[0] < 6 * 3600:
            out = dict(hit[1])
            out["cached"] = True
            _SCAN_PROGRESS[market] = {"phase": "done", "pct": 100, "done": 0, "total": 0,
                                      "msg": "已加载今日扫描缓存", "running": False, "ts": time.time()}
            return _apply_stale_fallback(out, market)
        return await run_scan(user_id, force=False, cfg_override=cfg_override, boards_only=boards_only, market=market)


# 进程启动即加载当日扫描结果磁盘缓存（减少重启后的上游请求）
_load_daily_scan_cache()


def _detect_style(regime, dml_names, board_rank):
    """行情风格识别：大盘攻守 + 主线连续性 + 板块持续性（电风扇/趋势/震荡）。
    - defensive：沿用防守模式（门槛62/最多2只/仅主线回踩热门龙头），风格不重复调参；
    - trend（趋势）：有复盘主线 且 主线板块连续上榜≥2 天 或 主线≥2 个；
    - fan（电风扇）：无主线 或 板块榜前8 中一日游（streak≤1）占比≥60%；
    - chop（震荡）：其余，稳健基准。
    """
    try:
        if regime == "defensive":
            return {"mode": "defensive", "label": "风格：防守", "note": "大盘走弱：仅主线双确认+零风险标的，最多 2 只，宁可空仓不勉强。"}
        ranks = [b for b in (board_rank or []) if isinstance(b, dict)][:8]
        has_streak = bool(ranks) and any(int(b.get('streak') or 0) > 0 for b in ranks)
        one_day = sum(1 for b in ranks if int(b.get('streak') or 0) <= 1) if has_streak else 0
        one_day_ratio = (one_day / len(ranks)) if (has_streak and ranks) else 0.0
        main_streak = 0
        ml_names = {str(n).replace(" ", "") for n in (dml_names or [])}
        for b in ranks:
            nm = str(b.get("name") or "").replace(" ", "")
            if nm and nm in ml_names:
                main_streak = max(main_streak, int(b.get("streak") or 0))
        if ml_names and (main_streak >= 2 or len(ml_names) >= 2):
            return {"mode": "trend", "label": "风格：趋势", "note": "主线持续（连续上榜≥2 天）：主线龙头+补涨卡位双线推进，回踩低吸为主，不追高。"}
        if not ml_names or one_day_ratio >= 0.6:
            return {"mode": "fan", "label": "风格：电风扇", "note": "板块快速轮动、一日游偏多：只做主线/回踩企稳低吸，绝不追当日大涨，破位即撤。"}
        return {"mode": "chop", "label": "风格：震荡", "note": "方向不明：以主线双确认+零风险标的为主，控制仓位，等主线明朗。"}
    except Exception:
        return {"mode": "chop", "label": "风格：震荡", "note": "方向不明：控制仓位，等主线明朗。"}


def _daily_mainlines():
    """读取复盘锁定主线（与复盘页完全同口径，掘金/复盘不再打架）：
    1) 优先当日复盘归档 mainlines.json（复盘实际生成，最准）；
    2) 无则用当日 sector_scores 缓存 + 连续性约束重算（与复盘报告口径一致）；
    3) 再无则回退最近归档日主线（与复盘页展示一致）。
    返回 {"names": [...], "date": "YYYY-MM-DD", "src": "archive"|"recalc"|"fallback"} 或 None。
    """
    try:
        from .daily_report import ARCHIVE_ROOT, today8, cache_load, pick_main_lines, _prev_mainlines
        _today = today8()
        # 1) 当日归档（复盘实际生成的主线）
        _mj = os.path.join(ARCHIVE_ROOT, _today, "mainlines.json")
        if os.path.exists(_mj):
            obj = json.load(open(_mj, encoding="utf-8"))
            ml = obj.get("mainlines") or []
            if ml:
                return {"names": list(ml), "date": _today, "src": "archive"}
        # 2) 当日板块评分缓存 + 连续性约束重算（与复盘报告口径一致）
        sc = cache_load("sector_scores")
        if sc:
            _prev = _prev_mainlines() or {}
            ml, _obs, _av = pick_main_lines(sc, (_prev.get("mainlines") or []))
            if ml:
                return {"names": list(ml), "date": _today, "src": "recalc"}
        # 3) 最近归档日主线（与复盘页展示一致）
        import re as _re
        _archs = sorted([x for x in os.listdir(ARCHIVE_ROOT) if _re.fullmatch(r"\d{8}", x) and os.path.isdir(os.path.join(ARCHIVE_ROOT, x))], reverse=True)
        for _d in _archs:
            if _d == _today:
                continue
            _p = os.path.join(ARCHIVE_ROOT, _d, "mainlines.json")
            if os.path.exists(_p):
                obj = json.load(open(_p, encoding="utf-8"))
                ml = obj.get("mainlines") or []
                if ml:
                    return {"names": list(ml), "date": _d, "src": "fallback"}
    except Exception:
        return None
    return None


# ---------------- 复盘主线板块成分（主线优先推荐） ----------------
_MAINLINE_MEMBERS: dict[str, Any] = {"date": "", "by_name": {}, "all": set()}


def _mainline_member_codes_sync(names: list[str]) -> dict[str, set[str]]:
    """从复盘 SECTORS 龙头列表取主线板块成分代码（零上游成本）。"""
    try:
        from .daily_report import SECTORS
        out: dict[str, set[str]] = {}
        for n in names:
            members = SECTORS.get(n) or []
            codes = {str(code) for code, _nm in members if str(code)}
            if codes:
                out[n] = codes
        return out
    except Exception:
        return {}


def _mainline_members(names: list[str]) -> dict[str, Any]:
    """主线板块成分代码集合（当日内存缓存）：返回 {date, by_name, all}。"""
    global _MAINLINE_MEMBERS
    today8 = time.strftime("%Y%m%d", time.localtime())
    if (
        _MAINLINE_MEMBERS.get("date") == today8
        and set(_MAINLINE_MEMBERS.get("by_name") or {}) == set(names)
        and _MAINLINE_MEMBERS.get("all")
    ):
        return _MAINLINE_MEMBERS
    by_name = _mainline_member_codes_sync(names)
    allset: set[str] = set()
    for codes in by_name.values():
        allset |= codes
    _MAINLINE_MEMBERS = {"date": today8, "by_name": by_name, "all": allset}
    return _MAINLINE_MEMBERS


# ---------------- 掘金收盘后定时预生成（服务内自触发） ----------------
# （同日已有缓存或已预生成过则跳过；force 重扫仍由用户手动触发）
_AUTO_SCAN_TS = 15 * 3600 + 3 * 60
_AUTO_SCAN_DONE: dict[str, bool] = {}


async def _auto_scan_loop() -> None:
    while True:
        try:
            now = time.localtime()
            sec = now.tm_hour * 3600 + now.tm_min * 60 + now.tm_sec
            if now.tm_wday < 5 and sec >= _AUTO_SCAN_TS:
                today8 = time.strftime("%Y%m%d", time.localtime())
                for market in ("all", "bj"):
                    key = f"{market}-scan:{today8}"
                    if _AUTO_SCAN_DONE.get(key):
                        continue
                    _AUTO_SCAN_DONE[key] = True
                    hit = _SCAN_CACHE.get(key)
                    if hit and time.time() - hit[0] < 6 * 3600:
                        continue
                    try:
                        await run_scan_dedup(0, force=False, market=market)
                    except Exception:
                        _AUTO_SCAN_DONE[key] = False  # 失败则下轮重试
            await asyncio.sleep(60)
        except Exception:
            await asyncio.sleep(300)


def start_bj_auto_scan() -> None:
    """在 startup 时启动掘金定时预生成后台任务。"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        return
    loop.create_task(_auto_scan_loop())
