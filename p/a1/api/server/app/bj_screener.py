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
import datetime
import json
import logging
import math
import os
import re
import time
from typing import Any

_log = logging.getLogger("bj_screener")

import httpx

from .big_cycle import (
    TIER_LABEL, TIER_RANK, above_ma144_structure, above_ma60_structure,
    count_ma60_strong_days, ma60_strong_ok, ma_tier_from_values,
    pick_ma_ok, pick_strong_ok,
)
from .providers import (_RateGate, fetch_em_suggest, fetch_tx_kline, market_data_status,
                          bk_to_ths_secid)
from .ths_fuyao import fetch_special as ths_fetch_special

EM_HOSTS = ["https://push2delay.eastmoney.com", "https://push2.eastmoney.com"]
EM_LIST_FIELDS = "f12,f14,f2,f3,f5,f6,f8,f9,f10,f20,f21,f23,f62,f100,f128"

# ---- 涨跌停阈值（按市场统一；coarse 排除线 = 涨停阈值 + 1 容差，避免误删涨停当天） ----
_ZT_TH_BJ = 29.5     # 北证 30cm
_ZT_TH_KC = 19.5     # 科创 20cm / 创业 20cm
_ZT_TH_HS = 9.5      # 沪深主板 10cm
_DN_TH_BJ = -29.5
_DN_TH_KC = -19.5
_DN_TH_HS = -9.5


def _is_bj_code6(code6: str) -> bool:
    """北证代码：43/83/87/88/89/92 开头（含部分历史码段）。"""
    c = str(code6 or "").zfill(6)
    return c.startswith(("43", "83", "87", "88", "89", "92"))


def _is_hs_kc_code6(code6: str) -> bool:
    """沪深主板 + 创业/科创（大波段栏目允许范围；明确排除北证）。"""
    c = str(code6 or "").zfill(6)
    if _is_bj_code6(c):
        return False
    return c.startswith(("00", "60", "30", "68"))


def _is_kc_code6(code6: str) -> bool:
    return str(code6 or "").zfill(6).startswith(("30", "68"))


def _zt_threshold(code6: str) -> float:
    """涨停判定阈值：北证 29.5 / 科创·创业 19.5 / 主板 9.5。"""
    if _is_bj_code6(code6):
        return _ZT_TH_BJ
    if _is_kc_code6(code6):
        return _ZT_TH_KC
    return _ZT_TH_HS


def _down_threshold(code6: str) -> float:
    """跌停判定阈值（负值）：北证 -29.5 / 科创·创业 -19.5 / 主板 -9.5。"""
    if _is_bj_code6(code6):
        return _DN_TH_BJ
    if _is_kc_code6(code6):
        return _DN_TH_KC
    return _DN_TH_HS


_WARN_RISK_CODES = {
    "close_weak", "odds_low", "chg5_high", "chg10_high", "chg20_high", "chg60_high",
    "surge_stale", "turn_low", "turn_high", "bias_over", "amp_high", "vol_sell",
}


def _risk_codes_of(risks: list[str]) -> list[str]:
    """把 analyze() 的展示用风险文案映射为结构化风险码（供评分/利空排查机器判断）。"""
    codes: list[str] = []
    for r in risks:
        if r == "收盘偏弱(承接不足)":
            codes.append("close_weak")
        elif r.startswith("赔率不足"):
            codes.append("odds_low")
        elif r == "板后破位(跌破板日低点/板后长阴)":
            codes.append("pb_break")
        elif r == "首板失败(跌破涨停价)":
            codes.append("zt_fail")
        elif r.startswith("5日涨幅偏大"):
            codes.append("chg5_high")
        elif r.startswith("10日涨幅偏大"):
            codes.append("chg10_high")
        elif r.startswith("20日涨幅过大"):
            codes.append("chg20_high")
        elif r.startswith("60日涨幅过大"):
            codes.append("chg60_high")
        elif r == "长上影滞涨":
            codes.append("upper_shadow")
        elif r == "量价背离(3日缩量上涨)":
            codes.append("ljdv_div")
        elif r == "跌破MA20且趋势下拐":
            codes.append("ma20_down")
        elif r == "放量长阴":
            codes.append("big_red_vol")
        elif r == "持续缩量阴跌":
            codes.append("vol_shrink")
        elif r == "无量新高":
            codes.append("high_weak")
        elif r == "贴前高缩量":
            codes.append("at_high_weak")
        elif r.startswith("乖离偏大"):
            codes.append("bias_over")
        elif r == "20日振幅过低(死水)":
            codes.append("amp_low")
        elif r == "20日振幅过大(偏疯)":
            codes.append("amp_high")
        elif r == "跌放量出货嫌疑":
            codes.append("vol_sell")
        elif r == "异动过时(>7日未再启动)":
            codes.append("surge_stale")
        elif r == "底部异动后未确认企稳":
            codes.append("surge_unconf")
        elif r.startswith("换手过低"):
            codes.append("turn_low")
        elif r.startswith("换手过高"):
            codes.append("turn_high")
        else:
            codes.append("other")
    return codes
_UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

# 东财 push2delay 共享 keep-alive 客户端：避免每次请求新建 TLS 连接（扫 20+ 板块时省时省资源）
_EM_CLIST_CLIENT: httpx.AsyncClient | None = None
_EM_CLIST_CLIENT_LOCK = asyncio.Lock()
# 东财 clist 全局节流：并发拉板块成分时仍保持温和访问，防 IP 级限流
_EM_CLIST_GATE = _RateGate(min_interval_s=0.08, max_per_minute=150)

async def _get_em_clist_client() -> httpx.AsyncClient:
    global _EM_CLIST_CLIENT
    if _EM_CLIST_CLIENT is not None:
        return _EM_CLIST_CLIENT
    async with _EM_CLIST_CLIENT_LOCK:
        if _EM_CLIST_CLIENT is None:
            _EM_CLIST_CLIENT = httpx.AsyncClient(
                timeout=httpx.Timeout(12.0, connect=6.0),
                headers=dict(_UA),
                limits=httpx.Limits(max_connections=12, max_keepalive_connections=12),
                follow_redirects=True,
                verify=False,
            )
    return _EM_CLIST_CLIENT

DEFAULT_CFG: dict[str, Any] = {
    "mcapMin": 5.0,      # 市值下限（亿）
    "mcapMax": 40.0,     # 市值上限（亿）
    "amountMin": 3000.0, # 最低成交额（万）
    "posMax": 30.0,      # 60日位置上限 %
    "max5d": 20.0, "max10d": 30.0, "max20d": 30.0, "max60d": 45.0,
    "aiMin": 60.0, "topN": 5, "cap": 160, "aiTop": 5, "aiOk": True,
    "kw": "", "minSurge": 4.0, "surgeVol": 1.8, "surgeDays": 15,
    "mainline": "score", "hotPct": 4.0, "hotN": 12, "mainlineMemberCap": 60,
    "obsMemberCap": 30,
    "turnMin": 2.0, "turnMax": 20.0, "useFund": True,
    "scoreMin": 46.0,
    # P0-1/P0-2 服务端开关（情绪周期 Gate + 涨停质量分级；异常可单项关闭）
    "emotionGate": True,
    "limitQuality": True,
    # P0-3/P0-4 服务端开关（ATR 自适应回撤容忍 + 量能分位；异常可单项关闭）
    "adaptiveAtr": True,
    # 全市场（沪深京）参数：板块先行两阶段筛选
    "mcapMinAll": 15.0, "mcapMaxAll": 200.0, "amountMinAll": 8000.0,
    "hotBoards": 16, "memberCap": 800, "allBackupN": 3,
    # 全市场强势股补池：板块先行之外的漏网捕捉（5日涨幅/主力净流入双榜）
    "globalTopN": 200, "globalChg5Min": 3.0, "globalChg5Max": 25.0,
    # 主线龙头层（板块确认后放宽市值/位置约束）与补涨卡位层
    "leaderBoards": 3, "leaderPerBoard": 2, "leaderMcapMax": 5000.0,
    "catchupMcapMin": 50.0, "catchupMcapMax": 300.0,
    "catchupChg5Max": 15.0, "catchupPosMax": 0.40,
    # 强势主推：三档门（上144 → 远高于60持续 → 站上60+涨停热门）+ 涨停池扩容
    "ztPoolDays": 30, "pickMinMaTier": "A", "pickRequireZt": True,
    "pickZtMaxDays": 25,
    "pickPreferMa144": True,
    "pickMa60StrongRatio": 1.02, "pickMa60StrongDays": 3,
    "pickMaxN": 4, "ztHotExtraCap": 80,
}


# 扫描结果缓存：同自然日重复请求直接返回（force=1 强制重扫）
_SCAN_CACHE: dict[str, tuple[float, dict]] = {}
# 扫描进度（供前端进度条轮询）：key = market，单进程内最新一次扫描的进度快照
_SCAN_PROGRESS: dict[str, dict[str, Any]] = {}
# 阶段性快筛结果缓存，不进入正式扫描缓存。
_PARTIAL_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}

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
        # 盘中（未收盘，15:01 前）扫描一律不写“当日历史”：未定型盘中数据只做短时缓存，
        # 不抢占当日最终版，避免本地/生产口径漂移；收盘后（15:01+）自动扫描与手动重扫照常更新。
        if not _market_closed():
            return
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
        # 兼容旧版无市场前缀的归档（仅北证；hs/kc/bj_all 无旧数据，避免串市场）
        if key.startswith(prefix) or (str(market or "bj") == "bj" and ":" not in key):
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
            if not (key.startswith(prefix) or (str(market or "bj") == "bj" and ":" not in key)):
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
        if isinstance(payload, dict) and payload.get("_bad"):
            continue  # 盘中空结果不入盘：避免盘前坏数据污染整日缓存
        out[k] = {"ts": ts, "payload": payload}
    _save_json_file(_DAILY_PATH, out)


# 盘中空扫描负缓存：盘前/数据未就绪的空结果只短时生效，10 分钟后允许重扫
_SCAN_BAD_TTL = 10 * 60


def _scan_cache_hit(key: str) -> tuple[float, dict] | None:
    hit = _SCAN_CACHE.get(key)
    if not hit:
        return None
    ts, payload = hit
    if isinstance(payload, dict) and payload.get("_bad"):
        if time.time() - ts < _SCAN_BAD_TTL:
            return hit
        _SCAN_CACHE.pop(key, None)
        return None
    if time.time() - ts < 6 * 3600:
        return hit
    return None


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


def _close_epoch_today() -> float:
    """今日 15:01（收盘后数据定型）epoch；解析失败返回 0。
    2026-08-18 事故：15:03 自动扫描抓到上游未定型当日 bar（利通电子盘中+10% 被当成收盘），
    导致 08-17 成分评分/主线排序生产与本地不一致；2026-08-25 雷总定：15:01 收盘后即可重扫，
    上游当日 bar 由 _kline_entry_valid 的「收盘后须含今日 K 线」校验兜底，未定型数据不落缓存。"""
    try:
        lt = time.localtime()
        return time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 15, 1, 0, 0, 0, -1))
    except Exception:
        return 0.0


def _kline_entry_valid(date8: str, rows: list[list[Any]] | None, ts: float) -> bool:
    """K线缓存有效期：盘中 30 分钟 TTL；收盘后仅“收盘后写入且已含今日K线”的缓存视为最终数据，整晚可复用。"""
    if not isinstance(rows, list) or not rows:
        return False
    if _market_closed():
        if ts < _close_epoch_today():
            return False
        try:
            return str(rows[-1][0])[:10].replace("-", "") == date8
        except Exception:
            return False
    return (time.time() - ts) < _KLINE_TTL


def _kline_cache_get(date8: str, code: str) -> list[list[Any]] | None:
    global _KLINE_DAILY
    if _KLINE_DAILY.get("date") != date8:
        data, ts = _kline_cache_load(date8)
        _KLINE_DAILY = {"date": date8, "data": data, "ts": ts}
    rows = _KLINE_DAILY["data"].get(code)
    ts = float(_KLINE_DAILY.get("ts", {}).get(code) or 0)
    if _kline_entry_valid(date8, rows, ts):
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
    if cache.get("ver") == 4 and cache.get("asof") == today8 and cache.get("ok"):
        return cache
    hist = _load_history() or {}
    cutoff = time.time() - days * 86400
    jobs: list[tuple[str, str, str, dict[str, Any]]] = []
    seen: set[tuple[str, str, str]] = set()
    for key, payload in hist.items():
        mk = str(key).split(":", 1)[0] if ":" in str(key) else "bj"
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
            asof = str(p.get("lastDate") or p.get("asof") or d)
            if not code or not asof or (mk, code, asof) in seen:
                continue
            seen.add((mk, code, asof))
            jobs.append((mk, code, asof, p))
    jobs = jobs[:50]
    _PRIO = ("ztPullback", "pullback2", "firstBoardRight", "surgeStart", "surgePullback", "steadyUp", "macdFirstRed")

    def _pattern_of(p: dict[str, Any]) -> str:
        pp = p.get("patterns") or {}
        for k in _PRIO:
            if pp.get(k):
                return k
        return "other"

    def _band_of(final: Any) -> str:
        try:
            f = int(final)
        except Exception:
            return "unknown"
        if f >= 70:
            return ">=70"
        if f >= 60:
            return "60-69"
        if f >= 50:
            return "50-59"
        return "<50"

    results: list[dict[str, Any]] = []
    for mk, code, asof, p in jobs:
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
        entry = float(p.get("price") or (rows[idx][2] if idx is not None else rows[-1][2])) or 1.0
        last = float(rows[-1][2])
        base = {
            "market": mk, "code": code, "asof": asof, "name": str(p.get("name") or ""),
            "tier": str(p.get("tier") or "normal"), "role": str(p.get("pickRole") or ""),
            "final": p.get("final"),
            "pattern": _pattern_of(p), "emotionRegime": str(p.get("emotionRegime") or "unknown"),
            "scoreBand": _band_of(p.get("final")),
            "entry": round(entry, 2), "last": round(last, 2), "lastDate": str(rows[-1][0]),
        }
        if idx is None or idx >= len(rows) - 1:
            base.update({
                "state": "tracking", "since": round((last / entry - 1) * 100, 1),
                "fwd1": None, "fwd3": None, "fwd5": None, "fwd10": None, "stop_hit": None,
            })
            results.append(base)
            continue
        hi5 = max(float(r[3]) for r in rows[idx + 1: min(idx + 6, len(rows))])
        fwd5 = (hi5 / entry - 1) * 100
        fwd10 = None
        stop_hit = None
        fwd1 = fwd3 = None
        def _fwd(nn: int) -> float | None:
            j = idx + nn
            return round((float(rows[j][2]) / entry - 1) * 100, 1) if j < len(rows) else None
        fwd1 = _fwd(1)
        fwd3 = _fwd(3)
        if idx + 1 < len(rows):
            stop = 0.0
            m = re.search(r"\d+(?:\.\d+)?", str((p.get("strategy") or {}).get("stop") or ""))
            if m:
                stop = float(m.group())
            if stop > 0:
                stop_hit = min(float(r[4]) for r in rows[idx + 1: min(idx + 11, len(rows))]) <= stop
            if idx + 10 < len(rows):
                fwd10 = (float(rows[idx + 10][2]) / entry - 1) * 100
        base.update({
            "state": "done", "high5": round(hi5, 2),
            "fwd1": fwd1, "fwd3": fwd3,
            "fwd5": round(fwd5, 1), "fwd10": round(fwd10, 1) if fwd10 is not None else None,
            "stop_hit": stop_hit,
        })
        results.append(base)
    results.sort(key=lambda r: str(r.get("asof") or ""), reverse=True)
    done = [r for r in results if r.get("state") == "done" and r.get("fwd5") is not None]
    n = len(done)
    hit5 = sum(1 for r in done if r["fwd5"] >= 5.0)
    pos5 = sum(1 for r in done if r["fwd5"] >= 0)
    stop_n = sum(1 for r in done if r.get("stop_hit"))
    tracking = sum(1 for r in results if r.get("state") == "tracking")

    def _grp(items: list[dict[str, Any]]) -> dict[str, Any]:
        dd = [r for r in items if r.get("state") == "done" and r.get("fwd5") is not None]
        nn = len(dd)
        if not nn:
            return {"n": 0}

        def _mean(k: str) -> float | None:
            vals = [float(r[k]) for r in dd if r.get(k) is not None]
            return round(sum(vals) / len(vals), 2) if vals else None
        return {
            "n": nn,
            "hit5_rate": round(sum(1 for r in dd if r["fwd5"] >= 5.0) / nn * 100, 1),
            "pos5_rate": round(sum(1 for r in dd if r["fwd5"] >= 0) / nn * 100, 1),
            "mean_fwd1": _mean("fwd1"), "mean_fwd3": _mean("fwd3"), "mean_fwd5": _mean("fwd5"),
        }

    by_pattern: dict[str, list[dict[str, Any]]] = {}
    by_regime: dict[str, list[dict[str, Any]]] = {}
    by_score: dict[str, list[dict[str, Any]]] = {}
    for r in done:
        by_pattern.setdefault(str(r.get("pattern") or "other"), []).append(r)
        by_regime.setdefault(str(r.get("emotionRegime") or "unknown"), []).append(r)
        by_score.setdefault(str(r.get("scoreBand") or "unknown"), []).append(r)

    by_tier: dict[str, dict[str, Any]] = {}
    for r in done:
        k = r.get("tier") or "normal"
        b = by_tier.setdefault(k, {"n": 0, "hit": 0})
        b["n"] += 1
        if r["fwd5"] >= 5.0:
            b["hit"] += 1
    by_market: dict[str, list[dict[str, Any]]] = {}
    for r in results:
        by_market.setdefault(str(r.get("market") or "bj"), []).append(r)

    out = {
        "ok": True, "asof": today8, "n": n, "tracking": tracking,
        "hit5_rate": round(hit5 / n * 100, 1) if n else None,
        "pos5_rate": round(pos5 / n * 100, 1) if n else None,
        "stop_rate": round(stop_n / n * 100, 1) if n else None,
        "hit_def": "5日内最高涨幅≥5%计为达标（T+1/T+3/T+5=信号日收盘后第N日收盘收益）",
        "by_tier": by_tier,
        "by_pattern": {k: _grp(v) for k, v in by_pattern.items()},
        "by_regime": {k: _grp(v) for k, v in by_regime.items()},
        "by_score": {k: _grp(v) for k, v in by_score.items()},
        "by_market": {k: _grp(v) for k, v in by_market.items()},
        "ver": 4,
        "items": results,
        "recent": results[:12],
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
            # 盘中（未收盘）扫描一律存多版本（HH:MM），不写“每日最终版”主文件；
            # 收盘后首次扫描才创建主版本（之后的收盘重扫仍走 HH:MM 多版本保护）。
            if not _market_closed() or os.path.exists(main):
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
            mm = re.match(r"^(\d{4}-\d{2}-\d{2})-((?:bj_all|all|bj|hs|kc))(?:-(\d{4}))?$", stem)
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
    if market in ("all", "bj", "hs", "kc", "bj_all"):
        items = [it for it in items if it.get("market") == market]
    out = dict(d)
    out["items"] = items
    return out


def _load_archive_raw(market: str, date_key: str) -> dict[str, Any] | None:
    """按市场读取归档（不含 pb 视图层）。"""
    market = str(market or "bj")
    if not _MULTI_ARCH_RE.match(str(date_key or "")):
        try:
            _hist0 = _load_history()
            _iv = _hist0.get(f"{market}:{str(date_key).split(' (', 1)[0]}")
            if isinstance(_iv, dict):
                return _reattach_ths(_iv)
        except Exception:
            pass
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
        d = _load_json_file(os.path.join(_ARCHIVE_DIR, f"{date_key}.json"), None)
    return _reattach_ths(d) if isinstance(d, dict) else None


def load_archive(market: str, date_key: str) -> dict[str, Any] | None:
    market = str(market or "bj")
    if market in ("pb", "mlpb", "breakout", "leader"):
        hs = _load_archive_raw("hs", date_key)
        return apply_column_view(market, hs) if isinstance(hs, dict) else None
    if market in ("macd", "low10", "tight"):
        raw = _load_archive_raw("all", date_key) or _load_archive_raw(market, date_key)
        return apply_column_view(market, raw) if isinstance(raw, dict) else None
    return _load_archive_raw(market, date_key)




# 回踩企稳 · 仅首板系形态（不含普通异动回踩/砸盘企稳等宽口径）
_PB_BOARD_KEYS = ("pb45", "firstWeek", "firstBoardRight", "pullback2", "ztPullback")
_PB_LEDGER_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "data", "pb_pick_ledger.json"
)
_PB_TRACK_CACHE_PATH = os.path.join(_ARCHIVE_DIR, "pb_track_cache.json")
_PB_TRACK_CACHE: dict[str, Any] = {}


def _pb_board_only(p: dict[str, Any]) -> bool:
    """仅首板系：首板4-5日回踩 / 近1周首板右侧 / 首板右侧上拐 / 板后回踩 / 涨停级回踩。"""
    pp = p.get("patterns") if isinstance(p.get("patterns"), dict) else {}
    return any(pp.get(k) for k in _PB_BOARD_KEYS)


def _pb_evp_score(p: dict[str, Any]) -> int:
    """首板系形态优先级（pb 专栏专用）。"""
    pp = p.get("patterns") if isinstance(p.get("patterns"), dict) else {}
    if pp.get("firstWeek"):
        return 5
    if pp.get("pb45"):
        return 4
    if pp.get("firstBoardRight"):
        return 5 if pp.get("breakout") else 4
    if pp.get("pullback2"):
        return 4 if pp.get("breakout") else 3
    if pp.get("ztPullback"):
        return 2
    return 0


def _pb_pattern_label(p: dict[str, Any]) -> str:
    """历史列表展示用：取最强首板系形态标签。"""
    pp = p.get("patterns") if isinstance(p.get("patterns"), dict) else {}
    if pp.get("firstWeek"):
        return "近1周首板·底部右侧"
    if pp.get("pb45"):
        return "首板4-5日回踩"
    if pp.get("firstBoardRight"):
        return "首板右侧上拐" + ("·二波突破" if pp.get("breakout") else "")
    if pp.get("pullback2"):
        return "板后回踩" + ("·二波突破" if pp.get("breakout") else "")
    if pp.get("ztPullback"):
        return "涨停级回踩"
    return ""


def _hist_pick_brief(p: dict[str, Any]) -> dict[str, Any]:
    return {
        "code": p.get("code"), "name": p.get("name"),
        "tier": p.get("tier") or "normal",
        "final": p.get("final"), "price": p.get("price"), "pct": p.get("pct"),
        "pattern": _pb_pattern_label(p),
    }


def _load_pb_ledger_file() -> list[dict[str, Any]]:
    raw = _load_json_file(_PB_LEDGER_PATH, {}) or {}
    items = raw.get("items") if isinstance(raw, dict) else raw
    return [x for x in (items or []) if isinstance(x, dict) and x.get("code")]


def _save_pb_ledger_file(items: list[dict[str, Any]]) -> None:
    try:
        os.makedirs(os.path.dirname(_PB_LEDGER_PATH), exist_ok=True)
        _save_json_file(_PB_LEDGER_PATH, {"ver": 1, "items": items[-800:]})
    except Exception:
        pass


def append_pb_ledger(date: str, asof: str, picks: list[dict[str, Any]]) -> None:
    """收盘扫描后追加首板系入选记录（供后期跟踪二次涨停概率）。"""
    day = str(date or "").split(" (", 1)[0]
    if not day or not picks:
        return
    items = _load_pb_ledger_file()
    seen = {(str(x.get("date") or ""), str(x.get("code") or "")) for x in items}
    for p in picks:
        if not isinstance(p, dict) or not _pb_board_only(p):
            continue
        code = str(p.get("code") or "")
        if not code:
            continue
        key = (day, code)
        if key in seen:
            continue
        seen.add(key)
        items.append({
            "date": day,
            "asof": str(asof or day),
            "code": code,
            "name": str(p.get("name") or ""),
            "final": p.get("final"),
            "price": p.get("price"),
            "pct": p.get("pct"),
            "pattern": _pb_pattern_label(p),
            "tier": p.get("tier") or "normal",
        })
    items.sort(key=lambda x: (str(x.get("date") or ""), str(x.get("code") or "")))
    _save_pb_ledger_file(items)


def pb_ledger(limit: int = 120) -> list[dict[str, Any]]:
    """首板系回踩历史入选台账（持久化 + 归档回溯，board-only）。"""
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for it in _load_pb_ledger_file():
        d, c = str(it.get("date") or ""), str(it.get("code") or "")
        if not d or not c or (d, c) in seen:
            continue
        seen.add((d, c))
        rows.append(dict(it))
    for it in archive_summary("pb"):
        day = str(it.get("date") or "")
        if not day:
            continue
        for p in it.get("picks") or []:
            if not isinstance(p, dict):
                continue
            code = str(p.get("code") or "")
            if not code or (day, code) in seen:
                continue
            seen.add((day, code))
            rows.append({
                "date": day,
                "asof": it.get("asof") or day,
                "code": code,
                "name": p.get("name"),
                "final": p.get("final"),
                "price": p.get("price"),
                "pct": p.get("pct"),
                "pattern": p.get("pattern") or "",
            })
    rows.sort(key=lambda x: (str(x.get("date") or ""), str(x.get("code") or "")), reverse=True)
    return rows[: max(1, min(int(limit or 120), 500))]


def _pb_relimit_in_window(rows: list, idx: int, code: str, within: int) -> bool:
    """信号日收盘后 within 个交易日内是否再次涨停。"""
    th = _zt_threshold(str(code or "").zfill(6))
    for j in range(idx + 1, min(idx + 1 + within, len(rows))):
        prev = float(rows[j - 1][2]) if j > 0 else float(rows[j][2])
        if prev <= 0:
            continue
        pct = (float(rows[j][2]) / prev - 1) * 100
        if pct >= th - 0.5:
            return True
    return False


async def compute_pb_track(days: int = 90, variant: str = "vip",
                           priority_override: str = "", allow_paid: bool = True) -> dict[str, Any]:
    """首板系回踩入选 · 后期跟踪：T+N 收益与再次涨停（二板）概率。"""
    days = max(7, min(int(days or 90), 180))
    today8 = _today8()
    cache = _PB_TRACK_CACHE or _load_json_file(_PB_TRACK_CACHE_PATH, {}) or {}
    if cache.get("ver") == 1 and cache.get("asof") == today8 and cache.get("ok"):
        return cache
    # 首次跟踪：把归档回溯条目写入持久台账
    try:
        file_items = _load_pb_ledger_file()
        seen_f = {(str(x.get("date") or ""), str(x.get("code") or "")) for x in file_items}
        for row in pb_ledger(500):
            d, c = str(row.get("date") or ""), str(row.get("code") or "")
            if d and c and (d, c) not in seen_f:
                file_items.append(dict(row))
                seen_f.add((d, c))
        if len(file_items) > len(_load_pb_ledger_file()):
            _save_pb_ledger_file(file_items)
    except Exception:
        pass
    cutoff_ts = time.time() - days * 86400
    jobs: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in pb_ledger(500):
        d = str(row.get("date") or "")
        code = str(row.get("code") or "")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d) or not code:
            continue
        try:
            if time.mktime(time.strptime(d, "%Y-%m-%d")) < cutoff_ts:
                continue
        except Exception:
            continue
        if (d, code) in seen:
            continue
        seen.add((d, code))
        jobs.append(row)
    results: list[dict[str, Any]] = []
    for row in jobs[:80]:
        code = str(row.get("code") or "")
        asof = str(row.get("asof") or row.get("date") or "")
        try:
            kl = await _kline_with_retry(code, variant, priority_override, allow_paid, use_cache=True)
        except Exception:
            continue
        if not kl:
            continue
        dates = [str(r[0]) for r in kl]
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
        entry = float(row.get("price") or 0) or (
            float(kl[idx][2]) if idx is not None else float(kl[-1][2])
        )
        if entry <= 0:
            continue
        base: dict[str, Any] = {
            "date": row.get("date"), "asof": asof, "code": code,
            "name": str(row.get("name") or ""), "pattern": str(row.get("pattern") or ""),
            "final": row.get("final"), "entry": round(entry, 2),
            "last": round(float(kl[-1][2]), 2), "lastDate": str(kl[-1][0]),
        }
        if idx is None or idx >= len(kl) - 1:
            base.update({
                "state": "tracking",
                "since": round((float(kl[-1][2]) / entry - 1) * 100, 1),
                "fwd1": None, "fwd3": None, "fwd5": None, "fwd10": None,
                "relimit5": None, "relimit10": None,
            })
            results.append(base)
            continue

        def _fwd(nn: int) -> float | None:
            j = idx + nn
            return round((float(kl[j][2]) / entry - 1) * 100, 1) if j < len(kl) else None

        base.update({
            "state": "done",
            "fwd1": _fwd(1), "fwd3": _fwd(3), "fwd5": _fwd(5),
            "fwd10": _fwd(10),
            "relimit5": _pb_relimit_in_window(kl, idx, code, 5),
            "relimit10": _pb_relimit_in_window(kl, idx, code, 10),
            "since": round((float(kl[-1][2]) / entry - 1) * 100, 1),
        })
        results.append(base)
    results.sort(key=lambda r: str(r.get("date") or ""), reverse=True)
    done = [r for r in results if r.get("state") == "done"]
    n_done = len(done)
    r5 = [r for r in done if r.get("relimit5") is not None]
    r10 = [r for r in done if r.get("relimit10") is not None]

    def _rate(items: list[dict[str, Any]], key: str) -> float | None:
        vals = [r for r in items if r.get(key) is not None]
        if not vals:
            return None
        return round(sum(1 for r in vals if r.get(key)) / len(vals) * 100, 1)

    def _mean_fwd(k: str) -> float | None:
        vals = [float(r[k]) for r in done if r.get(k) is not None]
        return round(sum(vals) / len(vals), 1) if vals else None

    by_pat: dict[str, list[dict[str, Any]]] = {}
    for r in done:
        pat = str(r.get("pattern") or "其他").split("·")[0]
        by_pat.setdefault(pat, []).append(r)

    out = {
        "ok": True, "asof": today8, "ver": 1,
        "days": days, "n": len(results), "n_done": n_done,
        "tracking": sum(1 for r in results if r.get("state") == "tracking"),
        "relimit5_rate": _rate(r5, "relimit5"),
        "relimit10_rate": _rate(r10, "relimit10"),
        "mean_fwd5": _mean_fwd("fwd5"),
        "mean_fwd10": _mean_fwd("fwd10"),
        "pos5_rate": round(sum(1 for r in done if (r.get("fwd5") or 0) >= 0) / n_done * 100, 1) if n_done else None,
        "hit5_rate": round(sum(1 for r in done if (r.get("fwd5") or 0) >= 5) / n_done * 100, 1) if n_done else None,
        "relimit_def": "信号日收盘后 N 个交易日内再次触及涨停阈值计为「再次涨停」",
        "by_pattern": {
            k: {
                "n": len(v),
                "relimit5_rate": _rate(v, "relimit5"),
                "relimit10_rate": _rate(v, "relimit10"),
                "mean_fwd5": round(sum(float(x["fwd5"]) for x in v if x.get("fwd5") is not None) /
                                   max(1, sum(1 for x in v if x.get("fwd5") is not None)), 1)
                if any(x.get("fwd5") is not None for x in v) else None,
            }
            for k, v in by_pat.items()
        },
        "items": results,
    }
    _PB_TRACK_CACHE.clear()
    _PB_TRACK_CACHE.update(out)
    try:
        _save_json_file(_PB_TRACK_CACHE_PATH, out)
    except Exception:
        pass
    return out



def column_ledger(market: str = "pb", limit: int = 120) -> list[dict[str, Any]]:
    """各栏目历史主推台账（不含备选池），供后期跟踪对比算法。"""
    market = str(market or "pb").strip().lower()
    lim = max(1, min(int(limit or 120), 500))
    if market == "pb":
        rows = pb_ledger(lim)
        for r in rows:
            if isinstance(r, dict):
                r.setdefault("market", "pb")
        return rows
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for it in archive_summary(market):
        day = str(it.get("date") or "")
        asof = str(it.get("asof") or day)
        if not day:
            continue
        for p in it.get("picks") or []:
            if not isinstance(p, dict):
                continue
            code = str(p.get("code") or "")
            if not code or (day, code) in seen:
                continue
            seen.add((day, code))
            rows.append({
                "date": day, "asof": asof, "code": code,
                "name": p.get("name"), "final": p.get("final"),
                "price": p.get("price") if p.get("price") is not None else (p.get("close") or p.get("last")),
                "pct": p.get("pct"),
                "pattern": p.get("pattern") or "",
                "tier": p.get("tier") or "normal",
                "market": market,
            })
    rows.sort(key=lambda x: (str(x.get("date") or ""), str(x.get("code") or "")), reverse=True)
    return rows[:lim]


async def compute_column_track(market: str = "pb", days: int = 90, variant: str = "vip",
                               priority_override: str = "", allow_paid: bool = True) -> dict[str, Any]:
    """栏目主推跟踪：入选后 T+5/T+10 收益与成功率（各栏目算法对比）。"""
    market = str(market or "pb").strip().lower()
    if market == "pb":
        out = await compute_pb_track(days, variant, priority_override, allow_paid)
        out = dict(out)
        out["market"] = "pb"
        return out
    days = max(7, min(int(days or 90), 180))
    today8 = _today8()
    cache_path = os.path.join(_ARCHIVE_DIR, "col_track_%s.json" % market)
    cache = _load_json_file(cache_path, {}) or {}
    if cache.get("ver") == 1 and cache.get("asof") == today8 and cache.get("ok") and cache.get("market") == market:
        return cache
    cutoff_ts = time.time() - days * 86400
    jobs: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in column_ledger(market, 500):
        d = str(row.get("date") or "")
        code = str(row.get("code") or "")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d) or not code:
            continue
        try:
            if time.mktime(time.strptime(d, "%Y-%m-%d")) < cutoff_ts:
                continue
        except Exception:
            continue
        if (d, code) in seen:
            continue
        seen.add((d, code))
        jobs.append(row)
    results: list[dict[str, Any]] = []
    for row in jobs[:80]:
        code = str(row.get("code") or "")
        asof = str(row.get("asof") or row.get("date") or "")
        try:
            kl = await _kline_with_retry(code, variant, priority_override, allow_paid, use_cache=True)
        except Exception:
            continue
        if not kl:
            continue
        dates = [str(r[0]) for r in kl]
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
        entry = float(row.get("price") or 0) or (
            float(kl[idx][2]) if idx is not None else float(kl[-1][2])
        )
        if entry <= 0:
            continue
        base: dict[str, Any] = {
            "date": row.get("date"), "asof": asof, "code": code, "market": market,
            "name": str(row.get("name") or ""), "pattern": str(row.get("pattern") or ""),
            "final": row.get("final"), "entry": round(entry, 2),
            "last": round(float(kl[-1][2]), 2), "lastDate": str(kl[-1][0]),
        }
        if idx is None or idx >= len(kl) - 1:
            base.update({
                "state": "tracking",
                "since": round((float(kl[-1][2]) / entry - 1) * 100, 1),
                "fwd1": None, "fwd3": None, "fwd5": None, "fwd10": None,
                "relimit5": None, "relimit10": None,
            })
            results.append(base)
            continue

        def _fwd(nn: int, _idx=idx, _kl=kl, _entry=entry) -> float | None:
            j = _idx + nn
            return round((float(_kl[j][2]) / _entry - 1) * 100, 1) if j < len(_kl) else None

        base.update({
            "state": "done",
            "fwd1": _fwd(1), "fwd3": _fwd(3), "fwd5": _fwd(5), "fwd10": _fwd(10),
            "relimit5": None, "relimit10": None,
            "since": round((float(kl[-1][2]) / entry - 1) * 100, 1),
        })
        results.append(base)
    results.sort(key=lambda r: str(r.get("date") or ""), reverse=True)
    done = [r for r in results if r.get("state") == "done"]
    n_done = len(done)

    def _mean_fwd(k: str) -> float | None:
        vals = [float(r[k]) for r in done if r.get(k) is not None]
        return round(sum(vals) / len(vals), 1) if vals else None

    out = {
        "ok": True, "asof": today8, "ver": 1, "market": market,
        "days": days, "n": len(results), "n_done": n_done,
        "tracking": sum(1 for r in results if r.get("state") == "tracking"),
        "relimit5_rate": None, "relimit10_rate": None,
        "mean_fwd5": _mean_fwd("fwd5"), "mean_fwd10": _mean_fwd("fwd10"),
        "pos5_rate": round(sum(1 for r in done if (r.get("fwd5") or 0) >= 0) / n_done * 100, 1) if n_done else None,
        "hit5_rate": round(sum(1 for r in done if (r.get("fwd5") or 0) >= 5) / n_done * 100, 1) if n_done else None,
        "relimit_def": "本栏目统计入选后收盘收益；强势=5日收益≥+5%",
        "by_pattern": {},
        "items": results,
    }
    try:
        _save_json_file(cache_path, out)
    except Exception:
        pass
    return out


def archive_summary(market: str = "bj") -> list[dict[str, Any]]:
    """历史归档选择器（按市场隔离）：优先以 bj_scan_history.json 索引为准。

    索引 = 每次扫描保存的「当日最终快照」，与 stale 回退 / 昨日跟踪同源，全站口径一致；
    避免按归档文件名倒序误选早盘临时版/旧主版本（如 08-10 北证 11:44 版 57/54 压过
    16:09 收盘版 68/60）。索引缺失的旧日期（如 2026-08-06 无市场前缀）回退扫描归档文件。
    同日多版本文件一律保留在磁盘，详情打开仍可寻址。
    pb = 从 hs 归档套用 pb_view 过滤（支持历史回溯，无需单独存盘）。
    """
    market = str(market or "bj")
    if market in ("pb", "mlpb", "breakout", "leader", "macd", "low10", "tight"):
        out_col: list[dict[str, Any]] = []
        try:
            hist = _load_history()
            days_seen: set[str] = set()
            src_prefix = "all" if market in ("macd", "low10", "tight") else "hs"

            def _col_picks_from_snap(snap: dict[str, Any]) -> list[dict[str, Any]]:
                if market == "macd":
                    raw = snap.get("macd_reds") or snap.get("picks") or []
                else:
                    raw = snap.get("picks") or []
                return [_hist_pick_brief(p) for p in raw[:6] if isinstance(p, dict)]

            for k, v in hist.items():
                if not isinstance(v, dict):
                    continue
                mk = k.split(":", 1)[0] if ":" in k else "bj"
                dk = k.split(":", 1)[1] if ":" in k else k
                if mk == market:
                    picks = _col_picks_from_snap(v)
                    if not picks and market == "macd":
                        picks = [_hist_pick_brief(p) for p in (v.get("macd_reds") or [])[:4] if isinstance(p, dict)]
                    if not picks:
                        picks = [_hist_pick_brief(p) for p in (v.get("picks") or [])[:6] if isinstance(p, dict)]
                    if picks:
                        out_col.append({
                            "date": dk,
                            "asof": v.get("asof") or dk,
                            "total": v.get("total"),
                            "fine": v.get("fine"),
                            "picks": picks,
                        })
                        days_seen.add(dk)
            for k, v in hist.items():
                if not isinstance(v, dict) or not k.startswith(src_prefix + ":"):
                    continue
                dk = k.split(":", 1)[1]
                if dk in days_seen:
                    continue
                snap = apply_column_view(market, v)
                picks = _col_picks_from_snap(snap)
                if not picks:
                    continue
                out_col.append({
                    "date": dk,
                    "asof": snap.get("asof") or dk,
                    "total": snap.get("total"),
                    "fine": snap.get("fine"),
                    "picks": picks,
                })
            out_col.sort(key=lambda x: str(x.get("date") or ""), reverse=True)
            if out_col:
                return out_col[:_ARCHIVE_KEEP_DAYS]
        except Exception:
            pass
        return out_col
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
            mm = re.match(r"^(\d{4}-\d{2}-\d{2})-((?:bj_all|all|bj|hs|kc))-(\d{4})$", stem)
            if mm:
                if mm.group(2) != market:
                    continue
                date_key = f"{mm.group(1)} ({mm.group(3)[:2]}:{mm.group(3)[2:]})"
            else:
                _suffix = "-" + str(market)
                if stem.endswith(_suffix):
                    date_key = stem[: -len(_suffix)]
                elif str(market) == "bj" and not re.search(r"-(?:all|bj|hs|kc|bj_all)$", stem):
                    date_key = stem  # 旧版无市场后缀 → 北证
                else:
                    continue
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


