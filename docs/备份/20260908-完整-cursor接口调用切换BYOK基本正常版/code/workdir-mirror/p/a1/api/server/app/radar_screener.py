# -*- coding: utf-8 -*-
"""AI雷达：热门涨停池 · 粘合启动 + 回踩二波（服务端扫描，Key 不暴露给前端）。"""
from __future__ import annotations

import asyncio
import json
import os
import re
import time
from datetime import datetime, timedelta
from typing import Any, Optional

from .big_cycle import check_big_cycle
from .bj_screener import _resolve_stock_names
from .ths_fuyao import fetch_historical_kline, fetch_special, fuyao_config

_RADAR_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "radar_cache")
os.makedirs(_RADAR_DIR, exist_ok=True)

# 与独立 HTML 对齐：fuyao forward K 线 + 全量热门候选（不截断）
_RADAR_KLINE_DAYS = 400
_RADAR_CONCURRENCY = 12
_CAND_POOL_CACHE: dict[str, list[dict[str, str]]] = {}
_KLINE_BARS_CACHE: dict[str, dict[str, list[float]]] = {}

_PRESETS: dict[str, dict[str, Any]] = {
    "strict": {
        "name": "严格",
        "bondThreshold": 0.03, "bondWindow": 5, "bondMinCount": 2,
        "ztYearMin": 5, "ztYearMax": 10, "ztDays": 10,
        "maxStageRise": 0.65, "avgAmountMin": 1e8, "ztAmountMin": 5e7,
        "bigCycleMode": "full", "divergeMode": "full", "volMode": "today",
        "ma144Lookback": 5, "ma144FlatPct": 1.0, "volMultiple": 1.0,
        "scanDays": 15, "minListDays": 120,
    },
    "balanced": {
        "name": "标准",
        "bondThreshold": 0.05, "bondWindow": 10, "bondMinCount": 2,
        "ztYearMin": 3, "ztYearMax": 15, "ztDays": 15,
        "maxStageRise": 0.80, "avgAmountMin": 5e7, "ztAmountMin": 3e7,
        "bigCycleMode": "medium", "divergeMode": "medium", "volMode": "recent3",
        "ma144Lookback": 5, "ma144FlatPct": 0.998, "volMultiple": 1.1,
        "scanDays": 30, "minListDays": 120,
    },
    "loose": {
        "name": "宽松",
        "bondThreshold": 0.06, "bondWindow": 10, "bondMinCount": 2,
        "ztYearMin": 2, "ztYearMax": 20, "ztDays": 15,
        "maxStageRise": 1.0, "avgAmountMin": 3e7, "ztAmountMin": 2e7,
        "bigCycleMode": "lite", "divergeMode": "lite", "volMode": "recent3",
        "ma144Lookback": 10, "ma144FlatPct": 0.995, "volMultiple": 1.05,
        "scanDays": 30, "minListDays": 120,
    },
}

_PULLBACK_EXTRA: dict[str, dict[str, Any]] = {
    "strict": {"pullMin": 0.10, "pullMax": 0.22, "volShrink": 0.65, "minScore": 7,
               "ztDaysMin": 5, "ztDaysMax": 15, "volLaunch": 1.15, "ma20Tol": 0.98},
    "balanced": {"pullMin": 0.08, "pullMax": 0.25, "volShrink": 0.72, "minScore": 6,
                 "ztDaysMin": 5, "ztDaysMax": 20, "volLaunch": 1.15, "ma20Tol": 0.98},
    "loose": {"pullMin": 0.06, "pullMax": 0.30, "volShrink": 0.80, "minScore": 5,
              "ztDaysMin": 3, "ztDaysMax": 25, "volLaunch": 1.10, "ma20Tol": 0.96},
}

_SCAN_CACHE: dict[str, dict[str, Any]] = {}
_RUNNING: Optional[asyncio.Task] = None
_PROGRESS: dict[str, Any] = {
    "running": False, "phase": "", "pct": 0, "msg": "",
    "done": 0, "total": 0, "hits": 0, "eta_s": 0,
}


def _fmt_eta(eta_s: int) -> str:
    if eta_s <= 0:
        return ""
    if eta_s >= 120:
        return f" · 约剩 {max(1, (eta_s + 59) // 60)} 分钟"
    return f" · 约剩 {eta_s} 秒"


def _touch_progress(**kw: Any) -> None:
    _PROGRESS.update(kw)
_RADAR_FORCE_COOLDOWN_S = 600.0
_LAST_FORCE_SCAN_END: float = 0.0


def _date8() -> str:
    return time.strftime("%Y%m%d", time.localtime())


