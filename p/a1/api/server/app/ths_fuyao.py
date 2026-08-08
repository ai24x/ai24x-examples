# -*- coding: utf-8 -*-
"""同花顺金融数据服务（hithink-finance / fuyao.aicubes.cn）Provider - 免费期增强通道。

官方 REST 基址: https://fuyao.aicubes.cn
请求头: X-api-key: <key>
统一信封: {"code":0,"message":"ok","request_id":"...","data":{...}}
业务码: 0 成功 / 2001 Key无效 / 2003 权限不足 / 4001 频率超限 / 1002-1003 参数错误 / 3002 数据暂不可用 / 5002-5003 上游故障（HTTP 恒 200）

接入纪律（老板确认 2026-08-08）:
- 免费期随时可能结束（先养b后收费），只做增强/交叉验证通道，不做唯一数据源
- 同花顺板块指数(886xxx/881xxx)与东财板块(BKxxxx)不同编制、K线不等 -> 不替换板块K线
- 同花顺没有主力净流入/板块资金流/北南向 -> 资金面仍走东财 push2delay
- 复用 _RateGate 限流 + 按日缓存 + 熔断，防 4001

配置（.env 或 DB admin_config，admin_config 优先）:
- AI24X_FUYAO_ENABLED=1
- AI24X_FUYAO_API_KEY=<key>
- AI24X_FUYAO_BASE_URL=https://fuyao.aicubes.cn（默认）
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from datetime import datetime
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Request

from . import db
from .config import settings
from .providers import _RateGate

router = APIRouter()

DEFAULT_BASE_URL = "https://fuyao.aicubes.cn"

# 特色数据端点（官方 /api/a-share/special-data/ 前缀）
_SPECIAL_ENDPOINTS: dict[str, str] = {
    "limit-up-pool": "/api/a-share/special-data/limit-up-pool",              # 涨停池
    "limit-up-ladder": "/api/a-share/special-data/limit-up-ladder",          # 连板天梯（近30个交易日）
    "skyrocket-list": "/api/a-share/special-data/skyrocket-list",            # 飙升榜（日/小时 Top30）
    "hot-stock-list": "/api/a-share/special-data/hot-stock-list",            # 热股榜（24h/小时级 Top30）
    "hot-stock-history": "/api/a-share/special-data/hot-stock-list-history", # 历史热股榜
    "hot-stock-rank-trend": "/api/a-share/special-data/hot-stock-rank-trend",# 个股排名走势
    "anomaly-analysis-list": "/api/a-share/special-data/anomaly-analysis-list",   # 个股异动原因列表（当日）
    "anomaly-analysis-stock": "/api/a-share/special-data/anomaly-analysis-stock", # 按股票查异动（thscodes 批量，如 600519.SH）
    "dragon-tiger-list": "/api/a-share/special-data/dragon-tiger-list",      # 龙虎榜（全部/机构/游资）
}

# 起步限流：0.2s / 60次每分钟（免费期，保守；实测稳定后可放宽）
_FUYAO_GATE = _RateGate(min_interval_s=0.2, max_per_minute=60)

# 按日缓存目录（当日命中不重抓；收盘后当日固定）
_CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "ths_fuyao_cache")

# 失败熔断：endpoint -> until_ts（网络/4001/上游故障）
_FAIL_UNTIL: dict[str, float] = {}
_FAIL_TTL_S = 120.0

# Key 无效熔断（2001/2003）：熔断更久，不重复打上游
_KEY_BAD_UNTIL: float = 0.0
_KEY_BAD_TTL_S = 900.0

_CLIENT: Optional[httpx.AsyncClient] = None
_CLIENT_LOCK = asyncio.Lock()
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "Chrome/124.0 Safari/537.36")


async def _client() -> httpx.AsyncClient:
    global _CLIENT
    if _CLIENT is not None:
        return _CLIENT
    async with _CLIENT_LOCK:
        if _CLIENT is None:
            _CLIENT = httpx.AsyncClient(
                timeout=httpx.Timeout(10.0, connect=5.0),
                headers={"User-Agent": _UA},
                limits=httpx.Limits(max_connections=4, max_keepalive_connections=4),
                follow_redirects=True,
            )
    return _CLIENT


def _db_conf() -> dict[str, str]:
    """DB admin_config（后台可热改，无需重启）。"""
    try:
        return db.admin_config_get_all()
    except Exception:
        return {}


def fuyao_config() -> dict[str, str]:
    c = _db_conf()
    key = (c.get("AI24X_FUYAO_API_KEY") or "").strip() \
        or str(getattr(settings, "fuyao_api_key", "") or "").strip()
    enabled = (c.get("AI24X_FUYAO_ENABLED") or "").strip() \
        or str(getattr(settings, "fuyao_enabled", "") or "").strip()
    base = (c.get("AI24X_FUYAO_BASE_URL") or "").strip() \
        or str(getattr(settings, "fuyao_base_url", "") or "").strip() \
        or DEFAULT_BASE_URL
    return {"api_key": key, "enabled": enabled, "base_url": base.rstrip("/")}


def fuyao_status() -> dict[str, Any]:
    cfg = fuyao_config()
    key = cfg["api_key"]
    masked = ""
    if key:
        masked = (key[:3] + "****" + key[-3:]) if len(key) > 8 else "****"
    return {
        "ok": True,
        "enabled": str(cfg.get("enabled") or "").strip().lower() in ("1", "true", "yes", "on"),
        "has_key": bool(key),
        "key_masked": masked,
        "base_url": cfg["base_url"],
        "gate": {"min_interval_s": _FUYAO_GATE.min_interval_s,
                 "max_per_minute": _FUYAO_GATE.max_per_minute},
        "key_bad_until": _KEY_BAD_UNTIL,
        "fail_until": dict(_FAIL_UNTIL),
    }


def _enabled() -> bool:
    return str(fuyao_config().get("enabled") or "").strip().lower() in ("1", "true", "yes", "on")


def _cache_path(name: str, params: dict[str, Any]) -> str:
    d8 = datetime.now().strftime("%Y%m%d")
    day_dir = os.path.join(_CACHE_DIR, d8)
    os.makedirs(day_dir, exist_ok=True)
    q = "&".join(f"{k}={v}" for k, v in sorted(params.items()) if v not in (None, ""))
    h = hashlib.md5(q.encode("utf-8")).hexdigest()[:8] if q else "default"
    return os.path.join(day_dir, f"{name}-{h}.json")


def _cache_ttl(name: str) -> float:
    """盘中 15 分钟；收盘后/周末当日固定（自然日粒度）。"""
    try:
        now = datetime.now()
        if now.weekday() >= 5:
            return 24 * 3600.0
        hm = now.hour * 60 + now.minute
        if hm >= 15 * 60 + 30:
            return 24 * 3600.0
    except Exception:
        pass
    return 900.0


def _cache_load(path: str, ttl_s: float) -> Optional[dict]:
    try:
        if not os.path.exists(path):
            return None
        if time.time() - os.path.getmtime(path) > ttl_s:
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _cache_save(path: str, payload: dict) -> None:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
    except Exception:
        pass


async def fetch_special(name: str, params: Optional[dict[str, Any]] = None,
                        force: bool = False) -> dict[str, Any]:
    """拉取同花顺特色数据（涨停池/连板天梯/飙升/热榜/异动/龙虎榜）。"""
    global _KEY_BAD_UNTIL
    params = dict(params or {})
    if not _enabled():
        return {"ok": False, "code": "disabled",
                "msg": "同花顺数据源未启用（AI24X_FUYAO_ENABLED=1 开启）"}
    api_key = fuyao_config()["api_key"]
    if not api_key:
        return {"ok": False, "code": "no_key",
                "msg": "未配置同花顺 API Key（AI24X_FUYAO_API_KEY）"}
    path = _SPECIAL_ENDPOINTS.get(name)
    if not path:
        return {"ok": False, "code": "unknown",
                "msg": f"未知端点 {name!r}，可用: {sorted(_SPECIAL_ENDPOINTS)}"}

    now = time.time()
    if now < _KEY_BAD_UNTIL:
        return {"ok": False, "code": "key_bad",
                "msg": "Key 已被上游拒绝，熔断中，稍后自动恢复"}
    if now < _FAIL_UNTIL.get(name, 0):
        return {"ok": False, "code": "cooldown",
                "msg": "该端点近端失败，熔断中，稍后重试"}

    cpath = _cache_path(name, params)
    if not force:
        hit = _cache_load(cpath, _cache_ttl(name))
        if hit is not None:
            hit["_cached"] = True
            return hit

    await _FUYAO_GATE.acquire()
    url = fuyao_config()["base_url"] + path
    headers = {"X-api-key": api_key, "User-Agent": _UA}
    try:
        client = await _client()
        resp = await client.get(url, params=params, headers=headers)
        try:
            data = resp.json()
        except Exception:
            data = {"code": -1, "message": f"非 JSON 响应 HTTP {resp.status_code}"}
        code = data.get("code")
        msg = data.get("message") or data.get("msg") or ""
        if code == 0:
            data_node = data.get("data") or {}
            # 龙虎榜等端点数据放在 data.stock_items / data.hot_money_items
            item = data_node.get("item") if data_node.get("item") is not None else data_node
            payload = {"ok": True, "code": 0, "name": name, "params": params,
                       "item": item, "request_id": data.get("request_id"),
                       "ts": data_node.get("timestamp")}
            _cache_save(cpath, payload)
            _FAIL_UNTIL.pop(name, None)
            return payload
        if code in (2001, 2003):
            _KEY_BAD_UNTIL = time.time() + _KEY_BAD_TTL_S
            return {"ok": False, "code": str(code), "msg": f"Key 被拒（{code}）: {msg}"}
        if code == 4001:
            _FAIL_UNTIL[name] = time.time() + _FAIL_TTL_S
            return {"ok": False, "code": "4001",
                    "msg": "上游限流(4001)，已熔断，稍后自动重试"}
        _FAIL_UNTIL[name] = time.time() + _FAIL_TTL_S
        return {"ok": False, "code": str(code), "msg": f"上游返回 {code}: {msg}"}
    except Exception as e:  # noqa: BLE001
        _FAIL_UNTIL[name] = time.time() + _FAIL_TTL_S
        return {"ok": False, "code": "network",
                "msg": f"请求失败: {type(e).__name__}: {e}"}


# ---------------- 情绪面聚合（复盘/掘金共用） ----------------
def _prev_trading_day(d=None):
    """最近一个交易日（周末回退到周五；节假日暂由调用方传日期）。"""
    from datetime import timedelta
    d = d or datetime.now()
    while d.weekday() >= 5:
        d = d - timedelta(days=1)
    return d


def _date_ms_of(d) -> int:
    return int(datetime(d.year, d.month, d.day).timestamp() * 1000)


async def build_sentiment(target_date: str | None = None) -> dict[str, Any]:
    """聚合同花顺情绪面：涨停池/连板天梯/热榜/飙升/异动/龙虎榜游资。

    全部复用 fetch_special 的按日缓存与限流；任一端点失败降级，不阻塞。
    """
    from datetime import timedelta
    tgt = None
    if target_date:
        try:
            tgt = datetime.strptime(str(target_date), "%Y-%m-%d")
        except Exception:
            tgt = None
    tgt = _prev_trading_day(tgt)
    date_s = tgt.strftime("%Y-%m-%d")
    out: dict[str, Any] = {"ok": True, "date": date_s, "source": "ths:fuyao",
                           "limit_up": {}, "ladder": {}, "hot": [], "skyrocket": [],
                           "hot_money": [], "anomaly": {}, "errors": []}
    # 1) 涨停池
    r = await fetch_special("limit-up-pool", {"size": "200", "date_ms": str(_date_ms_of(tgt))})
    if r.get("ok"):
        items = r.get("item") or []
        max_c = 0
        max_name = ""
        for it in items:
            cc = int(it.get("continue_day_cnt") or 0)
            if cc > max_c:
                max_c = cc
                max_name = it.get("name") or ""
        sealed = sorted(items, key=lambda x: float(x.get("seal_money") or 0), reverse=True)[:5]
        out["limit_up"] = {"count": len(items), "max_lianban": max_c, "max_name": max_name,
                            "seal_money_top": [{"name": it.get("name"), "ticker": it.get("ticker"),
                                                 "seal": float(it.get("seal_money") or 0),
                                                 "reason": it.get("limit_up_reason") or ""} for it in sealed]}
    else:
        out["errors"].append({"k": "limit-up-pool", "msg": r.get("msg")})
    # 2) 连板天梯（取最近交易日梯队）
    r = await fetch_special("limit-up-ladder")
    if r.get("ok"):
        items = r.get("item") or []
        if items:
            last = max(items, key=lambda x: str(x.get("date") or ""))
            boards = last.get("boards") or {}
            ladder = []
            for k in ("two_board", "three_board", "four_board", "five_board", "six_board", "seven_over"):
                lst = boards.get(k) or []
                ladder.append({"board": k, "count": len(lst),
                               "names": [x.get("name") or "" for x in lst][:4]})
            out["ladder"] = {"date": str(last.get("date") or ""), "rows": ladder}
    else:
        out["errors"].append({"k": "limit-up-ladder", "msg": r.get("msg")})
    # 3) 热股榜 / 飙升榜
    for name, key in (("hot-stock-list", "hot"), ("skyrocket-list", "skyrocket")):
        r = await fetch_special(name)
        if r.get("ok"):
            items = (r.get("item") or [])[:5]
            out[key] = [{"name": it.get("name"), "ticker": it.get("ticker"),
                         "rank": it.get("rank"), "heat": it.get("heat"),
                         "rank_trend": it.get("rank_trend")} for it in items]
        else:
            out["errors"].append({"k": name, "msg": r.get("msg")})
    # 4) 当日异动
    r = await fetch_special("anomaly-analysis-list")
    if r.get("ok"):
        items = r.get("item") or []
        tags: dict[str, int] = {}
        for it in items:
            t = it.get("tag_name") or "其他"
            tags[t] = tags.get(t, 0) + 1
        out["anomaly"] = {"count": len(items), "tags": tags,
                          "top": [{"name": it.get("stock_name"), "thscode": it.get("thscode"),
                                   "tag": it.get("tag_name"),
                                   "reason": (it.get("analysis_content") or "")[:60]} for it in items[:6]]}
    else:
        out["errors"].append({"k": "anomaly-analysis-list", "msg": r.get("msg")})
    # 5) 龙虎榜游资净买入
    r = await fetch_special("dragon-tiger-list", {"board_type": "hot_money", "date": date_s})
    if r.get("ok"):
        node = r.get("item") or {}
        hm = (node.get("hot_money_items") or []) if isinstance(node, dict) else []
        hm_sorted = sorted(hm, key=lambda x: float(x.get("buying") or 0), reverse=True)[:5]
        out["hot_money"] = [{"name": it.get("name"), "buying": float(it.get("buying") or 0),
                             "stocks": [x.get("name") for x in (it.get("rows") or [])[:3]]}
                            for it in hm_sorted]
    else:
        out["errors"].append({"k": "dragon-tiger-list", "msg": r.get("msg")})
    return out

# ---------------- 路由（骨架阶段保持开放方便实测；接入页面时再按需加鉴权） ----------------
@router.get("/api/ths/status")
def ths_status() -> dict[str, Any]:
    return fuyao_status()


@router.get("/api/ths/sentiment")
async def ths_sentiment(target_date: str = "") -> dict[str, Any]:
    """复盘/掘金情绪面聚合（涨停/连板/热榜/飙升/异动/龙虎榜游资）。"""
    return await build_sentiment(target_date or None)


@router.get("/api/ths/anomaly")
async def ths_anomaly(secid: str = "", thscodes: str = "", force: int = 0) -> dict[str, Any]:
    """个股异动排查：传内部 secid（如 1.600519）或 thscodes（600519.SH,000001.SZ）。"""
    if not thscodes:
        from .providers import _secid_to_ths_thscode
        ths_code = _secid_to_ths_thscode(secid)
        if not ths_code:
            return {"ok": False, "code": "no_code", "msg": f"无法解析 secid: {secid}"}
        thscodes = ths_code
    return await fetch_special("anomaly-analysis-stock", {"thscodes": thscodes}, force=bool(force))


@router.get("/api/ths/special/{name}")
async def ths_special(name: str, request: Request, force: int = 0) -> dict[str, Any]:
    """同花顺特色数据统一入口（官方参数原样透传）。

    name 可选:
      limit-up-pool 涨停池(size/sort_field/sort_dir/date_ms) / limit-up-ladder 连板天梯
      skyrocket-list 飙升榜(period=day|hour) / hot-stock-list 热股榜(period=day|hour)
      hot-stock-history 历史热股榜(date=yyyy-MM-dd)
      anomaly-analysis-list 当日异动列表(tag_codes=LIMIT_UP,SHARP_FALL,...)
      anomaly-analysis-stock 按股票查异动(thscodes=600519.SH,000001.SZ)
      dragon-tiger-list 龙虎榜(board_type=all|org|hot_money, date=yyyy-MM-dd)
    force=1 绕过当日缓存重拉。
    """
    params: dict[str, Any] = {}
    for k, v in request.query_params.items():
        if k == "force":
            force = int(v or 0) or force
            continue
        params[k] = v
    return await fetch_special(name, params, force=bool(force))