def _reattach_ths(payload: dict[str, Any]) -> dict[str, Any]:
    """归档/stale 回退读取时补挂板块 ths（旧归档无 ths 字段，无需重扫即可显示同花顺代码）。"""
    try:
        for key in ("board_rank", "mainlines", "hot_boards"):
            for it in payload.get(key) or []:
                if isinstance(it, dict):
                    sid = str(it.get("secid") or "").strip()
                    if sid and not str(it.get("ths") or "").strip():
                        it["ths"] = bk_to_ths_secid(sid) or ""
    except Exception:
        pass
    # 主线统一口径：归档/stale 回退时以「最近复盘定型主线」为准重建 mainlines + 判定依据小字
    # （2026-08-18 事故：15:03 未定型 K 线污染生产 08-17 数据；盘中一律以最近定型收盘为准，
    #   判定字段 top5/fund5/涨停/异动 从最近 sector_score 零上游补算，旧归档旧名字也被纠正）
    try:
        _dml = _daily_mainlines()
        _names = (_dml or {}).get("names") or []
        _info = (_dml or {}).get("info") or {}
        _src = (_dml or {}).get("src") or "daily"
        _today_final = bool(_dml) and _src in ("archive", "recalc")
        # 当日已定型（含“无主线”）→ 以复盘判定为准重建（空则清空），
        # 避免 stale/归档回退时残留旧归档主线，造成“排行与主线判定不一致”。
        if _names or _today_final:
            payload["mainlines"] = []
            for _n in _names:
                _mi = dict(_info.get(_n) or {})
                _mi["name"] = _n
                _mi["src"] = _src
                payload["mainlines"].append(_mi)
        _obs = (_dml or {}).get("observes") or []
        if _obs:
            payload["observes"] = [{"name": n, "src": _src} for n in _obs]
        # 日期/来源与复盘对齐：掘金常在 15:05 预扫、复盘约 15:10 才落归档，
        # 若不回写 mainline_date，前端会一直显示「数据截至 昨日」。
        if _dml:
            _dd = str((_dml.get("date") or "")).replace("-", "").strip()
            if _dd:
                payload["mainline_date"] = _dd
            payload["mainline_from"] = _src
        # 板块排行与主线口径同步（主线驱动市场）：king=主线首名，key=其余主线，backup=备选
        if str(payload.get("market_code") or "") in ("all", "hs", "kc", "bj", "bj_all"):
            _rank = payload.get("board_rank")
            if not isinstance(_rank, list):
                _rank = []
                payload["board_rank"] = _rank
            if _names:
                _miss = _rank_missing_mainlines(_rank, _names)
                if _miss:
                    _rank.extend(_build_mainline_rank_items(_miss))
            _obs_list = [str(o.get("name") or "").strip() for o in (payload.get("observes") or []) if str(o.get("name") or "").strip()]
            # 无主线时把观察板块补进榜（否则 _sync 无法前置点亮）
            if not _names and _obs_list:
                _miss_obs = _rank_missing_mainlines(_rank, _obs_list)
                if _miss_obs:
                    _rank.extend(_build_mainline_rank_items(_miss_obs))
            payload["board_rank"] = _sync_rank_mainlines(_rank, _names, observe_names=_obs_list or None)
            payload["board_rank"] = _attach_ml_why(payload.get("board_rank") or [], _names, _info)
            # 重点观察标记：有主线时 observes 显示「重点观察」；无主线时已由 _sync 赋 king/key
            _obs_names = {str(o.get("name") or "").replace(" ", "") for o in (payload.get("observes") or [])}
            if _names:
                for _b in payload.get("board_rank") or []:
                    if isinstance(_b, dict) and not _b.get("mainline") \
                            and str(_b.get("name") or "").replace(" ", "") in _obs_names:
                        _b["tier"] = "obs"
                        _b["observe"] = True
    except Exception:
        pass
    return payload


def _rank_missing_mainlines(board_rank, mainline_names):
    """榜单中缺失的主线名（同名或 SECTOR_BOARD_ALIASES 别名均未出现）。

    stale/归档回退时，旧扫描板块池可能没有复盘刚锁定的主线（如 创新药CXO/通信光模块CPO），
    导致 mainlines 卡片与板块排行不一致；这里找出缺失项供补缺进榜。
    """
    try:
        _norm = lambda s: re.sub(r"\s+", "", str(s or ""))
        _aliases: dict[str, list[str]] = {}
        try:
            from .daily_report import SECTOR_BOARD_ALIASES as _SBA
        except Exception:
            _SBA = {}
        for _n in mainline_names:
            _aliases[_n] = [_norm(a) for a in (_SBA.get(_n) or [_n]) if a]
        _miss: list[str] = []
        for _n in mainline_names:
            _a0 = _aliases.get(_n) or [_norm(_n)]
            _found = False
            for b in (board_rank or []):
                if not isinstance(b, dict):
                    continue
                _bn = _norm(str(b.get("name") or ""))
                if not _bn:
                    continue
                if _bn == _norm(_n) or any(len(a) >= 2 and a in _bn for a in _a0):
                    _found = True
                    break
            if not _found:
                _miss.append(_n)
        return _miss
    except Exception:
        return []


def _build_mainline_rank_items(names):
    """为缺失主线合成板块榜条目（stale 回退零上游成本）：secid 走 _MAINLINE_BOARD_MAP /
    _MAINLINE_SECID_FALLBACK，代表股走复盘 SECTORS，资金字段留 0 由前端显示「资金+技术双确认」。"""
    out: list[dict[str, Any]] = []
    try:
        from .daily_report import SECTORS
    except Exception:
        SECTORS = {}
    for _n in names:
        _sid = ""
        _sids = _MAINLINE_BOARD_MAP.get(_n)
        if _sids:
            _sid = _sids[0]
        else:
            _sid = _MAINLINE_SECID_FALLBACK.get(_n) or ""
        _members = SECTORS.get(_n) or []
        _lds = [{"code": str(c), "name": nm, "pct": None} for c, nm in _members[:3]]
        out.append({
            "name": _n, "secid": _sid,
            "ths": bk_to_ths_secid(_sid) if _sid else "",
            "f164": 0, "f62": 0, "pct": None, "p5": None,
            "hot": True, "mainline": True, "leaders": _lds,
        })
    return out


def _sync_rank_mainlines(board_rank, mainline_names, observe_names=None):
    """板块排行与主线口径同步：主线按复盘顺序前置，第1=今日主线(king)、其余=重点关注(key)、其余=备选(backup)。

    支持主线别名匹配（daily_report.SECTOR_BOARD_ALIASES，如 通信技术/CPO概念→通信光模块CPO），
    使科创/北证板块榜也能与全市场主线对齐；同一主线在榜中只保留 1 个代表板块（优先同名），
    其余同名/别名板块不再重复标注主线。修复旧归档/旧算法扫描留下的「排行 king 与主线首名不一致」。

    无主线时：若有重点观察板块，则观察板块前置为 king/key（点亮重点关注），资金热度板块降为 backup，
    避免电风扇日仍按资金排「王者」黄金链盖过观察板块。
    """
    try:
        if not isinstance(board_rank, list):
            return board_rank
        _names = [n for n in (mainline_names or []) if str(n or "").strip()]
        _obs = [n for n in (observe_names or []) if str(n or "").strip()]
        if not _names and not _obs:
            return board_rank
        _norm = lambda s: re.sub(r"\s+", "", str(s or ""))
        # 无主线：观察板块占 king/key，资金热度退为 backup
        if not _names and _obs:
            _obs_order = {_norm(n): i for i, n in enumerate(_obs)}
            _obs_br: list[tuple[dict[str, Any], str]] = []
            _other_br: list[dict[str, Any]] = []
            _used: set[str] = set()
            for b in board_rank:
                if not isinstance(b, dict):
                    continue
                _bn = _norm(b.get("name"))
                _on = _obs_order.get(_bn)
                if _on is None:
                    # 别名弱匹配：观察名包含于板块名或反之（≥2 字）
                    for _o, _i in _obs_order.items():
                        if len(_o) >= 2 and (_o in _bn or _bn in _o):
                            _on = _i
                            _bn = _o
                            break
                if _on is not None and _bn not in _used:
                    _used.add(_bn)
                    b["mainline"] = False
                    b["observe"] = True
                    b["ml_name"] = _obs[_on] if _on < len(_obs) else b.get("name")
                    b.pop("ml_why", None)
                    b.pop("ml_src", None)
                    _obs_br.append((b, _bn))
                else:
                    b["mainline"] = False
                    b.pop("ml_name", None)
                    b.pop("ml_why", None)
                    b.pop("ml_src", None)
                    if not b.get("observe"):
                        b["observe"] = False
                    _other_br.append(b)
            if not _obs_br:
                return board_rank
            _obs_br.sort(key=lambda x: _obs_order.get(_norm(x[1]), 99))
            _out = [b for b, _ in _obs_br]
            for _i, _b in enumerate(_out):
                _b["tier"] = "king" if _i == 0 else "key"
            for _b in _other_br:
                _b["tier"] = "backup"
            return _out + _other_br

        _order = {_norm(n): i for i, n in enumerate(_names)}
        _alias_items: list[tuple[str, str]] = []  # (归一化别名, 主线名)，按主线顺序
        try:
            from .daily_report import SECTOR_BOARD_ALIASES as _SBA
            for _n in _names:
                for _a in (_SBA.get(_n) or [_n]):
                    if _a:
                        _alias_items.append((_norm(_a), _n))
        except Exception:
            _alias_items = [(_norm(n), n) for n in _names]

        def _ml_of(_bn: str) -> str | None:
            if _bn in _order:
                return _bn
            # 别名匹配（板块名包含别名，如 CPO概念 含 CPO / 光通信模块 含 光通信），别名≥2 字防误伤
            for _a, _ml in _alias_items:
                if len(_a) >= 2 and _a in _bn:
                    return _ml
            return None

        _used: set[str] = set()
        _main_br: list[tuple[dict[str, Any], str]] = []
        _other_br: list[dict[str, Any]] = []
        _obs_set = {_norm(n) for n in _obs}
        for b in board_rank:
            if not isinstance(b, dict):
                continue
            _bn = _norm(b.get("name"))
            _ml = _ml_of(_bn)
            if _ml and _ml not in _used:
                _used.add(_ml)
                b["mainline"] = True
                b["observe"] = False
                b["ml_name"] = _ml
                _main_br.append((b, _ml))
            else:
                b["mainline"] = False
                b.pop("ml_name", None)
                b.pop("ml_why", None)
                b.pop("ml_src", None)
                if _bn in _obs_set or any(len(o) >= 2 and (o in _bn or _bn in o) for o in _obs_set):
                    b["observe"] = True
                _other_br.append(b)
        if not _main_br:
            return board_rank
        _main_br.sort(key=lambda x: _order.get(_norm(x[1]), 99))
        _out = [b for b, _ in _main_br]
        for _i, _b in enumerate(_out):
            _b["tier"] = "king" if _i == 0 else "key"
        # 有主线时：观察板块紧随主线（key），其余 backup
        _obs_br2: list[dict[str, Any]] = []
        _bak_br: list[dict[str, Any]] = []
        for _b in _other_br:
            if _b.get("observe"):
                _b["tier"] = "key"
                _obs_br2.append(_b)
            else:
                _b["tier"] = "backup"
                _bak_br.append(_b)
        return _out + _obs_br2 + _bak_br
    except Exception:
        return board_rank


def _attach_ml_why(rank: list[dict[str, Any]], dml_names: list[str], dml_info: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """板块榜主线条目透传主线判定小字（P1-4）：king/key 补 ml_src(new/cont) + ml_why，
    数据复用 _dml_info（mainline_judgment 已产出），零上游成本；非主线 backup 保持现状。"""
    try:
        if not rank or not dml_names:
            return rank
        prev: set[str] = set()
        try:
            from .daily_report import _prev_mainlines
            _p = _prev_mainlines() or {}
            prev = {str(x) for x in (_p.get("mainlines") or [])}
        except Exception:
            pass
        for b in rank:
            if b.get("tier") not in ("king", "key"):
                continue
            ml = str(b.get("ml_name") or "")
            if not ml:
                nm0 = str(b.get("name") or "").replace(" ", "")
                for _n in dml_names:
                    if nm0 == str(_n).replace(" ", ""):
                        ml = str(_n)
                        break
            if not ml:
                # 别名匹配（如 kc 榜「通信技术」→ 主线「通信光模块CPO」）
                try:
                    from .daily_report import SECTOR_BOARD_ALIASES as _SBA
                    for _n in dml_names:
                        for _a in (_SBA.get(str(_n)) or []):
                            if _a and nm0 == str(_a).replace(" ", ""):
                                ml = str(_n)
                                break
                        if ml:
                            break
                except Exception:
                    pass
            if not ml:
                continue
            is_new = ml not in prev
            b["ml_src"] = "new" if is_new else "cont"
            it = dml_info.get(ml) or {}
            # 补缺资金/涨幅：归档注入主线常 f62=0，先用复盘判定里的 fund_t/fund5/avg_up 填上
            try:
                if abs(float(b.get("f62") or 0)) < 1e5 and it.get("fund_t") is not None:
                    b["f62"] = float(it.get("fund_t") or 0)
                if abs(float(b.get("f164") or 0)) < 1e5 and it.get("fund5") is not None:
                    b["f164"] = float(it.get("fund5") or 0)
                if b.get("pct") is None and it.get("avg_up") is not None:
                    b["pct"] = round(float(it.get("avg_up") or 0), 2)
                if b.get("p5") is None and it.get("chg5_med") is not None:
                    b["p5"] = float(it.get("chg5_med") or 0)
            except Exception:
                pass
            top5 = it.get("top5")
            nzt = int(it.get("n_zt") or 0)
            aup = it.get("avg_up")
            ft = it.get("fund_t")
            if is_new:
                _parts = []
                if top5 is not None:
                    _parts.append(f"top5 {top5}")
                if nzt:
                    _parts.append(f"{nzt}涨停")
                if aup is not None:
                    _parts.append(f"今日 {aup:+.2f}%")
                b["ml_why"] = "新晋主线 · " + " / ".join(_parts) if _parts else "新晋主线"
            else:
                if ft is not None and ft > 0:
                    b["ml_why"] = "延续主线 · 资金主攻"
                elif top5 is not None:
                    b["ml_why"] = f"延续主线 · top5 {top5}"
                else:
                    b["ml_why"] = "延续主线"
        return rank
    except Exception:
        return rank


_COLUMN_VIEW_MARKETS = frozenset({"macd", "low10", "tight", "pb", "mlpb", "breakout", "leader"})


def _apply_stale_fallback(result: dict[str, Any], market: str = "bj", column: str = "") -> dict[str, Any]:
    """今日无合格标的时，回退展示上一交易日结果并打 stale 标记。

    专栏（tight/macd/low10 等）须按栏目口径判空/回退，禁止把 all 市场主推（含北证/MACD）原样透传。
    不原地修改 result：先浅拷贝再合并，避免污染 _SCAN_CACHE / 磁盘缓存。
    """
    result = dict(result)
    result.pop("_bad", None)
    col = str(column or "").strip().lower()

    def _view(r: dict[str, Any]) -> dict[str, Any]:
        if col in _COLUMN_VIEW_MARKETS:
            return apply_column_view(col, r)
        return r

    def _has_picks(r: dict[str, Any]) -> bool:
        v = _view(r)
        if col == "macd":
            return bool(v.get("macd_reds") or v.get("picks"))
        return bool(v.get("picks"))

    if _has_picks(result):
        out = _view(result)
        out.pop("_bad", None)
        return _reattach_ths(out)

    stale = None
    if col in _COLUMN_VIEW_MARKETS:
        stale = _latest_history(col)
    if not stale:
        stale = _latest_history(market)
    if not stale:
        out = _view(result)
        out.pop("_bad", None)
        return _reattach_ths(out)

    out = dict(result)
    out["stale"] = True
    out["stale_from"] = stale.get("asof") or stale.get("date") or ""
    out["stale_scan_date"] = stale.get("date") or ""
    merged = dict(stale)
    # 保留归档自身的 date/asof（供专栏回放对齐 K 线日）；今日扫描字段仅作 meta/透明度
    for _k in ("cached", "total", "scanned", "fine", "hard_rejected",
               "generated_ts", "elapsed_s", "market", "regime", "style", "meta"):
        if _k in out and out.get(_k) is not None:
            merged[_k] = out[_k]
    # 展示用：主结果日期仍标「今日」，真实数据日写在 stale_from
    if result.get("date"):
        merged["date"] = result.get("date")
    if not merged.get("asof"):
        merged["asof"] = out["stale_from"]
    if not merged.get("mainlines"):
        try:
            _dml0 = _daily_mainlines()
            _dml0_src = (_dml0 or {}).get("src") or ""
            _dml0_names = (_dml0 or {}).get("names") or []
        except Exception:
            _dml0_src, _dml0_names = "", []
        if not (_dml0_names or _dml0_src in ("archive", "recalc")):
            merged["mainlines"] = stale.get("mainlines") or []
    merged["stale"] = True
    merged["stale_from"] = out["stale_from"]
    merged["stale_scan_date"] = out["stale_scan_date"]
    if out.get("intraday"):
        merged["intraday"] = True
    if out.get("today_missing"):
        merged["today_missing"] = True
    _tf: dict[str, Any] = {"fine": int(result.get("fine") or 0), "hard": int(result.get("hard_rejected") or 0)}
    _top = (result.get("runners") or [])[:1]
    if _top:
        _t0 = _top[0]
        _tf["top"] = {
            "code": _t0.get("code"), "name": _t0.get("name"),
            "final": _t0.get("final"), "score": _t0.get("score"),
            "risks": _t0.get("risks") or [],
        }
    merged["today_fine"] = _tf
    # 专栏回放必须用归档 asof；临时把 asof 指回归档日再 view
    _asof_keep = stale.get("asof") or stale.get("date") or out["stale_from"]
    if _asof_keep:
        merged["asof"] = _asof_keep
    viewed = _view(merged)
    viewed["stale"] = True
    viewed["stale_from"] = out["stale_from"]
    viewed["stale_scan_date"] = out["stale_scan_date"]
    viewed["today_fine"] = _tf
    if result.get("date"):
        viewed["date"] = result.get("date")
    if out.get("intraday"):
        viewed["intraday"] = True
    if out.get("today_missing"):
        viewed["today_missing"] = True
    return _reattach_ths(viewed)


def _num(v: Any, d: float = 0.0) -> float:
    try:
        n = float(v)
        return n if math.isfinite(n) else d
    except Exception:
        return d


# ---------------- P0-1 情绪周期 Gate + P0-2 涨停质量分级（GPT5 批1） ----------------
# 数据：东财 push2ex 涨停池/跌停池/炸板池（date 参数化、进程内+磁盘日缓存共享，六栏目只算一次）；
# 温度 = 近 20 日分位加权（涨停 25% / 1-跌停 20% / 1-炸板率 20% / 连板高度 20% / 晋级率 15%），
# <30 → risk_off：全部栏目 scoreMin+5、候选池减半，回踩企稳额外 +3；历史不足 10 日不启用硬 Gate。
_EMO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "bj_emotion")
_EMO_HISTORY_PATH = os.path.join(_EMO_DIR, "snapshots.json")
_EMO_POOL_CACHE: dict[str, dict[str, Any]] = {}   # date8 -> 当日涨停/跌停/炸板池
_EMO_SNAP_CACHE: dict[str, dict[str, Any]] = {}   # date8 -> 当日情绪快照
_EMO_CURRENT: dict[str, Any] = {}                 # 最近一次快照（条目级字段透传）
_EMO_UT = "7eea3edcaed734bea9cbfc24409ed989"


def _emo_atomic_write(path: str, obj: Any) -> None:
    """原子写缓存：临时文件后 os.replace；损坏记录 warning 不阻断接口。"""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception:
        pass


def _emo_load_history() -> dict[str, Any]:
    try:
        if os.path.exists(_EMO_HISTORY_PATH):
            h = json.load(open(_EMO_HISTORY_PATH, encoding="utf-8"))
            if isinstance(h, dict) and isinstance(h.get("days"), list):
                return h
    except Exception:
        pass
    return {"days": []}


async def _emo_fetch_pool(date8: str, api: str) -> list[dict[str, Any]]:
    """东财 push2ex 涨停池/跌停池/炸板池（date 参数化，支持历史日期回看）。"""
    try:
        await _EM_CLIST_GATE.acquire()
        cli = await _get_em_clist_client()
        r = await cli.get("https://push2ex.eastmoney.com/%s" % api, params={
            "ut": _EMO_UT, "dpt": "wz.ztzt", "Pageindex": 0,
            "pagesize": 500, "sort": "fbt:asc", "date": date8,
        })
        if r.status_code != 200:
            return []
        j = r.json()
        return list((j.get("data") or {}).get("pool") or [])
    except Exception:
        return []


async def _emo_pools(date8: str) -> dict[str, Any]:
    """当日全市场涨停/跌停/炸板池统计（日缓存共享；zttj.days=连板数、zbc=炸板次数）。"""
    if date8 in _EMO_POOL_CACHE:
        return _EMO_POOL_CACHE[date8]
    fp = os.path.join(_EMO_DIR, "pools_%s.json" % date8)
    if os.path.exists(fp):
        try:
            obj = json.load(open(fp, encoding="utf-8"))
            if isinstance(obj, dict):
                _EMO_POOL_CACHE[date8] = obj
                return obj
        except Exception:
            pass
    pools: dict[str, Any] = {"limit_up": 0, "limit_down": 0, "zb": 0,
                             "zt_codes": [], "fb_codes": [], "max_lianban": 0,
                             "src": "东财涨停/跌停/炸板池"}
    try:
        zt, dt, zb = await asyncio.gather(
            _emo_fetch_pool(date8, "getTopicZTPool"),
            _emo_fetch_pool(date8, "getTopicDTPool"),
            _emo_fetch_pool(date8, "getTopicZBPool"),
        )
    except Exception:
        zt = dt = zb = []
    pools["limit_up"] = len(zt)
    pools["limit_down"] = len(dt)
    pools["zb"] = len(zb)
    max_lb = 0
    for x in zt:
        code = str(x.get("c") or "")
        zttj = x.get("zttj")
        days = 0
        if isinstance(zttj, dict):
            try:
                days = int(zttj.get("days") or 0)
            except Exception:
                days = 0
        if days < 1:
            try:
                days = int(x.get("lbc") or 0)
            except Exception:
                days = 0
        if days == 1:
            pools["fb_codes"].append(code)
        if days > max_lb:
            max_lb = days
    pools["max_lianban"] = max_lb
    pools["zt_codes"] = [str(x.get("c") or "") for x in zt]
    _EMO_POOL_CACHE[date8] = pools
    _emo_atomic_write(fp, pools)
    return pools


def _prev_date8(d8: str) -> str:
    """上一自然交易日（跳过周末；节假日历史由历史快照就近兜底）。"""
    try:
        d = datetime.date(int(d8[:4]), int(d8[4:6]), int(d8[6:8])) - datetime.timedelta(days=1)
        while d.weekday() >= 5:
            d -= datetime.timedelta(days=1)
        return d.strftime("%Y%m%d")
    except Exception:
        return d8


def _pct_rank(vals: list[float], v: float) -> float:
    """分位数（0~1）：近 20 日窗口内 v 的百分位。"""
    n = len(vals)
    if not n:
        return 0.5
    less = sum(1 for x in vals if x < v)
    eq = sum(1 for x in vals if x == v)
    return (less + 0.5 * eq) / n


async def compute_emotion_snapshot(trade_date8: str | None = None) -> dict[str, Any]:
    """情绪周期快照：温度 0-100（近 20 日分位加权），<30 → risk_off 启用 Gate。

    历史 <10 日 confidence=low、温度默认 50，不启用硬 Gate（禁止伪造历史）；
    盘中（未收盘）与数据缺失（非交易日）不启用 Gate、不写入历史快照。
    响应为兼容增补字段（meta.emotion + 条目 emotionRegime/emotionNote），不改原字段。
    """
    global _EMO_CURRENT
    d8 = trade_date8 or time.strftime("%Y%m%d")
    if d8 in _EMO_SNAP_CACHE:
        _EMO_CURRENT = _EMO_SNAP_CACHE[d8]
        return _EMO_CURRENT
    pools = await _emo_pools(d8)
    hist = _emo_load_history()
    days: list[dict[str, Any]] = [x for x in (hist.get("days") or []) if isinstance(x, dict)]
    prev_day = None
    for x in sorted(days, key=lambda y: str(y.get("date") or ""), reverse=True):
        if str(x.get("date") or "") < d8:
            prev_day = x
            break
    n_zt = int(pools.get("limit_up") or 0)
    n_dt = int(pools.get("limit_down") or 0)
    n_zb = int(pools.get("zb") or 0)
    zb_rate = n_zb / (n_zt + n_zb) if (n_zt + n_zb) else 0.0
    max_lb = int(pools.get("max_lianban") or 0)
    # 首板晋级率：昨日首板 ∩ 今日涨停 / 昨日首板数
    fb_prev = (prev_day or {}).get("fb_codes")
    if fb_prev is None:
        try:
            fb_prev = (await _emo_pools(_prev_date8(d8))).get("fb_codes") or []
        except Exception:
            fb_prev = []
    fb_cnt = len(fb_prev) if isinstance(fb_prev, list) else 0
    promote = 0
    if fb_cnt:
        _zt_set = set(pools.get("zt_codes") or [])
        promote = sum(1 for c in fb_prev if c in _zt_set)
    promote_rate = promote / fb_cnt if fb_cnt else 0.0
    intraday = bool(d8 == time.strftime("%Y%m%d") and not _market_closed())
    valid = bool((n_zt + n_zb) > 0)
    prior = days[-20:]
    if len(prior) >= 10 and valid:
        pu = _pct_rank([float(x.get("limit_up") or 0) for x in prior], n_zt)
        pd_ = _pct_rank([float(x.get("limit_down") or 0) for x in prior], n_dt)
        pzb = _pct_rank([float(x.get("zb_rate") or 0) for x in prior], zb_rate)
        plb = _pct_rank([float(x.get("max_lianban") or 0) for x in prior], max_lb)
        pjg = _pct_rank([float(x.get("promote_rate") or 0) for x in prior], promote_rate)
        temperature = int(max(0, min(100, round(25 * pu + 20 * (1 - pd_) + 20 * (1 - pzb)
                                               + 20 * plb + 15 * pjg))))
        confidence = "high"
    else:
        temperature = 50
        confidence = "low"
    regime = "risk_off" if (confidence == "high" and not intraday and valid and temperature < 30) else "normal"
    gate_active = bool(regime == "risk_off")
    if confidence == "low":
        note = "情绪历史样本不足10日，Gate未启用（温度默认50）"
    elif intraday:
        note = "盘中数据未定型，情绪Gate未启用"
    elif not valid:
        note = "非交易日/情绪数据缺失，Gate未启用"
    elif regime == "risk_off":
        note = "情绪偏冷(温度%d)：全部栏目门槛+5、候选池减半；回踩企稳额外+3" % temperature
    else:
        note = "情绪中性(温度%d)" % temperature
    snap: dict[str, Any] = {
        "date": d8, "temperature": temperature, "regime": regime, "confidence": confidence,
        "gate_active": gate_active, "intraday": intraday, "note": note,
        "limit_up": n_zt, "limit_down": n_dt, "zb": n_zb, "zb_rate": round(zb_rate, 4),
        "max_lianban": max_lb, "fb": fb_cnt, "promote": promote,
        "promote_rate": round(promote_rate, 4), "src": pools.get("src"),
    }
    if valid and not intraday:
        entry: dict[str, Any] = {
            "date": d8, "limit_up": n_zt, "limit_down": n_dt, "zb": n_zb,
            "zb_rate": zb_rate, "max_lianban": max_lb, "fb": fb_cnt,
            "promote": promote, "promote_rate": promote_rate,
            "fb_codes": pools.get("fb_codes") or [],
        }
        days = [x for x in days if str(x.get("date") or "") != d8] + [entry]
        days = sorted(days, key=lambda x: str(x.get("date") or ""))[-60:]
        hist["days"] = days
        _emo_atomic_write(_EMO_HISTORY_PATH, hist)
    _EMO_SNAP_CACHE[d8] = snap
    _EMO_CURRENT = snap
    return snap


def apply_emotion_gate(cfg: dict[str, Any], emotion: dict[str, Any], column: str = "") -> dict[str, Any] | None:
    """情绪 Gate：risk_off 时所有栏目 scoreMin+5、候选数上限减半；首板系/龙头系专栏额外 +3。
    返回调整后的 cfg 副本；未触发返回 None（调用方保持原 cfg）。"""
    if not (emotion and emotion.get("gate_active") and emotion.get("regime") == "risk_off"):
        return None
    adj = dict(cfg)
    adj["scoreMin"] = float(adj.get("scoreMin") or 0) + 5.0
    if column in ("pb", "mlpb", "breakout", "leader"):
        adj["scoreMin"] += 3.0
    adj["cap"] = max(20, int(adj.get("cap") or 60) // 2)
    return adj


# 涨停质量分级的启动证据权重修正（换手板 +4 / T字板 +1 / 一字板 -3 / 烂板 -5）
_LQ_DELTA = {"turnover_board": 4, "t_board": 1, "one_word": -3, "rotten_board": -5}


def classify_limit_quality(o_: float, h_: float, l_: float, c_: float,
                           prev_close: float, limit_pct: float, turnover: float) -> dict[str, Any]:
    """涨停质量分级（无逐笔开板/封单字段，OHLC+换手代理，置信度 medium/low，不虚构）。

    one_word 一字板（开盘最低均近涨停、换手<3%，不可交易强度）/ t_board T字板 /
    turnover_board 换手板（封板且换手5-15%）/ rotten_board 烂板（触板未封或高换手/长上影弱封）。
    """
    lp = float(prev_close) * (1 + float(limit_pct) / 100.0)
    near = 0.995
    open_near = bool(o_ >= lp * near)
    close_near = bool(c_ >= lp * near)
    high_near = bool(h_ >= lp * near)
    low_near = bool(l_ >= lp * near)
    turn = float(turnover or 0)
    span = (h_ - l_) or 1.0
    upper_shadow = (h_ - c_) / span
    if close_near:
        if open_near and low_near and turn < 3.0:
            q, score, trad, conf = "one_word", 35, "差", "medium"
        elif open_near and not low_near:
            q, score, trad, conf = "t_board", 65, "中", "low"
        elif 5.0 <= turn <= 15.0:
            q, score, trad, conf = "turnover_board", 80, "好", "medium"
        elif turn > 15.0 or upper_shadow > 0.3:
            q, score, trad, conf = "rotten_board", 30, "差", "medium"
        else:
            q, score, trad, conf = "normal", 55, "中", "medium"
    elif high_near:
        q, score, trad, conf = "rotten_board", 30, "差", "medium"
    else:
        q, score, trad, conf = "unknown", 45, "未知", "low"
    return {"limitQuality": q, "limitQualityScore": score, "tradability": trad,
            "qualityConfidence": conf, "note": "OHLC+换手代理（无逐笔）"}


# ---------------- P0-3/P0-4 ATR 自适应 + 回踩细分（GPT5 批2） ----------------
def calc_atr_profile(o: list[float], h: list[float], l: list[float], c: list[float],
                     v: list[float], period: int = 14, lookback: int = 60) -> dict[str, Any]:
    """ATR14 + 近 lookback 日 atrPct 分位 + 波动档（低<35% / 中 35-75% / 高>75%）
    + 量能 20 日分位 vol_rank20（含今日）。
    回撤容忍 ATR 倍数：低 0.5 / 中 0.75 / 高 1.0；数据不足或 ATR 异常时 fallback（mult=0.75、rank=0.5）。
    """
    n = len(c)
    trs: list[float] = []
    for i in range(1, n):
        trs.append(max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])))
    if len(trs) < period or not any(x > 0 for x in trs[-period:]):
        return {"atr": 0.0, "atr_pct": 0.0, "atr_pct_rank": 0.5, "vol_regime": "med",
                "atr_tol_mult": 0.75, "atr_tol": 0.0, "vol_rank20": 0.5, "fallback": True}
    atr_now = sum(trs[-period:]) / period
    cl = c[-1]
    atr_pct_now = atr_now / cl * 100 if cl else 0.0
    atr_pcts: list[float] = []
    for i in range(max(period, n - lookback), n):
        seg = trs[i - period: i]
        if len(seg) < period:
            continue
        _a = sum(seg) / period
        _base = c[i - 1] if i >= 1 else c[i]
        atr_pcts.append(_a / _base * 100 if _base else 0.0)
    atr_pct_rank = _pct_rank(atr_pcts, atr_pct_now) if atr_pcts else 0.5
    if atr_pct_rank < 0.35:
        vol_regime, mult = "low", 0.5
    elif atr_pct_rank > 0.75:
        vol_regime, mult = "high", 1.0
    else:
        vol_regime, mult = "med", 0.75
    atr_tol = atr_now * mult
    win = v[-20:] if n >= 20 else list(v)
    vol_rank20 = _pct_rank([float(x) for x in win], float(v[-1])) if win else 0.5
    return {"atr": atr_now, "atr_pct": round(atr_pct_now, 3), "atr_pct_rank": round(atr_pct_rank, 3),
            "vol_regime": vol_regime, "atr_tol_mult": mult, "atr_tol": atr_tol,
            "vol_rank20": round(vol_rank20, 3), "fallback": False}


def classify_pullback(o: list[float], h: list[float], l: list[float], c: list[float],
                      v: list[float], event_index: int, atr_tol: float,
                      atr_pct: float) -> dict[str, Any]:
    """回踩形态细分（基于涨停/异动日 event_index 之后到当前的回踩）。

    pullbackType: shallow_1d（1日浅回踩）/ contract_2_3d（2-3日缩量回踩）/
    deep_4_8d（4-8日深回踩或横盘）/ broken_rebound（破板日低点后反抽）/ none。
    回踩超 10% 或有效跌破板日低点 → pullbackRisk 标记（供 analyze 强制扣分）。
    """
    last = len(c) - 1
    if event_index is None or event_index < 0 or event_index >= last:
        return {"pullbackType": "none", "pullbackDays": 0, "pullbackDepthAtr": 0.0,
                "pullbackDepthPct": 0.0, "pullbackRisk": "none"}
    _blo = l[event_index]
    _bhi = h[event_index]
    _plat_lo = min(l[_j] for _j in range(event_index + 1, last + 1))
    depth_pct = (_bhi - _plat_lo) / _bhi * 100 if _bhi else 0.0
    depth_atr = (_bhi - _plat_lo) / atr_tol if atr_tol > 0 else depth_pct / 3.0
    days = last - event_index
    broken = bool(_plat_lo < _blo and (c[last] < _blo or _plat_lo < _blo - atr_tol))
    if broken:
        ptype, risk = "broken_rebound", "破板日低点后反抽"
    elif days <= 1 and depth_pct <= 4:
        ptype, risk = "shallow_1d", "1日浅回踩"
    elif 2 <= days <= 3 and depth_pct <= 8:
        ptype, risk = "contract_2_3d", "2-3日缩量回踩"
    elif 4 <= days <= 8:
        ptype, risk = "deep_4_8d", "4-8日深回踩/横盘"
    else:
        ptype, risk = "none", "none"
    if depth_pct > 10:
        risk = "回踩超10%"
    return {"pullbackType": ptype, "pullbackDays": days, "pullbackDepthAtr": round(depth_atr, 2),
            "pullbackDepthPct": round(depth_pct, 1), "pullbackRisk": risk}


def score_steady_up(o: list[float], h: list[float], l: list[float], c: list[float],
                    v: list[float], last: int) -> dict[str, Any]:
    """稳步向上独立评分（0-100）：20日趋势斜率 + 均线多头发散 + MA10/20支撑成功次数 + 量能温和递增。

    供 analyze 输出 trendScore 与 steadyUp 模式标签——情绪平淡期/主线外，趋势股更稳；
    与回踩/首板类并列，作为「启动证据」轴之一参与评分（受最强两个证据封顶约束）。
    """
    n = len(c)
    if n < 30:
        return {"trendScore": 0, "steadyUp": False,
                "parts": {"slope": 0.0, "ma": 0.0, "support": 0.0, "vol": 0.0}}
    ma5 = _ma_at(c, 5, last)
    ma10 = _ma_at(c, 10, last)
    ma20 = _ma_at(c, 20, last)
    ma60 = _ma_at(c, 60, last)
    ma20_3 = _ma_at(c, 20, last - 3)
    parts: dict[str, float] = {"slope": 0.0, "ma": 0.0, "support": 0.0, "vol": 0.0}
    # ① 20日线性回归斜率（%/日）
    seg = c[last - 19: last + 1]
    xs = list(range(20))
    xm = sum(xs) / 20
    ym = sum(seg) / 20
    denom = sum((x - xm) ** 2 for x in xs)
    slope = sum((x - xm) * (seg[i] - ym) for i, x in enumerate(xs)) / denom if denom else 0.0
    slope_pct = slope / ym * 100 if ym else 0.0
    if slope_pct > 0.15:
        parts["slope"] = 30.0
    elif slope_pct > 0.05:
        parts["slope"] = 20.0
    elif slope_pct > 0:
        parts["slope"] = 10.0
    # ② 均线多头发散（0-30）
    m = 0.0
    if ma5 > ma10 > ma20 > ma60:
        m += 12
    elif ma5 > ma10 > ma20:
        m += 8
    spread = (ma5 - ma20) / ma20 * 100 if ma20 and ma20 == ma20 else 0.0
    if spread > 1.0:
        m += 6
    elif spread > 0.5:
        m += 4
    elif spread > 0:
        m += 2
    if ma20 > ma20_3:
        m += 4
    parts["ma"] = min(30.0, m)
    # ③ MA10/MA20 支撑成功次数（0-20）：近20日回踩均线且收盘站回
    hits = 0
    for i in range(last - 19, last + 1):
        _ma10i = _ma_at(c, 10, i)
        _ma20i = _ma_at(c, 20, i)
        if _ma10i == _ma10i and l[i] <= _ma10i * 1.01 and c[i] >= _ma10i:
            hits += 1
        elif _ma20i == _ma20i and l[i] <= _ma20i * 1.01 and c[i] >= _ma20i:
            hits += 1
    parts["support"] = min(20.0, hits * 4.0)
    # ④ 量能温和递增（0-20）
    v5 = sum(v[last - 4: last + 1]) / 5
    v20 = sum(v[last - 19: last + 1]) / 20
    r = v5 / v20 if v20 > 0 else 0.0
    q = 0.0
    if 1.0 <= r <= 1.8:
        q += 10
    elif 1.8 < r <= 2.5:
        q += 6
    ups = sum(1 for i in range(last - 9, last + 1) if c[i] >= o[i])
    if ups >= 7:
        q += 6
    elif ups >= 5:
        q += 3
    if all(c[last - 4 + i] >= c[last - 5 + i] for i in range(1, 5)):
        q += 4
    parts["vol"] = min(20.0, q)
    total = int(round(parts["slope"] + parts["ma"] + parts["support"] + parts["vol"]))
    return {"trendScore": max(0, min(100, total)), "steadyUp": bool(total >= 58), "parts": parts}