def _norm_price_band(price: str | None) -> str:
    p = str(price or "any").strip().lower()
    if p in ("under10", "low10", "lt10", "10", "under_10"):
        return "under10"
    return "any"


def _price_in_band(px: Any, band: str) -> bool:
    """与复盘 10元下一致：2 ≤ 现价 < 10（排除面值退市警戒）。"""
    if band != "under10":
        return True
    try:
        v = float(px or 0)
    except Exception:
        return False
    return 2.0 <= v < 10.0


def _cache_key(signal: str, strictness: str, price: str = "any") -> str:
    band = _norm_price_band(price)
    if band == "under10":
        return f"{_date8()}:{signal}:{strictness}:under10"
    return f"{_date8()}:{signal}:{strictness}"


def _apply_price_band(payload: dict[str, Any], band: str) -> dict[str, Any]:
    """从「不限」结果切出 10元下子集（当日已有全量缓存时可免重扫）。"""
    band = _norm_price_band(band)
    out = dict(payload)
    out["price"] = band
    out["priceLabel"] = "10元下" if band == "under10" else "不限"
    if band != "under10":
        return out
    items = [x for x in (out.get("items") or []) if isinstance(x, dict) and _price_in_band(x.get("price"), band)]
    out["items"] = items
    out["count"] = len(items)
    stats = dict(out.get("filterStats") or {})
    dropped = int((payload.get("count") or len(payload.get("items") or [])) - len(items))
    if dropped > 0:
        stats["股价不符"] = stats.get("股价不符", 0) + dropped
    out["filterStats"] = stats
    out["cached"] = True
    out["priceDerived"] = True
    return out


def _disk_scan_path(key: str) -> str:
    return os.path.join(_RADAR_DIR, f"scan_{key.replace(':', '_')}.json")


def _load_disk_scan(key: str) -> Optional[dict[str, Any]]:
    try:
        fp = _disk_scan_path(key)
        if not os.path.exists(fp):
            return None
        with open(fp, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) and data.get("ok") is not False else None
    except Exception:
        return None


def get_radar_cached_result(
    signal: str = "both",
    strictness: str = "balanced",
    price: str = "any",
) -> Optional[dict[str, Any]]:
    """只读当日缓存（内存或磁盘），不触发扫描。"""
    signal = signal if signal in ("both", "bond", "pullback") else "both"
    strictness = strictness if strictness in _PRESETS else "balanced"
    band = _norm_price_band(price)
    key = _cache_key(signal, strictness, band)
    if key in _SCAN_CACHE:
        out = dict(_SCAN_CACHE[key])
        out["cached"] = True
        out["price"] = band
        out["priceLabel"] = "10元下" if band == "under10" else "不限"
        return out
    disk = _load_disk_scan(key)
    if disk:
        _SCAN_CACHE[key] = disk
        out = dict(disk)
        out["cached"] = True
        out["price"] = band
        out["priceLabel"] = "10元下" if band == "under10" else "不限"
        return out
    # 10元下：若无专属缓存，从「不限」当日结果即时切片
    if band == "under10":
        base = get_radar_cached_result(signal, strictness, "any")
        if base and base.get("ok") is not False and isinstance(base.get("items"), list):
            return _apply_price_band(base, "under10")
    return None


def _code_to_thscode(code: str) -> str:
    c = re.sub(r"\D", "", str(code or ""))[-6:].zfill(6)
    if c.startswith(("6", "9", "5")):
        return f"{c}.SH"
    return f"{c}.SZ"


def _norm_thscode(raw: str, code: str = "") -> str:
    s = str(raw or "").strip().upper()
    if re.fullmatch(r"\d{6}\.(SH|SZ)", s):
        return s
    return _code_to_thscode(code or s)


def _parse_fuyao_items(items: list[dict[str, Any]]) -> dict[str, list[float]]:
    rows = sorted(items, key=lambda x: int(x.get("date_ms") or 0))
    closes: list[float] = []
    opens: list[float] = []
    highs: list[float] = []
    lows: list[float] = []
    volumes: list[float] = []
    turnovers: list[float] = []
    for it in rows:
        try:
            closes.append(float(it["close_price"]))
            opens.append(float(it["open_price"]))
            highs.append(float(it["high_price"]))
            lows.append(float(it["low_price"]))
            volumes.append(float(it.get("volume") or 0))
            turnovers.append(float(it.get("turnover") or 0))
        except Exception:
            continue
    return {"closes": closes, "opens": opens, "highs": highs, "lows": lows,
            "volumes": volumes, "turnovers": turnovers}


def _is_bj(code: str) -> bool:
    c = str(code or "").zfill(6)
    return c.startswith(("8", "4", "920"))


def _board_meta(code: str) -> dict[str, Any]:
    c = str(code or "").zfill(6)
    is300 = c.startswith(("300", "301"))
    is688 = c.startswith("688")
    limit = 0.2 if (is300 or is688) else 0.1
    big_drop = 0.90 if (is300 or is688) else 0.93
    return {"limit": limit, "bigDrop": big_drop, "is300": is300, "is688": is688}


def _parse_rows(rows: list[list[Any]]) -> dict[str, list[float]]:
    closes, opens, highs, lows, volumes, turnovers = [], [], [], [], [], []
    for r in rows:
        if not r or len(r) < 6:
            continue
        o, c, h, l = float(r[1]), float(r[2]), float(r[3]), float(r[4])
        v = float(r[5])
        closes.append(c)
        opens.append(o)
        highs.append(h)
        lows.append(l)
        volumes.append(v)
        turnovers.append(v * c * 100)
    return {"closes": closes, "opens": opens, "highs": highs, "lows": lows,
            "volumes": volumes, "turnovers": turnovers}


def _ma(closes: list[float], period: int, idx: int) -> Optional[float]:
    if idx < period - 1:
        return None
    seg = closes[idx - period + 1: idx + 1]
    return sum(seg) / period


def _is_limit_up(close: float, prev: float, limit: float) -> bool:
    return close >= prev * (1 + limit) - 0.003


def _is_one_word(o: float, l: float, prev: float, limit: float) -> bool:
    zt = prev * (1 + limit) - 0.003
    return o >= zt and l >= zt


def _zt_stats(k: dict[str, list[float]], cfg: dict[str, Any], code: str = "") -> dict[str, Any]:
    closes, opens, lows, turnovers = k["closes"], k["opens"], k["lows"], k["turnovers"]
    last = len(closes) - 1
    limit = _board_meta(code)["limit"]
    zt250 = zt_recent = 0
    has_q = False
    last_zt = None
    zt_win = int(cfg.get("ztDays") or 15)
    for i in range(max(1, last - 249), last + 1):
        prev = closes[i - 1]
        if not _is_limit_up(closes[i], prev, limit):
            continue
        zt250 += 1
        days_ago = last - i
        if last_zt is None or days_ago < last_zt:
            last_zt = days_ago
        if i >= last - (zt_win - 1):
            zt_recent += 1
            if not _is_one_word(opens[i], lows[i], prev, limit) and turnovers[i] >= float(cfg.get("ztAmountMin") or 0):
                has_q = True
    return {"zt250": zt250, "ztRecent": zt_recent, "hasQualifiedZt": has_q, "lastZtDaysAgo": last_zt}


def _check_big_cycle(cfg: dict, MA, ma5, ma10, ma20, ma30, ma60, ma144, last) -> tuple[bool, str]:
    """委托公共模块 big_cycle.check_big_cycle（与复盘/主线同口径）。"""
    return check_big_cycle(cfg, MA, ma5, ma10, ma20, ma30, ma60, ma144, last)