def calc_path_activity(
    c: list[float], o: list[float], ma5: float, ma10: float, ma20: float, ma20_3: float,
    ma_bull3: bool, last: int, chg5: float, amp20: float, vol_shrink: bool,
    vol_health: int, vol_ratio: float, bias_over: bool, new_high_weak: bool,
    at_high_weak: bool, pos: float, turnover: float, patterns: dict[str, Any],
    wk: dict[str, Any] | None,
) -> dict[str, Any]:
    """右侧上涨途中 × 股性活跃 × 下坡否决（口语算法化）。

    downSlope：下坡途中（精筛/主推一票否决）
    pathOk：上涨途中（非下坡 + 均线上拐或事件站稳）
    midUpOk：未过热追高（途中阶段）
    activityScore / activeOk：股性活跃（振幅/换手/量能结构）
    """
    cl = c[last] if last >= 0 else 0.0
    # 20 日收盘线性斜率（%/日）
    slope_pct = 0.0
    if last >= 19:
        seg = c[last - 19: last + 1]
        xs = list(range(20))
        xm = sum(xs) / 20.0
        ym = sum(seg) / 20.0
        denom = sum((x - xm) ** 2 for x in xs)
        if denom and ym:
            slope = sum((x - xm) * (seg[i] - ym) for i, x in enumerate(xs)) / denom
            slope_pct = slope / ym * 100.0
    bear_ma = bool(ma5 < ma10 < ma20)
    ma20_down = bool(cl < ma20 and not (ma20 > ma20_3))
    down_days = 0
    if last >= 4:
        down_days = sum(1 for i in range(last - 4, last + 1) if c[i] < o[i])
    week_weak = bool(
        wk and int(wk.get("weekBars") or 0) >= 6
        and float(wk.get("wClose") or 0) < float(wk.get("wMa10") or 0)
        and not wk.get("weekMaOk")
    )
    flags = 0
    if ma20_down:
        flags += 1
    if slope_pct < -0.02:
        flags += 1
    if bear_ma:
        flags += 1
    if chg5 < 0 and down_days >= 4:
        flags += 1
    if week_weak:
        flags += 1
    if vol_shrink and chg5 < 0:
        flags += 1
    down_slope = flags >= 2

    event_stand = bool(
        patterns.get("pullback2") or patterns.get("ztPullback") or patterns.get("firstBoardRight")
        or patterns.get("firstWeek") or patterns.get("surgeStart") or patterns.get("washOut")
        or patterns.get("macdFirstRed") or patterns.get("strongMom") or patterns.get("eventPullback")
        or patterns.get("pb45") or patterns.get("surgePullback")
    )
    path_ok = (not down_slope) and bool(ma20 > ma20_3 or ma_bull3 or event_stand)
    mid_up_ok = bool(
        (not down_slope) and (not bias_over) and (not new_high_weak) and (not at_high_weak)
        and float(pos or 0) <= 0.70
    )

    # 股性活跃分（0-100）
    act = 0.0
    if 8 <= float(amp20 or 0) <= 28:
        act += 28
    elif 5 <= float(amp20 or 0) < 8 or 28 < float(amp20 or 0) <= 35:
        act += 14
    elif float(amp20 or 0) > 35:
        act += 4
    to = float(turnover or 0)
    if 3 <= to <= 15:
        act += 22
    elif 1.5 <= to < 3 or 15 < to <= 22:
        act += 10
    if vol_health == 1:
        act += 18
    elif vol_health == 0 and not vol_shrink:
        act += 6
    if float(vol_ratio or 0) >= 1.5:
        act += 12
    elif float(vol_ratio or 0) >= 1.1:
        act += 7
    if patterns.get("strongMom"):
        act += 12
    elif event_stand:
        act += 6
    if vol_shrink:
        act -= 15
    activity_score = int(max(0, min(100, round(act))))
    active_ok = bool(activity_score >= 48 and not vol_shrink and float(amp20 or 0) >= 5)
    return {
        "downSlope": down_slope,
        "pathOk": path_ok,
        "midUpOk": mid_up_ok,
        "activityScore": activity_score,
        "activeOk": active_ok,
        "slopePct20": round(slope_pct, 4),
        "pathFlags": flags,
    }


def _path_gate(item: dict[str, Any], *, require_active: bool = False) -> bool:
    """栏目/主推通用门：禁下坡；可选要求股性活跃。兼容 A 内嵌与扁平字段。"""
    a = item.get("A") if isinstance(item.get("A"), dict) else None
    src = a if a is not None else item
    if src.get("downSlope"):
        return False
    # 旧缓存无字段时不误杀
    if "pathOk" in src and not src.get("pathOk"):
        return False
    if require_active and "activeOk" in src and not src.get("activeOk"):
        # 事件形态可豁免股性硬门（回踩/首红本身已说明有弹性）
        p = src.get("patterns") or {}
        if not (p.get("pullback2") or p.get("ztPullback") or p.get("firstBoardRight")
                or p.get("firstWeek") or p.get("macdFirstRed") or p.get("strongMom")
                or p.get("washOut") or p.get("eventPullback") or p.get("pb45")):
            return False
    return True


# ---------------- 数据源 ----------------

async def _em_get_json(path: str, params: dict[str, Any]) -> dict[str, Any] | None:
    last_err: Exception | None = None
    await _EM_CLIST_GATE.acquire()
    cli = await _get_em_clist_client()
    for host in EM_HOSTS:
        try:
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
    """东财北证全市场列表（fid=f6 按成交额排序；单页最多 100 行，并发翻页取全量）。"""
    sem = asyncio.Semaphore(5)

    async def _page(pn: int) -> dict[str, Any]:
        async with sem:
            params = {
                "pn": pn, "pz": 100, "po": 1, "np": 1, "fltt": 2, "invt": 2,
                "fid": "f6", "fs": "m:0+t:81+s:2048", "fields": EM_LIST_FIELDS,
            }
            try:
                return await _em_get_json("/api/qt/clist/get", params) or {}
            except Exception:
                return {}

    pages = await asyncio.gather(*[_page(pn) for pn in range(1, 8)], return_exceptions=True)
    total = 0
    rows: list[dict[str, Any]] = []
    for j in pages:
        if not isinstance(j, dict):
            continue
        data = j.get("data") or {}
        if not total:
            total = int(_num(data.get("total"), 0))
        diff = data.get("diff") or []
        if not isinstance(diff, list):
            continue
        rows.extend(diff)
        if total and len(rows) >= total:
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


_BUCKET_ALIAS_REV: dict[str, str] | None = None


def _bucket_alias_rev() -> dict[str, str]:
    """主线别名反向表（惰性构建，零上游）：归一别名 → 主线规范名。"""
    global _BUCKET_ALIAS_REV
    if _BUCKET_ALIAS_REV is None:
        rev: dict[str, str] = {}
        try:
            from .daily_report import SECTOR_BOARD_ALIASES as _SBA
            for _ml, _als in (_SBA or {}).items():
                for _a in (_als or []):
                    if _a:
                        rev.setdefault(re.sub(r"\s+", "", str(_a)), _ml)
        except Exception:
            pass
        _BUCKET_ALIAS_REV = rev
    return _BUCKET_ALIAS_REV


def _bucket_norm(name: str) -> str:
    """板块桶名归一化（P0-2）：去空格/业务性后缀，按主线别名反向表归一到规范名（未知保留原文）。
    例：煤炭开采/焦煤/煤化工 → 煤炭；CPO概念 → 通信光模块CPO；未知名仅去后缀。
    """
    n = re.sub(r"\s+", "", str(name or ""))
    if not n:
        return n
    n2 = re.sub(r"(板块|概念|行业|指数|开采加工|开采|采选|加工|化工|制品|设备|材料|及器件|及材料|及服务|产业链)$", "", n)
    if len(n2) < 2:
        n2 = n  # 单字残留（如 煤化工→煤）回退原文，避免「煤」这种垃圾桶
    if n2 in _bucket_alias_rev():
        return _bucket_alias_rev()[n2]
    return n2 or n


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




def _market_ok(code6: str, market: str) -> bool:
    """按市场过滤 A 股代码：hs=沪深主板(60/00)、kc=科创(创业板30+科创板688)、bj/bj_all=北证。"""
    code6 = str(code6 or "").strip()
    if market == "hs":
        return code6.startswith(("60", "00"))
    if market == "kc":
        return code6.startswith(("30", "688"))
    if market in ("bj", "bj_all"):
        return code6.startswith(("43", "83", "87", "88", "92"))
    return True  # all（兼容旧入口）

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
    # 当日涨幅超过涨停上限的异常暴涨（如无涨跌停限制新股）才排除；涨停当天纳入候选
    if _num(row.get("f3")) > _zt_threshold(code) + 1.0:
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
    concepts: list[str] = []
    for _c in re.split(r"[;,，、]", str(row.get("f128") or "")):
        _c = _c.strip()
        if _c and _c != "-" and _c not in concepts:
            concepts.append(_c)
    return {
        "code": code, "name": name,
        "price": _num(row.get("f2")), "pct": _num(row.get("f3")),
        "amount": amount, "mcap": mcap, "floatMcap": _num(row.get("f21")),
        "turnover": _num(row.get("f8")), "pe": _num(row.get("f9")),
        "pb": _num(row.get("f23")), "volRatio": _num(row.get("f10")),
        "fund": _num(row.get("f62")), "fundIn": _num(row.get("f62")), "ind": ind, "indCnt": 0,
        "hot": bool(hn), "hotName": hn, "kwHits": kh,
        "concepts": concepts[:12],
        "A": None, "snap": None, "final": None, "revHit": False, "revName": "",
    }


# ---------------- 全市场：板块先行两阶段抓取 ----------------