def _analyze_bond(k: dict[str, list[float]], code: str, name: str, cfg: dict[str, Any]) -> Optional[dict[str, Any]]:
    if len(k["closes"]) < 180:
        return None
    min_days = int(cfg.get("minListDays") or 120)
    if len(k["closes"]) < min_days + 30:
        return None
    meta = _board_meta(code)
    zt = _zt_stats(k, cfg, code)
    if zt["zt250"] < cfg["ztYearMin"] or zt["zt250"] > cfg["ztYearMax"]:
        return None
    if zt["ztRecent"] < 1 or not zt["hasQualifiedZt"]:
        return None
    closes, lows, volumes, turnovers = k["closes"], k["lows"], k["volumes"], k["turnovers"]
    last = len(closes) - 1
    MA = lambda p, i: _ma(closes, p, i)
    ma5, ma10, ma20 = MA(5, last), MA(10, last), MA(20, last)
    ma30, ma60, ma144 = MA(30, last), MA(60, last), MA(144, last)
    ok, _ = _check_big_cycle(cfg, MA, ma5, ma10, ma20, ma30, ma60, ma144, last)
    if not ok:
        return None
    bond = 0
    for i in range(last - int(cfg["bondWindow"]) + 1, last + 1):
        m5, m10, m20 = MA(5, i), MA(10, i), MA(20, i)
        if m5 and m10 and m20:
            th = cfg["bondThreshold"]
            if abs(m5 / m20 - 1) <= th and abs(m10 / m20 - 1) <= th and abs(m5 / m10 - 1) <= th:
                bond += 1
    if bond < cfg["bondMinCount"]:
        return None
    ma5_1, ma5_2 = MA(5, last - 1), MA(5, last - 2)
    dm = cfg.get("divergeMode") or "medium"
    if dm == "full":
        if not (ma5 and ma10 and ma20 and ma5_1 and ma5_2 and ma5 > ma10 > ma20 and ma5 > ma5_1 > ma5_2):
            return None
    elif dm == "medium":
        if not (ma5 and ma10 and ma20 and ma5_1 and ma5 > ma10 > ma20 and ma5 > ma5_1):
            return None
    else:
        if not (ma5 and ma20 and ma5_1 and ma5 > ma20 and ma5 > ma5_1):
            return None
    if cfg.get("volMode") == "today":
        vma5 = sum(volumes[last - 4:last + 1]) / 5
        if volumes[last] <= vma5:
            return None
    else:
        vm = float(cfg.get("volMultiple") or 1.1)
        hit = False
        for i in range(last - 2, last + 1):
            if i >= 4:
                vma = sum(volumes[i - 4:i + 1]) / 5
                if volumes[i] >= vma * vm:
                    hit = True
        if not hit:
            return None
    low60 = min(lows[last - 59:last + 1])
    rise60 = closes[last] / low60 - 1
    if rise60 > cfg["maxStageRise"]:
        return None
    avg20 = sum(turnovers[last - 19:last + 1]) / 20
    if avg20 < cfg["avgAmountMin"]:
        return None
    for i in range(last - 9, last + 1):
        if i > 0 and closes[i] / closes[i - 1] <= meta["bigDrop"]:
            return None
    return {
        "code": code.zfill(6), "name": name, "signalType": "粘合启动",
        "matchLabel": cfg.get("name") or "标准", "matchScore": bond + 4,
        "bondCount": bond, "pullPct": None, "daysSinceZt": None, "stabScore": None,
        "zt10": zt["ztRecent"], "ztYear": zt["zt250"],
        "rise": round(rise60 * 100, 1), "avgTurnover": int(avg20 / 10000),
        "price": round(closes[last], 2),
    }


def _analyze_pullback(k: dict[str, list[float]], code: str, name: str,
                      cfg: dict[str, Any], strictness: str) -> Optional[dict[str, Any]]:
    if len(k["closes"]) < 180:
        return None
    pb = dict(_PULLBACK_EXTRA.get(strictness) or _PULLBACK_EXTRA["balanced"])
    meta = _board_meta(code)
    if meta["is300"] or meta["is688"]:
        pb["pullMax"] = min(pb["pullMax"] + 0.05, 0.35)
    zt = _zt_stats(k, cfg, code)
    if zt["zt250"] < cfg["ztYearMin"] or zt["zt250"] > cfg["ztYearMax"]:
        return None
    if zt["lastZtDaysAgo"] is None:
        return None
    if zt["lastZtDaysAgo"] < pb["ztDaysMin"] or zt["lastZtDaysAgo"] > pb["ztDaysMax"]:
        return None
    closes, highs, lows, opens, volumes, turnovers = (
        k["closes"], k["highs"], k["lows"], k["opens"], k["volumes"], k["turnovers"])
    last = len(closes) - 1
    MA = lambda p, i: _ma(closes, p, i)
    ma5, ma10, ma20 = MA(5, last), MA(10, last), MA(20, last)
    ma30, ma60, ma144 = MA(30, last), MA(60, last), MA(144, last)
    ok, _ = _check_big_cycle(cfg, MA, ma5, ma10, ma20, ma30, ma60, ma144, last)
    if not ok:
        return None
    high20 = max(closes[max(0, last - 19):last + 1])
    pull = (high20 - closes[last]) / high20 if high20 else 0
    if pull < pb["pullMin"] or pull > pb["pullMax"]:
        return None
    for i in range(last - 4, last + 1):
        m20 = MA(20, i)
        if m20 and lows[i] < m20 * pb["ma20Tol"]:
            return None
    vol5 = sum(volumes[last - 4:last + 1]) / 5
    vol20 = sum(volumes[last - 19:last + 1]) / 20
    if vol5 >= vol20 * pb["volShrink"]:
        return None
    low60 = min(lows[last - 59:last + 1])
    rise60 = closes[last] / low60 - 1
    if rise60 > cfg["maxStageRise"]:
        return None
    avg20 = sum(turnovers[last - 19:last + 1]) / 20
    if avg20 < cfg["avgAmountMin"]:
        return None
    for i in range(last - 9, last + 1):
        if i > 0 and closes[i] / closes[i - 1] <= meta["bigDrop"]:
            return None
    score = 0
    ma5_1, ma5_2 = MA(5, last - 1), MA(5, last - 2)
    if ma5_1 and ma5_2 and ma5 and ma5 > ma5_1 and ma5_1 <= ma5_2:
        score += 2
    if ma5 and closes[last] > ma5:
        score += 2
    if volumes[last] > vol5 * pb["volLaunch"]:
        score += 2
    if _avg_range(highs, lows, closes, last - 2, last) < _avg_range(highs, lows, closes, last - 9, last) * 0.85:
        score += 1
    if _avg_body(opens, closes, last - 2, last) < 0.03:
        score += 1
    hl = highs[last] - lows[last]
    if hl > 0 and (closes[last] - lows[last]) / hl > 0.6:
        score += 1
    if ma5_1 and ma10 and abs(ma5 / ma10 - 1) < 0.02 and ma5 > ma5_1:
        score += 1
    if 5 <= zt["lastZtDaysAgo"] <= 15:
        score += 1
    if score < pb["minScore"]:
        return None
    label = "较强" if score >= 8 else "关注"
    return {
        "code": code.zfill(6), "name": name, "signalType": "回踩二波",
        "matchLabel": f"{cfg.get('name') or '标准'}·{label}", "matchScore": score,
        "bondCount": None, "pullPct": round(pull * 100, 1),
        "daysSinceZt": zt["lastZtDaysAgo"], "stabScore": score,
        "zt10": zt["ztRecent"], "ztYear": zt["zt250"],
        "rise": round(rise60 * 100, 1), "avgTurnover": int(avg20 / 10000),
        "price": round(closes[last], 2),
    }


def _avg_range(highs, lows, closes, fr, to) -> float:
    s, n = 0.0, 0
    for i in range(fr, to + 1):
        if closes[i]:
            s += (highs[i] - lows[i]) / closes[i]
            n += 1
    return s / n if n else 0


def _avg_body(opens, closes, fr, to) -> float:
    s, n = 0.0, 0
    for i in range(fr, to + 1):
        if closes[i]:
            s += abs(closes[i] - opens[i]) / closes[i]
            n += 1
    return s / n if n else 0


def _merge_hits(hits: dict[str, dict[str, Any]], row: dict[str, Any]) -> None:
    code = row["code"]
    if code not in hits:
        hits[code] = row
        return
    old = hits[code]
    if old.get("signalType") == row.get("signalType"):
        return
    hits[code] = {
        **old, **row,
        "signalType": "双信号",
        "matchLabel": f"{old.get('matchLabel')}+{row.get('matchLabel')}",
        "matchScore": int(old.get("matchScore") or 0) + int(row.get("matchScore") or 0),
        "bondCount": old.get("bondCount") if old.get("bondCount") is not None else row.get("bondCount"),
        "pullPct": row.get("pullPct") if row.get("pullPct") is not None else old.get("pullPct"),
        "daysSinceZt": row.get("daysSinceZt") if row.get("daysSinceZt") is not None else old.get("daysSinceZt"),
        "stabScore": row.get("stabScore") if row.get("stabScore") is not None else old.get("stabScore"),
    }


def _trading_days_ms(count: int = 30) -> list[int]:
    out: list[int] = []
    d = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    while len(out) < count:
        if d.weekday() < 5:
            out.append(int(d.timestamp() * 1000))
        d -= timedelta(days=1)
    return out


async def _radar_kline_bars(code: str, thscode: str = "") -> Optional[dict[str, list[float]]]:
    """fuyao 前复权日 K，与独立 HTML 完全一致。"""
    date8 = _date8()
    ck = f"{date8}:{code}"
    if ck in _KLINE_BARS_CACHE:
        return _KLINE_BARS_CACHE[ck]
    ths = _norm_thscode(thscode, code)
    r = await fetch_historical_kline(ths, days=_RADAR_KLINE_DAYS, adjust="forward", gate=None)
    if not r.get("ok"):
        return None
    items = r.get("items") or []
    k = _parse_fuyao_items(items)
    if len(k["closes"]) >= 180:
        _KLINE_BARS_CACHE[ck] = k
        return k
    return None


async def _fetch_limit_up_day(day_ms: int, max_pages: int = 1) -> tuple[list[dict[str, Any]], bool]:
    items: list[dict[str, Any]] = []
    ok = False
    pages = ("1", "2", "3")[: max(1, min(3, int(max_pages)))]
    for page in pages:
        r = await fetch_special(
            "limit-up-pool", {"date_ms": str(day_ms), "page": page, "size": "200"}, gate=None,
        )
        if r.get("ok"):
            ok = True
        batch = r.get("item") or []
        if isinstance(batch, dict):
            batch = batch.get("item") or []
        items.extend(batch)
        if len(batch) < 200:
            break
    return items, ok