async def fetch_hot_boards_funds(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """东财行业/概念板块资金流榜（今日 f62 / 5日 f164 主力净流入）→ 热门板块池（含 BK secid）。"""
    def _abs_max(a, b):
        """取绝对值更大的资金值（保留负值：净流出也是真实数据）。"""
        a = float(a or 0); b = float(b or 0)
        if b == 0: return a
        if a == 0: return b
        return b if abs(b) > abs(a) else a

    out: dict[str, dict[str, Any]] = {}
    for fid, limit in (("f62", 40), ("f164", 16)):
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
            e["f62"] = _abs_max(e.get("f62"), _num(r.get("f62")))
            e["f164"] = _abs_max(e.get("f164"), _num(r.get("f164")))
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
    skip_terms = ("融资融券", "昨日", "富时", "标普", "MSCI", "机构重仓", "深股通", "沪股通", "中证", "转债", "ST", "预盈预增", "预亏预减", "转融券", "百元股", "风格", "成分", "样本", "微盘股", "大盘股", "中盘股", "小盘股", "低价股", "高价股", "破净", "活跃", "专精特新", "小盘成长", "中盘成长", "大盘成长", "微盘成长", "机构持仓", "基金重仓")
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
        e["f62"] = _abs_max(e.get("f62"), _num(r.get("f62")))
        e["f164"] = _abs_max(e.get("f164"), _num(r.get("f164")))
        if e.get("p5") is None:
            e["p5"] = _num(r.get("f109")) if r.get("f109") is not None else None
        if e.get("pct") is None:
            e["pct"] = _num(r.get("f3")) if r.get("f3") is not None else None
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

    sem = asyncio.Semaphore(5)

    async def _one_board(b: dict[str, Any]) -> None:
        async with sem:
            bname = str(b.get("name") or "").strip()
            bk = str(b.get("secid") or "").replace("90.", "").strip()
            if not bk or not bk.startswith("BK"):
                return
            board_rows: dict[str, dict[str, Any]] = {}
            # 路1：成交额头部（1~2 页，至 per 只）
            got = 0
            for pn in (1, 2):
                params = {
                    "pn": pn, "pz": 200, "po": 1, "np": 1, "fltt": 2, "invt": 2,
                    "fid": "f6", "fs": "b:" + bk,
                    "fields": "f12,f14,f2,f3,f6,f8,f9,f10,f20,f21,f23,f62,f100,f164,f128",
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
            # 路2：当日涨幅头部（1 页，至 per_rise 只）——捕捉底部刚异动、成交额尚未放大者
            if len(rows) < cap:
                try:
                    j2 = await _em_get_json("/api/qt/clist/get", {
                        "pn": 1, "pz": 200, "po": 1, "np": 1, "fltt": 2, "invt": 2,
                        "fid": "f3", "fs": "b:" + bk,
                        "fields": "f12,f14,f2,f3,f6,f8,f9,f10,f20,f21,f23,f62,f100,f164,f128",
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
    await asyncio.gather(*[_one_board(b) for b in boards], return_exceptions=True)
    return list(rows.values())[:cap], leaders


async def fetch_market_strong_rows(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """全市场强势股补池：东财沪深京A股 5日涨幅榜 + 主力净流入榜 双路取数，
    捕捉“底部刚异动但不在热门板块成分”的漏网标的（板块先行的补充通道）。
    5日涨幅限定在 [globalChg5Min, globalChg5Max] 窗口，主力净流入榜只留净流入为正者。"""
    fs = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048"
    fields = "f12,f14,f2,f3,f6,f8,f9,f10,f20,f21,f23,f62,f100,f164,f109,f128"
    n = int(cfg.get("globalTopN") or 200)
    c5min = float(cfg.get("globalChg5Min") or 3.0)
    c5max = float(cfg.get("globalChg5Max") or 25.0)
    rows: dict[str, dict[str, Any]] = {}
    for fid in ("f109", "f62"):
        try:
            j = await _em_get_json("/api/qt/clist/get", {
                "pn": 1, "pz": n, "po": 1, "np": 1, "fltt": 2, "invt": 2,
                "fid": fid, "fs": fs, "fields": fields,
            }) or {}
        except Exception:
            continue
        diff = (j.get("data") or {}).get("diff") or []
        if not isinstance(diff, list):
            continue
        for r in diff:
            code = str(r.get("f12") or "")
            if not re.fullmatch(r"\d{6}", code) or code in rows:
                continue
            c5 = _num(r.get("f109"))
            if c5 < c5min or c5 > c5max:
                continue
            if fid == "f62" and _num(r.get("f62")) <= 0:
                continue
            rows[code] = r
    return list(rows.values())



async def _fetch_recent_zt_rows(cfg: dict[str, Any], market: str, days: int = 30) -> list[dict[str, Any]]:
    """近 N 日东财涨停池并集 → 批量行情，供 hs/kc 候选扩池（对齐雷达「近期涨停强势股」）。"""
    days = max(5, min(int(days or 30), 60))
    codes: list[str] = []
    seen: set[str] = set()
    d8 = time.strftime("%Y%m%d", time.localtime())
    for _ in range(days + 12):
        try:
            pools = await _emo_pools(d8)
        except Exception:
            pools = {}
        for c in (pools.get("zt_codes") or []):
            c6 = re.sub(r"\D", "", str(c or ""))[-6:].zfill(6)
            if len(c6) != 6 or c6 in seen:
                continue
            if not _market_ok(c6, market):
                continue
            seen.add(c6)
            codes.append(c6)
        d8 = _prev_date8(d8)
        if len(codes) >= 400:
            break
    if not codes:
        return []
    # 批量 ulist 行情（每批 80）
    fields = "f12,f14,f2,f3,f6,f8,f9,f10,f20,f21,f23,f62,f100,f164,f109,f128"
    rows: list[dict[str, Any]] = []
    for i in range(0, len(codes), 80):
        batch = codes[i:i + 80]
        try:
            j = await _em_get_json("/api/qt/ulist.np/get", {
                "secids": ",".join(_stock_secid(c) for c in batch),
                "fields": fields, "fltt": 2, "invt": 2,
            }) or {}
        except Exception:
            continue
        for r in ((j.get("data") or {}).get("diff") or []):
            if isinstance(r, dict) and r.get("f12"):
                rows.append(r)
        await asyncio.sleep(0.15)
    return rows


async def _collect_candidates(
    cfg: dict[str, Any], market: str, with_global: bool = True
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]] | None, int, list[dict[str, Any]]]:
    """收集候选池：bj/bj_all=北证；hs/kc/all=板块先行两阶段（资金流榜→成分股粗筛，按市场过滤）
    + 全市场强势股补池（with_global=False 时跳过，如非 VIP 板块视图）。返回 (cands, hot, board_pool, total, rows_all)。"""
    if market in ("all", "hs", "kc"):
        funds_task = asyncio.create_task(fetch_hot_boards_funds(cfg))
        hot5_task = asyncio.create_task(fetch_hot_sectors(cfg))
        global_task = asyncio.create_task(fetch_market_strong_rows(cfg)) if with_global else None
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
            if not _market_ok(str(row.get("f12") or ""), market):
                continue
            c = coarse(row, cfg, hot)
            if c:
                c["indCnt"] = ind_count.get(c.get("ind") or "", 0)
                cands.append(c)
        # 全市场强势股补池：与板块成分并行抓取，粗筛后补进池，标记 global 供排序让位
        if global_task is not None:
            _grows = await global_task
            _have_c = {str(c.get("code")) for c in cands}
            for _row in _grows:
                _code = str(_row.get("f12") or "")
                if _code in _have_c or not _market_ok(_code, market):
                    continue
                _c = coarse(_row, cfg, hot)
                if _c:
                    _c["indCnt"] = ind_count.get(_c.get("ind") or "", 0)
                    _c["global"] = True
                    cands.append(_c)
                    _have_c.add(_code)
        # 近 N 日涨停池扩容（对齐雷达）：优先进入精筛，标记 zt_hot
        if with_global:
            try:
                _zt_rows = await _fetch_recent_zt_rows(cfg, market, int(cfg.get("ztPoolDays") or 30))
            except Exception:
                _zt_rows = []
            _have_c = {str(c.get("code")) for c in cands}
            for _row in _zt_rows:
                _code = str(_row.get("f12") or "")
                if _code in _have_c or not _market_ok(_code, market):
                    continue
                # 涨停池放宽市值粗筛：临时抬高 mcapMax
                _cfg2 = dict(cfg)
                _cfg2["mcapMax"] = max(float(cfg.get("mcapMax") or 40), float(cfg.get("mcapMaxAll") or 200))
                _cfg2["mcapMin"] = min(float(cfg.get("mcapMin") or 5), float(cfg.get("mcapMinAll") or 15))
                _c = coarse(_row, _cfg2, hot)
                if _c:
                    _c["indCnt"] = ind_count.get(_c.get("ind") or "", 0)
                    _c["zt_hot"] = True
                    cands.append(_c)
                    _have_c.add(_code)
        return cands, hot, funds, len(rows), rows
    # 北证全列表（bj 主线 / bj_all 纯评分共用）
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


def _weekly_bars(bars):
    """daily bars -> weekly bars (group by Monday; same as providers._aggregate_week_month_from_day)."""
    from datetime import datetime, timedelta
    wmap: dict[str, list[int]] = {}
    for i, b in enumerate(bars):
        try:
            parts = str(b[0]).split("-")
            y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
            dt = datetime(y, m, d)
        except Exception:
            continue
        wk = (dt - timedelta(days=dt.weekday())).strftime("%Y-%m-%d")
        wmap.setdefault(wk, []).append(i)
    keys = sorted(wmap.keys())
    if len(keys) < 3:
        return None
    w_o, w_c, w_h, w_l, w_v = [], [], [], [], []
    for k in keys:
        idx = wmap[k]
        w_o.append(float(bars[idx[0]][1]))
        w_c.append(float(bars[idx[-1]][2]))
        w_h.append(max(float(bars[i][3]) for i in idx))
        w_l.append(min(float(bars[i][4]) for i in idx))
        w_v.append(sum(float(bars[i][5]) or 0.0 for i in idx))
    return w_o, w_c, w_h, w_l, w_v


def _weekly_factor(bars):
    """Weekly mid-term confirm factor (zero upstream cost, aggregated from daily bars):
    position(52w percentile) / MACD(red hist) / MA(wMA5>wMA10 turning up) /
    volume(this week >=1.3x prev-4w avg and up week). 2-of-3 hit -> weekConfirm.
    Returns None when <3 weeks (avoid killing new listings)."""
    agg = _weekly_bars(bars)
    if not agg:
        return None
    w_o, w_c, w_h, w_l, w_v = agg
    wn = len(w_c)
    wl = wn - 1
    lo52 = min(w_l[max(0, wl - 51):])
    hi52 = max(w_h[max(0, wl - 51):])
    w_pos = (w_c[wl] - lo52) / (hi52 - lo52) if hi52 > lo52 else 1.0
    w_ma5 = sum(w_c[wl - 4: wl + 1]) / 5 if wn >= 5 else sum(w_c) / wn
    w_ma10 = sum(w_c[max(0, wl - 9): wl + 1]) / min(10, wn)
    w_ma5_prev = sum(w_c[wl - 5: wl]) / 5 if wn >= 6 else None
    e12 = _ema(w_c, 12)
    e26 = _ema(w_c, 26)
    w_dif = [e12[i] - e26[i] for i in range(wn)]
    w_dea = _ema(w_dif, 9)
    w_hist = [(w_dif[i] - w_dea[i]) * 2 for i in range(wn)]
    w_v4 = sum(w_v[max(0, wl - 4): wl]) / min(4, max(1, wl))
    w_vr = w_v[wl] / w_v4 if w_v4 > 0 else 0.0
    week_up = w_c[wl] > w_o[wl]
    # 金叉：本周或近 2 周内 DIF 上穿 DEA；红柱扩张：红柱且高于上周
    gold_now = w_dif[wl] > w_dea[wl] and (wl < 1 or w_dif[wl - 1] <= w_dea[wl - 1])
    gold_prev = wl >= 2 and w_dif[wl - 1] > w_dea[wl - 1] and w_dif[wl - 2] <= w_dea[wl - 2]
    macd_ok = bool(gold_now or gold_prev)
    # 拐头：周MA5 > 周MA10 且差幅 >= 0.5%（过滤横盘噪声）且 MA5 上拐
    ma_ok = bool(w_ma5 > w_ma10 * 1.005 and (w_ma5_prev is None or w_ma5 > w_ma5_prev))
    vol_ok = bool(week_up and w_vr >= 1.3)
    confirm = (int(macd_ok) + int(ma_ok) + int(vol_ok)) >= 2
    return {
        "weekPos": round(w_pos, 3),
        "weekMacdOk": macd_ok,
        "weekMaOk": ma_ok,
        "weekVolOk": vol_ok,
        "weekVolRatio": round(w_vr, 2),
        "weekConfirm": confirm,
        "weekBars": wn,
        "weekUp": week_up,
        "wClose": w_c[wl],
        "wMa10": w_ma10,
    }


def _momentum_score(c: list[float], h: list[float], v: list[float],
                    last: int, rsi14: float, rsi14_3: float, zt_th: float,
                    fund: float, fund5: float) -> dict[str, Any]:
    """强势动量评分（0-100，P0-2）：近3日涨幅斜率 + 涨停/大阳次数 + 量比/放量拐头
    + 创新高速度 + RSI 加速度 + 主力净流入拐头。

    供 analyze 作为「强势动量」轴并入 final，让“刚右侧起来 + 放量 + 涨停/大阳确认”
    的标的压过“低位慢涨”的标的；strongMom 供 king 位与排序优先使用。
    """
    cl = c[last]
    parts: dict[str, float] = {"slope3": 0.0, "big": 0.0, "vol": 0.0,
                               "newhigh": 0.0, "rsi_acc": 0.0, "fund": 0.0}
    # ① 近3日涨幅斜率（0-25）
    if last >= 3 and c[last - 3] > 0:
        chg3 = (cl / c[last - 3] - 1) * 100
        if chg3 >= 12:
            parts["slope3"] = 25
        elif chg3 >= 8:
            parts["slope3"] = 20
        elif chg3 >= 5:
            parts["slope3"] = 14
        elif chg3 >= 3:
            parts["slope3"] = 8
        elif chg3 > 0:
            parts["slope3"] = 3
    # ② 涨停/大阳次数（0-25）：近10日涨停=2、大阳(≥5%)=1
    big = 0
    zt_cnt10 = 0
    for i in range(max(1, last - 9), last + 1):
        p0 = (c[i] / c[i - 1] - 1) * 100 if c[i - 1] > 0 else 0.0
        if p0 >= zt_th - 0.5:
            big += 2
            zt_cnt10 += 1
        elif p0 >= 5:
            big += 1
    parts["big"] = min(25.0, big * 6)
    # ③ 量比 / 放量拐头（0-20）
    v20 = sum(v[max(0, last - 19): last + 1]) / min(20, last + 1)
    v_ratio = v[last] / v20 if v20 > 0 else 0.0
    v_prev = v[last - 1] / v20 if last >= 1 and v20 > 0 else 0.0
    if v_ratio >= 2.0:
        parts["vol"] = 20
    elif v_ratio >= 1.5:
        parts["vol"] = 16
    elif v_ratio >= 1.2:
        parts["vol"] = 12
    elif v_ratio >= 1.0:
        parts["vol"] = 7
    if v_ratio > v_prev * 1.2 and v_ratio >= 1.0:
        parts["vol"] = min(20.0, parts["vol"] + 3)
    # ④ 创新高速度（0-15）：近 N 日创 20 日新高（越新越强）
    hi20 = max(h[max(0, last - 19): last + 1]) if last >= 19 else max(h)
    days_since_hi = last
    for i in range(last, max(-1, last - 20), -1):
        if h[i] >= hi20:
            days_since_hi = last - i
            break
    if days_since_hi <= 1 and cl >= hi20 * 0.995:
        parts["newhigh"] = 15
    elif days_since_hi <= 2 and cl >= hi20 * 0.985:
        parts["newhigh"] = 10
    elif days_since_hi <= 5 and cl >= hi20 * 0.98:
        parts["newhigh"] = 6
    # ⑤ RSI 加速度（0-10）
    rsi_acc = rsi14 - rsi14_3
    if rsi_acc >= 10:
        parts["rsi_acc"] = 10
    elif rsi_acc >= 6:
        parts["rsi_acc"] = 7
    elif rsi_acc >= 3:
        parts["rsi_acc"] = 4
    elif rsi_acc >= 0:
        parts["rsi_acc"] = 1
    # ⑥ 主力净流入拐头（0-5）
    if fund > 0 and fund5 > 0:
        parts["fund"] = 5
    elif fund > 0:
        parts["fund"] = 3
    total = int(round(sum(parts.values())))
    tags: list[str] = []
    if parts["slope3"] >= 14:
        tags.append("近3日强斜率")
    if zt_cnt10 >= 1:
        tags.append(f"近10日{zt_cnt10}个涨停/大阳")
    if parts["newhigh"] >= 10:
        tags.append("创新高")
    return {
        "momScore": max(0, min(100, total)),
        "momParts": parts,
        "strongMom": bool(total >= 55),
        "momTags": tags,
    }


def analyze(bars: list[list[Any]], cand: dict[str, Any], cfg: dict[str, Any], market: str = "bj", loose_macd: bool = False) -> dict[str, Any]:
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
    ma30 = _ma_at(c, 30, last)
    ma60 = _ma_at(c, 60, last)
    ma144 = _ma_at(c, 144, last) if n >= 144 else 0.0
    ma144_prev = _ma_at(c, 144, last - 5) if n >= 149 else 0.0
    ma144_prev10 = _ma_at(c, 144, last - 10) if n >= 154 else 0.0
    ma6 = _ma_at(c, 6, last)
    ma12 = _ma_at(c, 12, last)
    ma20_3 = _ma_at(c, 20, last - 3)
    _su = score_steady_up(o, h, l, c, v, last)
    wk = _weekly_factor(bars)
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
    # P0-3 ATR 自适应：ATR14 + 60 日 atrPct 分位 + 波动档 + 量能 20 日分位（数据不足时 fallback）
    atr_prof = calc_atr_profile(o, h, l, c, v)
    atr = atr_prof["atr"]
    atr_pct = atr_prof["atr_pct"]
    vol_rank20 = atr_prof["vol_rank20"]
    atr_tol = atr_prof["atr_tol"]
    atr_adaptive = bool(not atr_prof["fallback"] and cfg.get("adaptiveAtr", True))
    pullbackType: str | None = None
    pullbackDepthAtr: float | None = None
    pullbackDepthPct: float | None = None
    bias6 = (cl - ma6) / ma6 * 100 if ma6 else 0.0
    bias12 = (cl - ma12) / ma12 * 100 if ma12 else 0.0
    ma_bull = bool(ma5 > ma10 > ma20 > ma60)
    ma_bull3 = bool(ma5 > ma10 > ma20)
    # 大周期档位（与 AI 雷达 5/10/20/30/60/144 对齐）：S/A/B/""
    ma_tier = ma_tier_from_values(
        ma5=ma5, ma10=ma10, ma20=ma20, ma30=ma30, ma60=ma60,
        ma144=ma144, ma144_prev=ma144_prev, ma144_prev10=ma144_prev10,
        n_bars=n,
    )
    above_ma60 = above_ma60_structure(
        ma5=ma5, ma10=ma10, ma20=ma20, ma30=ma30, ma60=ma60,
        ma144=ma144, n_bars=n,
    )
    above_ma144 = above_ma144_structure(
        ma5=ma5, ma10=ma10, ma20=ma20, ma30=ma30, ma60=ma60,
        ma144=ma144, n_bars=n,
    )
    _r60 = float(cfg.get("pickMa60StrongRatio") or 1.03)
    ma60_strong_days = count_ma60_strong_days(c, ratio=_r60, lookback=25)
    ma60_strong = ma60_strong_ok(
        ma5=ma5, ma10=ma10, ma20=ma20, ma30=ma30, ma60=ma60,
        strong_days=ma60_strong_days,
        min_days=int(cfg.get("pickMa60StrongDays") or 5),
        ratio=_r60,
    )
    # 若档位为空但结构已站上144，记为 S；站上60记 A（三档门底线可读）
    if not ma_tier and above_ma144:
        ma_tier = "S"
    elif not ma_tier and (above_ma60 or ma60_strong):
        ma_tier = "A"
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
    if _su["steadyUp"]:
        patterns["steadyUp"] = 1  # 稳步向上：趋势斜率+均线发散+支撑+温和量能，情绪平淡期更稳
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
    pull_idx = -1
    # 异动门槛：沪深 8%+（用户口径“异动涨8-10个点以上”），北证 30cm 用 10%+
    surge_min = 10.0 if market in ("bj", "bj_all") else 8.0
    surge_vol = 2.0 if market in ("bj", "bj_all") else 1.5
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
                    pull_idx = i
                    break
            if pulled:
                break
    _c6 = str(cand.get("code") or "").zfill(6)
    if pulled:
        patterns["pullback"] = 1
        _pbc = classify_pullback(o, h, l, c, v, pull_idx, atr_tol, atr_pct)
        if pull_surge_pct >= _zt_threshold(_c6) - 0.5 and _pbc.get("pullbackType") != "broken_rebound":
            patterns["ztPullback"] = 1  # 涨停级回踩：最强低吸形态
        if _pbc.get("pullbackType") == "broken_rebound":
            risks.append("破板日低点后反抽(不算高质量回踩)")
        if _pbc.get("pullbackDepthPct", 0) > 10:
            risks.append("回踩过深(超10%)")
    # 板后回踩企稳（2周内一个板 + 回踩数日企稳、未破位，最贴合“二波低吸”偏好）
    pb2_ok = False
    pb2_days = 0
    _zt2 = _zt_threshold(_c6)
    pb2_bi = -1
    for _i in range(max(1, n - 11), last):
        _pi = (c[_i] / c[_i - 1] - 1) * 100 if c[_i - 1] > 0 else 0.0
        if _pi >= _zt2 - 0.5:
            pb2_bi = _i
    if pb2_bi >= 0 and (last - pb2_bi) >= 2:
        _after = list(range(pb2_bi + 1, last + 1))
        _v_pull = sum(v[_j] for _j in _after) / len(_after)
        _plat_lo = min(l[_j] for _j in _after)
        _blo = l[pb2_bi]
        _bvol = v[pb2_bi]
        _worst = min((c[_j] / c[_j - 1] - 1) * 100 for _j in _after if c[_j - 1] > 0)
        _yi = _bvol < 0.5 * v20
        _vol_ok = _v_pull <= 1.6 * v20 and (_yi or _v_pull <= 1.25 * max(_bvol, v20))
        _dump = False
        if not _yi:
            for _j in _after:
                if c[_j] < o[_j] and v[_j] > 1.3 * _bvol:
                    _dump = True
                    break
        _pb_cls = classify_pullback(o, h, l, c, v, pb2_bi, atr_tol, atr_pct)
        pullbackType = _pb_cls.get("pullbackType")
        pullbackDepthAtr = _pb_cls.get("pullbackDepthAtr")
        pullbackDepthPct = _pb_cls.get("pullbackDepthPct")
        _pb_nb1 = cl >= ma10 and (
            _plat_lo >= _blo - atr_tol if (atr_adaptive and atr_tol > 0) else _plat_lo >= _blo * 0.97
        )
        _pb_nb2 = cl >= ma20 and ma20 > ma20_3
        _pb_stab_a = cl >= ma5 and ma5 > _ma_at(c, 5, last - 3)
        _pb_s0 = max(pb2_bi + 1, last - 2)
        _pb_small = all(abs((c[_j] / c[_j - 1] - 1) * 100) <= 5 for _j in range(_pb_s0, last + 1)) and cl >= c[max(pb2_bi + 1, last - 3)]
        _pb_pct3 = [(c[_j] / c[_j - 1] - 1) * 100 for _j in range(last - 2, last + 1) if c[_j - 1] > 0]
        _pb_stab_c = (not _pb_pct3 or min(_pb_pct3) > -3.5) and cl >= c[last - 1]
        _pb_stable = _pb_stab_a or _pb_small or _pb_stab_c
        pb2_days = last - pb2_bi
        pb2_ok = bool(
            _worst >= -6 and (_pb_nb1 or _pb_nb2) and _pb_stable and _vol_ok
            and not _dump and pos <= 0.60 and chg10 <= 40 and pb2_days <= 10
            and pullbackType != "broken_rebound" and (pullbackDepthPct or 0) <= 10
        )
        if pb2_ok:
            patterns["pullback2"] = 1
        elif _worst < -6 or cl < _blo * 0.97:
            risks.append("板后破位(跌破板日低点/板后长阴)")
        elif (pullbackDepthPct or 0) > 10:
            risks.append("回踩过深(超10%)")
    # 首板 4-5 日回踩企稳（用户补充的最优形态）：
    # 底部右侧刚起（位置≤45%）+ 没大涨（5日≤18%/10日≤30%）+ 近期 1-2 个板
    # + 板后回踩 4-5 天稳住未破位（复用 pullback2 的未破位/缩量/企稳判定）
    pb45_ok = False
    if pb2_ok and 4 <= pb2_days <= 5 and pos <= 0.45 and chg5 <= 18 and chg10 <= 30:
        _zt_cnt45 = 0
        for _i in range(max(1, n - 10), last + 1):
            _pi45 = (c[_i] / c[_i - 1] - 1) * 100 if c[_i - 1] > 0 else 0.0
            if _pi45 >= _zt2 - 0.5:
                _zt_cnt45 += 1
        if 1 <= _zt_cnt45 <= 2:
            pb45_ok = True
            patterns["pb45"] = 1
    # 二波突破确认：近 3 日放量突破板日高点/板后平台高点（右侧确认，低吸后的加速信号）
    if pb2_bi >= 0 and last > pb2_bi + 1:
        _brk_hi = max(h[pb2_bi], max(h[pb2_bi + 1:last]))
        for _i in range(max(pb2_bi + 1, last - 2), last + 1):
            if c[_i] > _brk_hi and v[_i] >= 1.5 * v20:
                patterns["breakout"] = 1
                break
    # 一路小阳
    if up_days >= 3 and max_day_pct <= 8 and 0 <= chg5 <= 18:
        patterns["smallYang"] = 1
    # 底部放量异动启动（核心：刚底部异动起来）
    ms_min = max(float(cfg["minSurge"]), 10.0 if market in ("bj", "bj_all") else 8.0)
    sv_min = max(float(cfg["surgeVol"]), 2.0 if market in ("bj", "bj_all") else 1.5)
    # 异动涨幅上限按市场涨停阈值放宽：北证 30cm 提到 ~28.5%、科创创业 ~18.5%、
    # 主板保持 14%（避免把 15-28% 的“半路异动”当天漏检，30cm 涨停当天仍由涨停级形态承接）
    _surge_hi = max(14.0, _zt_threshold(str(cand.get("code") or "").zfill(6)) - 1.0)
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
        if ms_min <= pcti <= _surge_hi and v[i] >= sv_min * v_ma and pos_at_i <= 0.5:
            surge_idx = i
    surge_ok = False
    if surge_idx >= 0:
        surge_days_ago = last - surge_idx
        if surge_days_ago <= int(cfg["surgeDays"]) and cl >= ma5 and cl >= c[surge_idx] * 0.97:
            surge_ok = True
    if surge_ok:
        patterns["surgeStart"] = 1
        if surge_days_ago > 10:
            patterns.pop("surgeStart", None)
            risks.append("异动过时(>10日未再启动)")
    # 异动后中回踩企稳（北证专享）：放量异动后 4-8 日缩量回踩、未破异动日低点、
    # 今日站稳 MA10 或连续收小阳（用户口径“回踩数日企稳，没破位或连续收小阳”）。
    # 与 surgeStart 互补：surgeStart 要求站回 MA5（强确认），此处允许仍在 MA10 附近缩量企稳（弱确认）。
    surge_pb_ok = False
    surge_pb_days = 0
    if market in ("bj", "bj_all") and surge_idx >= 0 and not surge_ok and 2 <= surge_days_ago <= 8 and pos <= 0.55:
        _saft = list(range(surge_idx + 1, last + 1))
        if _saft:
            _va = sum(v[_j] for _j in _saft) / len(_saft)
            _lmin = min(l[_j] for _j in _saft)
            _vol_ok = _va <= 1.6 * v20 and _va <= 1.3 * max(v[surge_idx], v20)
            _low_ok = _lmin >= l[surge_idx] * 0.97
            _stab_ma10 = cl >= ma10 * 0.97
            _last2 = [(c[_j] / c[_j - 1] - 1) * 100 for _j in (last - 1, last) if _j >= 1 and c[_j - 1] > 0]
            _stab_xiaoyang = len(_last2) == 2 and all(_x >= 0 for _x in _last2) and all(_x <= 8 for _x in _last2)
            if _vol_ok and _low_ok and (_stab_ma10 or _stab_xiaoyang):
                surge_pb_ok = True
                surge_pb_days = surge_days_ago
    if surge_pb_ok:
        patterns["surgePullback"] = 1
    # surgePullback 已满足“弱确认”（站稳 MA10 或连续小阳），不再叠加“未确认企稳”风险
    if surge_idx >= 0 and not surge_ok and not surge_pb_ok:
        risks.append("底部异动后未确认企稳")
    # 单日砸盘企稳（洗盘）：底部刚起 + 近期异动 10%+（放量）+ 回调中单日砸盘 5%+ 但未破位。
    # 未破位：砸盘日最低未破异动日低点(3%容差)、今日收盘站稳 MA10 且收复砸盘日收盘、砸盘后缩量企稳。
    # 这是与 pullback2 互补的形态：pullback2 要求回调平稳，这里允许“单日剧烈下杀后重新企稳”的洗盘。
    wash_ok = False
    washout_days = 0
    if surge_idx >= 0 and pos <= 0.55 and surge_days_ago <= 12:
        _spct = (c[surge_idx] / c[surge_idx - 1] - 1) * 100 if surge_idx >= 1 and c[surge_idx - 1] > 0 else 0.0
        if _spct >= 9.5:
            for _j in range(surge_idx + 1, last):
                _pcj = c[_j - 1] if _j > 0 else 0
                _chgj = (c[_j] / _pcj - 1) * 100 if _pcj > 0 else 0.0
                if _chgj <= -5 and (last - _j) <= 7:
                    _hold = (
                        l[_j] >= l[surge_idx] * 0.97
                        and cl >= ma10 * 0.97
                        and cl >= c[_j] * 0.97
                    )
                    _after_v = v[_j + 1:] if _j + 1 <= last else []
                    _settle = (not _after_v) or (sum(_after_v) / len(_after_v) <= 1.3 * v[_j])
                    if _hold and _settle:
                        wash_ok = True
                        washout_days = last - _j
                        break
    if wash_ok:
        patterns["washOut"] = 1
    # 均线粘合后发散（启动初期）
    spread = (max(ma5, ma10, ma20) - min(ma5, ma10, ma20)) / ma20 * 100 if ma20 else 0.0
    if spread <= 2.5 and ma5 > ma10 and ma10 > ma20 and hist[last] > 0:
        patterns["tightBurst"] = 1
    # 大波段（同花顺「多头粘合涨停」落地）：仅沪深主板+创业/科创，硬排除北证
    # 对齐原式核心；过严处放宽：大周期双路径、粘合窗10日、年涨停改软门、额/位置略松
    tight_zt = False
    tight_zt_meta: dict[str, Any] = {}
    try:
        _name_u = str(cand.get("name") or "")
        _not_st = not bool(re.search(r"(?:\*?ST)|退", _name_u, flags=re.I))
        _hs_kc = _is_hs_kc_code6(_c6)
        _listed_ok = n > 120
        ma30 = _ma_at(c, 30, last)
        ma144 = _ma_at(c, 144, last) if n >= 144 else 0.0
        ma144_prev5 = _ma_at(c, 144, last - 5) if n >= 149 else 0.0
        # 大周期：路径A=原式（5/10/20/30>60 且 60>144）；路径B=短多头贴近60/144（防空仓）
        _path_a = bool(
            n >= 144 and ma5 > ma60 and ma10 > ma60 and ma20 > ma60 and ma30 > ma60
            and ma144 > 0 and ma60 > ma144
        )
        _path_b = bool(
            ma5 > ma10 > ma20 and ma20 >= ma60 * 0.98
            and (ma144 <= 0 or ma60 >= ma144 * 0.98)
        )
        _big_ok = _path_a or _path_b
        _ma144_up = bool(ma144 > 0 and ma144_prev5 > 0 and ma144 >= ma144_prev5 * 0.997)
        # 粘合阈 3%：近10日≥2日粘合，或今日价差≤3.5%；发散=MA5>10>20 且 MA5 不下行
        _glue_th = 0.03
        _glue_cnt = 0
        for _gi in range(max(19, last - 9), last + 1):
            _g5 = _ma_at(c, 5, _gi)
            _g10 = _ma_at(c, 10, _gi)
            _g20 = _ma_at(c, 20, _gi)
            if _g5 > 0 and _g10 > 0 and _g20 > 0 \
                    and abs(_g5 / _g20 - 1) <= _glue_th \
                    and abs(_g10 / _g20 - 1) <= _glue_th \
                    and abs(_g5 / _g10 - 1) <= _glue_th:
                _glue_cnt += 1
        _ma5_1 = _ma_at(c, 5, last - 1) if last >= 1 else 0.0
        _ma5_2 = _ma_at(c, 5, last - 2) if last >= 2 else 0.0
        _diverge_strict = bool(ma5 > ma10 > ma20 and ma5 > _ma5_1 > 0 and _ma5_1 > _ma5_2 > 0)
        _diverge = bool(ma5 > ma10 > ma20 and ma5 >= _ma5_1 > 0)
        _spread_now = (max(ma5, ma10, ma20) - min(ma5, ma10, ma20)) / ma20 * 100 if ma20 else 99.0
        _glue_up = bool((_glue_cnt >= 2 or _spread_now <= 3.5) and _diverge)
        _amt_scale = 100.0
        _snap_amt = _num(cand.get("amount"))
        if _snap_amt > 0 and c[last] > 0 and v[last] > 0:
            _amt_scale = _snap_amt / (c[last] * v[last])

        def _bar_amt(i: int) -> float:
            return float(c[i]) * float(v[i]) * _amt_scale if c[i] > 0 and v[i] > 0 else 0.0

        def _vol_confirm_at(i: int) -> bool:
            if i < 4:
                return False
            _v5i = sum(v[i - 4: i + 1]) / 5.0
            return _v5i > 0 and v[i] >= 1.2 * _v5i

        _zt_th_tz = _zt_threshold(_c6)
        _zt_amt_min = 3.0e7  # 原式 5000 万，放宽至 3000 万
        _good_zt_idx = -1
        for _zi in range(max(1, last - 9), last + 1):
            _zp = (c[_zi] / c[_zi - 1] - 1) * 100 if c[_zi - 1] > 0 else 0.0
            if _zp < _zt_th_tz - 0.3:
                continue
            _zt_px = c[_zi - 1] * (1.0 + _zt_th_tz / 100.0)
            if l[_zi] >= _zt_px * 0.997:
                continue
            if _bar_amt(_zi) < _zt_amt_min:
                continue
            _good_zt_idx = _zi
        _near_zt = _good_zt_idx >= 0
        _vol_ok = _vol_confirm_at(last) or (_good_zt_idx >= 0 and _vol_confirm_at(_good_zt_idx))
        _look = min(last, 169)
        _yr_zt = 0
        for _yi in range(max(1, last - _look + 1), last + 1):
            _yp = (c[_yi] / c[_yi - 1] - 1) * 100 if c[_yi - 1] > 0 else 0.0
            if _yp >= _zt_th_tz - 0.3:
                _yr_zt += 1
        # 年涨停：原式 5–10 作软加分；硬门只要求近窗有效涨停
        _yr_ideal = 5 <= _yr_zt <= 10
        _yr_soft = 3 <= _yr_zt <= 12
        _llv60 = min(l[max(0, last - 59): last + 1]) if n >= 2 else cl
        _pos_from_low = (cl / _llv60 - 1.0) if _llv60 > 0 else 99.0
        _pos_ok = _pos_from_low <= 0.70  # 原式 0.65，略放宽
        _amt20 = sum(_bar_amt(i) for i in range(max(0, last - 19), last + 1)) / 20.0
        _liq_ok = _amt20 > 5.0e7  # 原式 1 亿，放宽至 5000 万
        _big_dn = -10.0 if _is_kc_code6(_c6) else -7.0
        _no_big_yin = True
        for _yi in range(max(1, last - 9), last + 1):
            _yd = (c[_yi] / c[_yi - 1] - 1) * 100 if c[_yi - 1] > 0 else 0.0
            if _yd <= _big_dn:
                _no_big_yin = False
                break
        tight_zt = bool(
            _hs_kc and _not_st and _listed_ok and _big_ok and _glue_up
            and _near_zt and _pos_ok and _liq_ok and _no_big_yin and _vol_ok
        )
        tight_zt_meta = {
            "glueDays": _glue_cnt, "yrZt": _yr_zt, "yrSoft": _yr_ideal or _yr_soft,
            "ma144Up": _ma144_up, "aboveMa144": bool(ma144 > 0 and ma60 > ma144),
            "pathA": _path_a, "divergeStrict": _diverge_strict,
            "posFromLow": round(_pos_from_low, 3),
            "ztDaysAgo": (last - _good_zt_idx) if _good_zt_idx >= 0 else None,
            "spread": round(_spread_now, 2),
            "amt20yi": round(_amt20 / 1e8, 2),
        }
        if tight_zt:
            patterns["tightZt"] = 1
    except Exception:
        tight_zt = False
    # MACD 首根红柱（底部金叉第一根红柱 + 量能确认：右侧启动强信号）
    fr_idx = last - gc_days + 1
    # P1-2 B：all（沪深京全市场）扫描时放宽首红量能与位置门槛，减少漏检（1.2×→1.0×、位置≤50%→≤60%）
    _macd_vol_k = 1.0 if loose_macd else 1.2
    _macd_pos_max = 0.60 if loose_macd else 0.50
    # P0-3 量能 20 日分位：MACD 首红量能 >=60% 分位（数据不足时用原固定倍数 fallback）
    macd_underwater = bool(dif[last] <= 0)
    fr_vol_ok = False
    if 0 < fr_idx < n:
        _fr_base = sum(v[max(0, fr_idx - 20):fr_idx]) / max(1, fr_idx)
        fr_vol_ok = _fr_base > 0 and (
            v[fr_idx] >= _macd_vol_k * _fr_base or (atr_adaptive and vol_rank20 >= 0.60)
        )
    macd_first_red = bool(
        1 <= gc_days <= 3
        and fr_idx >= 1
        and hist[fr_idx - 1] <= 0
        and pos <= _macd_pos_max
        and (fr_vol_ok or vol5v20 >= 0.9)
        and cl >= ma5 * 0.97
    )
    if macd_first_red:
        patterns["macdFirstRed"] = 1
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
    # 近期涨停（按市场阈值统一）：近 10 日内的涨停日
    _c6u = _c6 if _c6 else str(cand.get("code") or "").zfill(6)
    zt_th = _zt_threshold(_c6u)
    zt_day = -1
    for i in range(max(1, n - 10), last + 1):
        p0 = (c[i] / c[i - 1] - 1) * 100 if c[i - 1] > 0 else 0.0
        if p0 >= zt_th - 0.5:
            zt_day = i
    # P0-2 涨停质量分级：涨停日 OHLC+换手代理（历史涨停日用当日换手代理，置信度降级）
    lq: dict[str, Any] = {}
    if zt_day >= 0 and cfg.get("limitQuality", True):
        _pc = c[zt_day - 1] if zt_day >= 1 else c[zt_day]
        lq = classify_limit_quality(o[zt_day], h[zt_day], l[zt_day], c[zt_day],
                                    _pc, zt_th, _num(cand.get("turnover")))
        if zt_day < last:
            lq["qualityConfidence"] = "low"
        if lq.get("limitQuality") == "one_word":
            risks.append("一字板·不可交易强度")
    # 首板右侧上拐：近 5 日内有涨停 → 回调 ≥1 日、不破涨停日低点/MA5、今日放量上拐
    first_board_ok = False
    if zt_day >= 0 and 1 <= (last - zt_day) <= 5:
        _nb_low = l[last] >= l[zt_day] * 0.97
        _nb_ma5 = cl >= ma5 * 0.97
        # 首板右侧上拐需收复涨停价（与“首板失败(跌破涨停价)”互斥，避免同一标的两种结论）
        _nb_close = cl >= c[zt_day] * 0.985
        _up_turn = cl > h[last - 1] or (cl >= ma5 and (v[last] >= 1.2 * v20
                                                       or (atr_adaptive and vol_rank20 >= 0.80)))
        if _nb_low and _nb_ma5 and _nb_close and _up_turn:
            first_board_ok = True
    if first_board_ok and not pb2_ok:
        patterns["firstBoardRight"] = 1
    # 近1周首板 + 底部右侧刚启动（用户要求更苛刻的优选形态）：
    # 5 个交易日内有 1-2 个首板/涨停（非连板妖股）+ 位置≤45%（底部）
    # + 未破板日低点/MA5 + 站稳右侧（站上 MA10 或 MA20 上拐）+ 未大幅回吐板日涨幅
    first_week_ok = False
    if zt_day >= 0 and 1 <= (last - zt_day) <= 5 and pos <= 0.45:
        _zt_cnt5 = 0
        for _i in range(max(1, n - 5), last + 1):
            _pi5 = (c[_i] / c[_i - 1] - 1) * 100 if c[_i - 1] > 0 else 0.0
            if _pi5 >= zt_th - 0.5:
                _zt_cnt5 += 1
        _fw_hold = l[last] >= l[zt_day] * 0.97 and cl >= ma5 * 0.97
        _fw_right = cl >= ma10 or (ma20 > ma20_3 and cl >= ma20 * 0.97)
        _fw_stab = cl >= c[zt_day] * 0.95
        if 1 <= _zt_cnt5 <= 2 and _fw_hold and _fw_right and _fw_stab:
            first_week_ok = True
            patterns["firstWeek"] = 1
    # 近一周有涨停（软优先信号，2026-08-25 A 方案）：5 个交易日内有 1-2 个涨停日即标记，
    # 不要求形态/位置（是 firstWeek/firstBoardRight 的更宽超集），供排序与 king 位优先；
    # 连板妖股（≥3 板）与一字板（不可交易强度）不作为优选信号，涨停质量由 limitQuality 分级兜底。
    if zt_day >= 0 and 1 <= (last - zt_day) <= 5 and lq.get("limitQuality") != "one_word":
        _zt_cnt5 = 0
        for _i in range(max(1, n - 5), last + 1):
            _pi5 = (c[_i] / c[_i - 1] - 1) * 100 if c[_i - 1] > 0 else 0.0
            if _pi5 >= zt_th - 0.5:
                _zt_cnt5 += 1
        if 1 <= _zt_cnt5 <= 2:
            patterns["ztWeek"] = 1
    # 事件回踩企稳统一标签：1-2 周内有首板（涨停级回踩/板后回踩/首板右侧/二波突破）
    # 或异动 8-10%+（底部放量异动/异动回踩）→ 回调数日企稳未破位。
    # 供排序与主推优先使用（不额外加分，避免重复计分）。
    ev_days: int | None = None
    _ev_days_cand: list[int] = []
    if patterns.get("pullback2"):
        _ev_days_cand.append(pb2_days)
    if patterns.get("firstBoardRight") and zt_day >= 0:
        _ev_days_cand.append(last - zt_day)
    if patterns.get("firstWeek") and zt_day >= 0:
        _ev_days_cand.append(last - zt_day)
    if patterns.get("ztPullback") and pull_idx >= 0:
        _ev_days_cand.append(last - pull_idx)
    if patterns.get("surgeStart"):
        _ev_days_cand.append(surge_days_ago)
    if patterns.get("surgePullback"):
        _ev_days_cand.append(surge_pb_days)
    if patterns.get("breakout") and pb2_bi >= 0:
        _ev_days_cand.append(last - pb2_bi)
    if patterns.get("pullback") and pull_idx >= 0:
        _ev_days_cand.append(last - pull_idx)
    if patterns.get("washOut"):
        _ev_days_cand.append(washout_days)
    if _ev_days_cand:
        ev_days = min(_ev_days_cand)
    if ev_days is not None:
        patterns["eventPullback"] = 1
    # ⑨ 强势动量轴（P0-2，0-15 封顶）：让“刚右侧+放量+涨停/大阳确认”压过“低位慢涨”。
    # 独立于启动证据轴（不重复计分），strongMom 同时作为启动确认，供 king 位与排序优先。
    _rsi14_3 = _rsi_wilder(c[:max(1, last - 2)]) if n >= 4 else rsi14
    mom = _momentum_score(c, h, v, last, rsi14, _rsi14_3, zt_th,
                          fund, _num(cand.get("fund5")))
    _mom = mom["momScore"]
    _mom_bonus = 0
    if _mom >= 70:
        _mom_bonus = 15
    elif _mom >= 60:
        _mom_bonus = 12
    elif _mom >= 50:
        _mom_bonus = 9
    elif _mom >= 40:
        _mom_bonus = 6
    elif _mom >= 30:
        _mom_bonus = 3
    elif _mom >= 20:
        _mom_bonus = 1
    if mom["strongMom"]:
        patterns["strongMom"] = 1
    # 涨停后破位才是风险；“刚涨停”不再当作减分项
    if zt_day >= 0 and not (pulled or pb2_ok) and cl < c[zt_day] * 0.985:
        risks.append("首板失败(跌破涨停价)")
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
    # 周线中期维度：高位/走弱警示（零上游，日线本地聚合）
    if wk:
        if wk["weekPos"] > 0.85 and pos > 0.80:
            risks.append("周线高位(52周)")
        if wk["weekBars"] >= 6 and wk["wClose"] < wk["wMa10"] and not wk["weekMaOk"]:
            risks.append("周线走弱(周MA10下)")
    if amp20 and amp20 < 3:
        risks.append("20日振幅过低(死水)")
    if amp20 and amp20 > 35:
        risks.append("20日振幅过大(偏疯)")
    if vol_health == -1:
        risks.append("跌放量出货嫌疑")
    # 路径三轴：右侧上涨途中 × 股性活跃 × 禁下坡
    _path = calc_path_activity(
        c, o, ma5, ma10, ma20, ma20_3, ma_bull3, last, chg5, amp20,
        vol_shrink, vol_health, vol_ratio, bias_over, new_high_weak, at_high_weak,
        pos, _num(cand.get("turnover")), patterns, wk,
    )
    if _path["downSlope"]:
        risks.append("下坡途中(趋势走弱)")
    elif not _path["pathOk"]:
        risks.append("未确认右侧上涨途中")
    if not _path["activeOk"] and float(amp20 or 0) < 5:
        risks.append("股性偏死(振幅过低)")
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
        scar_tags.append("行业稀缺" + f"\u00b7{('北证仅' if market in ('bj', 'bj_all') else '候选池仅')}{ind_cnt}只")
    if 0 < float_ratio < 0.5:
        scarcity += 3
        scar_tags.append("流通盘稀缺" + f"\u00b7流通占比{float_ratio * 100:.0f}%")
    sc += scarcity
    # ② 启动证据（0-25 封顶）：最强 1 个 + 次强 1 个，不重复累加
    _START_W = {
        "ztPullback": 13,      # 涨停级回踩：最强低吸
        "firstWeek": 12,       # 近1周首板·底部右侧刚启动（用户更苛刻优选形态）
        "pullback2": 12,       # 板后回踩企稳
        "washOut": 11,         # 单日砸盘企稳（洗盘后企稳，未破位）
        "surgeStart": 10,      # 底部放量异动
        "surgePullback": 10,   # 异动后中回踩企稳（北证全市场：缩量回踩未破位，站MA10或连续小阳）
        "firstBoardRight": 10, # 首板右侧上拐
        "pullback": 9,         # 异动回踩
        "breakout": 12,        # 二波放量突破（P0-3 权重 8→12，仍受证据封顶）
        "macdFirstRed": 8,     # MACD 首红（水下降权 4，仅辅助）
        "steadyUp": 8,         # 稳步向上（趋势确认型启动，与 MACD 首红同档辅助）
        "weekConfirm": 8,     # 周线中期确认（金叉/拐头/放量三选二，仅辅助确认）
    }
    # P0-2 涨停质量权重修正：换手板 +4 / T字板 +1 / 一字板 -3 / 烂板 -5（仍受证据封顶约束）
    _start_w = dict(_START_W)
    _lq_delta = _LQ_DELTA.get(lq.get("limitQuality") or "", 0)
    if _lq_delta:
        for _k in ("ztPullback", "firstBoardRight", "breakout"):
            if patterns.get(_k):
                _start_w[_k] = max(1, _start_w[_k] + _lq_delta)
    if patterns.get("macdFirstRed") and macd_underwater:
        _start_w["macdFirstRed"] = 4  # 零轴下水下首红：降权仅作辅助
    # 周线中期确认：仅当已有日线启动证据时启用（周线不单独构成启动）
    if wk and wk.get("weekConfirm") and any(patterns.get(k) for k in _start_w):
        patterns["weekConfirm"] = 1
    _start_vals = sorted((w for k, w in _start_w.items() if patterns.get(k)), reverse=True)
    sc += min(25, sum(_start_vals[:2]))
    # ③ 承接与量价（0-15 封顶）
    q = 0.0
    if vol_health == 1:
        q += 3
    if fund_streak:
        q += 2
    if patterns.get("smallYang"):
        q += 2  # 吸筹辅助确认（不单独构成启动证据）
    if 1.1 <= vol5v20 <= 2.5:
        q += 6
    elif 0.8 <= vol5v20 < 1.1:
        q += 3
    elif 2.5 < vol5v20 <= 4:
        q += 2
    if 1.1 <= vol_ratio <= 3:
        q += 3
    elif vol_ratio > 0.6:
        q += 1
    if close_pos >= 0.60:
        q += 3
    if odds_use >= 2.0:
        q += 3
    elif odds_use >= 1.5:
        q += 1
    elif 0 < odds_use < 1.2:
        q -= 2
    sc += max(-2, min(15, q))
    # ④ 资金与主线（0-15 封顶）
    m = 0.0
    if cfg.get("useFund") and fund > 0:
        m += 5
    if cfg.get("useFund") and _num(cand.get("fund5")) > 0:
        m += 3
    if cand.get("hot"):
        m += 4
    if kw_hits:
        m += 2
    sc += min(15, m)
    # ⑤ 时机与均线（0-15 封顶）
    t = 0.0
    if patterns.get("baseUp"):
        t += 6
    if patterns.get("tightBurst"):
        t += 4
    if patterns.get("tightZt"):
        t += 5
        if tight_zt_meta.get("yrSoft"):
            t += 1
        if tight_zt_meta.get("ma144Up"):
            t += 1
        if tight_zt_meta.get("aboveMa144"):
            t += 1
    if hist[last] > 0:
        t += 2
    gc = False
    for i in range(last - 4, last + 1):
        if dif[i] > dea[i] and dif[i - 1] <= dea[i - 1]:
            gc = True
    if gc:
        t += 2
    if ma_bull:
        t += 6
    elif ma_bull3:
        t += 4
    # 大周期档位加分（雷达同口径）
    if ma_tier == "S":
        t += 5
    elif ma_tier == "A":
        t += 3
    elif ma_tier == "B":
        t += 1
    if ma20 > ma20_3:
        t += 2
    # 主线龙头确认：资金回流 + 短期趋势走强 + MACD 不弱
    leader_ok = bool(
        fund > 0 and chg5 > 0 and cl > ma10
        and cl >= ma20 * 0.97
        and (hist[last] > 0 or gc)
    )
    if leader_ok:
        patterns["leaderOk"] = 1
        t += 3
    if 55 <= rsi14 <= 72:
        t += 2
    elif 40 <= rsi14 < 55:
        t += 1
    if 4 <= atr_pct <= 10:
        t += 2
    elif 1.5 <= atr_pct < 4:
        t += 1
    if -3 <= bias6 <= 8:
        t += 1
    if plateau_days >= 20:
        t += 2
    elif plateau_days and plateau_days < 5:
        t -= 2
    # 换手率
    turnover = _num(cand.get("turnover"))
    if 3 <= turnover <= 12:
        t += 4
    elif 12 < turnover <= float(cfg["turnMax"]):
        t += 2
    elif turnover < float(cfg["turnMin"]):
        risks.append(("换手" + "过低" + f"{turnover:.1f}%"))
    else:
        risks.append(("换手" + "过高" + f"{turnover:.1f}%"))
    sc += max(-2, min(15, t))
    # ⑥ 风险扣分（hard×8 / warn×3，结构化风险码）
    risk_codes = _risk_codes_of(risks)
    n_hard_risk = n_warn_risk = 0
    for _rc in risk_codes:
        if _rc in _WARN_RISK_CODES:
            n_warn_risk += 1
        else:
            n_hard_risk += 1
    sc -= n_hard_risk * 8 + n_warn_risk * 3
    # ⑦ 无启动确认（小阳不算）：异动/回踩/首板/走多一个都没有 → 强扣
    if not (patterns.get("pullback") or patterns.get("pullback2") or patterns.get("surgeStart")
            or patterns.get("surgePullback")
            or patterns.get("baseUp") or patterns.get("macdFirstRed") or patterns.get("firstBoardRight")
            or patterns.get("steadyUp") or patterns.get("washOut") or patterns.get("firstWeek")
            or patterns.get("strongMom") or patterns.get("tightZt")):
        sc -= 6
    # ⑧ 动量修正
    if bias_over:
        sc -= 4
    if amp20 and amp20 > 35:
        sc -= 3
    sc += _mom_bonus
    # ⑨ 路径三轴修正：下坡重扣；右侧途中+股性活跃轻加
    if _path["downSlope"]:
        sc -= 12
    elif not _path["pathOk"]:
        sc -= 6
    if _path["activeOk"]:
        sc += 3
    elif _path["activityScore"] < 30:
        sc -= 3
    return {
        "closes": c, "opens": o, "highs": h, "lows": l, "vols": v,
        "ma5": ma5, "ma10": ma10, "ma20": ma20, "ma60": ma60, "ma20_3": ma20_3,
        "dif": dif, "dea": dea, "hist": hist,
        "pos": pos, "chg1": chg1, "chg5": chg5, "chg10": chg10,
        "chg20": chg20, "chg60": chg60, "volRatio": vol_ratio,
        "vol5v20": vol5v20, "upDays": up_days,
        "patterns": patterns, "risks": risks, "riskCodes": risk_codes,
        "score": max(0, min(100, int(round(sc)))),
        "surgeDaysAgo": surge_days_ago, "surgePullbackDays": surge_pb_days,
        "pullback2Days": pb2_days, "spread": spread,
        "eventDays": ev_days,
        "washoutDays": washout_days,
        "macdFirstRedDays": gc_days - 1,
        "scarcity": scarcity, "scarcityTags": scar_tags, "floatRatio": round(float_ratio, 4),
        "levels": {"s1": s1, "s2": s2, "p1": p1, "p2": p2, "stop": stop},
        "closePos": round(close_pos, 2), "odds1": round(odds1, 2), "odds2": round(odds2, 2), "oddsUse": round(odds_use, 2),
        "kwHits": kw_hits, "hot": bool(cand.get("hot")),
        "hotName": cand.get("hotName") or "", "fund": fund,
        "ind": cand.get("ind") or "",
        # 新增因子
        "rsi14": rsi14, "boll_pos": boll_pos, "boll_width": boll_width,
        "atr_pct": atr_pct, "bias6": bias6, "bias12": bias12,
        "atrPctRank": atr_prof["atr_pct_rank"], "volRank20": vol_rank20,
        "volRegime": atr_prof["vol_regime"], "macdUnderwater": macd_underwater,
        "pullbackType": pullbackType, "pullbackDays": pb2_days,
        "pullbackDepthAtr": pullbackDepthAtr, "pullbackDepthPct": pullbackDepthPct,
        "limitQuality": lq.get("limitQuality"), "limitQualityScore": lq.get("limitQualityScore"),
        "tradability": lq.get("tradability"), "qualityConfidence": lq.get("qualityConfidence"),
        "trendScore": _su["trendScore"], "steadyUpParts": _su["parts"],
        "ma_bull": ma_bull, "ma_bull3": ma_bull3, "gc_days": gc_days,
        "ma_tier": ma_tier, "ma_tier_label": TIER_LABEL.get(ma_tier, ""),
        "above_ma60": bool(above_ma60),
        "above_ma144": bool(above_ma144),
        "ma60_strong": bool(ma60_strong),
        "ma60_strong_days": int(ma60_strong_days),
        "daysSinceZt": (int(last - zt_day) if zt_day >= 0 else None),
        "ma30": ma30, "ma144": ma144,
        "leaderOk": leader_ok,
        "tightZtMeta": tight_zt_meta,
        "momScore": mom["momScore"], "momParts": mom["momParts"],
        "strongMom": bool(mom["strongMom"]), "momTags": mom["momTags"],
        "pe": pe, "pb": pb, "mcap": mcap,
        # 第一批安全因子
        "volShrink": vol_shrink, "newHighWeak": new_high_weak, "atHighWeak": at_high_weak,
        "volHealth": vol_health, "biasMa5": round(bias_ma5, 1), "biasMa20": round(bias_ma20, 1),
        "biasOver": bias_over, "plateauDays": plateau_days, "amp20": round(amp20, 1),
        "weekPos": wk["weekPos"] if wk else None,
        "weekConfirm": bool(wk and wk["weekConfirm"]),
        "weekMacdOk": bool(wk and wk["weekMacdOk"]),
        "weekMaOk": bool(wk and wk["weekMaOk"]),
        "weekVolOk": bool(wk and wk["weekVolOk"]),
        "weekVolRatio": round(wk["weekVolRatio"], 2) if wk else None,
        "weekBars": wk["weekBars"] if wk else 0,
        "fundStreak": fund_streak,
        # 路径三轴（右侧上涨途中 / 股性活跃 / 禁下坡）
        "downSlope": bool(_path["downSlope"]),
        "pathOk": bool(_path["pathOk"]),
        "midUpOk": bool(_path["midUpOk"]),
        "activityScore": int(_path["activityScore"]),
        "activeOk": bool(_path["activeOk"]),
        "slopePct20": _path["slopePct20"],
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
    _dn_th = _down_threshold(str(cand.get("code") or ""))
    for i in range(max(1, n - 10), last + 1):
        p0 = (c[i] / c[i - 1] - 1) * 100 if c[i - 1] > 0 else 0.0
        if p0 <= _dn_th + 0.5:
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
    _rc = set(a.get("riskCodes") or _risk_codes_of(a.get("risks") or []))
    if "pb_break" in _rc:
        hard("板后破位(跌破板日低点/板后长阴)")
    elif any(x in _rc for x in ("upper_shadow", "ljdv_div", "surge_unconf")):
        _warn_text = {
            "upper_shadow": "长上影滞涨",
            "ljdv_div": "量价背离(3日缩量上涨)",
            "surge_unconf": "底部异动后未确认企稳",
        }
        for _code in ("upper_shadow", "ljdv_div", "surge_unconf"):
            if _code in _rc:
                warn(_warn_text[_code])
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

# 警示消息：降权并展示（减持已拆分为 _jc_flag 分级：进行时/计划=硬伤，落地=警示）
_NEWS_WARN = ["解禁", "质押", "冻结", "问询", "关注函", "警示函", "监管函",
              "预亏", "业绩预减", "业绩下滑", "商誉减值", "诉讼", "仲裁", "终止",
              "违规", "通报批评", "公开谴责", "亏损", "担保", "协议转让", "离任", "出售控股子公司"]

# 减持公告分级：进行时/计划=硬伤排除；落地（完毕/届满/过半）=警示；否定承诺=中性
_JC_NEG = ("承诺不减持", "不减持", "未减持", "无减持", "未发生减持", "暂停减持",
           "终止减持", "终止股份减持计划", "提前终止", "取消减持", "减持计划终止")
_JC_DONE = ("减持完成", "减持完毕", "实施完成", "实施结果", "减持结果", "减持股份结果",
            "减持计划到期", "减持期限届满", "实施完毕", "时间过半", "数量过半",
            "减持计划实施完毕", "减持计划实施完成", "减持计划期限届满")
_JC_HARD = ("拟减持", "减持计划", "减持进展", "减持股份", "股东减持", "大股东减持",
            "控股股东减持", "高管减持", "董事减持", "监事减持", "减持比例",
            "集中竞价减持", "大宗交易减持", "累计减持", "减持数量", "被动减持", "减持期间")


def _jc_flag(t: str) -> str | None:
    """减持公告分级：hard 硬伤排除 / warn 落地警示 / None 中性（否定承诺）。"""
    if any(k in t for k in _JC_NEG):
        return None
    if any(k in t for k in _JC_DONE):
        return "warn"
    if any(k in t for k in _JC_HARD) or "减持" in t:
        return "hard"
    return None


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
    ok = False
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
        ok = True
    except Exception:
        fin = None
    if ok:
        _FIN_CACHE[code] = (_today8(), fin)
    return fin


async def _fetch_news_ann(code: str) -> list[str]:
    """东财 F10 公告标题（近 30 条），用于负面消息排查。"""
    hit = _NEWS_CACHE.get(code)
    if hit and hit[0] == _today8():
        return hit[1]
    titles: list[str] = []
    ok = False
    try:
        url = ("https://np-anotice-stock.eastmoney.com/api/security/ann?sr=-1&page_size=30&page_index=1"
               "&ann_type=A&client_source=web&stock_list=" + code)
        async with httpx.AsyncClient(timeout=12.0, headers=_UA) as cli:
            j = (await cli.get(url)).json()
        data = j.get("data") or {}
        titles = [str(it.get("title") or "") for it in (data.get("list") or [])]
        ok = True
    except Exception:
        titles = []
    if ok:
        _NEWS_CACHE[code] = (_today8(), titles)
    return titles


# 东财限售解禁日历（RPT_LIFT_STAGE）：独立于公告标题的解禁台账，日缓存 + 温和限流
_UNLOCK_CACHE: dict[str, tuple[str, list[dict[str, Any]]]] = {}
_EM_DC_GATE = _RateGate(min_interval_s=0.15, max_per_minute=90)
# 全市场未来 120 天解禁批量表（日缓存）：一次拉齐全部 A 股解禁事件，逐候选查表零上游成本
_UNLOCK_MAP: dict[str, dict[str, list[dict[str, Any]]] | None] = {}
_UNLOCK_MAP_INFLIGHT: asyncio.Task | None = None


async def _fetch_unlock_map() -> dict[str, list[dict[str, Any]]] | None:
    """批量拉取未来约 120 天全市场解禁事件，按代码建索引（日缓存，2 页请求封顶）。

    供 _fetch_unlock 优先查表——逐股请求 datacenter-web 只在 aiTop 候选上执行，
    主推/备选兜底池的候选会漏检「临近大规模解禁」（三协电机 920100 案例：
    9/8 解禁 2.77%·28.3 亿仍进北证主线主推）。返回 None 表示拉取失败（回退逐股接口）。
    """
    today_s = time.strftime("%Y-%m-%d")
    if today_s in _UNLOCK_MAP:
        return _UNLOCK_MAP[today_s]
    global _UNLOCK_MAP_INFLIGHT
    if _UNLOCK_MAP_INFLIGHT is not None and not _UNLOCK_MAP_INFLIGHT.done():
        try:
            await _UNLOCK_MAP_INFLIGHT
        except Exception:
            pass
        return _UNLOCK_MAP.get(today_s)

    async def _do() -> None:
        out: dict[str, list[dict[str, Any]]] = {}
        try:
            end_s = (datetime.date.today() + datetime.timedelta(days=125)).isoformat()
            base = ("https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_LIFT_STAGE"
                    "&columns=SECURITY_CODE,SECURITY_NAME_ABBR,FREE_DATE,LIFT_MARKET_CAP,FREE_RATIO,"
                    "TOTAL_RATIO,FREE_SHARES_TYPE,BATCH_HOLDER_NUM"
                    "&filter=(FREE_DATE%3E%3D%27" + today_s + "%27)(FREE_DATE%3C%3D%27" + end_s + "%27)"
                    "&source=WEB&client=WEB&pageNumber=1&pageSize=500&sortColumns=FREE_DATE&sortTypes=1")
            for page in range(1, 4):
                await _EM_DC_GATE.acquire()
                async with httpx.AsyncClient(timeout=12.0, headers=_UA) as cli:
                    j = (await cli.get(base.replace("pageNumber=1", "pageNumber=%d" % page))).json()
                rows = ((j.get("result") or {}).get("data")) or []
                if not rows:
                    break
                for r in rows:
                    code = str(r.get("SECURITY_CODE") or "")
                    fd = str(r.get("FREE_DATE") or "")[:10]
                    if not code or not fd:
                        continue
                    out.setdefault(code, []).append({
                        "date": fd,
                        "ratio": _num(r.get("FREE_RATIO")),
                        "capWan": _num(r.get("LIFT_MARKET_CAP")),
                        "type": str(r.get("FREE_SHARES_TYPE") or ""),
                        "holders": int(_num(r.get("BATCH_HOLDER_NUM"))),
                    })
            for v in out.values():
                v.sort(key=lambda x: x["date"])
            _UNLOCK_MAP[today_s] = out
        except Exception:
            _UNLOCK_MAP[today_s] = None

    t = asyncio.ensure_future(_do())
    _UNLOCK_MAP_INFLIGHT = t
    try:
        await t
    finally:
        _UNLOCK_MAP_INFLIGHT = None
    return _UNLOCK_MAP.get(today_s)


async def _fetch_unlock(code: str) -> list[dict[str, Any]]:
    """东财解禁日历：该股未来解禁事件（解禁日/市值/占流通盘比例）。

    优先当日批量解禁表（全市场一次拉齐，逐候选零上游成本）；批量表拉取失败
    才回退逐股接口；失败结果不写日缓存，避免瞬时故障污染全天（漏检解禁硬伤）。
    """
    hit = _UNLOCK_CACHE.get(code)
    if hit and hit[0] == _today8():
        return hit[1]
    try:
        _m = await _fetch_unlock_map()
        if isinstance(_m, dict):
            _evts = _m.get(code) or []
            _UNLOCK_CACHE[code] = (_today8(), _evts)
            return _evts
    except Exception:
        pass
    out: list[dict[str, Any]] = []
    ok = False
    try:
        url = ("https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_LIFT_STAGE"
               "&columns=SECURITY_CODE,SECURITY_NAME_ABBR,FREE_DATE,LIFT_MARKET_CAP,FREE_RATIO,"
               "TOTAL_RATIO,FREE_SHARES_TYPE,BATCH_HOLDER_NUM"
               "&filter=(SECURITY_CODE%3D%22" + code + "%22)&source=WEB&client=WEB"
               "&pageNumber=1&pageSize=20&sortColumns=FREE_DATE&sortTypes=1")
        await _EM_DC_GATE.acquire()
        async with httpx.AsyncClient(timeout=12.0, headers=_UA) as cli:
            j = (await cli.get(url)).json()
        rows = ((j.get("result") or {}).get("data")) or []
        today_s = time.strftime("%Y-%m-%d")
        for r in rows:
            fd = str(r.get("FREE_DATE") or "")[:10]
            if not fd or fd < today_s:
                continue
            out.append({
                "date": fd,
                "ratio": _num(r.get("FREE_RATIO")),
                "capWan": _num(r.get("LIFT_MARKET_CAP")),
                "type": str(r.get("FREE_SHARES_TYPE") or ""),
                "holders": int(_num(r.get("BATCH_HOLDER_NUM"))),
            })
        out.sort(key=lambda x: x["date"])
        ok = True
    except Exception:
        out = []
    if ok:
        _UNLOCK_CACHE[code] = (_today8(), out)
    return out


def _unlock_grade(unlocks: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    """解禁日历分级：未来120天内解禁且占流通≥2%=硬伤排除（最近解禁一律剔除，含小比例）；
    120天内极小解禁（<2%）=警示降权；更远期解禁不纳入（超出波段持仓周期）。"""
    hard: list[str] = []
    warn: list[str] = []
    today_s = time.strftime("%Y-%m-%d")
    for u in unlocks:
        fd = u.get("date") or ""
        try:
            days = (datetime.date.fromisoformat(fd) - datetime.date.fromisoformat(today_s)).days
        except Exception:
            days = 999
        # 东财 FREE_RATIO 单位即百分比（如 2.7715 = 占流通 2.77%，非小数）
        ratio = float(u.get("ratio") or 0)
        cap_yi = float(u.get("capWan") or 0) / 10000.0
        tag = f"{fd}解禁{cap_yi:.1f}亿·占流通{ratio:.1f}%"
        if days <= 120 and ratio >= 2.0:
            hard.append(tag)
        elif days <= 120:
            warn.append(tag)
    return hard[:2], warn[:2]


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
    unlock_task = asyncio.create_task(_fetch_unlock(c["code"]))
    fin = await fin_task
    titles = await news_task
    unlocks = await unlock_task
    jc_hard = [t for t in titles if _jc_flag(t) == "hard"][:2]
    jc_warn = [t for t in titles if _jc_flag(t) == "warn"][:2]
    unlock_hard, unlock_warn = _unlock_grade(unlocks)
    news_hard = list(dict.fromkeys(
        [t for t in titles if any(k in t for k in _NEWS_HARD)] + jc_hard + unlock_hard
    ))[:4]
    base_warn = [
        t for t in titles
        if not any(k in t for k in _NEWS_HARD) and _jc_flag(t) != "hard"
        and (any(k in t for k in _NEWS_WARN) or _jc_flag(t) == "warn")
    ]
    news_warn = list(dict.fromkeys(base_warn + unlock_warn))[:5]
    # 组合升级：解禁警示 + 消息面警示（问询/离任/质押等）→ 硬伤（多重利空叠加）
    if unlock_warn and base_warn:
        combo = "解禁临近叠加消息面利空"
        if combo not in news_hard:
            news_hard = (news_hard + [combo])[:4]
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
        # 无主线 / 仅观察命中：文案改为「重点观察代表」，避免电风扇日仍写「主线代表」
        _period = (
            "重点观察代表 · 波段跟踪 1~4周"
            if (pick.get("obsHit") and not pick.get("mainHit"))
            else "主线代表 · 趋势波段 2~8周"
        )
        return {
            "period": _period,
            "entry": f"回踩参考区间 MA5/MA10（{lo:.2f}~{hi:.2f}）",
            "stop": f"{stop:.2f}（下方破位参考）",
            "target1": f"{p1:.2f}（近10日压力）",
            "target2": f"{t2:.2f}" + ("（保守参考）" if t2 < lv.get("p2", 0) else "（60日压力）"),
            "position": "",
            "conditions": "观察：站稳MA10且MACD红柱延续、主力持续净流入；风险信号：冲高放量滞涨、跌破MA5、收盘破MA10或单日放量长阴-8%",
            "rules": "注意：高开>5%或冲高回落破分时均线时谨慎；回踩缩量（量≤启动日70%）形态更稳；单日放量长阴-8%注意风险",
        }
    period_txt = {"catchup": "补涨观察 · 区间波段 2~8周"}.get(role, "中线波段 · 2~8周")
    return {
        "period": period_txt,
        "entry": f"回踩参考区间 {entry_lo:.2f}~{entry_hi:.2f}",
        "stop": f"{stop:.2f}（下方破位参考）",
        "target1": f"{p1:.2f}（近10日压力）",
        "target2": f"{t2:.2f}" + ("（保守参考）" if t2 < lv.get("p2", 0) else "（60日压力）"),
        "position": "",
        "conditions": "观察：站稳MA20且MACD红柱持续；风险信号：放量滞涨、跌破MA5、破参考位或单日放量长阴-8%",
        "rules": "关注点：高开>5%或冲高回落破分时均线时保持谨慎；回踩缩量（量≤启动日70%）形态更稳；单日放量长阴-8%注意风险",
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
    """先看标的异动 → 反推热门主线题材（优先按 f128 概念聚合，行业名兜底）。

    题材主线（PCB/液冷/算力/机器人等）比东财行业名更能反映资金主线；
    北证 f128 概念字段大量为 "-"，用 f100 行业名兜底，避免题材主线漏判。
    2026-08-18 P0-2：桶名归一化（煤炭开采/煤炭/焦煤 → 煤炭），避免主线被拆桶稀释；
    P1-1：命中率归一化 + 形态加权排序分，防大板块绝对容量占优。
    """
    buckets: dict[str, dict[str, Any]] = {}
    # 第一遍：全部候选 → 桶归属（total_cands，含未命中形态者；每股票每桶只计一次）
    for c in cands:
        names = [str(x).strip() for x in (c.get("concepts") or [])
                 if str(x).strip() and str(x).strip() != "-"]
        if not names:
            ind = str(c.get("ind") or "").strip()
            if ind and ind != "-":
                names = [ind]
            else:
                continue
        seen: set[str] = set()
        for nm in names:
            bkey = _bucket_norm(nm)
            if not bkey or bkey in seen:
                continue
            seen.add(bkey)
            b = buckets.setdefault(bkey, {"name": bkey, "count": 0, "wcount": 0.0,
                                         "amount": 0.0, "stocks": [], "total_cands": 0,
                                         "hit_rate": 0.0, "rank_score": 0.0,
                                         "hot": False, "hot_name": "", "orig": set()})
            b["total_cands"] += 1
            b["orig"].add(nm)
    # 第二遍：有形态候选 → 异动家数/加权分/成交额/代表（形态权重：强形态 1.0、pullback 0.8、弱形态 0.6）
    for c in cands:
        a = c.get("A") or {}
        p = a.get("patterns") or {}
        w = 0.0
        if p.get("surgeStart") or p.get("pullback2") or p.get("ztPullback") or p.get("firstBoardRight"):
            w = 1.0
        elif p.get("pullback"):
            w = 0.8
        elif p.get("smallYang") or p.get("baseUp"):
            w = 0.6
        if w <= 0:
            continue
        # P0-1 主线去滞后：增量动量加权——事件越新、今日越强、量能越活，权重越高，
        # 避免“涨过一波/资金已流入后才反推”的滞后主线占据前列。
        fresh = 1.0
        _ev = a.get("eventDays")
        if _ev is not None:
            if _ev <= 3:
                fresh = 1.4
            elif _ev <= 6:
                fresh = 1.15
            else:
                fresh = 0.8
        if (a.get("chg1") or 0) >= 4:
            fresh *= 1.15   # 今日续强（新增异动当天）
        if (a.get("volRatio") or 0) >= 1.5:
            fresh *= 1.1    # 放量拐头
        w = w * fresh
        names = [str(x).strip() for x in (c.get("concepts") or [])
                 if str(x).strip() and str(x).strip() != "-"]
        if not names:
            ind = str(c.get("ind") or "").strip()
            if ind and ind != "-":
                names = [ind]
            else:
                continue
        seen = set()
        for nm in names:
            bkey = _bucket_norm(nm)
            if not bkey or bkey in seen:
                continue
            seen.add(bkey)
            b = buckets[bkey]
            b["count"] += 1
            b["wcount"] += w
            b["amount"] += _num(c.get("amount"))
            if len(b["stocks"]) < 8 and c.get("name"):
                b["stocks"].append(str(c["name"]))
    items = list(buckets.values())
    for it in items:
        # 命中率归一化 + 形态加权排序分（P1-1）：展示 count 仍为整数异动家数，排序用 rank_score
        it["hit_rate"] = (it["count"] / it["total_cands"]) if it["total_cands"] else 0.0
        it["rank_score"] = it["wcount"] * (1 + min(it["hit_rate"], 1.0) * 0.5)
        hn = board_hit(it["name"], hot)
        if not hn:
            for _on in list(it["orig"])[:6]:
                hn = board_hit(_on, hot)
                if hn:
                    break
        it["hot"] = bool(hn)
        it["hot_name"] = hn
        it.pop("orig", None)
    items.sort(key=lambda x: (-x["rank_score"], 0 if x["hot"] else 1, -x["amount"]))
    return items[:12]


# ---------------- 单票快照（AI 综合分 / 风险标签，服务端同口径） ----------------

# ---------------- 板块排行（王者 1 + 辅线 2 + 备选 N） ----------------

def _board_rank(mainlines: list[dict[str, Any]], hot_boards: list[dict[str, Any]], keep_backup: int = 3) -> list[dict[str, Any]]:
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
            "ths": bk_to_ths_secid(str(it.get("secid") or "")) or "",
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


async def _fetch_mainline_funds(secids: list[str]) -> dict[str, dict[str, Any]]:
    """批量拉主线板块真实资金（东财 ulist.np，板块级 f62/f164/f3/f109）。"""
    secids = [str(s or "").strip() for s in (secids or []) if str(s or "").strip()]
    if not secids:
        return {}
    out: dict[str, dict[str, Any]] = {}
    try:
        j = await _em_get_json("/api/qt/ulist.np/get", {
            "secids": ",".join(secids),
            "fields": "f12,f14,f62,f164,f3,f109",
            "fltt": 2, "invt": 2,
        }) or {}
    except Exception:
        return out
    for r in ((j.get("data") or {}).get("diff") or []):
        sid = "90." + str(r.get("f12") or "")
        if sid not in secids:
            continue
        out[sid] = {
            "name": str(r.get("f14") or "").strip(),
            "f62": float(r.get("f62") or 0),
            "f164": float(r.get("f164") or 0),
            "p5": _num(r.get("f109")) if r.get("f109") is not None else None,
            "pct": _num(r.get("f3")) if r.get("f3") is not None else None,
        }
    return out


async def _fetch_stock_quotes(codes: list[str]) -> dict[str, dict[str, Any]]:
    """批量拉个股实时行情（东财 ulist.np，按代码聚合 f3/f6/f8/f20/f62/f164）。
    用于主线板块静态龙头兜底：板块 secid 解不出/上游成分拉取失败时，代表股也要有真实涨跌。"""
    codes = [str(c or "").strip() for c in (codes or []) if re.fullmatch(r"\d{6}", str(c or ""))]
    if not codes:
        return {}
    out: dict[str, dict[str, Any]] = {}
    try:
        j = await _em_get_json("/api/qt/ulist.np/get", {
            "secids": ",".join(_stock_secid(c) for c in codes),
            "fields": "f12,f14,f2,f3,f6,f8,f20,f62,f164",
            "fltt": 2, "invt": 2,
        }) or {}
    except Exception:
        return out
    for r in ((j.get("data") or {}).get("diff") or []):
        code = str(r.get("f12") or "")
        if not re.fullmatch(r"\d{6}", code):
            continue
        # fltt=2：现价 f2 / 涨跌幅 f3 已是小数口径，勿再 /100
        _px = r.get("f2")
        out[code] = {
            "code": code,
            "name": str(r.get("f14") or ""),
            "price": _num(_px) if _px is not None else None,
            "pct": _num(r.get("f3")) if r.get("f3") is not None else None,
            "amount": _num(r.get("f6")),
            "mcap": _num(r.get("f20")),
            "turnover": _num(r.get("f8")),
            "fund": _num(r.get("f62")),
            "fund5": _num(r.get("f164")),
        }
    return out


_LEADER_Q_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_LEADER_Q_TTL = 60.0


async def _backfill_board_funds(payload: dict[str, Any]) -> dict[str, Any]:
    """板块排行缺资金/涨幅时补拉（归档补主线常 f62=f164=0 且无 secid）。

    典型场景：复盘新锁定主线（如军工）不在当日掘金资金热度池 → _build_mainline_rank_items
    零上游合成条目；本函数在出站时一次批量补齐，不写归档。
    """
    try:
        if not isinstance(payload, dict):
            return payload
        rank = payload.get("board_rank")
        if not isinstance(rank, list) or not rank:
            return payload

        async def _resolve_sid(nm: str) -> str:
            nm = str(nm or "").strip()
            if not nm:
                return ""
            sid = (_MAINLINE_BOARD_MAP.get(nm) or [""])[0] if _MAINLINE_BOARD_MAP.get(nm) else ""
            if not sid:
                sid = _MAINLINE_SECID_FALLBACK.get(nm) or ""
            if not sid:
                try:
                    sid = await _resolve_board_secid(nm) or ""
                except Exception:
                    sid = ""
            return sid

        need: list[dict[str, Any]] = []
        for b in rank:
            if not isinstance(b, dict):
                continue
            sid = str(b.get("secid") or "").strip()
            if not sid:
                sid = await _resolve_sid(str(b.get("name") or ""))
                if sid:
                    b["secid"] = sid
                    if not str(b.get("ths") or "").strip():
                        b["ths"] = bk_to_ths_secid(sid) or ""
            if not sid:
                continue
            f62 = abs(float(b.get("f62") or 0))
            f164 = abs(float(b.get("f164") or 0))
            # 任一缺失都要补拉：常见于「今日有、5日无」的归档判定补丁（如军工）
            miss_fund = f62 < 1e5 or f164 < 1e5
            miss_px = b.get("p5") is None or b.get("pct") is None
            if miss_fund or miss_px:
                need.append(b)
        if not need:
            return payload
        funds = await _fetch_mainline_funds([str(b.get("secid") or "") for b in need])
        for b in need:
            q = funds.get(str(b.get("secid") or ""))
            if not q:
                continue
            if abs(float(b.get("f62") or 0)) < 1e5 and q.get("f62") is not None:
                b["f62"] = q.get("f62")
            if abs(float(b.get("f164") or 0)) < 1e5 and q.get("f164") is not None:
                b["f164"] = q.get("f164")
            if b.get("p5") is None and q.get("p5") is not None:
                b["p5"] = q.get("p5")
            if b.get("pct") is None and q.get("pct") is not None:
                b["pct"] = q.get("pct")
        return payload
    except Exception:
        return payload


async def _backfill_leader_quotes(payload: dict[str, Any]) -> dict[str, Any]:
    """板块排行代表 / MACD首红卡片缺价或缺涨跌时，用实时行情补一次（带 60s 缓存）。

    旧归档/静态龙头兜底（如 AI服务器算力 走 SECTORS 静态代表、上游失败时 pct 为 null）
    会让「代表：xxx」无涨跌幅可显示；MACD 复盘样本补齐条目通常无 price，也在此补齐。
    同时补主线板块缺失的今日/5日主力（见 _backfill_board_funds）。
    不改写归档与扫描缓存。
    """
    try:
        payload = await _backfill_board_funds(payload)
        if not isinstance(payload, dict):
            return payload
        miss: list[tuple[dict[str, Any], str]] = []
        now0 = time.time()
        _q_keys = ("price", "pct", "amount", "mcap", "turnover", "fund", "fund5", "name")

        def _need_quote(row: dict[str, Any]) -> bool:
            pct = row.get("pct")
            pct_miss = pct is None or (isinstance(pct, str) and not str(pct).strip())
            code = str(row.get("code") or "").strip()
            name = str(row.get("name") or "").strip()
            name_miss = (not name) or (name == code)
            return row.get("price") is None or pct_miss or name_miss

        def _apply_cache_or_miss(row: dict[str, Any]) -> None:
            code = str(row.get("code") or "")
            if not re.fullmatch(r"\d{6}", code):
                return
            if not _need_quote(row):
                return
            hit = _LEADER_Q_CACHE.get(code)
            if hit and now0 - hit[0] < _LEADER_Q_TTL:
                for _k in _q_keys:
                    if _k == "name":
                        _nm = str(row.get("name") or "").strip()
                        if (not _nm or _nm == code) and hit[1].get("name"):
                            row["name"] = hit[1]["name"]
                        continue
                    if row.get(_k) is None and _k in hit[1] and hit[1][_k] is not None:
                        row[_k] = hit[1][_k]
                if not _need_quote(row):
                    return
            miss.append((row, code))

        rank = payload.get("board_rank")
        if isinstance(rank, list):
            for b in rank:
                if not isinstance(b, dict):
                    continue
                for ld in (b.get("leaders") or []):
                    if isinstance(ld, dict):
                        _apply_cache_or_miss(ld)
        for m in (payload.get("macd_reds") or []):
            if isinstance(m, dict):
                _apply_cache_or_miss(m)
        for m in (payload.get("picks") or []) + (payload.get("runners") or []):
            if isinstance(m, dict):
                _apply_cache_or_miss(m)

        if miss:
            codes = list(dict.fromkeys(c for _, c in miss))
            qmap = await _fetch_stock_quotes(codes)
            now1 = time.time()
            for _c in codes:
                if _c in qmap:
                    _LEADER_Q_CACHE[_c] = (now1, qmap[_c])
            for row, code in miss:
                q = qmap.get(code)
                if not q:
                    continue
                for _k in _q_keys:
                    if row.get(_k) is None and _k in q and q[_k] is not None:
                        row[_k] = q[_k]
        return payload
    except Exception:
        return payload


def _board_rank_funds(
    boards: list[dict[str, Any]],
    keep_backup: int = 3,
    mainline_names: list[str] | None = None,
    market: str = "",
    observe_names: list[str] | None = None,
) -> list[dict[str, Any]]:
    """全市场板块排行：复盘主线优先；无主线时重点观察优先；其余按 5日主力净流入，王者 1 + 辅线 2 + 备选 N。"""
    items = sorted((boards or []), key=lambda x: -float(x.get("f164") or 0))
    _ml: set[str] = set()
    _ml_order: dict[str, int] = {}
    _ml_aliases: set[str] = set()
    _obs: set[str] = set()
    _obs_order: dict[str, int] = {}
    if mainline_names:
        try:
            from .daily_report import SECTOR_BOARD_ALIASES as _SBA
            for _i, _n in enumerate(mainline_names):
                _n0 = str(_n or "").strip()
                if not _n0:
                    continue
                _ml.add(_n0.replace(" ", ""))
                _ml_order.setdefault(_n0.replace(" ", ""), _i)
                for _a in (_SBA.get(_n0) or [_n0]):
                    if _a:
                        _ml_aliases.add(str(_a).replace(" ", ""))
        except Exception:
            _ml = {str(n).replace(" ", "") for n in mainline_names if str(n).strip()}
            _ml_order = {str(n).replace(" ", ""): i for i, n in enumerate(mainline_names) if str(n).strip()}
        if _ml:
            # 主线按复盘顺序（第 1 个 = 主线 king，其余 = 重点关注 key），非主线按资金靠后
            items.sort(key=lambda x: (
                _ml_order.get(str(x.get("name") or "").replace(" ", ""), 99),
                -float(x.get("f164") or 0),
            ))
    elif observe_names:
        # 无主线：观察板块前置，避免资金热度独占 king/key
        for _i, _n in enumerate(observe_names):
            _n0 = str(_n or "").strip().replace(" ", "")
            if _n0:
                _obs.add(_n0)
                _obs_order.setdefault(_n0, _i)
        if _obs:
            items.sort(key=lambda x: (
                _obs_order.get(str(x.get("name") or "").replace(" ", ""), 99),
                -float(x.get("f164") or 0),
            ))
    tiers = ["king", "key", "key"] + ["backup"] * max(0, keep_backup)
    rank: list[dict[str, Any]] = []
    pos = 0
    for b in items:
        if pos >= len(tiers):
            break
        _bn = str(b.get("name") or "").replace(" ", "")
        # 主线别名重复（如 创新药/医药生物 属 创新药CXO）不入榜，避免“同名不同叫法”混乱
        if _bn not in _ml and _bn in _ml_aliases:
            continue
        _lds = list(b.get("leaders") or [])
        # P1-5：科创榜代表股按市场过滤（kc 只留 30/688），避免与栏目错位（如科创榜显示沪主板煤炭龙头）
        if market == "kc" and _lds:
            _kc_lds = [x for x in _lds if str((x or {}).get("code") or "").startswith(("30", "688"))]
            if _kc_lds:
                _lds = _kc_lds
            else:
                _lds = []
        _is_obs = (not _ml) and (_bn in _obs or bool(b.get("observe")))
        rank.append({
            "name": str(b.get("name") or ""),
            "secid": str(b.get("secid") or ""),
            "ths": bk_to_ths_secid(str(b.get("secid") or "")) or "",
            "count": None,
            "amount": None,
            "f62": float(b.get("f62") or 0),
            "f164": float(b.get("f164") or 0),
            "p5": b.get("p5"),
            "pct": b.get("pct"),
            "hot": True,
            "hot_name": "",
            "kind": str(b.get("kind") or "industry"),
            "leaders": _lds,
            "mainline": bool(b.get("mainline") or (_bn in _ml)) if _ml else bool(b.get("mainline")),
            "observe": _is_obs or bool(b.get("observe")),
            "tier": tiers[pos],
        })
        pos += 1
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


def _stock_secid(code: str) -> str:
    """个股代码 → 正确市场 secid：沪 1.、深/北 0.；北交所代码由 secid_to_tencent_symbol 按码段识别。"""
    c = str(code or "").strip()
    if c[:1] in ("6", "9", "5"):
        return "1." + c
    return "0." + c


_NAME_CACHE: dict[str, str] = {}


def _tencent_symbol(code6: str) -> str:
    c = str(code6 or "").zfill(6)
    if c.startswith(("5", "6", "9")):
        return "sh" + c
    if _is_bj_code6(c):
        return "bj" + c
    return "sz" + c


def _resolve_stock_names(codes: list[str]) -> dict[str, str]:
    """批量补股票简称（腾讯行情，同步、短超时）。回放池常只有代码无名称时用。"""
    out: dict[str, str] = {}
    need: list[str] = []
    for c0 in codes or []:
        c = str(c0 or "").strip().zfill(6)
        if not re.fullmatch(r"\d{6}", c):
            continue
        hit = _NAME_CACHE.get(c)
        if hit:
            out[c] = hit
        else:
            need.append(c)
    if not need:
        return out
    # 去重保序，单次最多 40 只
    uniq = list(dict.fromkeys(need))[:40]
    try:
        import urllib.request
        q = ",".join(_tencent_symbol(c) for c in uniq)
        req = urllib.request.Request(
            "http://qt.gtimg.cn/q=" + q,
            headers={"User-Agent": "Mozilla/5.0", "Referer": "https://finance.qq.com/"},
        )
        raw = urllib.request.urlopen(req, timeout=4).read()
        try:
            text = raw.decode("gbk", errors="replace")
        except Exception:
            text = raw.decode("utf-8", errors="replace")
        for part in text.split(";"):
            part = part.strip()
            if not part or "~" not in part:
                continue
            # v_sz003030="51~祖名股份~003030~...
            try:
                body = part.split("=", 1)[1].strip().strip('"')
                fields = body.split("~")
                if len(fields) < 3:
                    continue
                name = str(fields[1] or "").strip()
                code = str(fields[2] or "").strip().zfill(6)
                if name and re.fullmatch(r"\d{6}", code) and name != code:
                    _NAME_CACHE[code] = name
                    out[code] = name
            except Exception:
                continue
    except Exception:
        pass
    return out


def _fill_missing_names(rows: list[dict[str, Any]] | None) -> None:
    """就地补全 name 为空或等于代码的条目。"""
    if not rows:
        return
    miss = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        code = str(r.get("code") or "").strip().zfill(6)
        name = str(r.get("name") or "").strip()
        if re.fullmatch(r"\d{6}", code) and (not name or name == code):
            miss.append(code)
    if not miss:
        return
    nmap = _resolve_stock_names(miss)
    for r in rows:
        if not isinstance(r, dict):
            continue
        code = str(r.get("code") or "").strip().zfill(6)
        name = str(r.get("name") or "").strip()
        if (not name or name == code) and code in nmap:
            r["name"] = nmap[code]

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
                _stock_secid(code), "day", count=180, timeout=8.0,
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



def _ma_tier_ok(c: dict[str, Any], *, min_tier: str = "A") -> bool:
    """主推大周期门：优先短均站上144（S/above_ma144）；不再用空档或仅 bull3 放行。"""
    a = c.get("A") or {}
    if a.get("above_ma144"):
        return True
    tier = str(a.get("ma_tier") or "")
    if not tier and a.get("ma60_strong") and a.get("above_ma60"):
        tier = "A"
    if not tier:
        return False
    return TIER_RANK.get(tier, 0) >= TIER_RANK.get(str(min_tier or "A").upper(), 2)


def _pick_zt_ok(c: dict[str, Any], *, max_days: int = 20) -> bool:
    """近期涨停基因：近 max_days 有涨停，或涨停相关形态。"""
    a = c.get("A") or {}
    p = a.get("patterns") or {}
    ds = a.get("daysSinceZt")
    if ds is not None:
        try:
            if 0 <= int(ds) <= int(max_days):
                return True
        except Exception:
            pass
    return bool(
        p.get("ztWeek") or p.get("firstWeek") or p.get("ztPullback")
        or p.get("tightZt") or p.get("firstBoardRight") or p.get("pullback2")
        or p.get("surgeStart")
    )


def _pick_ma144_ok(c: dict[str, Any]) -> bool:
    """优先门：短均站上 MA144（或趋势 S）。"""
    a = c.get("A") or {}
    if a.get("above_ma144"):
        return True
    return TIER_RANK.get(str(a.get("ma_tier") or ""), 0) >= TIER_RANK["S"]


def _pick_ma60_strong_ok(c: dict[str, Any]) -> bool:
    """次优门：短均远高于 MA60 且已持续一段时间。"""
    a = c.get("A") or {}
    if a.get("ma60_strong"):
        return True
    # 兼容：已有 A/S 且站上60（旧字段）
    if a.get("above_ma60") and TIER_RANK.get(str(a.get("ma_tier") or ""), 0) >= TIER_RANK["A"]:
        return True
    return False


def _pick_above60_ok(c: dict[str, Any]) -> bool:
    """底线门：短均站上 MA60（用户底线；不含仅 bull3）。"""
    a = c.get("A") or {}
    if a.get("above_ma60") or a.get("ma_bull"):
        return True
    return TIER_RANK.get(str(a.get("ma_tier") or ""), 0) >= TIER_RANK["A"]


def _pick_strong_gate(
    c: dict[str, Any],
    *,
    min_tier: str = "S",
    require_zt: bool = True,
    prefer_144: bool = True,
    allow_above60: bool = False,
) -> bool:
    """主推强势总门。prefer_144 / 远高于60 / 站上60（allow_above60）三档。"""
    if prefer_144:
        if not _pick_ma144_ok(c):
            return False
    elif allow_above60:
        if not (_pick_ma144_ok(c) or _pick_ma60_strong_ok(c) or _pick_above60_ok(c)):
            return False
    else:
        if not (_pick_ma144_ok(c) or _pick_ma60_strong_ok(c)):
            return False
    if require_zt:
        # 涨停池补入的热门票视为具备涨停基因
        if not (_pick_zt_ok(c) or c.get("zt_hot")):
            return False
    return True


def _filter_strong_picks(
    cands: list[dict[str, Any]],
    *,
    require_zt: bool = True,
) -> list[dict[str, Any]]:
    """主推门（严）：上144优先，否则远高于60持续；不含「仅站上60」。"""
    hard = [
        c for c in cands
        if _pick_strong_gate(c, min_tier="S", require_zt=require_zt, prefer_144=True)
    ]
    if hard:
        return hard
    return [
        c for c in cands
        if _pick_strong_gate(c, min_tier="A", require_zt=require_zt, prefer_144=False, allow_above60=False)
    ]


def _filter_watch_picks(
    cands: list[dict[str, Any]],
    *,
    exclude_codes: set[str] | None = None,
    require_zt: bool = True,
    limit: int = 6,
) -> list[dict[str, Any]]:
    """观察池（宽）：短均站上60 + 近期涨停/热门；不含已进主推者。"""
    ex = exclude_codes or set()
    out: list[dict[str, Any]] = []
    for c in cands:
        code = str(c.get("code") or "")
        if not code or code in ex:
            continue
        if not _pick_strong_gate(c, min_tier="A", require_zt=require_zt, prefer_144=False, allow_above60=True):
            continue
        # 观察池不要再塞已经能进主推严门的（避免重复）
        if _pick_ma144_ok(c) or _pick_ma60_strong_ok(c):
            continue
        out.append(c)
    out.sort(key=lambda x: (-_ma_tier_rank(x), -int(x.get("final") or 0)))
    return out[: max(0, int(limit))]


def build_decision(pick: dict[str, Any], *, lane: str = "pick") -> dict[str, Any]:
    """用户可见决策条：动作 / 失效 / 确认标签（避免运维黑话）。"""
    a = pick.get("A") or {}
    dual = bool(
        (a.get("above_ma144") or _pick_ma144_ok(pick))
        and (pick.get("zt_hot") or _pick_zt_ok(pick) or a.get("daysSinceZt") is not None)
    )
    if a.get("above_ma144") or _pick_ma144_ok(pick):
        trend = "短均站上中长期均线"
        action = "可跟踪，优先等回踩再考虑"
        invalid = "收盘跌破近端支撑，或单日放量长阴约 8%，建议先观望"
    elif a.get("ma60_strong") or _pick_ma60_strong_ok(pick):
        trend = "短均明显高于中期均线，且已持续一段时间"
        action = "可列入关注，回踩企稳后再看"
        invalid = "短均重新跌回中期均线下方，或放量滞涨，建议降级观望"
    else:
        trend = "短均刚站上中期均线"
        action = "仅观察，暂不作为重点"
        invalid = "重新跌回均线下方，或热度退潮，可移出观察"
    if lane == "watch":
        action = "观察池：确认站稳后再考虑，勿追高"
    if pick.get("mainHit"):
        confirm = "主线内强势"
    elif pick.get("zt_hot") or pick.get("hot"):
        confirm = "热门活跃"
    else:
        confirm = "结构达标"
    if dual:
        confirm = "热门强势·双确认"
    ds = a.get("daysSinceZt")
    zt_note = ""
    if ds is not None:
        try:
            dsi = int(ds)
            if dsi == 0:
                zt_note = "今日有过涨停表现"
            elif 0 < dsi <= 25:
                zt_note = f"近 {dsi} 日内有过涨停"
        except Exception:
            pass
    elif pick.get("zt_hot"):
        zt_note = "近期涨停活跃"
    return {
        "lane": "watch" if lane == "watch" else "pick",
        "laneLabel": "观察" if lane == "watch" else "精选",
        "action": action,
        "invalid": invalid,
        "trend": trend,
        "confirm": confirm,
        "dualConfirm": dual,
        "ztNote": zt_note,
        "algo": "strong-layer-v2",
    }


def _pick_strength_rank(c: dict[str, Any]) -> int:
    """排序用：上144 > 强60 > 站上60 > 其它。"""
    a = c.get("A") or {}
    if a.get("above_ma144") or TIER_RANK.get(str(a.get("ma_tier") or ""), 0) >= TIER_RANK["S"]:
        return 3
    if a.get("ma60_strong"):
        return 2
    if _pick_above60_ok(c):
        return 1
    return 0


def _ma_tier_rank(c: dict[str, Any]) -> int:
    a = c.get("A") or {}
    return int(TIER_RANK.get(str(a.get("ma_tier") or ""), 0)) + _pick_strength_rank(c) * 10

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
        "atrPctRank": _num(a.get("atrPctRank")) if a.get("atrPctRank") is not None else None,
        "volRank20": _num(a.get("volRank20")) if a.get("volRank20") is not None else None,
        "volRegime": a.get("volRegime"),
        "pullbackType": a.get("pullbackType"),
        "pullbackDays": a.get("pullbackDays"),
        "macdUnderwater": bool(a.get("macdUnderwater")),
        "trendScore": a.get("trendScore"),
        "bias6": round(_num(a.get("bias6")), 1) if a.get("bias6") is not None else None,
        "ma_bull": bool(a.get("ma_bull")), "gc_days": int(a.get("gc_days") or 0),
        "maTier": str(a.get("ma_tier") or ""),
        "aboveMa60": bool(a.get("above_ma60")),
        "aboveMa144": bool(a.get("above_ma144")),
        "ma60Strong": bool(a.get("ma60_strong")),
        "ma60StrongDays": a.get("ma60_strong_days"),
        "daysSinceZt": a.get("daysSinceZt"),
        "maTierLabel": str(a.get("ma_tier_label") or TIER_LABEL.get(str(a.get("ma_tier") or ""), "")),
        "closePos": a.get("closePos"), "odds1": a.get("odds1"), "oddsUse": a.get("oddsUse"),
        "pe": _num(a.get("pe")), "pb": _num(a.get("pb")), "mcap_yi": round(_num(a.get("mcap")) / 1e8, 1),
        "tightZtMeta": a.get("tightZtMeta") or {},
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
        "surgePullbackDays": (a or {}).get("surgePullbackDays"),
        "pullback2Days": (a or {}).get("pullback2Days"),
        "eventDays": (a or {}).get("eventDays"),
        "washoutDays": (a or {}).get("washoutDays"),
        "macdFirstRedDays": (a or {}).get("macdFirstRedDays"),
        "tail": c.get("tail") or {},
        "lhb": c.get("lhb"),
        "patterns": (a or {}).get("patterns") or {}, "risks": (a or {}).get("risks") or [],
        "limitQuality": (a or {}).get("limitQuality"),
        "limitQualityScore": (a or {}).get("limitQualityScore"),
        "tradability": (a or {}).get("tradability"),
        "qualityConfidence": (a or {}).get("qualityConfidence"),
        "pullbackType": (a or {}).get("pullbackType"),
        "pullbackDays": (a or {}).get("pullbackDays"),
        "pullbackDepthAtr": (a or {}).get("pullbackDepthAtr"),
        "pullbackDepthPct": (a or {}).get("pullbackDepthPct"),
        "macdUnderwater": bool((a or {}).get("macdUnderwater")),
        "trendScore": (a or {}).get("trendScore"),
        "atrPctRank": (a or {}).get("atrPctRank"),
        "volRank20": (a or {}).get("volRank20"),
        "emotionRegime": _EMO_CURRENT.get("regime") if _EMO_CURRENT else None,
        "emotionNote": _EMO_CURRENT.get("note") if _EMO_CURRENT else None,
        "levels": levels, "kwHits": (a or {}).get("kwHits") or [],
        "hot": bool((a or {}).get("hot")), "hotName": (a or {}).get("hotName") or "",
        "revHit": bool(c.get("revHit")), "revName": c.get("revName") or "",
        "boardLeader": bool(c.get("boardLeader")),
        "mainHit": bool(c.get("mainHit")), "mainName": c.get("mainName") or "",
        "obsHit": bool(c.get("obsHit")), "obsName": c.get("obsName") or "",
        "volHealth": (a or {}).get("volHealth"), "fundStreak": bool((a or {}).get("fundStreak")),
        "plateauDays": (a or {}).get("plateauDays"), "biasOver": bool((a or {}).get("biasOver")),
        "amp20": (a or {}).get("amp20"),
        "trendScore": (a or {}).get("trendScore"),
        "downSlope": bool((a or {}).get("downSlope")),
        "pathOk": bool((a or {}).get("pathOk", True)),
        "midUpOk": bool((a or {}).get("midUpOk", True)),
        "activityScore": (a or {}).get("activityScore"),
        "activeOk": bool((a or {}).get("activeOk")),
        "snap": ({"score": snap.get("score"), "risks": snap.get("risks") or [], "tags": snap.get("tags") or []}
                 if snap and not snap.get("error") else None),
        "chart": chart,
        # 决策层字段（前端一眼可读；缺 maTier 视为旧结果）
        "maTier": str(a.get("ma_tier") or ""),
        "aboveMa60": bool(a.get("above_ma60")),
        "aboveMa144": bool(a.get("above_ma144")),
        "ma60Strong": bool(a.get("ma60_strong")),
        "ma60StrongDays": a.get("ma60_strong_days"),
        "daysSinceZt": a.get("daysSinceZt"),
        "ztHot": bool(c.get("zt_hot")),
        "dualConfirm": bool(
            (a.get("above_ma144") or False)
            and (c.get("zt_hot") or _pick_zt_ok(c) or a.get("daysSinceZt") is not None)
        ),
        "decision": c.get("decision") or build_decision(c, lane=str(c.get("pick_lane") or "pick")),
        "algo": "strong-layer-v2",
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
        "patterns": (a or {}).get("patterns") or {},
        "limitQuality": (a or {}).get("limitQuality"),
        "limitQualityScore": (a or {}).get("limitQualityScore"),
        "tradability": (a or {}).get("tradability"),
        "qualityConfidence": (a or {}).get("qualityConfidence"),
        "pullbackType": (a or {}).get("pullbackType"),
        "pullbackDays": (a or {}).get("pullbackDays"),
        "pullbackDepthAtr": (a or {}).get("pullbackDepthAtr"),
        "pullbackDepthPct": (a or {}).get("pullbackDepthPct"),
        "macdUnderwater": bool((a or {}).get("macdUnderwater")),
        "atrPctRank": (a or {}).get("atrPctRank"),
        "volRank20": (a or {}).get("volRank20"),
        "emotionRegime": _EMO_CURRENT.get("regime") if _EMO_CURRENT else None,
        "emotionNote": _EMO_CURRENT.get("note") if _EMO_CURRENT else None,
        "surgeDaysAgo": (a or {}).get("surgeDaysAgo"),
        "surgePullbackDays": (a or {}).get("surgePullbackDays"),
        "pullback2Days": (a or {}).get("pullback2Days"),
        "eventDays": (a or {}).get("eventDays"),
        "washoutDays": (a or {}).get("washoutDays"),
        "macdFirstRedDays": (a or {}).get("macdFirstRedDays"),
        "risks": risks[:3] or ["排名靠后"],
        "bearish_level": bearish.get("level") or "pass",
        "revName": c.get("revName") or "", "hotName": (a or {}).get("hotName") or "",
        "mainHit": bool(c.get("mainHit")), "mainName": c.get("mainName") or "",
    }


def _macd_reds_from_report(d8: str | None = None, limit: int = 4) -> list[dict[str, Any]]:
    """MACD首红数据源拓宽（P1-2 A）：从每日复盘 sector_score.json 全量体检样本提取
    「MACD翻红第 1-3 天 + 位置≤50% + 无 hard 风险」标的，保证今日必有内容（零上游成本）。"""
    try:
        from .daily_report import ARCHIVE_ROOT
        d8 = d8 or time.strftime("%Y%m%d")
        _sp = os.path.join(ARCHIVE_ROOT, d8, "sector_score.json")
        if not os.path.exists(_sp):
            # 当日归档未生成（盘中）→ 回退最近归档日
            _archs = sorted([x for x in os.listdir(ARCHIVE_ROOT)
                             if re.fullmatch(r"\d{8}", x) and os.path.isdir(os.path.join(ARCHIVE_ROOT, x))],
                            reverse=True)
            for _d in _archs:
                _sp = os.path.join(ARCHIVE_ROOT, _d, "sector_score.json")
                if os.path.exists(_sp):
                    d8 = _d
                    break
            else:
                return []
        sc = json.load(open(_sp, encoding="utf-8"))
    except Exception:
        return []
    _hard = ("退市", "立案", "质押", "商誉", "诉讼", "减持", "解禁", "亏损")
    out: list[dict[str, Any]] = []
    for _sec, _rows in (sc or {}).items():
        if not isinstance(_rows, list):
            continue
        for r in _rows:
            if not isinstance(r, dict):
                continue
            try:
                red_days = int(r.get("red_days") or 0)
            except Exception:
                red_days = 0
            if not (1 <= red_days <= 3):
                continue
            # 位置≤50%：从 tags 解析「位置XX%」
            pos = None
            for _t in (r.get("tags") or []):
                m = re.search(r"位置(\d+(?:\.\d+)?)%", str(_t))
                if m:
                    pos = float(m.group(1))
                    break
            if pos is not None and pos > 50:
                continue
            _risks = [str(x) for x in (r.get("risks") or [])]
            if any(any(_h in str(x) for _h in _hard) for x in _risks):
                continue
            # 与全市场扫描 _macd_red_out / 前端 macdRedSection 字段对齐：
            # red_days=1→今日首红(macdFirstRedDays=0)；pos 用 0~1 小数；pct←up_pct
            _score = r.get("score")
            _up = r.get("up_pct")
            _pos60 = r.get("pos60")
            if pos is None and _pos60 is not None:
                try:
                    pos = float(_pos60)
                except Exception:
                    pos = None
            _pos_frac = (float(pos) / 100.0) if pos is not None else None
            _final = None
            try:
                if _score is not None:
                    _final = round(float(_score), 1)
            except Exception:
                _final = None
            out.append({
                "code": str(r.get("code") or ""),
                "name": str(r.get("name") or ""),
                "score": _score,
                "final": _final,
                "price": None,  # 由 _backfill_leader_quotes 补现价
                "pct": _up,
                "up_pct": _up,
                "chg5": r.get("chg5"),
                "mcap": None,
                "red_days": red_days,
                "macdFirstRedDays": max(0, int(red_days) - 1),
                "patterns": {"macdFirstRed": 1},
                "risks": _risks[:3],
                "pos": _pos_frac,
                "src": "复盘样本",
                "board": str(_sec or ""),
                "obsName": str(_sec or ""),
                "obsHit": bool(_sec),
            })
    out.sort(key=lambda x: -(x.get("score") or 0))
    return out[:limit]


def _macd_red_out(c: dict[str, Any]) -> dict[str, Any]:
    """MACD 量能首红专栏条目：底部刚收红 / 1-3 根红柱 + 量能确认的右侧启动标的。"""
    a = c.get("A") or {}
    risks = list((a or {}).get("risks") or [])
    snap = c.get("snap") if isinstance(c.get("snap"), dict) else None
    if snap and snap.get("risks"):
        risks = list(snap["risks"]) + risks
    bearish = c.get("bearish") if isinstance(c.get("bearish"), dict) else {"level": "pass", "items": []}
    btxt = [it.get("text") for it in (bearish.get("items") or [])]
    if btxt:
        risks = btxt + risks
    lv = (a or {}).get("levels") or {}
    return {
        "code": c.get("code"), "name": c.get("name"), "price": c.get("price"),
        "pct": c.get("pct"), "mcap": c.get("mcap"), "amount": c.get("amount"),
        "turnover": _num(c.get("turnover")),
        "final": c.get("final"), "score": (a or {}).get("score"),
        "pos": (a or {}).get("pos"), "chg5": (a or {}).get("chg5"),
        "chg20": (a or {}).get("chg20"),
        "macdFirstRedDays": (a or {}).get("macdFirstRedDays"),
        "gcDays": (a or {}).get("gc_days"),
        "patterns": (a or {}).get("patterns") or {},
        "limitQuality": (a or {}).get("limitQuality"),
        "limitQualityScore": (a or {}).get("limitQualityScore"),
        "tradability": (a or {}).get("tradability"),
        "qualityConfidence": (a or {}).get("qualityConfidence"),
        "pullbackType": (a or {}).get("pullbackType"),
        "pullbackDays": (a or {}).get("pullbackDays"),
        "macdUnderwater": bool((a or {}).get("macdUnderwater")),
        "trendScore": (a or {}).get("trendScore"),
        "atrPctRank": (a or {}).get("atrPctRank"),
        "volRank20": (a or {}).get("volRank20"),
        "emotionRegime": _EMO_CURRENT.get("regime") if _EMO_CURRENT else None,
        "emotionNote": _EMO_CURRENT.get("note") if _EMO_CURRENT else None,
        "mainHit": bool(c.get("mainHit")), "mainName": c.get("mainName") or "",
        "obsHit": bool(c.get("obsHit")), "obsName": c.get("obsName") or "",
        "revHit": bool(c.get("revHit")), "revName": c.get("revName") or "",
        "risks": risks[:3] or [],
        "bearish_level": bearish.get("level") or "pass",
        "levels": {"s1": lv.get("s1"), "s2": lv.get("s2"), "p1": lv.get("p1"), "p2": lv.get("p2"), "stop": lv.get("stop")},
        "tail": c.get("tail") or {},
        "fund": c.get("fundIn"),
        "downSlope": bool((a or {}).get("downSlope")),
        "pathOk": bool((a or {}).get("pathOk", True)),
        "midUpOk": bool((a or {}).get("midUpOk", True)),
        "activityScore": (a or {}).get("activityScore"),
        "activeOk": bool((a or {}).get("activeOk")),
    }


def macd_view(out: dict[str, Any]) -> dict[str, Any]:
    """从沪深京全市场扫描结果提取「MACD 量能首红」专栏（复用 all 扫描与当日缓存）。"""
    o: dict[str, Any] = {
        "ok": True, "cached": bool(out.get("cached")), "date": out.get("date"), "asof": out.get("asof"),
        "market_code": "macd",
        "meta": out.get("meta"),
        "total": out.get("total"), "scanned": out.get("scanned"), "fine": out.get("fine"),
        "generated_ts": out.get("generated_ts"), "elapsed_s": out.get("elapsed_s"),
        "market": out.get("market"), "regime": out.get("regime"), "style": out.get("style"),
        "mainlines": out.get("mainlines") or [],
        "board_rank": out.get("board_rank") or [],
        "macd_reds": out.get("macd_reds") or [],
    }
    for _k in ("stale", "stale_from", "off_market", "intraday", "refresh_locked", "vip_required", "today_missing"):
        if _k in out:
            o[_k] = out[_k]
    # MACD首红数据源拓宽（P1-2 A）：全市场扫描结果不足时，用复盘样本补齐（保证今日必有内容）
    try:
        _mr = list(o.get("macd_reds") or [])
        for _x in _mr:
            if isinstance(_x, dict):
                _x.setdefault("src", "全市场扫描")
        _need = max(0, 4 - len(_mr))
        if _need > 0:
            _fill = _macd_reds_from_report(limit=_need + 4)
            _have_codes = {str(x.get("code") or "") for x in _mr}
            for _x in _fill:
                if str(_x.get("code") or "") in _have_codes:
                    continue
                _mr.append(_x)
                _have_codes.add(str(_x.get("code") or ""))
                if len(_mr) >= 4:
                    break
        # 路径门：禁下坡，优先右侧上涨途中 + 股性活跃
        _mr = [x for x in _mr if isinstance(x, dict) and _path_gate(x, require_active=True)]
        o["macd_reds"] = _mr[:4]
    except Exception:
        pass
    return o


def pb_view(out: dict[str, Any]) -> dict[str, Any]:
    """从沪深主线扫描结果提取「首板回踩企稳」专栏（复用 hs 扫描与当日缓存）。

    仅首板系形态：pb45 / firstWeek / firstBoardRight / pullback2 / ztPullback。
    不含普通异动回踩、砸盘企稳等非首板宽口径。
    """
    o: dict[str, Any] = {
        "ok": True, "cached": bool(out.get("cached")), "date": out.get("date"), "asof": out.get("asof"),
        "market_code": "pb",
        "meta": out.get("meta"),
        "total": out.get("total"), "scanned": out.get("scanned"), "fine": out.get("fine"),
        "generated_ts": out.get("generated_ts"), "elapsed_s": out.get("elapsed_s"),
        "market": out.get("market"), "regime": out.get("regime"), "style": out.get("style"),
        "mainlines": out.get("mainlines") or [],
        "board_rank": out.get("board_rank") or [],
        "picks": [], "runners": [],
    }
    for _k in ("stale", "stale_from", "off_market", "intraday", "refresh_locked", "vip_required", "today_missing"):
        if _k in out:
            o[_k] = out[_k]

    def _pb_sort_key(c: dict[str, Any]) -> tuple:
        pp = c.get("patterns") or {}
        return (
            -_pb_evp_score(c),
            0 if pp.get("breakout") else 1,
            0 if pp.get("ztWeek") else 1,
            0 if pp.get("strongMom") else 1,
            0 if c.get("mainHit") else (1 if c.get("obsHit") else 2),
            -int(c.get("final") or 0),
        )

    pool = [c for c in ((out.get("picks") or []) + (out.get("runners") or []))
            if isinstance(c, dict) and _pb_board_only(c) and _path_gate(c, require_active=True)]
    pool.sort(key=_pb_sort_key)

    def _has_chart(x: dict[str, Any]) -> bool:
        ch = x.get("chart") if isinstance(x, dict) else None
        if not isinstance(ch, dict):
            return False
        return bool(ch.get("closes") or ch.get("c") or ch.get("dates"))

    # 主推只要带完整 K 线的；无图的备选不上主推卡（避免「有名无图」）
    with_chart = [c for c in pool if _has_chart(c)]
    use = with_chart[:2] if with_chart else []
    ranked: list[dict[str, Any]] = []
    for i, c in enumerate(use):
        cc = dict(c)
        cc["rank"] = i + 1
        ranked.append(cc)
    o["picks"] = ranked
    o["runners"] = []  # 备选池已下线
    return o


# 主线回踩低吸：偏「低吸」子集（相对回踩企稳：硬 mainHit、排除已突破、位置/涨幅更严）
_MLPB_CORE_KEYS = ("pb45", "pullback2", "ztPullback", "firstWeek")
_MLPB_WIDE_KEYS = ("pullback", "washOut", "surgePullback", "eventPullback")


def _pos_frac(c: dict[str, Any]) -> float:
    """候选位置 0~1；兼容百分制字段。"""
    p = c.get("pos")
    if p is None and isinstance(c.get("A"), dict):
        p = (c.get("A") or {}).get("pos")
    try:
        v = float(p)
    except Exception:
        return 99.0
    return v / 100.0 if v > 1.5 else v


def _chg_n(c: dict[str, Any], key: str) -> float:
    v = c.get(key)
    if v is None and isinstance(c.get("A"), dict):
        v = (c.get("A") or {}).get(key)
    try:
        return float(v)
    except Exception:
        return 999.0


def mlpb_view(out: dict[str, Any]) -> dict[str, Any]:
    """主线回踩低吸：当日主攻板块内回踩/低吸，硬要求 mainHit；排除已突破（留给二波突破栏）。

    与「回踩企稳」差异：mainHit 硬门；形态偏低吸；pos≤0.50 且 chg5/chg10 不过热；宁缺带图主推最多 2 只。
    """
    o = _hs_column_shell(out, "mlpb")

    def _match(c: dict[str, Any]) -> bool:
        if not c.get("mainHit"):
            return False
        pp = c.get("patterns") or {}
        if pp.get("breakout"):
            return False
        core = any(pp.get(k) for k in _MLPB_CORE_KEYS)
        wide = any(pp.get(k) for k in _MLPB_WIDE_KEYS)
        if not (core or wide):
            return False
        if _pos_frac(c) > 0.50:
            return False
        if _chg_n(c, "chg5") > 18.0 or _chg_n(c, "chg10") > 30.0:
            return False
        return _path_gate(c, require_active=True)

    def _sort_key(c: dict[str, Any]) -> tuple:
        pp = c.get("patterns") or {}
        core = 0 if any(pp.get(k) for k in _MLPB_CORE_KEYS) else 1
        return (
            core,
            -_pb_evp_score(c),
            _pos_frac(c),
            _chg_n(c, "chg5"),
            -int(c.get("final") or 0),
        )

    def _has_chart(x: dict[str, Any]) -> bool:
        ch = x.get("chart") if isinstance(x, dict) else None
        if not isinstance(ch, dict):
            return False
        return bool(ch.get("closes") or ch.get("c") or ch.get("dates"))

    pool = [c for c in ((out.get("picks") or []) + (out.get("runners") or []))
            if isinstance(c, dict) and _match(c)]
    pool.sort(key=_sort_key)
    with_chart = [c for c in pool if _has_chart(c)]
    use = with_chart[:2] if with_chart else []
    ranked: list[dict[str, Any]] = []
    for i, c in enumerate(use):
        cc = dict(c)
        cc["rank"] = i + 1
        ranked.append(cc)
    o["picks"] = ranked
    o["runners"] = []
    return o


def _hs_column_shell(out: dict[str, Any], market_code: str) -> dict[str, Any]:
    o: dict[str, Any] = {
        "ok": True, "cached": bool(out.get("cached")), "date": out.get("date"), "asof": out.get("asof"),
        "market_code": market_code,
        "meta": out.get("meta"),
        "total": out.get("total"), "scanned": out.get("scanned"), "fine": out.get("fine"),
        "generated_ts": out.get("generated_ts"), "elapsed_s": out.get("elapsed_s"),
        "market": out.get("market"), "regime": out.get("regime"), "style": out.get("style"),
        "mainlines": out.get("mainlines") or [],
        "board_rank": out.get("board_rank") or [],
        "picks": [], "runners": [],
    }
    for _k in ("stale", "stale_from", "off_market", "intraday", "refresh_locked", "vip_required", "today_missing"):
        if _k in out:
            o[_k] = out[_k]
    return o


def breakout_view(out: dict[str, Any]) -> dict[str, Any]:
    """二波突破：板后/首板回踩之后，近3日放量突破板日或平台高点（右侧加速确认）。"""
    o = _hs_column_shell(out, "breakout")

    def _match(c: dict[str, Any]) -> bool:
        pp = c.get("patterns") or {}
        if not pp.get("breakout"):
            return False
        lq = str(c.get("limitQuality") or "")
        if lq in ("one_word", "rotten_board"):
            return False
        return _path_gate(c, require_active=True)

    def _sort_key(c: dict[str, Any]) -> tuple:
        pp = c.get("patterns") or {}
        tier = 0
        if pp.get("firstBoardRight"):
            tier = 3
        elif pp.get("pb45") or pp.get("pullback2"):
            tier = 2
        elif pp.get("ztPullback") or pp.get("firstWeek"):
            tier = 1
        lq = str(c.get("limitQuality") or "")
        lq_ok = 0 if lq in ("turnover_board", "t_board", "normal", "") else 1
        return (-tier, lq_ok, 0 if c.get("mainHit") else (1 if c.get("obsHit") else 2),
                0 if pp.get("strongMom") else 1, -int(c.get("final") or 0))

    pool = [c for c in ((out.get("picks") or []) + (out.get("runners") or []))
            if isinstance(c, dict) and _match(c)]
    pool.sort(key=_sort_key)
    o["picks"] = pool[:2]
    o["runners"] = pool[2:8]
    return o


def leader_view(out: dict[str, Any]) -> dict[str, Any]:
    """主线龙头：当日主攻板块内 leaderOk + strongMom + 主线命中，宁缺毋滥。"""
    o = _hs_column_shell(out, "leader")

    def _match(c: dict[str, Any]) -> bool:
        if not c.get("mainHit"):
            return False
        pp = c.get("patterns") or {}
        if not (pp.get("leaderOk") and pp.get("strongMom")):
            return False
        if str(c.get("limitQuality") or "") == "one_word":
            return False
        if (c.get("bearish") or {}).get("level") == "hard":
            return False
        return _path_gate(c, require_active=True)

    def _sort_key(c: dict[str, Any]) -> tuple:
        pp = c.get("patterns") or {}
        return (
            0 if c.get("boardLeader") else 1,
            0 if pp.get("breakout") else 1,
            0 if c.get("tier") == "king" else (1 if c.get("tier") == "key" else 2),
            -int(c.get("final") or 0),
        )

    pool = [c for c in ((out.get("picks") or []) + (out.get("runners") or []))
            if isinstance(c, dict) and _match(c)]
    pool.sort(key=_sort_key)
    o["picks"] = pool[:2]
    o["runners"] = pool[2:8]
    return o


def _recent_tight_replay_preview(max_try: int = 12) -> tuple[str, list[dict[str, Any]]]:
    """今日无大波段标的时，从近若干交易日 K 线缓存回放，供前端展示可验证的历史样本。"""
    dates: list[str] = []
    seen: set[str] = set()
    try:
        hist = _load_history()
        for k in reversed(list(hist.keys())):
            mk = k.split(":", 1)[0] if ":" in k else "bj"
            dk = k.split(":", 1)[1] if ":" in k else k
            if mk not in ("all", "tight"):
                continue
            d8 = re.sub(r"\D", "", str(dk))[-8:]
            if not re.fullmatch(r"\d{8}", d8) or d8 in seen:
                continue
            seen.add(d8)
            dates.append(d8)
    except Exception:
        pass
    for d8 in dates[:max_try]:
        try:
            rp = replay_scan(d8, "tight")
            picks = [
                p for p in (rp.get("picks") or [])
                if isinstance(p, dict) and _is_hs_kc_code6(str(p.get("code") or ""))
            ]
            if picks:
                return d8, picks[:2]
        except Exception:
            continue
    return "", []


def tight_view(out: dict[str, Any]) -> dict[str, Any]:
    """大波段：多头粘合涨停（沪深+创业/科创，不含北证；复用 all 扫描）。"""
    o: dict[str, Any] = {
        "ok": True, "cached": bool(out.get("cached")), "date": out.get("date"), "asof": out.get("asof"),
        "market_code": "tight",
        "meta": out.get("meta"),
        "total": out.get("total"), "scanned": out.get("scanned"), "fine": out.get("fine"),
        "generated_ts": out.get("generated_ts"), "elapsed_s": out.get("elapsed_s"),
        "market": out.get("market"), "regime": out.get("regime"), "style": out.get("style"),
        "mainlines": out.get("mainlines") or [],
        # 专栏不展示全市场板块热度（含北证代表），避免与「大波段」推荐混淆
        "board_rank": [],
        "picks": [], "runners": [],
    }
    for _k in ("stale", "stale_from", "off_market", "intraday", "refresh_locked", "vip_required", "today_missing"):
        if _k in out:
            o[_k] = out[_k]

    def _is_tight(x: dict[str, Any]) -> bool:
        if not isinstance(x, dict):
            return False
        # 硬排除北证：仅允许沪深主板 / 创业 / 科创
        if not _is_hs_kc_code6(str(x.get("code") or "")):
            return False
        if re.search(r"(?:\*?ST)|退", str(x.get("name") or ""), flags=re.I):
            return False
        if str(x.get("limitQuality") or "") == "one_word":
            return False
        if (x.get("bearish") or {}).get("level") == "hard":
            return False
        pp = x.get("patterns") or {}
        return bool(pp.get("tightZt"))

    def _has_chart(x: dict[str, Any]) -> bool:
        ch = x.get("chart") if isinstance(x, dict) else None
        return bool(ch and (ch.get("closes") or ch.get("dates")))

    def _sort_key(c: dict[str, Any]) -> tuple:
        pp = c.get("patterns") or {}
        meta = {}
        if isinstance(c.get("factors"), dict):
            meta = (c.get("factors") or {}).get("tightZtMeta") or {}
        if not meta and isinstance(c.get("A"), dict):
            meta = (c.get("A") or {}).get("tightZtMeta") or {}
        return (
            0 if meta.get("pathA") else 1,
            0 if meta.get("yrSoft") else 1,
            0 if meta.get("ma144Up") else 1,
            0 if meta.get("divergeStrict") else 1,
            0 if c.get("mainHit") else (1 if c.get("obsHit") else 2),
            0 if pp.get("tightBurst") else 1,
            -int(c.get("final") or 0),
        )

    lst = [x for x in (out.get("tight") or []) if _is_tight(x) and _has_chart(x)]
    if len(lst) < 2:
        _asof = str(out.get("asof") or out.get("date") or "")
        _d8 = re.sub(r"\D", "", _asof)[-8:]
        if re.fullmatch(r"\d{8}", _d8):
            try:
                _rp = replay_scan(_d8, "tight")
                _have = {str(x.get("code")) for x in lst}
                for _x in (_rp.get("picks") or [])[:8]:
                    if str(_x.get("code")) in _have:
                        continue
                    if not _is_tight(_x) or not _has_chart(_x):
                        continue
                    lst.append(_x)
                    _have.add(str(_x.get("code")))
                    if len(lst) >= 2:
                        break
            except Exception:
                pass
    lst = [x for x in lst if _path_gate(x, require_active=True)]
    lst.sort(key=_sort_key)
    lst = lst[:2]
    for _i, _it in enumerate(lst):
        _it["tier"] = "king" if _i == 0 else "key"
        _it["rank"] = _i + 1
    o["picks"] = lst
    o["runners"] = []
    # 今日无标的（含 stale 归档回退仍无大波段命中）→ 近几日 K 线回放，供打开验证
    if not lst:
        _rd8, _rpicks = _recent_tight_replay_preview()
        if _rpicks:
            _dash = f"{_rd8[:4]}-{_rd8[4:6]}-{_rd8[6:]}" if len(_rd8) == 8 else _rd8
            o["replay_preview"] = {"date": _dash, "date8": _rd8, "picks": _rpicks, "replay": True}
    return o


_HS_COLUMN_MARKETS = frozenset({"pb", "mlpb", "breakout", "leader"})


def scan_market_for(market_code: str) -> str:
    mc = str(market_code or "bj").strip().lower()
    if mc in ("macd", "low10", "tight"):
        return "all"
    if mc in _HS_COLUMN_MARKETS:
        return "hs"
    return mc


def apply_column_view(market_code: str, out: dict[str, Any]) -> dict[str, Any]:
    mc = str(market_code or "").strip().lower()
    if not isinstance(out, dict):
        return out
    if mc == "macd":
        return macd_view(out)
    if mc == "low10":
        return low10_view(out)
    if mc == "tight":
        return tight_view(out)
    if mc == "pb":
        return pb_view(out)
    if mc == "mlpb":
        return mlpb_view(out)
    if mc == "breakout":
        return breakout_view(out)
    if mc == "leader":
        return leader_view(out)
    return out



def _save_all_column_histories(today: str, asof: str, hist_payload: dict[str, Any],
                               result: dict[str, Any]) -> None:
    """全市场扫描完成后，写入 macd / low10 / tight 专栏历史（供跟踪台账）。"""
    for mc, vf in (("macd", macd_view), ("low10", low10_view), ("tight", tight_view)):
        try:
            snap = vf(result)
            if mc == "macd":
                picks = snap.get("macd_reds") or snap.get("picks") or []
            else:
                picks = snap.get("picks") or []
            if not picks:
                continue
            col_hist = dict(hist_payload)
            col_hist["market_code"] = mc
            col_hist["picks"] = picks[:8]
            if mc == "macd":
                col_hist["macd_reds"] = picks[:4]
            if mc == "tight":
                col_hist["tight"] = picks[:8]
            col_hist["runners"] = []
            _save_history(f"{mc}:{str(today)}", col_hist)
        except Exception:
            pass


def _save_hs_column_histories(today: str, asof: str, hist_payload: dict[str, Any],
                              result: dict[str, Any]) -> None:
    """沪深扫描完成后，写入 pb / 主线回踩低吸 / 二波突破 / 主线龙头 专栏历史。"""
    for mc, vf in (("pb", pb_view), ("mlpb", mlpb_view), ("breakout", breakout_view), ("leader", leader_view)):
        try:
            snap = vf(result)
            picks = snap.get("picks") or []
            if not picks:
                continue
            col_hist = dict(hist_payload)
            col_hist["market_code"] = mc
            col_hist["picks"] = picks
            col_hist["runners"] = snap.get("runners") or []
            _save_history(f"{mc}:{str(today)}", col_hist)
            if mc == "pb":
                append_pb_ledger(str(today), asof, picks)
        except Exception:
            pass


def low10_view(out: dict[str, Any]) -> dict[str, Any]:
    """从沪深京全市场扫描结果提取「10元下」专栏（复用 all 扫描与当日缓存，零额外上游成本）。

    入选口径 = 优质标的（刚右侧起来 + 强势动量）+ 股价 2~10 元；
    硬伤排除：ST/退市（coarse 已排）、面值退市警戒（<2 元）、一字板不可交易、流动性不足（amountMin 已保证）。
    """
    o: dict[str, Any] = {
        "ok": True, "cached": bool(out.get("cached")), "date": out.get("date"), "asof": out.get("asof"),
        "market_code": "low10",
        "meta": out.get("meta"),
        "total": out.get("total"), "scanned": out.get("scanned"), "fine": out.get("fine"),
        "generated_ts": out.get("generated_ts"), "elapsed_s": out.get("elapsed_s"),
        "market": out.get("market"), "regime": out.get("regime"), "style": out.get("style"),
        "mainlines": out.get("mainlines") or [],
        "board_rank": out.get("board_rank") or [],
        "picks": [], "runners": [],
    }
    for _k in ("stale", "stale_from", "off_market", "intraday", "refresh_locked", "vip_required", "today_missing"):
        if _k in out:
            o[_k] = out[_k]

    def _ok_price(p: Any) -> bool:
        try:
            fp = float(p or 0)
        except Exception:
            fp = 0.0
        return 2.0 <= fp < 10.0

    def _tradable(x: dict[str, Any]) -> bool:
        return str((x.get("limitQuality") or "") or "") != "one_word"

    def _has_chart(x: Any) -> bool:
        ch = x.get("chart") if isinstance(x, dict) else None
        return bool(ch and (ch.get("closes") or ch.get("dates")))

    # 只展示带完整 K 线图（chart）的标的：备选池（_runner_out）为省体积不带图，
    # 归档回退时若混入会渲染成空白卡片（价格 0.00 / 无 K 线），宁缺毋滥。
    lst = [x for x in (out.get("low10") or [])
           if _ok_price(x.get("price")) and _tradable(x) and _has_chart(x)]
    if not lst:
        # 旧归档回退：从主推/备选过滤补足
        for _x in (out.get("picks") or []) + (out.get("runners") or []):
            if _ok_price(_x.get("price")) and _tradable(_x) and _has_chart(_x):
                lst.append(_x)
        lst = lst[:8]
    if not lst:
        for _x in (out.get("macd_reds") or []):
            if _ok_price(_x.get("price")) and _tradable(_x) and _has_chart(_x):
                lst.append(_x)
        lst = lst[:8]
    # 最多 2 只、宁缺毋滥（用户口径：有数据 2 只最好，不足不强凑）：
    # 不足 2 只时用当日 K 线缓存重放补齐（replay_scan 只读、零上游），仍要求带图+质量。
    if len(lst) < 2:
        _asof = str(out.get("asof") or out.get("date") or "")
        _d8 = re.sub(r"\D", "", _asof)[-8:]
        if re.fullmatch(r"\d{8}", _d8):
            try:
                _rp = replay_scan(_d8, "low10")
                _have = {str(x.get("code")) for x in lst}
                for _x in (_rp.get("picks") or [])[:8]:
                    if str(_x.get("code")) in _have:
                        continue
                    if not _ok_price(_x.get("price")) or not _tradable(_x):
                        continue
                    if not _has_chart(_x):
                        continue
                    lst.append(_x)
                    _have.add(str(_x.get("code")))
                    if len(lst) >= 2:
                        break
            except Exception:
                pass
    # 路径门：禁下坡；10元下要求股性活跃（刚右侧强势）
    lst = [x for x in lst if _path_gate(x, require_active=True)]
    lst = lst[:2]
    # 重排 tier：第一个（动量+评分排序最高）为王者，其余重点
    for _i, _it in enumerate(lst):
        _it["tier"] = "king" if _i == 0 else "key"
        _it["star"] = _i == 0
    o["picks"] = lst
    return o


# ============ 历史日期回放（最新算法 × 指定收盘日数据，只读不写、零上游） ============
_REPLAY_CFG_HS: dict[str, Any] | None = None
_REPLAY_CFG_BJ: dict[str, Any] | None = None
_REPLAY_CFG_BJ_ALL: dict[str, Any] | None = None
_REPLAY_CFG_LOW10: dict[str, Any] | None = None


def _replay_cfg(market: str) -> dict[str, Any]:
    """回放用各市场参数（与 run_scan 口径一致）。"""
    global _REPLAY_CFG_HS, _REPLAY_CFG_BJ, _REPLAY_CFG_BJ_ALL, _REPLAY_CFG_LOW10
    if _REPLAY_CFG_HS is None:
        _hs = dict(DEFAULT_CFG)
        _hs.update({"mcapMin": 15.0, "mcapMax": 200.0, "amountMin": 8000.0,
                    "posMax": 35.0, "max5d": 25.0, "max10d": 40.0, "max20d": 40.0,
                    "max60d": 60.0, "scoreMin": 44.0})
        _REPLAY_CFG_HS = _hs
        _bj = dict(DEFAULT_CFG)
        _REPLAY_CFG_BJ = _bj
        _ba = dict(DEFAULT_CFG)
        _ba.update({"posMax": 40.0, "mcapMin": 5.0, "mcapMax": 60.0, "scoreMin": 46.0,
                    "max5d": 28.0, "max10d": 40.0, "max20d": 40.0, "max60d": 60.0,
                    "turnMax": 25.0})
        _REPLAY_CFG_BJ_ALL = _ba
        _l10 = dict(DEFAULT_CFG)
        _l10.update({"mcapMin": 5.0, "mcapMax": 200.0, "amountMin": 5000.0,
                     "posMax": 35.0, "max5d": 25.0, "max10d": 40.0, "max20d": 40.0,
                     "max60d": 60.0, "scoreMin": 46.0, "turnMin": 1.5, "turnMax": 25.0})
        _REPLAY_CFG_LOW10 = _l10
    if market == "bj":
        return _REPLAY_CFG_BJ
    if market == "bj_all":
        return _REPLAY_CFG_BJ_ALL
    if market == "low10":
        return _REPLAY_CFG_LOW10
    return _REPLAY_CFG_HS


def _replay_market_of(code6: str) -> str:
    code6 = str(code6 or "").strip()
    if code6.startswith(("43", "83", "87", "88", "92")):
        return "bj"
    if code6.startswith(("30", "688")):
        return "kc"
    return "hs"


def _replay_fine_pass(recs: list[dict[str, Any]], cfg: dict[str, Any],
                      style_mode: str = "chop", relaxed: bool = False) -> list[dict[str, Any]]:
    """回放用精筛（与 run_scan._fine_pass 核心口径一致）。"""
    out: list[dict[str, Any]] = []
    _sm_delta = {"fan": 4, "chop": 2, "trend": -2, "defensive": 0}.get(style_mode, 0)
    sm = float(cfg.get("scoreMin") or 50) - (2 if relaxed else 0) + _sm_delta
    pos_max = (float(cfg["posMax"]) + (5 if relaxed else 0)) / 100
    chg5_max = float(cfg["max5d"]) + (5 if relaxed else 0)
    turn_min = 1.5 if relaxed else float(cfg.get("turnMin") or 2)
    sm_plain = float(cfg.get("scoreMin") or 50) + (8 if relaxed else 12) + _sm_delta
    sm_base = float(cfg.get("scoreMin") or 50) + (0 if relaxed else 2) + _sm_delta
    mcap_min = float(cfg.get("mcapMin") or 0) * 1e8
    mcap_max = float(cfg.get("mcapMax") or 1e18) * 1e8
    amount_min = float(cfg.get("amountMin") or 0) * 1e4
    for c in recs:
        if (c.get("bearish") or {}).get("level") == "hard":
            continue
        a = c.get("A") or {}
        p = a.get("patterns") or {}
        mc = _num(c.get("mcap"))
        amt = _num(c.get("amount"))
        if not (mcap_min <= mc <= mcap_max) or amt < amount_min:
            continue
        sv = float(a.get("score") or 0)
        if p.get("surgeStart") or p.get("pullback") or p.get("ztPullback") or p.get("pullback2") \
                or p.get("macdFirstRed") or p.get("firstBoardRight") or p.get("washOut") or p.get("firstWeek") \
                or p.get("tightZt"):
            must_start = sv >= sm - 4
        elif p.get("baseUp") or p.get("tightBurst"):
            must_start = sv >= sm_base
        else:
            must_start = sv >= sm_plain and (bool(p.get("leaderOk")) or bool(a.get("ma_bull3")) or a.get("volHealth") == 1)
        ev_pat = bool(p.get("pullback2") or p.get("surgeStart") or p.get("surgePullback") or p.get("firstWeek")
                      or p.get("pb45") or p.get("washOut") or p.get("firstBoardRight") or p.get("ztPullback"))
        mom_ok = bool(p.get("strongMom"))
        pos_ok = a.get("pos", 99) <= (min(pos_max + 0.25, 0.60) if (ev_pat or c.get("mainHit") or mom_ok) else pos_max)
        chg5_ok = a.get("chg5", 999) <= (chg5_max + (10 if mom_ok else 0))
        chg10_ok = a.get("chg10", 999) <= (40.0 if ev_pat else float(cfg["max10d"]))
        turn = _num(c.get("turnover"))
        if (pos_ok and chg5_ok and chg10_ok
                and a.get("chg20", 999) <= float(cfg["max20d"])
                and a.get("chg60", 999) <= float(cfg["max60d"])
                and turn_min <= turn <= float(cfg.get("turnMax") or 20)
                and not a.get("volShrink") and not a.get("newHighWeak") and not a.get("atHighWeak")
                and not (a.get("amp20") and float(a.get("amp20") or 0) < 3)
                and not a.get("downSlope")
                and (a.get("pathOk", True) if "pathOk" in a else True)
                and must_start):
            if c.get("mainHit"):
                a["score"] = min(100, int(a["score"]) + 4)
            elif c.get("obsHit"):
                a["score"] = min(100, int(a["score"]) + 2)
            if c.get("revHit"):
                a["score"] = min(100, int(a["score"]) + 3)
            out.append(c)
    return out


def _replay_evp(c: dict[str, Any]) -> int:
    p = (c.get("A") or {}).get("patterns") or {}
    if p.get("firstWeek"):
        return 4
    if p.get("pb45") or p.get("washOut"):
        return 3
    if p.get("pullback2") or p.get("surgeStart") or p.get("surgePullback") or p.get("firstBoardRight"):
        return 2
    return 1 if p.get("eventPullback") else 0


def _replay_sort_key(c: dict[str, Any]) -> tuple:
    a = c.get("A") or {}
    p = a.get("patterns") or {}
    mom_tier = 0 if p.get("strongMom") else 1
    return (-_replay_evp(c), mom_tier,
            0 if c.get("mainHit") else (1 if c.get("obsHit") else 2),
            -int(a.get("score") or 0))


def _replay_prev_mainlines(date8: str) -> list[str]:
    """date8 之前最近归档日的主线（pick_main_lines 的惯性保护基线）。"""
    try:
        from .daily_report import ARCHIVE_ROOT
        _ds = sorted([x for x in os.listdir(ARCHIVE_ROOT)
                      if re.fullmatch(r"\d{8}", x) and os.path.isdir(os.path.join(ARCHIVE_ROOT, x))])
        for _d in reversed(_ds):
            if _d >= date8:
                continue
            _p = os.path.join(ARCHIVE_ROOT, _d, "mainlines.json")
            if not os.path.exists(_p):
                continue
            try:
                _m = json.load(open(_p, encoding="utf-8"))
                return [str(x) for x in (_m.get("mainlines") or [])]
            except Exception:
                continue
    except Exception:
        pass
    return []


def replay_scan(date8: str, market: str = "hs") -> dict[str, Any]:
    """历史日期回放：用指定收盘日的 K 线缓存 + 当日归档 + 复盘成分，以最新算法重放各栏目。

    只读不写、零上游请求；返回与 /api/bj/history 同构的 payload（meta.replay=true）。
    数据局限：仅覆盖本机当日扫描过的成分池（bj_kline_cache/{date8}.json），
    未入选票缺市值/成交额字段时按数据缺失处理（宁缺毋滥）。
    """
    date8 = re.sub(r"\D", "", str(date8 or ""))[-8:]
    if not re.fullmatch(r"\d{8}", date8):
        return {"ok": False, "error": "bad_date", "message": "日期格式应为 YYYY-MM-DD 或 YYYYMMDD"}
    market = str(market or "hs").strip().lower()
    if market not in ("hs", "kc", "bj", "bj_all", "all", "macd", "pb", "mlpb", "breakout", "leader", "low10", "tight"):
        market = "hs"
    dash = f"{date8[:4]}-{date8[4:6]}-{date8[6:]}"
    t0 = time.time()
    kl_path = os.path.join(_KLINE_CACHE_DIR, date8 + ".json")
    if not os.path.exists(kl_path):
        return {"ok": False, "error": "no_kline_cache",
                "message": f"{dash} 无当日 K 线缓存，无法回放（仅支持本机扫描过的交易日）。"}
    try:
        _kl = json.load(open(kl_path, encoding="utf-8"))
        kl = _kl.get("data") if isinstance(_kl, dict) and isinstance(_kl.get("data"), dict) else _kl
    except Exception as e:
        return {"ok": False, "error": "bad_cache", "message": f"K 线缓存损坏：{e}"}
    # 当日归档：候选完整字段 + 板块榜 + 大盘环境
    cand_map: dict[str, dict[str, Any]] = {}
    board_rank: list[dict[str, Any]] = []
    market_env: dict[str, Any] = {}
    regime: str = ""
    style: dict[str, Any] = {}
    style_mode = "chop"
    for mk in ("all", "hs", "kc", "bj", "bj_all"):
        _p = os.path.join(_ARCHIVE_DIR, f"{dash}-{mk}.json")
        if not os.path.exists(_p):
            continue
        try:
            _d = json.load(open(_p, encoding="utf-8"))
        except Exception:
            continue
        for _x in (_d.get("picks") or []) + (_d.get("runners") or []) + (_d.get("macd_reds") or []) \
                + (_d.get("low10") or []) + (_d.get("tight") or []):
            if isinstance(_x, dict) and _x.get("code"):
                cand_map.setdefault(str(_x.get("code")), dict(_x))
        for _b in (_d.get("board_rank") or []):
            if not isinstance(_b, dict):
                continue
            for _ld in (_b.get("leaders") or []):
                if isinstance(_ld, dict) and _ld.get("code"):
                    cand_map.setdefault(str(_ld.get("code")), dict(_ld))
        if mk == market and not board_rank:
            board_rank = _d.get("board_rank") or []
            market_env = _d.get("market") or {}
            regime = str(_d.get("regime") or "")
            style = _d.get("style") or {}
            style_mode = str((style or {}).get("mode") or "chop")
    if not board_rank:
        try:
            _ad = json.load(open(os.path.join(_ARCHIVE_DIR, f"{dash}-all.json"), encoding="utf-8"))
            board_rank = _ad.get("board_rank") or []
            market_env = _ad.get("market") or {}
            regime = str(_ad.get("regime") or "")
            style = _ad.get("style") or {}
            style_mode = str((style or {}).get("mode") or "chop")
        except Exception:
            pass
    # 主线：该日复盘成分重判（新算法）；无成分回退当日归档
    mainlines: list[dict[str, Any]] = []
    observes: list[dict[str, Any]] = []
    try:
        from .daily_report import ARCHIVE_ROOT, mainline_judgment, pick_main_lines
        _sp = os.path.join(ARCHIVE_ROOT, date8, "sector_score.json")
        if os.path.exists(_sp):
            _sc = json.load(open(_sp, encoding="utf-8"))
            _prev = _replay_prev_mainlines(date8)
            _ml, _ob, _av = pick_main_lines(_sc, prev_mainlines=_prev, plates=None)
            mainlines = [{"name": str(n), "src": "replay"} for n in _ml]
            observes = [{"name": str(n), "src": "replay"} for n in _ob]
    except Exception:
        pass
    if not mainlines:
        try:
            _ad = json.load(open(os.path.join(_ARCHIVE_DIR, f"{dash}-all.json"), encoding="utf-8"))
            mainlines = [{"name": str(n), "src": "archive"} for n in (_ad.get("mainlines") or [])]
            observes = [{"name": str(n), "src": "archive"} for n in (_ad.get("observes") or [])]
        except Exception:
            pass
    # 全池重算（新算法 analyze）
    cfg = _replay_cfg(market if market != "kc" else "hs")
    recs: list[dict[str, Any]] = []
    for code, bars in kl.items():
        bars = [b for b in (bars or []) if str(b[0])[:10].replace("-", "") <= date8]
        if len(bars) < 30:
            continue
        cand = cand_map.get(str(code))
        if cand is None:
            cand = {"code": str(code), "name": str(code), "price": float(bars[-1][2]),
                    "mcap": 0, "amount": 0, "turnover": 0, "volRatio": 0,
                    "fundIn": None, "fund5": None, "ind": ""}
        try:
            a = analyze(bars, cand, cfg, market=_replay_market_of(str(code)))
        except Exception:
            continue
        rec = dict(cand)
        rec["A"] = a
        rec["_bars"] = bars
        rec["final"] = int(a.get("score") or 0)
        recs.append(rec)
    # 分栏目
    picks: list[dict[str, Any]] = []
    watch_list: list[dict[str, Any]] = []
    runners: list[dict[str, Any]] = []
    macd_reds: list[dict[str, Any]] = []
    fine: list[dict[str, Any]] = []
    if market in ("hs", "kc", "bj", "bj_all"):
        pool = [c for c in recs if _market_ok(str(c.get("code")), market)]
        fine = _replay_fine_pass(pool, cfg, style_mode)
        fine.sort(key=_replay_sort_key)
        picks = [_pick_out(c) for c in fine[:2]]
        runners = [_pick_out(c) for c in fine[2:8]]
    elif market == "macd":
        fine = _replay_fine_pass(recs, cfg, style_mode)
        macd_reds = [_pick_out(c) for c in fine if (c.get("A") or {}).get("patterns", {}).get("macdFirstRed")][:4]
    elif market == "breakout":
        fine = _replay_fine_pass(recs, cfg, style_mode)
        _bo = [c for c in fine if bool((c.get("A") or {}).get("patterns", {}).get("breakout"))]
        def _bo_key(c: dict[str, Any]) -> tuple:
            pp = (c.get("A") or {}).get("patterns") or {}
            tier = 3 if pp.get("firstBoardRight") else (2 if pp.get("pullback2") or pp.get("pb45") else 1)
            return (-tier, 0 if c.get("mainHit") else 1, -int(c.get("final") or 0))
        _bo.sort(key=_bo_key)
        picks = [_pick_out(c) for c in _bo[:2]]
        runners = [_pick_out(c) for c in _bo[2:8]]
    elif market == "leader":
        fine = _replay_fine_pass(recs, cfg, style_mode)
        _ld = [c for c in fine if c.get("mainHit")
               and (c.get("A") or {}).get("patterns", {}).get("leaderOk")
               and (c.get("A") or {}).get("patterns", {}).get("strongMom")]
        _ld.sort(key=lambda c: (0 if c.get("boardLeader") else 1, -int(c.get("final") or 0)))
        picks = [_pick_out(c) for c in _ld[:2]]
        runners = [_pick_out(c) for c in _ld[2:8]]
    elif market == "pb":
        fine = _replay_fine_pass(recs, cfg, style_mode)
        _pb = [c for c in fine if _pb_board_only({"patterns": (c.get("A") or {}).get("patterns") or {}})]
        def _pb_replay_key(c: dict[str, Any]) -> tuple:
            pp = (c.get("A") or {}).get("patterns") or {}
            evp = 5 if pp.get("firstWeek") else (
                4 if pp.get("pb45") or (pp.get("firstBoardRight") and pp.get("breakout")) else
                4 if pp.get("firstBoardRight") else
                4 if pp.get("pullback2") and pp.get("breakout") else
                3 if pp.get("pullback2") else (2 if pp.get("ztPullback") else 0))
            return (-evp, 0 if pp.get("breakout") else 1, 0 if pp.get("ztWeek") else 1, -int(c.get("final") or 0))
        _pb.sort(key=_pb_replay_key)
        picks = [_pick_out(c) for c in _pb[:2]]
        runners = [_pick_out(c) for c in _pb[2:8]]
    elif market == "mlpb":
        fine = _replay_fine_pass(recs, cfg, style_mode)
        def _mlpb_ok(c: dict[str, Any]) -> bool:
            if not c.get("mainHit"):
                return False
            pp = (c.get("A") or {}).get("patterns") or {}
            if pp.get("breakout"):
                return False
            core = any(pp.get(k) for k in _MLPB_CORE_KEYS)
            wide = any(pp.get(k) for k in _MLPB_WIDE_KEYS)
            if not (core or wide):
                return False
            a = c.get("A") or {}
            try:
                pos = float(a.get("pos") if a.get("pos") is not None else c.get("pos") or 99)
            except Exception:
                pos = 99.0
            if pos > 1.5:
                pos = pos / 100.0
            if pos > 0.50:
                return False
            try:
                chg5 = float(a.get("chg5") if a.get("chg5") is not None else c.get("chg5") or 999)
                chg10 = float(a.get("chg10") if a.get("chg10") is not None else c.get("chg10") or 999)
            except Exception:
                return False
            return chg5 <= 18.0 and chg10 <= 30.0
        _ml = [c for c in fine if _mlpb_ok(c)]
        _ml.sort(key=lambda c: (0 if any(((c.get("A") or {}).get("patterns") or {}).get(k) for k in _MLPB_CORE_KEYS) else 1,
                                 -int(c.get("final") or 0)))
        picks = [_pick_out(c) for c in _ml[:2]]
        runners = [_pick_out(c) for c in _ml[2:8]]
    elif market == "low10":
        lcfg = _replay_cfg("low10")
        for c in recs:
            if c.get("price") is None or _num(c.get("price")) <= 0:
                c["price"] = (c.get("A") or {}).get("closes", [0])[-1]
        pool = [c for c in recs if 2.0 <= _num(c.get("price")) < 10.0 and not _re_oneword(c)]
        fine = _replay_fine_pass(pool, lcfg, style_mode)
        fine.sort(key=_replay_sort_key)
        picks = [_pick_out(c) for c in fine[:8]]
    elif market == "tight":
        # 不经主线精筛门槛：直接在 analyze 全池筛 tightZt（否则易空）
        _tz = [
            c for c in recs
            if (c.get("A") or {}).get("patterns", {}).get("tightZt")
            and _is_hs_kc_code6(str(c.get("code") or ""))
            and not re.search(r"(?:\*?ST)|退", str(c.get("name") or ""), flags=re.I)
            and not _re_oneword(c)
            and (c.get("bearish") or {}).get("level") != "hard"
        ]
        _tz.sort(key=_replay_sort_key)
        fine = _tz
        picks = [_pick_out(c) for c in _tz[:8]]
    meta = {
        "replay": True, "date": dash, "asof": dash,
        "coverage": len(recs), "kline_cached": len(kl),
        "note": "最新算法 × 历史收盘数据回放（只读，未写入归档）",
    }
    _fill_missing_names(picks)
    _fill_missing_names(runners)
    _fill_missing_names(macd_reds)
    return {
        "ok": True, "archive": True, "replay": True,
        "date": dash, "asof": dash, "market_code": market,
        "generated_ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "elapsed_s": round(time.time() - t0, 2),
        "total": len(kl), "scanned": len(recs), "fine": len(fine),
        "market": market_env, "regime": regime, "style": style,
        "mainlines": mainlines, "observes": observes,
        "board_rank": board_rank,
        "picks": picks, "runners": runners, "macd_reds": macd_reds,
        "tight": picks if market == "tight" else [],
        "meta": meta,
    }


def _re_oneword(c: dict[str, Any]) -> bool:
    """一字板判定（开盘≈最低≈收盘且当日触板，不可交易）。"""
    bars = c.get("_bars") or []
    if len(bars) < 2:
        return False
    b = bars[-1]
    o, cl, h, l = float(b[1]), float(b[2]), float(b[3]), float(b[4])
    prev_c = float(bars[-2][2])
    if prev_c <= 0:
        return False
    if (h - l) <= 0:
        return False
    th = _zt_threshold(str(c.get("code") or "").zfill(6))
    if (cl / prev_c - 1) * 100 >= th - 0.5 and abs(o - l) <= (h - l) * 0.02 and abs(o - cl) <= (h - l) * 0.02:
        return True
    return False


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


def _strip_boards_conclusions(o: dict[str, Any]) -> dict[str, Any]:
    """非 VIP 板块视图：隐藏主线锁定结论。"""
    o = dict(o)
    o["board_rank"] = [dict(_b) for _b in (o.get("board_rank") or []) if isinstance(_b, dict)]
    for _br in o["board_rank"]:
        _br.pop("mainline", None)
    o["mainlines"] = []
    o.pop("prev_track", None)
    o.pop("prev_date", None)
    return o


def get_bj_screener_cached_result(
    market: str = "bj",
    column: str = "",
    boards_only: bool = False,
) -> dict[str, Any]:
    """只读当日缓存/归档；绝不触发扫描。无数据时 ok=False error=no_cache。"""
    market = str(market or "bj").strip().lower()
    if market not in ("bj", "all", "hs", "kc", "bj_all", "macd", "pb", "mlpb", "low10", "breakout", "leader", "tight"):
        market = "bj"
    col = str(column or "").strip().lower()
    if col not in _COLUMN_VIEW_MARKETS:
        col = market if market in _COLUMN_VIEW_MARKETS else ""
    scan_m = scan_market_for(col or market)

    running_task = _RUNNING_SCAN.get(scan_m)
    if running_task is not None and not running_task.done():
        p = scan_progress(scan_m)
        return {"ok": True, "running": True, "scanning": True, "message": "扫描进行中，请稍候…", **p}
    p = scan_progress(scan_m)
    if p.get("running"):
        return {"ok": True, "running": True, "scanning": True, "message": "扫描进行中，请稍候…", **p}

    today8 = time.strftime("%Y%m%d", time.localtime())
    full_key = f"{scan_m}-scan:{today8}"
    boards_key = f"{scan_m}-boards:{today8}"

    def _finish(out: dict[str, Any]) -> dict[str, Any]:
        out = dict(out)
        out["ok"] = True
        if boards_only:
            out["vip_required"] = True
            out = _strip_boards_conclusions(out)
            out.pop("picks", None)
            out.pop("runners", None)
            out.pop("macd_reds", None)
        elif col:
            out = apply_column_view(col, out)
        return out

    if boards_only:
        bh = _BOARDS_CACHE.get(boards_key)
        if bh and time.time() - bh[0] < 6 * 3600:
            out = dict(bh[1])
            out["cached"] = True
            return _finish(out)

    hit = _scan_cache_hit(full_key)
    if hit:
        out = dict(hit[1])
        out["cached"] = True
        if not boards_only:
            out = _apply_stale_fallback(out, scan_m, col)
        return _finish(out)

    hist_m = col if col in _COLUMN_VIEW_MARKETS else scan_m
    stale = _latest_history(hist_m)

    if _today_off_market() or not _market_closed():
        if stale:
            out = dict(stale)
            out["cached"] = True
            out["stale"] = True
            out["stale_from"] = stale.get("asof") or stale.get("date") or ""
            out["stale_scan_date"] = stale.get("date") or ""
            out["market_code"] = scan_m
            out["intraday"] = True
            out["date"] = stale.get("date") or stale.get("asof") or ""
            out = _reattach_ths(out)
            return _finish(out)

    if stale:
        _arch_day = str(stale.get("date") or stale.get("asof") or "").replace("-", "")[:8]
        out = dict(stale)
        out["cached"] = True
        out["stale"] = True
        out["stale_from"] = stale.get("asof") or stale.get("date") or ""
        out["stale_scan_date"] = stale.get("date") or ""
        out["market_code"] = scan_m
        out["date"] = stale.get("date") or stale.get("asof") or ""
        if _arch_day != today8:
            out["today_missing"] = True
            if _today_off_market():
                out["off_market"] = True
        out = _reattach_ths(out)
        return _finish(out)

    return {"ok": False, "error": "no_cache", "message": "暂无扫描结果，请点「重新扫描」生成。"}


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
    """交易日 15:01 后视为收盘，可更新今日数据；盘中（15:01 前）默认展示上一交易日归档。
    2026-08-25 雷总定：15:01 收盘后即可重扫；未定型 K 线由缓存校验兜底（见 _kline_entry_valid）。"""
    return int(time.strftime("%H%M", time.localtime())) >= 1501


# 复盘主线 → 东财板块 secid（主线成分补进掘金候选池用；未知板块回落 suggest 解析）
_MAINLINE_BOARD_MAP: dict[str, list[str]] = {
    "PCB": ["90.BK0877", "90.BK1340"],
    "创新药CXO": ["90.BK1600", "90.BK0899"],
    "通信光模块CPO": ["90.BK1128", "90.BK1136"],
    "煤炭": ["90.BK0437", "90.BK1250", "90.BK1493", "90.BK1494"],
    "半导体": ["90.BK1036", "90.BK1325"],
    # 军工：概念「军工」优先；行业「国防军工」+ 航天/船舶作备链
    "军工": ["90.BK0490", "90.BK1204", "90.BK0480", "90.BK0729"],
    "证券": ["90.BK0473"],
    "光伏设备": ["90.BK1031", "90.BK1602"],
    # 同花顺行业 881101；东财「种植业」BK1261 资金/成分最接近
    "种植业与林业": ["90.BK1261", "90.BK0433"],
}

# 主线名 → 真实东财板块 secid 轻量兜底（仅用于排行/链接展示，不改变候选池与龙头来源）：
# 东财无同名板块时（如 AI服务器算力），映射到成分最贴近的真实板块，保证排行可点击。
_MAINLINE_SECID_FALLBACK: dict[str, str] = {
    "AI服务器算力": "90.BK1134",
}


async def _collect_mainline_cands(cfg: dict[str, Any], names: list[str], hot: dict[str, Any], obs: bool = False) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    """主线/次主线板块全成分补进候选池（含板块名归属）：主线不在资金热度榜时，其低风险成分也要有机会进主推。
    obs=True 时标记为次主线（观察板块）成分，优先级低于主线。"""
    out: list[dict[str, Any]] = []
    leaders_by_name: dict[str, list[dict[str, Any]]] = {}
    seen: set[str] = set()
    cap_total = int(cfg.get("obsMemberCap") or 30) if obs else int(cfg.get("mainlineMemberCap") or 40)
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
            if obs:
                c["obsline"] = True
                c["obslineName"] = n
            else:
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
    column: str = "",
) -> dict[str, Any]:
    """掘金扫描主流程（服务端执行，VIP 路由层已校验）。

    market: hs=沪深主线、kc=科创主线（板块先行两阶段）；bj=北证主线、bj_all=北证全市场（纯评分，不跟主线）。
    boards_only=True 用于非 VIP 的“板块视图”：缩小候选池、跳过 AI 快照/基本面体检，
    结果独立缓存，仅返回板块与市场概览（不含个股分析）。
    """
    market = str(market or "bj").strip().lower()
    if market not in ("bj", "all", "hs", "kc", "bj_all"):
        market = "bj"
    cfg = dict(DEFAULT_CFG)
    board_rank: list[dict[str, Any]] = []  # 北证路径无板块榜，预置空表防 UnboundLocalError
    if market in ("all", "hs", "kc"):
        cfg["mcapMin"] = float(cfg.get("mcapMinAll") or 15.0)
        cfg["mcapMax"] = float(cfg.get("mcapMaxAll") or 200.0)
        cfg["amountMin"] = float(cfg.get("amountMinAll") or 8000.0)
        cfg["posMax"] = 35.0
        cfg["max5d"] = 25.0
        cfg["max10d"] = 40.0
        cfg["max20d"] = 40.0
        cfg["max60d"] = 60.0
        cfg["scoreMin"] = 44.0
    elif market == "bj_all":
        # 北证全市场：纯评分博弹性，位置放宽到 40%（宁缺毋滥，硬风控仍保留）。
        # 北证全市场池子小（348只）+ 30cm 波动大：放宽 5/10/20/60 日涨幅与换手上限、
        # 扩大 K线精筛名额，让「底部刚右侧异动拉升」的票不被涨幅门槛卡在精筛外。
        cfg["posMax"] = 40.0
        cfg["mcapMin"] = 5.0
        cfg["mcapMax"] = 60.0
        cfg["scoreMin"] = 46.0
        cfg["max5d"] = 28.0
        cfg["max10d"] = 40.0
        cfg["max20d"] = 40.0
        cfg["max60d"] = 60.0
        cfg["turnMax"] = 25.0
        cfg["cap"] = 80
    if cfg_override:
        for k, v in cfg_override.items():
            if k in cfg and v is not None:
                cfg[k] = v
    # P0-1 情绪周期 Gate：risk_off 时全部栏目 scoreMin+5、候选池减半；回踩企稳(pb)额外 +3。
    # 快照按日共享（全市场只算一次，六栏目复用），盘中/历史不足不启用 Gate。
    emotion: dict[str, Any] = {}
    if cfg.get("emotionGate", True):
        try:
            emotion = await compute_emotion_snapshot()
        except Exception:
            emotion = {}
            _EMO_CURRENT.clear()
        _emo_adj = apply_emotion_gate(cfg, emotion, column)
        if _emo_adj:
            cfg = _emo_adj
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
        full = _scan_cache_hit(full_key)
        if full:
            out = dict(full[1])
            out["cached"] = True
            out["vip_required"] = True
            out.pop("picks", None)
            out.pop("runners", None)
            out = _strip_conclusions(out)
            _BOARDS_CACHE[boards_key] = (time.time(), out)
            _mark_cached("已加载今日缓存")
            return out

        # 非交易日或盘中（未到 15:01）：直接展示最近归档板块视图，避免盘中半成品
        if _today_off_market() or not _market_closed():
            stale = _latest_history(market)
            if stale:
                out = dict(stale)
                out["ok"] = True
                out["cached"] = True
                out["stale"] = True
                out["vip_required"] = True
                out["stale_from"] = stale.get("asof") or stale.get("date") or ""
                out["stale_scan_date"] = stale.get("date") or ""
                out["market_code"] = market
                out["intraday"] = True
                out["date"] = stale.get("date") or stale.get("asof") or ""
                out.pop("picks", None)
                out.pop("runners", None)
                out = _strip_conclusions(out)
                out = _reattach_ths(out)
                _BOARDS_CACHE[boards_key] = (time.time(), out)
                _mark_cached("盘中/非交易日：展示最近归档板块视图")
                return out
        cfg["cap"] = min(int(cfg.get("cap") or 60), 30)
        cfg["aiOk"] = False
        cfg["aiTop"] = 0
        force = False
    else:
        if not force:
            hit = _scan_cache_hit(full_key)
            if hit:
                out = dict(hit[1])
                out["cached"] = True
                _mark_cached("已加载今日扫描缓存")
                return _apply_stale_fallback(out, market, column)
            # 非交易日（周末/休市）：不重复扫描，直接展示最近归档，节省上游与系统资源
            if _today_off_market():
                stale = _latest_history(market)
                if stale:
                    out = dict(stale)
                    out["ok"] = True
                    out["cached"] = True
                    out["stale"] = True
                    out["stale_from"] = stale.get("asof") or stale.get("date") or ""
                    out["stale_scan_date"] = stale.get("date") or ""
                    out["market_code"] = market
                    out["off_market"] = True
                    out["date"] = stale.get("date") or stale.get("asof") or ""
                    out = _reattach_ths(out)
                    _mark_cached("非交易日：直接展示最近交易日归档（可点「重新扫描」强制刷新）")
                    return out
            # 交易日盘中（未到 15:01 收盘）：今日数据尚未生成，展示上一交易日归档
            if not _market_closed():
                stale = _latest_history(market)
                if stale:
                    out = dict(stale)
                    out["ok"] = True
                    out["cached"] = True
                    out["stale"] = True
                    out["stale_from"] = stale.get("asof") or stale.get("date") or ""
                    out["stale_scan_date"] = stale.get("date") or ""
                    out["market_code"] = market
                    out["intraday"] = True
                    out["date"] = stale.get("date") or stale.get("asof") or ""
                    out = _reattach_ths(out)
                    _mark_cached("盘中未收盘：展示上一交易日归档（约 15:05 服务端自动更新今日）")
                    return out
        else:
            global _LAST_FULL_SCAN_TS
            if time.time() - _LAST_FULL_SCAN_TS < _FORCE_MIN_INTERVAL:
                hit = _scan_cache_hit(full_key)
                if hit:
                    out = dict(hit[1])
                    out["cached"] = True
                    out["refresh_locked"] = True
                    _mark_cached("已加载今日扫描缓存")
                    return _apply_stale_fallback(out, market, column)
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
    cands, hot, board_pool, total, rows_all = await _collect_candidates(cfg, market, with_global=not boards_only)
    mkt_env = await mkt_task
    _set_prog("kline", 18, "开始K线形态体检…")
    # 复盘主线（资金+技术双确认）：先读主线，把主线板块成分补进候选池（主线小票优先主推）
    _dml = _daily_mainlines()
    _dml_names = (_dml or {}).get("names") or []
    _dml_obs = (_dml or {}).get("observes") or []
    _dml_date = (_dml or {}).get("date") or ""
    _dml_src = (_dml or {}).get("src") or ""
    _dml_info = (_dml or {}).get("info") or {}
    _ml_leaders: dict[str, list[dict[str, Any]]] = {}
    _obs_leaders: dict[str, list[dict[str, Any]]] = {}
    if market in ("all", "hs", "kc") and _dml_names and not boards_only:
        _ml_cands, _ml_leaders = await _collect_mainline_cands(cfg, _dml_names, hot)
        # 主线成分补池按市场隔离（hs/kc 只留对应板块代码，避免跨市场混入）
        _ml_cands = [_c for _c in _ml_cands if _market_ok(str(_c.get("code")), market)]
        _ml_leaders = {_k: [_ld for _ld in (_v or []) if _market_ok(str((((_ld.get("_row") if isinstance(_ld, dict) else None) or {}).get("f12") or _ld.get("code") or "")), market)] for _k, _v in (_ml_leaders or {}).items()}
        _have = {str(c.get("code")): c for c in cands}
        for _c in _ml_cands:
            _code = str(_c.get("code"))
            if _code in _have:
                _have[_code]["mainline"] = True
                _have[_code]["mainlineName"] = _c.get("mainlineName") or _have[_code].get("mainlineName") or ""
            else:
                cands.append(_c)
    # 次主线（复盘观察板块）成分补池：优先级低于主线、高于普通候选
    if market in ("all", "hs", "kc") and _dml_obs and not boards_only:
        _obs_cands, _obs_leaders = await _collect_mainline_cands(cfg, _dml_obs[:3], hot, obs=True)
        _obs_cands = [_c for _c in _obs_cands if _market_ok(str(_c.get("code")), market)]
        _obs_leaders = {_k: [_ld for _ld in (_v or []) if _market_ok(str((((_ld.get("_row") if isinstance(_ld, dict) else None) or {}).get("f12") or _ld.get("code") or "")), market)] for _k, _v in (_obs_leaders or {}).items()}
        _have2 = {str(c.get("code")): c for c in cands}
        for _c in _obs_cands:
            _code = str(_c.get("code"))
            if _code in _have2:
                _have2[_code]["obsline"] = True
                _have2[_code]["obslineName"] = _c.get("obslineName") or _have2[_code].get("obslineName") or ""
            else:
                cands.append(_c)
    # 全局补池最后：涨停热门/主线/观察优先占用 K线精筛名额
    cands.sort(key=lambda x: (0 if x.get("zt_hot") or x.get("mainline") or x.get("obsline") else (1 if x.get("global") else 2), -(x.get("amount") or 0)))
    if len(cands) > int(cfg["cap"]):
        _trunc = cands[: int(cfg["cap"])]
        _have_t = {str(c.get("code")) for c in _trunc}
        _ml_extra = [_c for _c in cands[int(cfg["cap"]):] if _c.get("mainline") or _c.get("obsline")]
        for _c in _ml_extra[: int(cfg.get("mainlineMemberCap") or 40) + int(cfg.get("obsMemberCap") or 30)]:
            _cd = str(_c.get("code"))
            if _cd not in _have_t:
                _trunc.append(_c)
                _have_t.add(_cd)
        # 涨停池票尽量不因 cap 被丢弃（对齐雷达：热门易涨停优先精筛）
        _zt_extra = [_c for _c in cands[int(cfg["cap"]):] if _c.get("zt_hot")]
        for _c in _zt_extra[: int(cfg.get("ztHotExtraCap") or 80)]:
            _cd = str(_c.get("code"))
            if _cd not in _have_t:
                _trunc.append(_c)
                _have_t.add(_cd)
        cands = _trunc

    # 主线龙头候选：全市场下取板块排行前列（5日主力净流入排序）的板块龙头，
    # 放宽市值至 leaderMcapMax、不做“未大幅拉升”硬约束，用 leaderOk 确认形态与资金。
    leader_cands: list[dict[str, Any]] = []
    if market in ("all", "hs", "kc") and (board_pool or _ml_leaders or _obs_leaders):
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
                if not _market_ok(code, market):
                    continue  # 龙头层按市场隔离（hs=60/00、kc=30/688）
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
        # ①′ 复盘次主线（观察板块）龙头：资金+技术双确认的第二梯队，可进王者兜底（优先于纯资金热度）
        for _on in (_dml_obs or [])[: int(cfg.get("obsBoards") or 3)]:
            if _dml_names and _on in _dml_names:
                continue  # 已是主线，跳过
            _b1 = next((b for b in (board_pool or []) if str(b.get("name") or "").strip() == _on), None)
            _lds1 = (_obs_leaders or {}).get(_on) or (_b1 or {}).get("leaders") or []
            for _ld in (_lds1 or [])[: int(cfg.get("leaderPerBoard") or 2)]:
                _row1 = _ld.get("_row") if isinstance(_ld, dict) else None
                code1 = str((_row1 or {}).get("f12") or _ld.get("code") or "")
                if not re.fullmatch(r"\d{6}", code1) or code1 in seen_leader:
                    continue
                if not _market_ok(code1, market):
                    continue
                name1 = str((_row1 or {}).get("f14") or _ld.get("name") or "").strip()
                if re.search(r"ST|退", name1):
                    continue
                mcap1 = _num((_row1 or {}).get("f20") or _ld.get("mcap") or 0)
                if mcap1 and not (0 < mcap1 <= float(cfg.get("leaderMcapMax") or 800.0) * 1e8):
                    continue
                seen_leader.add(code1)
                leader_cands.append({
                    "code": code1, "name": name1,
                    "price": _num((_row1 or {}).get("f2") or _ld.get("price") or 0),
                    "pct": _num((_row1 or {}).get("f3") if (_row1 or {}).get("f3") is not None else _ld.get("pct") or 0),
                    "amount": _num((_row1 or {}).get("f6") or _ld.get("amount") or 0),
                    "mcap": mcap1,
                    "floatMcap": _num((_row1 or {}).get("f21") or 0),
                    "turnover": _num((_row1 or {}).get("f8") or _ld.get("turnover") or 0),
                    "pe": _num((_row1 or {}).get("f9") or 0),
                    "pb": _num((_row1 or {}).get("f23") or 0),
                    "volRatio": _num((_row1 or {}).get("f10") or 0),
                    "fund": _num((_row1 or {}).get("f62") or _ld.get("fund") or 0),
                    "fundIn": _num((_row1 or {}).get("f62") or _ld.get("fund") or 0),
                    "fund5": _num((_row1 or {}).get("f164") or _ld.get("fund5") or 0),
                    "ind": str((_row1 or {}).get("f100") or "").strip(), "indCnt": 0,
                    "hot": True, "hotName": _on, "kwHits": [],
                    "A": None, "snap": None, "final": None,
                    "revHit": True, "revName": _on,
                    "obsline": True, "obslineName": _on,
                    "_board": _on, "_board_tier": "key",
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
                if not _market_ok(code, market):
                    continue  # 龙头层按市场隔离
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
    sem = asyncio.Semaphore(8)

    async def work(c: dict[str, Any], cfg_use: dict[str, Any] | None = None) -> None:
        async with sem:
            bars = await _kline_with_retry(c["code"], variant, priority_override, allow_paid, use_cache=use_cache)
            if not bars:
                return
            c["A"] = analyze(bars, c, cfg_use or cfg, market, loose_macd=(market == "all"))
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
        await asyncio.sleep(0.05)
    for c in leader_cands:
        tasks.append(asyncio.create_task(work(c, leader_cfg)))
        await asyncio.sleep(0.05)
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

    # 复盘主线/次主线板块成分标记：主线板块内的标的优先主推（资金+技术双确认），次主线次之
    _mlm = _mainline_members(_dml_names) if _dml_names else None
    _obsm = _mainline_members(_dml_obs) if _dml_obs else None
    _ml_codes = (_mlm or {}).get("all") or set()
    _ml_by_name = (_mlm or {}).get("by_name") or {}
    _obs_codes = (_obsm or {}).get("all") or set()
    _obs_by_name = (_obsm or {}).get("by_name") or {}
    for _c in analyzed + leader_analyzed:
        _code = str(_c.get("code") or "")
        if _code in _ml_codes or _c.get("mainline"):
            _c["mainHit"] = True
            _c["mainName"] = _c.get("mainlineName") or next(
                (n for n, codes in _ml_by_name.items() if _code in codes), ""
            )
        elif _code in _obs_codes or _c.get("obsline"):
            _c["obsHit"] = True
            _c["obsName"] = _c.get("obslineName") or next(
                (n for n, codes in _obs_by_name.items() if _code in codes), ""
            )

    # 复盘主线/观察板块补齐板块榜：不在资金热度池时也入榜。
    # 无主线时注入观察板块，避免电风扇日榜上只有资金热板块、观察板块缺席。
    _inject_names = list(_dml_names) if _dml_names else list(_dml_obs or [])[:3]
    _inject_as_ml = bool(_dml_names)
    if market in ("all", "hs", "kc") and _inject_names:
        try:
            from .daily_report import SECTORS, SECTOR_BOARD_ALIASES as _SBA
            _have = {str(b.get("name") or "") for b in (board_pool or [])}
            _pool_names = set(_have)
            # 主线/观察真实资金批量补拉：不在资金热度池时也能显示今日/5日主力
            _ML_FUNDS: dict[str, dict[str, Any]] = {}
            try:
                _miss_secs: list[tuple[str, str]] = []
                for _mn2 in _inject_names:
                    if _mn2 in _have:
                        continue
                    _sec2 = ""
                    try:
                        _sec2 = (_MAINLINE_BOARD_MAP.get(_mn2) or [""])[0] if _MAINLINE_BOARD_MAP.get(_mn2) else await _resolve_board_secid(_mn2)
                        if not _sec2:
                            _sec2 = _MAINLINE_SECID_FALLBACK.get(_mn2) or ""
                    except Exception:
                        _sec2 = _MAINLINE_SECID_FALLBACK.get(_mn2) or ""
                    if _sec2:
                        _miss_secs.append((_mn2, _sec2))
                if _miss_secs:
                    _funds2 = await _fetch_mainline_funds([_s for _, _s in _miss_secs])
                    for _mn2, _sid2 in _miss_secs:
                        if _sid2 in _funds2:
                            _ML_FUNDS[_mn2] = _funds2[_sid2]
            except Exception:
                pass
            for _mn in _inject_names:
                if _mn in _have:
                    continue
                _members = SECTORS.get(_mn) or []
                _secid = ""
                try:
                    _secid = (_MAINLINE_BOARD_MAP.get(_mn) or [""])[0] if _MAINLINE_BOARD_MAP.get(_mn) else await _resolve_board_secid(_mn)
                    if not _secid:
                        _secid = _MAINLINE_SECID_FALLBACK.get(_mn) or ""
                except Exception:
                    _secid = _MAINLINE_SECID_FALLBACK.get(_mn) or ""
                # 龙头带真实行情：优先复用主线/观察成分拉取时已获得的 leaders；
                # 板块 secid 解不出时用复盘静态代表（SECTORS），仅补实时涨跌，不混入真实板块 top3
                _ml_lds = (_ml_leaders or {}).get(_mn) or (_obs_leaders or {}).get(_mn) or []
                if not _ml_lds:
                    _ml_lds = [
                        {"code": _c, "name": _n, "pct": None, "amount": 0.0,
                         "mcap": 0.0, "turnover": 0.0, "fund": 0.0, "fund5": 0.0, "_row": {}}
                        for _c, _n in _members[:3]
                    ]
                    # 静态龙头补实时行情：板块 secid 解不出/上游失败时，代表股也要有真实涨跌
                    try:
                        _qmap = await _fetch_stock_quotes([_ld.get("code") or "" for _ld in _ml_lds])
                        for _ld in _ml_lds:
                            _q = _qmap.get(str(_ld.get("code") or ""))
                            if not _q:
                                continue
                            _ld["pct"] = _q.get("pct")
                            _ld["amount"] = _q.get("amount") or 0.0
                            _ld["mcap"] = _q.get("mcap") or 0.0
                            _ld["turnover"] = _q.get("turnover") or 0.0
                            _ld["fund"] = _q.get("fund") or 0.0
                            _ld["fund5"] = _q.get("fund5") or 0.0
                            _ld["_row"] = _q
                    except Exception:
                        pass
                # 主线/观察资金：按别名从资金池匹配真实板块（如 创新药CXO→创新药），匹配不到保持 0
                _src = None
                _aliases = _SBA.get(_mn) or [_mn]
                # 按别名顺序优先匹配（完全相等 → 包含），如 创新药CXO→创新药，兜底医药生物
                for _round in (0, 1):
                    for _a in _aliases:
                        if not _a:
                            continue
                        for _b in (board_pool or []):
                            _bn = str(_b.get("name") or "").strip()
                            if _bn not in _pool_names:
                                continue
                            if (_round == 0 and _bn == _a) or (_round == 1 and _a in _bn):
                                _src = _b
                                break
                        if _src is not None:
                            break
                    if _src is not None:
                        break
                if _src is None:
                    _src = _ML_FUNDS.get(_mn)
                board_pool.append({
                    "name": _mn, "secid": _secid,
                    "f164": float((_src or {}).get("f164") or 0),
                    "f62": float((_src or {}).get("f62") or 0),
                    "p5": (_src or {}).get("p5"),
                    "pct": (_src or {}).get("pct"),
                    "hot": True,
                    "mainline": bool(_inject_as_ml),
                    "observe": not _inject_as_ml,
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
        # 风格门槛调参：电风扇抬高（只做回踩低吸）、震荡保守、趋势放宽、防守沿用现有
        # 全市场视图（all，服务 MACD首红/10元下）是「全市场强势筛选」，不跟随主线状态：
        # 今日无主线导致风格判 fan/trend 波动时，门槛保持稳定基准，避免强势刚启动标的被误杀。
        _all_view = market == "all"
        _style_delta = 0 if _all_view else {"fan": 4, "chop": 2, "trend": -2, "defensive": 0}.get(style_mode, 0)
        _sm = float(cfg.get("scoreMin") or 50) - (2 if relaxed else 0) + _style_delta
        _pos_max = (float(cfg["posMax"]) + (5 if relaxed else 0)) / 100
        _chg5_max = float(cfg["max5d"]) + (5 if relaxed else 0)
        _turn_min = 1.5 if relaxed else float(cfg["turnMin"])
        _sm_plain = float(cfg.get("scoreMin") or 50) + (8 if relaxed else 12) + _style_delta
        _sm_base = float(cfg.get("scoreMin") or 50) + (0 if relaxed else 2) + _style_delta
        for c in cands:
            if (c.get("bearish") or {}).get("level") == "hard":
                continue
            a = c["A"]
            p = a.get("patterns") or {}
            # 电风扇：只做主线/次主线 + 回踩低吸类形态，不追纯热度
            if style_mode == "fan" and not _all_view and not (
                c.get("mainHit") or c.get("obsHit") or c.get("revHit")
                or p.get("pullback") or p.get("ztPullback") or p.get("pullback2") or p.get("firstBoardRight")
            ):
                continue
            if str(c.get("ind") or "") in rev_names:
                c["revHit"] = True
                c["revName"] = str(c.get("ind") or "")
            _sv = float(a.get("score") or 0)
            if p.get("surgeStart") or p.get("pullback") or p.get("ztPullback") or p.get("pullback2") \
                    or p.get("macdFirstRed") or p.get("firstBoardRight") or p.get("washOut") \
                    or p.get("firstWeek") or p.get("tightZt"):
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
            # 首板/异动回踩类（板后回踩/底部异动/近1周首板/首板右侧/单日砸盘企稳）：
            # 位置放宽至 posMax+25%、10日涨幅上限放宽至 40%（回踩企稳的自然形态，不误杀刚异动的票）
            _ev_pat = bool(p.get("pullback2") or p.get("surgeStart") or p.get("surgePullback") or p.get("firstWeek")
                           or p.get("pb45") or p.get("washOut") or p.get("firstBoardRight")
                           or p.get("ztPullback"))
            # P0-4 门槛校准：强动量（刚右侧起来）豁免“没涨”硬门槛——位置放宽到 ≤60%、
            # 5日涨幅 +10%（避免误杀刚放量启动的强势票；弱票仍守原门槛）
            _mom_ok = bool(p.get("strongMom"))
            _pos_ok = a.get("pos", 99) <= (min(_pos_max + 0.25, 0.60) if (_ev_pat or c.get("mainHit") or _mom_ok) else _pos_max)
            _chg5_ok = a.get("chg5", 999) <= (_chg5_max + (10 if _mom_ok else 0))
            _chg10_ok = a.get("chg10", 999) <= (40.0 if _ev_pat else float(cfg["max10d"]))
            if (
                _pos_ok
                and _chg5_ok
                and _chg10_ok
                and a.get("chg20", 999) <= float(cfg["max20d"])
                and a.get("chg60", 999) <= float(cfg["max60d"])
                and _turn_min <= _num(c.get("turnover")) <= float(cfg["turnMax"])
                and not a.get("volShrink")
                and not a.get("newHighWeak")
                and not a.get("atHighWeak")
                and not (a.get("amp20") and float(a.get("amp20") or 0) < 3)
                and not a.get("downSlope")
                and (a.get("pathOk", True) if "pathOk" in a else True)
                and must_start and line_ok
            ):
                if c.get("mainHit"):
                    a["score"] = min(100, int(a["score"]) + 4)
                elif c.get("obsHit"):
                    a["score"] = min(100, int(a["score"]) + 2)
                if c["revHit"]:
                    a["score"] = min(100, int(a["score"]) + 3)
                out.append(c)
        return out

    fine = _fine_pass(analyzed, False)
    relaxed_used = bool(not fine)
    if relaxed_used:
        fine = _fine_pass(analyzed, True)

    fine.sort(key=lambda x: (0 if x.get("mainHit") else 1, -int(x["A"].get("score") or 0)))
    finals = fine[: int(cfg["aiTop"])]    # K线快筛完成后发布有限预览；未完成 AI/基本面复核，不视为正式主推。
    try:
        _pk = f"{market}-scan:{today8}"
        _pp = []
        for _rank, _pc in enumerate(fine[:max(8, int(cfg.get("aiTop") or 5) * 2)], 1):
            _pc["rank"] = _rank
            _pp.append(_pick_out(_pc))
        _PARTIAL_CACHE[_pk] = (time.time(), {"ok": True, "partial": True, "stage": "quick",
            "date": today, "asof": str(fine[0].get("lastDate") or today),
            "market_code": market, "market": mkt_env, "regime": regime,
            "mainlines": [{"name": n, "src": "daily"} for n in _dml_names],
            "picks": _pp, "message": "K线初筛完成，深度复核进行中"})
    except Exception:
        pass

    prog_snap = {"n": 0}
    snap_total = 0
    sem2 = asyncio.Semaphore(3)

    # 龙虎榜是全市场映射，只需在本轮扫描预热一次；避免每只候选重复触发缓存检查。
    try:
        _ths_lhb_map, _em_lhb_map = await asyncio.gather(
            _fetch_ths_lhb_map(), _fetch_lhb_map(), return_exceptions=True
        )
        if not isinstance(_ths_lhb_map, dict):
            _ths_lhb_map = {}
        if not isinstance(_em_lhb_map, dict):
            _em_lhb_map = {}
    except Exception:
        _ths_lhb_map, _em_lhb_map = {}, {}

    async def snap_work(c: dict[str, Any], leader_mode: bool = False) -> None:
        async with sem2:
            try:
                snap = await _fetch_snapshot(_stock_secid(c["code"]), c["code"], c["name"], variant, priority_override, allow_paid)
            except Exception:
                snap = {"error": "fetch"}
            c["snap"] = snap
            # Basic data and minute tail strength are independent; run them together.
            async def _fund_job():
                try:
                    return await _fundamental_check(c)
                except Exception:
                    return None

            async def _minute_job():
                try:
                    return _tail_strength(await _fetch_minute(c["code"]))
                except Exception:
                    return {}

            c["fund"], c["tail"] = await asyncio.gather(_fund_job(), _minute_job())
            _lhbe = _ths_lhb_map.get(c["code"])
            _src = "ths"
            if not _lhbe:
                _lhbe = _em_lhb_map.get(c["code"])
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

    # 解禁日历覆盖全部 fine 候选：仅 finals 复核时，大规模解禁标的会从主推/备选
    # 兜底池漏检（三协电机 920100 案例：9/8 解禁 2.77%·28.3 亿仍进北证主线主推）。
    # 批量解禁表为日缓存，逐候选零上游成本；发现硬伤置 fund.level=hard，由 _post_adjust 统一剔除。
    async def _ensure_unlock(c: dict[str, Any]) -> None:
        if isinstance(_fund_of(c), dict):
            return
        try:
            unlocks = await _fetch_unlock(str(c.get("code") or ""))
            hard, warn = _unlock_grade(unlocks)
            if hard or warn:
                c["fund"] = {
                    "level": "hard" if hard else "warn",
                    "growth": 0, "flags": [],
                    "newsHard": hard, "newsWarn": warn,
                    "earnNeg": [], "earnPos": [], "fin": None,
                }
        except Exception:
            pass

    _fund_gap = [c for c in fine if not isinstance(_fund_of(c), dict)]
    if _fund_gap:
        _set_prog("snapshot", 78, "解禁日历复核（全部候选）…", 0, len(_fund_gap))
        _u_sem = asyncio.Semaphore(6)
        async def _u_work(c: dict[str, Any]) -> None:
            async with _u_sem:
                await _ensure_unlock(c)
        await asyncio.gather(*[_u_work(c) for c in _fund_gap], return_exceptions=True)

    def _post_adjust(c: dict[str, Any]) -> bool:
        """利空/业绩/消息警示降权；返回 False 表示硬伤剔除（已计入 hard_rejected）。"""
        if c.get("final") is None:
            c["final"] = int((c.get("A") or {}).get("score") or 0)
        fund = _fund_of(c)
        if fund and fund.get("level") == "hard":
            return False
        # 用户口径「回踩企稳低吸·没破位」：板后破位(跌破板日低点/板后长阴)/跌放量出货
        # 一律不进推荐池（含备选），避免把“破位/出货”标的当潜在龙头主推；
        # 首板失败(跌破涨停价)保留为警示（未破板日低点仍可能回踩企稳，降权展示）
        _pick_rc = set((c.get("A") or {}).get("riskCodes")
                       or _risk_codes_of((c.get("A") or {}).get("risks") or []))
        if _pick_rc & {"pb_break", "vol_sell"}:
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
    # 北证全市场：不跟主线，纯评分选优（宁缺毋滥）；其余市场主线命中优先
    _pure = market == "bj_all"
    # 事件回踩优先：1-2 周内首板 / 异动 8-10%+ → 回调企稳未破位者排序置前；
    # firstWeek（近1周首板·底部右侧）最优先，pb45 / washOut 次之，
    # 板后回踩 / 底部异动 / 首板右侧上拐 再之（都是用户要的“刚右侧异动回踩企稳”形态）
    def _evp(c: dict[str, Any]) -> int:
        p = (c.get("A") or {}).get("patterns") or {}
        if p.get("firstWeek"):
            return 4
        if p.get("pb45") or p.get("washOut"):
            return 3
        if p.get("pullback2") or p.get("surgeStart") or p.get("surgePullback") or p.get("firstBoardRight"):
            return 2
        return 1 if p.get("eventPullback") else 0
    # 注意：事件回踩形态“优先置前”需按 -_evp 升序（高 evp=更优先）；若用 _evp 升序会把
    # 刚异动/首板回踩的标的排在最后（历史 bug：创达新材 surgeStart 被挤到备选池尾部）
    # P0-3 强动量优先：同级事件形态内，先选“刚右侧+放量+涨停/大阳确认”的强势标的
    def _mom_tier(x: dict[str, Any]) -> int:
        return 0 if bool((x.get("A") or {}).get("patterns", {}).get("strongMom")) else 1
    def _ztw(x: dict[str, Any]) -> int:
        """近一周有涨停软优先：同事件形态内，有涨停的强势票排前（2026-08-25 A 方案）。"""
        return 0 if bool((x.get("A") or {}).get("patterns", {}).get("ztWeek")) else 1

    _sort_key = (lambda x: (
        -_evp(x), _ztw(x), _mom_tier(x), -int(x.get("final") or 0),
    )) if _pure else (lambda x: (
        -_evp(x),
        _ztw(x),
        _mom_tier(x),
        0 if x.get("mainHit") else (1 if x.get("obsHit") else 2),
        -int(x.get("final") or 0),
    ))
    zero_risk.sort(key=_sort_key)
    warned.sort(key=_sort_key)
    pool = zero_risk + warned

    all_sorted = sorted(fine, key=_sort_key)
    # 电风扇风格：回踩企稳优先（低吸为主，不追热度；北证全市场保持纯评分）
    if style_mode == "fan" and not _pure:
        all_sorted.sort(key=lambda x: (
            0 if _evp(x) else 1,
            _ztw(x),
            0 if (x.get("mainHit") or x.get("obsHit") or x.get("revHit")) else 1,
            0 if x.get("mainHit") else (1 if x.get("obsHit") else 2),
            -int(x.get("final") or 0),
        ))

    picks: list[dict[str, Any]] = []
    watch_list: list[dict[str, Any]] = []
    if market in ("all", "hs", "kc"):
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

        # 低位右侧优先；已站上144/远高于60/涨停热门站上60 时放宽，避免滤光真强势
        def _low_right_ok(c, pos_lo=0.60, c10_hi=40.0, mcap_hi=600.0):
            a = c.get("A") or {}
            if a.get("above_ma144") or a.get("ma60_strong") or (
                a.get("above_ma60") and (c.get("zt_hot") or _pick_zt_ok(c))
            ):
                pos_lo, c10_hi, mcap_hi = 0.88, 60.0, 1200.0
            try:
                _p = float(a.get("pos") if a.get("pos") is not None else c.get("pos") or 0)
            except Exception:
                _p = 0.0
            try:
                _c10 = float(a.get("chg10") if a.get("chg10") is not None else c.get("chg10") or 0)
            except Exception:
                _c10 = 0.0
            _mc = float(c.get("mcap") or 0) / 1e8
            return _p <= pos_lo and _c10 <= c10_hi and _mc <= mcap_hi
        leader_final = [c for c in leader_final if _low_right_ok(c)]
        leader_final = [c for c in leader_final if _path_gate(c, require_active=True)]
        leader_final.sort(key=lambda x: (-_evp(x), _ztw(x), _mom_tier(x),
                                         0 if x.get("mainHit") else 1, -int(x.get("final") or 0)))

        # 王者：主线/观察强势优先；全空则涨停热门强势兜底（对齐雷达出票）
        _main_leaders = [c for c in leader_final if c.get("mainHit")]
        _obs_leaders = [c for c in leader_final if not c.get("mainHit") and c.get("obsHit")]
        _rq_zt = bool(cfg.get("pickRequireZt", True))
        _ml_ma = _filter_strong_picks(_main_leaders, require_zt=_rq_zt)
        _ol_ma = _filter_strong_picks(_obs_leaders, require_zt=_rq_zt)
        _main_leaders = sorted(_ml_ma, key=lambda x: (-_ma_tier_rank(x), -int(x.get("final") or 0)))
        _obs_leaders = sorted(_ol_ma, key=lambda x: (-_ma_tier_rank(x), -int(x.get("final") or 0)))
        if style_mode == "fan" and not _dml_names:
            _main_leaders = [c for c in _main_leaders if _evp(c) >= 1]
            _obs_leaders = [c for c in _obs_leaders if _evp(c) >= 1]
        _lead_src = (_main_leaders or _obs_leaders)[:1]
        _pick_role0 = "leader"
        if not _lead_src:
            _hot_pool = [
                c for c in all_sorted
                if (c.get("zt_hot") or c.get("hot") or c.get("global")
                    or c.get("mainHit") or c.get("obsHit"))
                and _path_gate(c, require_active=True) and _low_right_ok(c)
            ]
            _hot_strong = _filter_strong_picks(_hot_pool or all_sorted, require_zt=_rq_zt)
            _hot_strong = sorted(_hot_strong, key=lambda x: (-_ma_tier_rank(x), -int(x.get("final") or 0)))
            _lead_src = _hot_strong[:1]
            _pick_role0 = "hot_strong"
        for c in _lead_src:
            c["tier"] = "king"
            c["star"] = True
            c["pick_role"] = _pick_role0
            picks.append(c)
        # 卡位：最多 pickMaxN；涨停热门强势可走简化通道
        _pick_max = max(2, int(cfg.get("pickMaxN") or 4))
        if market == "bj_all":
            _pick_max = max(_pick_max, 4)
        if len(picks) < _pick_max:
            used = {str(c.get("code")) for c in picks}
            ind_used: dict[str, int] = {}
            for c in picks:
                _ik = str(c.get("ind") or "-")
                ind_used[_ik] = ind_used.get(_ik, 0) + 1
            _rq_key = bool(cfg.get("pickRequireZt", True))
            _strong_codes = {
                str(c.get("code"))
                for c in _filter_strong_picks(all_sorted, require_zt=_rq_key)
            }
            for c in all_sorted:
                if str(c.get("code")) in used or str(c.get("code")) not in _strong_codes:
                    continue
                _f = int(c.get("final") or 0)
                if c.get("mainHit") or c.get("obsHit"):
                    if _f < (62 if defensive_mode else 52) or not _low_right_ok(c):
                        continue
                    if (style_mode == "fan" and not _dml_names and c.get("obsHit")
                            and not c.get("mainHit") and _evp(c) < 1):
                        continue
                    c["pick_role"] = "catchup"
                elif c.get("zt_hot") or c.get("hot") or c.get("global"):
                    if _f < (58 if defensive_mode else 48) or not _low_right_ok(c):
                        continue
                    if not _path_gate(c, require_active=True):
                        continue
                    c["pick_role"] = "hot_strong"
                else:
                    if style_mode == "fan" and not _dml_names:
                        continue
                    if _f < (62 if defensive_mode else 55):
                        continue
                    if not (c.get("revHit") or c.get("obsHit") or c.get("hot") or c.get("boardLeader")):
                        continue
                    if not (_num(c.get("mcap")) >= float(cfg.get("catchupMcapMin") or 50.0) * 1e8
                            and _num(c.get("mcap")) <= float(cfg.get("catchupMcapMax") or 300.0) * 1e8
                            and (c.get("A") or {}).get("chg5", 999) <= float(cfg.get("catchupChg5Max") or 15.0)
                            and (c.get("A") or {}).get("pos", 99) <= float(cfg.get("catchupPosMax") or 0.40)
                            and _num(c.get("fundIn")) > 0):
                        continue
                    c["pick_role"] = "catchup"
                _ik = str(c.get("ind") or "-")
                if ind_used.get(_ik, 0) >= 2:
                    continue
                c["tier"] = "key"
                c["star"] = False
                picks.append(c)
                used.add(str(c.get("code")))
                ind_used[_ik] = ind_used.get(_ik, 0) + 1
                if len(picks) >= _pick_max:
                    break

    if not picks:
        # 北证 / 龙头不足兜底：王者(1⭐) + 重点；仍须强势两段门，宁缺勿推弱势
        _tier_min = 58 if defensive_mode else (52 if market == "bj_all" else 56)
        _rq_zt = bool(cfg.get("pickRequireZt", True))
        _fb_src = list(pool or []) or list(all_sorted or [])
        _fb_strong = {
            str(c.get("code"))
            for c in _filter_strong_picks(_fb_src, require_zt=_rq_zt)
        }
        def _strong_enough(c):
            return str(c.get("code")) in _fb_strong
        king: dict[str, Any] | None = None
        _z_pool = [c for c in zero_risk if _strong_enough(c)]
        if market == "bj_all":
            # 北证全市场：王者优先「刚异动/首板后回踩企稳」事件标的（evp≥1）。
            def _king_rank(c):
                _ev = _evp(c) >= 1
                _mo = bool((c.get("A") or {}).get("patterns", {}).get("strongMom"))
                _zw = bool((c.get("A") or {}).get("patterns", {}).get("ztWeek"))
                _zr = (not risk_of(c) and (c.get("bearish") or {}).get("level") == "pass"
                       and (_fund_of(c) or {}).get("level", "pass") == "pass")
                return (0 if (_zw and _mo and _ev and _zr) else
                        (1 if (_zw and _ev and _zr) else
                         (2 if (_zw and _ev) else
                          (3 if (_mo and _ev and _zr) else
                           (4 if (_mo and _ev) else
                            (5 if (_ev and _zr) else
                             (6 if _mo else (7 if _ev else (8 if _zr else 9)))))))),
                        -int(c.get("final") or 0))
            _king_pool = sorted(
                [c for c in pool if int(c.get("final") or 0) >= _tier_min and _strong_enough(c)],
                key=_king_rank,
            )
            _z_pool = _king_pool or _z_pool
        if _z_pool:
            z0 = _z_pool[0]
            if int(z0.get("final") or 0) >= _tier_min:
                if not defensive_mode or (z0.get("mainHit") or z0.get("revHit") or z0.get("hot") or z0.get("boardLeader")):
                    king = z0
        if king is None and all_sorted:
            for cand in all_sorted:
                if not _strong_enough(cand):
                    continue
                if int(cand.get("final") or 0) >= _tier_min and _num((cand.get("A") or {}).get("pe")) > 0:
                    if not defensive_mode or (cand.get("mainHit") or cand.get("revHit") or cand.get("hot") or cand.get("boardLeader")):
                        king = cand
                        break
            if king is None:
                for cand in all_sorted:
                    if not _strong_enough(cand):
                        continue
                    if int(cand.get("final") or 0) >= _tier_min:
                        if not defensive_mode or (cand.get("mainHit") or cand.get("revHit") or cand.get("hot") or cand.get("boardLeader")):
                            king = cand
                            break
        rest = [c for c in pool if c is not king and int(c.get("final") or 0) >= _tier_min and _strong_enough(c)]
        if market == "bj_all":
            rest.sort(key=_sort_key)  # 北证全市场：刚异动/首板回踩形态优先入主推（仍须过 final 入选线）
        keys = rest[:3] if market == "bj_all" else rest[:1]  # 北证全市场 2⭐+2 重点；其余收敛为 1⭐+1 重点
        if king:
            king["tier"] = "king"
            king["star"] = True
            picks.append(king)
        for c in keys:
            c["tier"] = "key"
            c["star"] = False
            picks.append(c)
    # 主推 2×2 排版：足 4 只显示 4 只；不足 4 只只显示 2 只（3 只砍为 2 只，避免缺一格）；1 只补足到 2 只。
    # 北证全市场放宽到最多 4 只（2⭐+2 重点），其余市场仍收敛为最多 2 只
    if market == "bj_all":
        if len(picks) > 4:
            picks = picks[:4]
        elif len(picks) == 3:
            picks = picks[:2]
    else:
        _pm = max(2, int(cfg.get("pickMaxN") or 4))
        if len(picks) > _pm:
            picks = picks[:_pm]
    # 主推仅 1 只时，从备选池补 1 只到 2 只（仍须强势两段门），避免单卡孤悬；无强势则宁缺
    if len(picks) == 1 and all_sorted:
        _used = {str(c.get("code")) for c in picks}
        _rq_zt2 = bool(cfg.get("pickRequireZt", True))
        _bk_ok = {
            str(c.get("code"))
            for c in _filter_strong_picks(all_sorted, require_zt=_rq_zt2)
        }
        for _bk in all_sorted:
            if str(_bk.get("code")) in _used:
                continue
            if int(_bk.get("final") or 0) < 40:
                continue
            if str(_bk.get("code")) not in _bk_ok:
                continue
            _bk["tier"] = "key"
            _bk["star"] = False
            _bk["pick_role"] = "backup"
            picks.append(_bk)
            break
    # 情绪控量：偏冷时精选最多 1 只；正常最多 pickMaxN
    _emo_reg = str((emotion or {}).get("regime") or "")
    if _emo_reg == "risk_off":
        picks = picks[:1]
    else:
        _pm2 = max(1, int(cfg.get("pickMaxN") or 4))
        if market == "bj_all":
            _pm2 = max(_pm2, 4)
        picks = picks[:_pm2]

    for c in picks:
        if relaxed_used and c.get("pick_role") != "leader":
            c["relaxed"] = True
        c["pick_lane"] = "pick"
        c["decision"] = build_decision(c, lane="pick")
        c["strategy"] = build_strategy(c, c.get("tier") or "normal", c.get("pick_role"))
    # 轮动偏快时：追加一句用户可读纪律（非运维说明）
    if style_mode == "fan":
        for _c in picks:
            _st = _c.get("strategy") or {}
            _extra = "行情轮动偏快：优先等回踩再看，避免追高；破位先观望。"
            _st["rules"] = ((_st.get("rules") or "") + "；" if _st.get("rules") else "") + _extra
            _c["strategy"] = _st
    for i, c in enumerate(picks):
        c["rank"] = i + 1

    picked = {str(c.get("code")) for c in picks}
    # 观察池：站上60+涨停热门，但不达精选严门
    _watch_src = list(all_sorted or []) or list(pool or [])
    _rq_w = bool(cfg.get("pickRequireZt", True))
    watch_list = _filter_watch_picks(_watch_src, exclude_codes=picked, require_zt=_rq_w, limit=6)
    if _emo_reg == "risk_off":
        watch_list = watch_list[:2]
    for i, c in enumerate(watch_list):
        c["tier"] = "watch"
        c["star"] = False
        c["pick_role"] = "watch"
        c["pick_lane"] = "watch"
        c["rank"] = i + 1
        c["decision"] = build_decision(c, lane="watch")
        c["strategy"] = build_strategy(c, "normal", "watch")
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
            _rec["status"] = "建议先放下（出现硬伤）"; _rec["tag"] = "bad"
        elif _c0 in picked:
            _rec["status"] = "可继续跟踪（今日仍在精选）"; _rec["tag"] = "ok"
        elif _c0 in fine_codes:
            _rec["status"] = "可继续跟踪（仍达标，未进精选）"; _rec["tag"] = "ok"
        elif _cur:
            _a0 = _cur.get("A") or {}
            if (float(_a0.get("pos") or 99) > float(cfg["posMax"]) / 100
                    or float(_a0.get("chg5") or 999) > float(cfg["max5d"])
                    or float(_a0.get("chg10") or 999) > float(cfg["max10d"])):
                _rec["status"] = "涨幅过热（注意风险）"; _rec["tag"] = "warn"
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
    runners = [c for c in all_sorted if str(c.get("code")) not in picked][: (12 if market == "bj_all" else 10)]

    asof = picks[0].get("lastDate") if picks else (today or "")
    pick_out = [_pick_out(c) for c in picks]
    watch_out = [_pick_out(c) for c in watch_list]
    run_out = [_runner_out(c) for c in runners]
    # MACD 量能首红专栏：全候选池收集“底部刚收红/1-3根红柱+量能确认”标的，
    # 剔除硬伤，刚收红优先 + 评分排序，最多 8 只（独立于主推/备选）
    macd_red_pool: list[dict[str, Any]] = []
    _mr_seen: set[str] = set()
    for _c in analyzed:
        _cp = (_c.get("A") or {}).get("patterns") or {}
        if not _cp.get("macdFirstRed"):
            continue
        _ccode = str(_c.get("code") or "")
        if not _ccode or _ccode in _mr_seen:
            continue
        _mr_seen.add(_ccode)
        if (_c.get("bearish") or {}).get("level") == "hard":
            continue
        await _ensure_unlock(_c)
        if (_fund_of(_c) or {}).get("level") == "hard":
            continue
        _c["_inFine"] = _ccode in fine_codes
        macd_red_pool.append(_c)
    # 事件回踩优先：同时命中 1-2 周内首板/异动回踩企稳的 MACD 首红排前，纯首红兜底
    macd_red_pool.sort(key=lambda x: (
        -_evp(x),
        0 if x.get("_inFine") else 1,
        int((x.get("A") or {}).get("macdFirstRedDays") or 0),
        -int(x.get("final") or 0),
    ))
    macd_red_out = [_macd_red_out(c) for c in macd_red_pool[:8]]
    # 板块 secid 解析（供前端点击跳转 AI行情官对应板块）
    try:
        await _attach_board_secids(rev_mainlines[:10], hot.get("list") or [])
    except Exception:
        pass
    if market in ("all", "hs", "kc"):
        board_rank = _board_rank_funds(
            board_pool or [], int(cfg.get("allBackupN") or 4),
            mainline_names=_dml_names or None, market=market,
            observe_names=_dml_obs or None,
        )
    else:
        board_rank = _board_rank(rev_mainlines[:10], hot.get("list") or [])
    # 北证板块排行龙头：从已分析的候选按行业聚合 top3（成交额），零上游成本
    if market in ("bj", "bj_all"):
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

    # 板块排行与主线口径同步：主线按复盘顺序前置（第1=今日主线 king），与 mainlines 卡片完全一致
    if market in ("all", "hs", "kc", "bj", "bj_all"):
        board_rank = _sync_rank_mainlines(board_rank, _dml_names or [], observe_names=_dml_obs or None)
        board_rank = _attach_ml_why(board_rank, _dml_names or [], _dml_info)

    # 复盘主线统一口径：当日已定型（含“无主线”）就以复盘判定为准；
    # 仅当复盘侧完全无数据（_dml 为 None）时才回退本栏目的异动反推（rev_mainlines）。
    result_mainlines = rev_mainlines[:10]
    if _dml:
        result_mainlines = []
        for _n in _dml_names:
            _mi = dict(_dml_info.get(_n) or {})
            _mi["name"] = _n
            _mi["src"] = _dml_src or "daily"
            result_mainlines.append(_mi)
    # 行情风格终算（含板块持续性 streak）：覆盖初算
    style = _detect_style(regime, _dml_names, board_rank)
    style_mode = str(style.get("mode") or "chop") if style else "chop"
    # P2「10元下」：全市场优质 <10 元标的（复用 fine 池，零额外上游成本）。
    # 硬伤排除：ST/退市（coarse 已排）、面值退市警戒 <2 元、一字板不可交易、流动性（amountMin 已保证）
    low10_list: list[dict[str, Any]] = []
    tight_list: list[dict[str, Any]] = []
    if market == "all":
        _l10 = [c for c in fine
                if 2.0 <= _num(c.get("price")) < 10.0
                and str((c.get("A") or {}).get("limitQuality") or "") != "one_word"]
        _l10.sort(key=_sort_key)
        low10_list = [_pick_out(c) for c in _l10[:8]]
        _tz = [
            c for c in analyzed
            if (c.get("A") or {}).get("patterns", {}).get("tightZt")
            and _is_hs_kc_code6(str(c.get("code") or ""))
            and not re.search(r"(?:\*?ST)|退", str(c.get("name") or ""), flags=re.I)
            and str((c.get("A") or {}).get("limitQuality") or "") != "one_word"
            and (c.get("bearish") or {}).get("level") != "hard"
        ]
        _tz.sort(key=_sort_key)
        tight_list = [_pick_out(c) for c in _tz[:8]]
    result: dict[str, Any] = {
        "ok": True, "cached": False, "date": today, "asof": asof,
        "market_code": market,
        "meta": {"emotion": emotion},
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
        "observes": [{"name": n, "src": _dml_src or "daily"} for n in _dml_obs],
        "mainline_hit": sorted({str(c.get("mainName") or c.get("mainlineName") or "") for c in picks if c.get("mainHit") and (c.get("mainName") or c.get("mainlineName"))}),
        "mainline_gap": bool(picks) and market in ("all", "hs", "kc") and not any(c.get("mainHit") or c.get("obsHit") for c in picks),
        "board_rank": board_rank,
        "picks": pick_out,
        "watch": watch_out,
        "runners": run_out,
        "macd_reds": macd_red_out,
        "algo": "strong-layer-v2",
        "pickLaneNote": "精选看趋势更强的；观察仅作跟踪，不与精选等同",
        "low10": low10_list,
        "tight": tight_list,
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
        result.pop("macd_reds", None)
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
        "observes": [{"name": n, "src": "daily"} for n in _dml_obs],
            "mainline_hit": sorted({str(c.get("mainName") or c.get("mainlineName") or "") for c in picks if c.get("mainHit") and (c.get("mainName") or c.get("mainlineName"))}),
            "mainline_gap": bool(picks) and market in ("all", "hs", "kc") and not any(c.get("mainHit") or c.get("obsHit") for c in picks),
            "board_rank": board_rank,
            "picks": pick_out, "watch": watch_out, "runners": run_out, "macd_reds": macd_red_out,
            "low10": low10_list, "tight": tight_list, "algo": "strong-layer-v2",
        }
        _save_history(f"{market}:{str(today)}", hist_payload)
        _save_archive(market, str(today), hist_payload)
        if market == "hs":
            _save_hs_column_histories(str(today), asof, hist_payload, result)
        if market == "all":
            _save_all_column_histories(str(today), asof, hist_payload, result)
    if not pick_out and not _market_closed():
        # 盘中空结果（盘前/数据未就绪）：仅短时负缓存，不入盘、不污染整日 6h 缓存
        result["_bad"] = True
        _SCAN_PROGRESS[market] = {"phase": "done", "pct": 100, "done": 0, "total": 0,
                                  "msg": "盘中数据未就绪：展示最近归档（稍后可重新扫描）", "running": False, "ts": time.time()}
    _SCAN_CACHE[full_key] = (time.time(), result)
    _BOARDS_CACHE.pop(boards_key, None)
    _persist_daily_scan_cache()
    return _apply_stale_fallback(result, market, column)


def get_partial_scan(market: str) -> dict[str, Any] | None:
    """返回短时有效的 K 线快筛预览。"""
    _m = str(market or "bj")
    _key = f"{_m}-scan:{time.strftime('%Y%m%d', time.localtime())}"
    _hit = _PARTIAL_CACHE.get(_key)
    if not _hit or time.time() - _hit[0] > 300:
        return None
    return dict(_hit[1])

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
    column: str = "",
) -> dict[str, Any]:
    """掘金扫描并发去重包装：
    - 同市场已有扫描在跑 → 等待复用该任务结果（force 也复用，避免重复全量扫描浪费上游预算）；
    - force=True 无任务在跑 → 启动新扫描（后台/同步皆可）；
    - force=False → 优先今日缓存，无缓存才扫描。"""
    market = str(market or "bj").strip().lower()
    if market not in ("bj", "all", "hs", "kc", "bj_all"):
        market = "bj"
    today8 = time.strftime("%Y%m%d", time.localtime())
    full_key = f"{market}-scan:" + today8
    running = _RUNNING_SCAN.get(market)
    if running is not None and not running.done():
        try:
            await running
        except Exception:
            pass
        hit = _scan_cache_hit(full_key)
        if hit:
            out = dict(hit[1])
            out["cached"] = True
            _SCAN_PROGRESS[market] = {"phase": "done", "pct": 100, "done": 0, "total": 0,
                                      "msg": "已加载今日扫描缓存", "running": False, "ts": time.time()}
            return _apply_stale_fallback(out, market, column)
        return await run_scan(user_id, force=False, cfg_override=cfg_override,
                              boards_only=boards_only, market=market, column=column)

    if force:
        async def _wrap_scan() -> dict[str, Any]:
            try:
                return await run_scan(user_id, force=True, cfg_override=cfg_override,
                                      boards_only=boards_only, market=market, column=column)
            finally:
                _RUNNING_SCAN.pop(market, None)
        t = asyncio.ensure_future(_wrap_scan())
        _RUNNING_SCAN[market] = t
        return await t

    lock = _SCAN_LOCKS.setdefault(market, asyncio.Lock())
    async with lock:
        hit = _scan_cache_hit(full_key)
        if hit:
            out = dict(hit[1])
            out["cached"] = True
            _SCAN_PROGRESS[market] = {"phase": "done", "pct": 100, "done": 0, "total": 0,
                                      "msg": "已加载今日扫描缓存", "running": False, "ts": time.time()}
            return _apply_stale_fallback(out, market, column)
        return await run_scan(user_id, force=False, cfg_override=cfg_override,
                              boards_only=boards_only, market=market, column=column)


# 进程启动即加载当日扫描结果磁盘缓存（减少重启后的上游请求）
_load_daily_scan_cache()


def _detect_style(regime, dml_names, board_rank):
    """行情风格识别：大盘攻守 + 主线连续性 + 板块持续性（电风扇/趋势/震荡）。
    - defensive：沿用防守模式（门槛62/最多2只/仅主线回踩热门龙头），风格不重复调参；
    - trend（趋势）：有复盘主线 且 主线板块连续上榜≥2 天 或 主线≥2 个；门槛放宽 2 分；
    - fan（电风扇）：无主线 或 板块榜前8 中一日游（streak≤1）占比≥60%；门槛抬高 4 分、
      且只做主线/回踩低吸类形态（pullback/ztPullback/pullback2/firstBoardRight）；
    - chop（震荡）：其余，稳健基准（门槛抬高 2 分）。
    """
    try:
        if regime == "defensive":
            return {"mode": "defensive", "label": "风格：防守", "note": "大盘走弱：仅主线双确认+零风险标的，最多 2 只，严格控制标的数量，注意控制仓位风险。"}
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
            return {"mode": "trend", "label": "风格：趋势", "note": "主线持续（连续上榜≥2 天）：主线代表+补涨观察双线跟踪，以回踩企稳为主，避免追高。"}
        if not ml_names or one_day_ratio >= 0.6:
            return {"mode": "fan", "label": "风格：电风扇", "note": "板块快速轮动、一日游偏多：优先主线/回踩企稳形态，避免追当日大涨，破位注意风险。"}
        return {"mode": "chop", "label": "风格：震荡", "note": "方向不明：以主线双确认+零风险标的为主，控制仓位，等主线明朗。"}
    except Exception:
        return {"mode": "chop", "label": "风格：震荡", "note": "方向不明：控制仓位，等主线明朗。"}


def _daily_mainlines():
    """读取复盘锁定主线/次主线（与复盘页完全同口径，掘金/复盘不再打架）：
    1) 优先当日复盘归档 mainlines.json（复盘实际生成，最准）；
       归档存在即代表当日已定型（即使判定“无主线”也返回当日口径，不擅自回退昨日）；
    2) 无归档但当日 sector_scores 缓存存在 → 用缓存 + 连续性约束重算（与复盘报告口径一致）；
    3) 当日完全无数据（盘中/早间未扫描）才回退最近归档日主线（与复盘页展示一致）。
    返回 {"names": [...], "observes": [...], "date": "YYYY-MM-DD", "src": "archive"|"recalc"|"fallback",
          "info": {主线名: {"top5","fund5","fund_t","n_zt","n_surge",...}}}（判定依据小字）或 None。
    """
    try:
        from .daily_report import (ARCHIVE_ROOT, today8, cache_load, pick_main_lines,
                                   _prev_mainlines, mainline_judgment)
        _today = today8()
        # 1) 当日归档（复盘实际生成的主线 + 观察板块）
        _mj = os.path.join(ARCHIVE_ROOT, _today, "mainlines.json")
        if os.path.exists(_mj):
            obj = json.load(open(_mj, encoding="utf-8"))
            ml = obj.get("mainlines") or []
            obs = obj.get("observes") or []
            return {"names": list(ml), "observes": list(obs), "date": _today, "src": "archive",
                    "info": _mainline_info_from_archive(ml, _today)}
        # 2) 当日板块评分缓存 + 连续性约束重算（与复盘报告口径一致）
        sc = cache_load("sector_scores")
        if sc:
            _prev = _prev_mainlines() or {}
            _pl = cache_load("plates")
            ml, obs, _av = pick_main_lines(sc, (_prev.get("mainlines") or []), _pl)
            return {"names": list(ml), "observes": list(obs or []), "date": _today, "src": "recalc",
                    "info": mainline_judgment(sc, _pl)}
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
                obs = obj.get("observes") or []
                if ml:
                    return {"names": list(ml), "observes": list(obs), "date": _d, "src": "fallback",
                            "info": _mainline_info_from_archive(ml, _d)}
    except Exception:
        return None
    return None


def _mainline_info_from_archive(names: list[str], d8: str) -> dict[str, dict[str, Any]]:
    """从复盘归档 sector_score.json + plate_data.json 重算主线判定依据（零上游成本）。"""
    try:
        from .daily_report import ARCHIVE_ROOT, mainline_judgment
        _sp = os.path.join(ARCHIVE_ROOT, d8, "sector_score.json")
        if not os.path.exists(_sp):
            return {}
        sc = json.load(open(_sp, encoding="utf-8"))
        _pp = os.path.join(ARCHIVE_ROOT, d8, "plate_data.json")
        plates = json.load(open(_pp, encoding="utf-8")) if os.path.exists(_pp) else None
        info = mainline_judgment(sc, plates) or {}
        return {n: info[n] for n in names if n in info}
    except Exception:
        return {}


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
# 15:01 收盘定型可看/可手扫；15:05 服务端统一预扫一次，全站读缓存（非按用户扫）。
# 同日已有「收盘后」缓存或已预生成过则跳过；force 重扫仍由用户手动触发。
_AUTO_SCAN_HHMM = (15, 15)
_AUTO_SCAN_TS = _AUTO_SCAN_HHMM[0] * 3600 + _AUTO_SCAN_HHMM[1] * 60
_AUTO_SCAN_MARKETS = ("hs", "kc", "bj", "bj_all", "all")
_AUTO_SCAN_DONE: dict[str, bool] = {}
_AUTO_SCAN_DAY_LOGGED: set[str] = set()


async def _auto_scan_loop() -> None:
    try:
        from .daily_report import _today_close_epoch
    except Exception:
        _today_close_epoch = lambda: 0.0  # type: ignore[assignment, misc]
    while True:
        try:
            now = time.localtime()
            sec = now.tm_hour * 3600 + now.tm_min * 60 + now.tm_sec
            if now.tm_wday < 5 and sec >= _AUTO_SCAN_TS:
                today8 = time.strftime("%Y%m%d", time.localtime())
                # 只保留当日标记，避免跨日字典膨胀
                for k in list(_AUTO_SCAN_DONE):
                    if not str(k).endswith(f":{today8}"):
                        _AUTO_SCAN_DONE.pop(k, None)
                _AUTO_SCAN_DAY_LOGGED.intersection_update({today8})
                _close_ts = _today_close_epoch()  # 今日收盘定型时刻（auto_scan_time，默认 15:01）
                # all（沪深京全市场）为 MACD首红 栏目的数据源，必须纳入收盘后自动扫描；
                # 放最后：先把轻量的 hs/kc/bj/bj_all 定型，再跑最重的全市场
                for market in _AUTO_SCAN_MARKETS:
                    key = f"{market}-scan:{today8}"
                    if _AUTO_SCAN_DONE.get(key):
                        continue
                    _AUTO_SCAN_DONE[key] = True
                    hit = _SCAN_CACHE.get(key)
                    # 仅在「收盘后已生成且 6h 内」才跳过；盘中缓存（未定型）必须重扫，
                    # 避免 13:xx 盘中扫描把 15:01 收盘定型扫描顶掉（曾致归档保留盘中弱数据）。
                    if hit and time.time() - hit[0] < 6 * 3600 and hit[0] >= _close_ts:
                        _log.info("bj auto-scan skip cached market=%s date=%s", market, today8)
                        continue
                    try:
                        # 加超时防上游卡死：单市场最多 15 分钟，超时视为失败下轮重试
                        await asyncio.wait_for(run_scan_dedup(0, force=False, market=market), timeout=900)
                        _log.info("bj auto-scan ok market=%s date=%s", market, today8)
                    except Exception as e:
                        _AUTO_SCAN_DONE[key] = False  # 失败/超时则下轮重试
                        _log.warning("bj auto-scan fail market=%s date=%s err=%s", market, today8, e)
                if (
                    today8 not in _AUTO_SCAN_DAY_LOGGED
                    and all(_AUTO_SCAN_DONE.get(f"{m}-scan:{today8}") for m in _AUTO_SCAN_MARKETS)
                ):
                    _AUTO_SCAN_DAY_LOGGED.add(today8)
                    _log.info(
                        "bj auto-scan complete date=%s markets=%s",
                        today8,
                        ",".join(_AUTO_SCAN_MARKETS),
                    )
            await asyncio.sleep(60)
        except Exception as e:
            _log.warning("bj auto-scan loop error: %s", e)
            await asyncio.sleep(300)


def start_bj_auto_scan() -> None:
    """在 startup 时启动掘金定时预生成后台任务。

    03 生产（a.ai24x.com）以本地 sync_final_to_03 同步的 bj_scan_daily 为权威，
    禁止进程内自动重扫覆盖，避免与本地验收口径漂移。
    """
    if os.getenv("AI24X_BJ_AUTO_SCAN", "1").strip().lower() in ("0", "false", "no", "off"):
        _log.info("bj auto-scan disabled (AI24X_BJ_AUTO_SCAN=0)")
        return
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        return
    _log.info(
        "bj auto-scan loop started (weekday >= %02d:%02d, shared cache)",
        _AUTO_SCAN_HHMM[0],
        _AUTO_SCAN_HHMM[1],
    )
    loop.create_task(_auto_scan_loop())