async def _collect_candidates(sources: dict[str, list[str]], scan_days: int = 30) -> list[dict[str, str]]:
    pool_key = f"{_date8()}:{scan_days}"
    if pool_key in _CAND_POOL_CACHE:
        return list(_CAND_POOL_CACHE[pool_key])

    seen: dict[str, dict[str, str]] = {}

    def add(code: str, name: str = "", src: str = "", thscode: str = "") -> None:
        c = re.sub(r"\D", "", str(code or ""))[-6:].zfill(6)
        if len(c) != 6 or _is_bj(c):
            return
        if c.startswith(("ST", "st")):
            return
        ths = _norm_thscode(thscode or code, c)
        if c not in seen:
            seen[c] = {"code": c, "name": str(name or c).strip() or c, "thscode": ths}
        elif name and seen[c].get("name") in ("", c):
            seen[c]["name"] = str(name).strip()
        sources.setdefault(src, [])
        if c not in sources[src]:
            sources[src].append(c)

    fuyao_ok = False
    day_sem = asyncio.Semaphore(8)

    days = _trading_days_ms(scan_days)
    day_total = len(days)

    async def one_day(day_ms: int) -> tuple[list[dict[str, Any]], bool]:
        async with day_sem:
            return await _fetch_limit_up_day(day_ms, max_pages=3)

    pool_done = 0
    tasks = [asyncio.create_task(one_day(d)) for d in days]
    for fut in asyncio.as_completed(tasks):
        items, ok = await fut
        pool_done += 1
        _touch_progress(
            running=True, phase="候选池",
            pct=2 + int(7 * pool_done / max(day_total, 1)),
            msg=f"汇总热门股 {pool_done}/{day_total} 天…",
            done=pool_done, total=day_total, hits=len(seen), eta_s=0,
        )
        if ok:
            fuyao_ok = True
            if "fuyao:zt" not in sources.get("primary", []):
                sources.setdefault("primary", []).append("fuyao:zt")
        for it in items:
            if it.get("is_st") or it.get("is_new"):
                continue
            raw = it.get("ticker") or it.get("thscode", "")
            add(raw, it.get("name") or "", "fuyao:zt", str(it.get("thscode") or raw))

    extra_sources = (
        ("limit-up-ladder", "fuyao:ladder", "300", "连板天梯"),
        ("hot-stock-list", "fuyao:hot", "30", "热股榜"),
        ("skyrocket-list", "fuyao:sky", "30", "飙升榜"),
    )
    for i, (ep, src, size, label) in enumerate(extra_sources):
        _touch_progress(
            running=True, phase="候选池", pct=9,
            msg=f"补充{label}… · 已收集 {len(seen)} 只",
            done=day_total + i, total=day_total + len(extra_sources),
            hits=len(seen), eta_s=0,
        )
        r = await fetch_special(ep, {"page": "1", "size": size, "period": "day"}, gate=None)
        if r.get("ok"):
            fuyao_ok = True
            if src not in sources.get("primary", []):
                sources.setdefault("primary", []).append(src)
            items = r.get("item") or []
            if isinstance(items, dict):
                items = items.get("item") or []
            for it in items:
                raw = it.get("ticker") or it.get("thscode", "")
                add(raw, it.get("name") or it.get("stock_name") or "", src, str(it.get("thscode") or raw))

    if not fuyao_ok or len(seen) < 20:
        try:
            from .bj_screener import _emo_pools
            pools = await _emo_pools(_date8())
            for c in pools.get("zt_codes") or []:
                add(c, "", "eastmoney:zt")
            sources.setdefault("fallback", []).append("eastmoney:zt")
        except Exception:
            pass

    names = _resolve_stock_names(list(seen.keys()))
    for c, item in seen.items():
        if names.get(c):
            item["name"] = names[c]
    out = list(seen.values())
    _CAND_POOL_CACHE[pool_key] = out
    return out


async def run_radar_scan(
    signal: str = "both",
    strictness: str = "balanced",
    force: bool = False,
    price: str = "any",
) -> dict[str, Any]:
    global _RUNNING, _LAST_FORCE_SCAN_END
    signal = signal if signal in ("both", "bond", "pullback") else "both"
    strictness = strictness if strictness in _PRESETS else "balanced"
    band = _norm_price_band(price)
    key = _cache_key(signal, strictness, band)
    if not force:
        hit = get_radar_cached_result(signal, strictness, band)
        if hit:
            return hit

    cfg = _PRESETS[strictness]
    scan_days = int(cfg.get("scanDays") or 30)
    sources: dict[str, list[str]] = {"primary": [], "fallback": []}
    t0 = time.time()
    _touch_progress(
        running=True, phase="候选池", pct=2,
        msg=f"汇总近{scan_days}日热门涨停股…",
        done=0, total=scan_days, hits=0, eta_s=0,
    )
    candidates = await _collect_candidates(sources, scan_days=scan_days)
    if not candidates:
        _touch_progress(running=False, pct=100, msg="未找到可扫描股票")
        return {"ok": False, "error": "empty_pool", "message": "未获取到候选股票", "items": [], "filterStats": {}}

    _touch_progress(
        running=True, phase="K线分析", pct=10,
        msg=f"共 {len(candidates)} 只，开始筛选…",
        done=0, total=len(candidates), hits=0, eta_s=0,
    )

    hits: dict[str, dict[str, Any]] = {}
    stats: dict[str, int] = {}
    total = len(candidates)
    sem = asyncio.Semaphore(_RADAR_CONCURRENCY)
    prog_lock = asyncio.Lock()
    started_n = 0

    scan_ts = int(time.time())

    async def one(st: dict[str, str], idx: int) -> None:
        nonlocal started_n
        async with sem:
            async with prog_lock:
                started_n += 1
                sn = started_n
                hit_n = len(hits)
            elapsed = max(0.001, time.time() - t0)
            eta = int(elapsed / sn * (total - sn)) if sn < total else 0
            _touch_progress(
                running=True, phase="K线分析",
                pct=10 + int(85 * sn / max(total, 1)),
                msg=f"已筛选 {sn}/{total} · 入选 {hit_n}{_fmt_eta(eta)}",
                done=sn, total=total, hits=hit_n, eta_s=eta,
            )
            code = st["code"]
            k = await _radar_kline_bars(code, st.get("thscode") or "")
            if not k or len(k["closes"]) < 180:
                stats["数据不足"] = stats.get("数据不足", 0) + 1
            else:
                name = st.get("name") or code
                last_px = float(k["closes"][-1]) if k.get("closes") else 0.0
                if not _price_in_band(last_px, band):
                    stats["股价不符"] = stats.get("股价不符", 0) + 1
                else:
                    if signal in ("bond", "both"):
                        r = _analyze_bond(k, code, name, cfg)
                        if r:
                            r["scanTime"] = scan_ts
                            r["thscode"] = st.get("thscode") or _code_to_thscode(code)
                            _merge_hits(hits, r)
                        else:
                            stats["[粘合]未达标"] = stats.get("[粘合]未达标", 0) + 1
                    if signal in ("pullback", "both"):
                        r2 = _analyze_pullback(k, code, name, cfg, strictness)
                        if r2:
                            r2["scanTime"] = scan_ts
                            r2["thscode"] = st.get("thscode") or _code_to_thscode(code)
                            _merge_hits(hits, r2)
                        else:
                            stats["[回踩]未达标"] = stats.get("[回踩]未达标", 0) + 1
            async with prog_lock:
                hit_n = len(hits)
            _touch_progress(hits=hit_n, msg=f"已筛选 {sn}/{total} · 入选 {hit_n}{_fmt_eta(eta)}")

    await asyncio.gather(*[one(st, i + 1) for i, st in enumerate(candidates)])

    items = list(hits.values())
    pri = {"双信号": 3, "回踩二波": 2, "粘合启动": 1}
    items.sort(key=lambda x: (
        -pri.get(x.get("signalType") or "", 0),
        -int(x.get("matchScore") or 0),
        -int(x.get("zt10") or 0),
    ))

    fuyao_on = bool(fuyao_config().get("api_key"))
    elapsed = max(0, int(time.time() - t0))
    out = {
        "ok": True,
        "cached": False,
        "date": _date8(),
        "signal": signal,
        "strictness": strictness,
        "strictnessLabel": cfg.get("name"),
        "price": band,
        "priceLabel": "10元下" if band == "under10" else "不限",
        "scanned": total,
        "count": len(items),
        "items": items,
        "filterStats": stats,
        "meta": {
            "sources": {
                "candidate": "ths:fuyao" if sources.get("primary") or fuyao_on else "eastmoney",
                "kline": "ths:fuyao:forward",
                "fallback_used": sources.get("fallback") or [],
            },
            "elapsed_s": elapsed,
        },
        "generated_ts": int(time.time()),
    }
    _SCAN_CACHE[key] = out
    try:
        fp = _disk_scan_path(key)
        with open(fp, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False)
    except Exception:
        pass
    _touch_progress(
        running=False, phase="完成", pct=100,
        msg=f"共看 {total} 只 · 入选 {len(items)}",
        done=total, total=total, hits=len(items), eta_s=0,
    )
    if force:
        _LAST_FORCE_SCAN_END = time.time()
    return out


def radar_progress() -> dict[str, Any]:
    return dict(_PROGRESS)


async def start_radar_background(
    signal: str = "both",
    strictness: str = "balanced",
    force: bool = True,
    price: str = "any",
) -> None:
    global _RUNNING
    if _RUNNING is not None and not _RUNNING.done():
        return
    _RUNNING = asyncio.create_task(run_radar_scan(signal, strictness, force=force, price=price))
    try:
        await _RUNNING
    finally:
        _RUNNING = None


async def run_radar_dedup(
    signal: str = "both",
    strictness: str = "balanced",
    force: bool = False,
    price: str = "any",
) -> dict[str, Any]:
    global _RUNNING
    if _RUNNING is not None and not _RUNNING.done():
        return {"ok": True, "running": True, "message": "扫描进行中", **radar_progress()}
    _RUNNING = asyncio.create_task(run_radar_scan(signal, strictness, force, price=price))
    try:
        return await _RUNNING
    finally:
        _RUNNING = None


def radar_task_running() -> bool:
    return _RUNNING is not None and not _RUNNING.done()


def check_force_rescan_allowed() -> Optional[str]:
    """完整重扫全站冷却（防多用户连点耗资源）。返回用户可见拒绝原因。"""
    if radar_task_running():
        return "扫描正在进行中，请稍候"
    if _LAST_FORCE_SCAN_END > 0:
        left = _RADAR_FORCE_COOLDOWN_S - (time.time() - _LAST_FORCE_SCAN_END)
        if left > 0:
            mins = max(1, int((left + 59) // 60))
            return f"完整重扫过于频繁，请 {mins} 分钟后再试"
    return None


def assert_radar_vip(user_id: int) -> None:
    """AI雷达 / 代理接口 VIP 校验。"""
    from fastapi import HTTPException
    from . import db
    db.downgrade_expired_vip_plan(int(user_id))
    quota = db.get_quota_status(int(user_id))
    plan = str(quota.get("plan") or "anon").strip().lower()
    if plan in ("", "free", "anon"):
        raise HTTPException(status_code=403, detail="AI雷达为 VIP 专属功能，请先开通 VIP。")


_RADAR_PROXY_SPECIAL = frozenset({
    "limit-up-pool", "limit-up-ladder", "hot-stock-list", "skyrocket-list",
})

# 交易日收盘后统一预扫（全站 VIP 共用缓存，非按用户重复扫）
_RADAR_AUTO_HHMM = (15, 15)
_RADAR_AUTO_TS = _RADAR_AUTO_HHMM[0] * 3600 + _RADAR_AUTO_HHMM[1] * 60
_RADAR_AUTO_COMBOS = (("both", "balanced"), ("both", "strict"), ("both", "loose"))
_RADAR_AUTO_DONE: dict[str, bool] = {}


async def _radar_auto_scan_loop() -> None:
    import logging
    log = logging.getLogger(__name__)
    while True:
        try:
            now = time.localtime()
            sec = now.tm_hour * 3600 + now.tm_min * 60 + now.tm_sec
            if now.tm_wday < 5 and sec >= _RADAR_AUTO_TS:
                today8 = _date8()
                for k in list(_RADAR_AUTO_DONE):
                    if not str(k).endswith(f":{today8}"):
                        _RADAR_AUTO_DONE.pop(k, None)
                if radar_task_running():
                    await asyncio.sleep(60)
                    continue
                for signal, strictness in _RADAR_AUTO_COMBOS:
                    auto_key = f"{signal}:{strictness}:{today8}"
                    if _RADAR_AUTO_DONE.get(auto_key):
                        continue
                    hit = get_radar_cached_result(signal, strictness)
                    if hit and str(hit.get("date") or "") == today8:
                        _RADAR_AUTO_DONE[auto_key] = True
                        continue
                    try:
                        await run_radar_scan(signal, strictness, force=True)
                        _RADAR_AUTO_DONE[auto_key] = True
                        log.info("radar auto-scan ok signal=%s strictness=%s date=%s", signal, strictness, today8)
                    except Exception as e:
                        _RADAR_AUTO_DONE[auto_key] = False
                        log.warning("radar auto-scan fail signal=%s strictness=%s err=%s", signal, strictness, e)
            await asyncio.sleep(60)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("radar auto-scan loop error: %s", e)
            await asyncio.sleep(120)


def start_radar_auto_scan() -> None:
    import logging
    import os
    log = logging.getLogger(__name__)
    if str(os.getenv("AI24X_RADAR_AUTO_SCAN", "1") or "").strip().lower() in ("0", "false", "off", "no"):
        log.info("radar auto-scan disabled (AI24X_RADAR_AUTO_SCAN=0)")
        return
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        return
    loop.create_task(_radar_auto_scan_loop())
    log.info(
        "radar auto-scan loop started (weekday >= %02d:%02d, shared cache)",
        _RADAR_AUTO_HHMM[0],
        _RADAR_AUTO_HHMM[1],
    )
