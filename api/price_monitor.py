# -*- coding: utf-8 -*-
"""价格与供应链监控：售价/成本/毛利（三口径）+ 供货商比价 + 倒挂/低毛利检测。

管理端：
  GET  /v1/admin/price/monitor   → snapshot()
  POST /v1/admin/price/refresh   → 实拉 OR/TL/Requesty 价目 + snapshot()

数据落盘：api/data/provider_prices.json（gitignored；12h 内不重复实拉）
阈值（env，默认值）：
  PRICE_GM_WARN=20       混合毛利黄线 %
  PRICE_GM_RED=0         混合毛利红线 %（< 0 即倒挂）
  PRICE_COST_MARKUP=1.2  我方成本 > 市场最低供货商价 × 该倍数 → 提示可切通道

口径：
  gm_in    = (sell_in - cost_in) / sell_in
  gm_out   = (sell_out - cost_out) / sell_out
  gm_blend = 1 - (cost_in+cost_out)/(sell_in+sell_out)      （1:1 混合）
  gm_1to4  = 1 - (cost_in+4*cost_out)/(sell_in+4*sell_out)  （1:4 加权，贴近实际流量）
倒挂判定：gm_in < 0 或 gm_out < 0 或 gm_blend < 0。
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

import model_warehouse as mw

_DATA_PATH = Path(__file__).resolve().parent / "data" / "provider_prices.json"
_CACHE_TTL_S = 12 * 3600
_ROLES = {"default_flash", "default_pro", "default_ultra", "vip_pick"}


def _cfg(key: str, default: float) -> float:
    v = (os.getenv(key) or "").strip()
    if not v:
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def warn_gm() -> float:
    return _cfg("PRICE_GM_WARN", 20.0)


def red_gm() -> float:
    return _cfg("PRICE_GM_RED", 0.0)


def cost_markup() -> float:
    return max(1.0, _cfg("PRICE_COST_MARKUP", 1.2))


def _cst(ts: Optional[int]) -> str:
    try:
        return datetime.fromtimestamp(int(ts or 0), tz=timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(ts)


def _load() -> dict[str, Any]:
    try:
        if _DATA_PATH.is_file():
            raw = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                return raw
    except Exception:
        pass
    return {"_meta": {"time": None, "source": "none"}}


def _save(data: dict[str, Any]) -> None:
    try:
        _DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        _DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except Exception:
        pass


# —— 拉价 ——
def _http_get_json(url: str, headers: Optional[dict] = None, timeout: int = 30):
    import urllib.request

    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _provider_upstream(pid: str) -> Optional[dict[str, Any]]:
    try:
        from upstream_providers import resolve_provider

        return resolve_provider(pid)
    except Exception:
        return None


def _parse_pricing(pid: str, raw: Any) -> Optional[dict[str, float]]:
    """归一化供货商价目到 {in,out}（$/1M）。"""
    try:
        if pid == "openrouter" and isinstance(raw, dict):
            p = float(raw.get("prompt") or 0) * 1e6
            c = float(raw.get("completion") or 0) * 1e6
            if p > 0 or c > 0:
                return {"in": round(p, 6), "out": round(c, 6)}
        elif pid == "requesty" and isinstance(raw, list) and raw:
            p = float(raw[0].get("input_price") or 0) * 1e6
            c = float(raw[0].get("output_price") or 0) * 1e6
            if p > 0 or c > 0:
                return {"in": round(p, 6), "out": round(c, 6)}
        elif pid == "tokenlab":
            if isinstance(raw, dict):
                def _num(v):
                    if isinstance(v, (int, float)):
                        return float(v)
                    s = str(v or "").replace("$", "").strip()
                    return float(s) if s else 0.0
                p, c = _num(raw.get("in")), _num(raw.get("out"))
                if p > 0 or c > 0:
                    return {"in": p, "out": c}
    except Exception:
        pass
    return None


def _fetch_provider(pid: str, timeout_s: int = 20) -> list[dict[str, Any]]:
    up = _provider_upstream(pid)
    if not up:
        return []
    base = str(up.get("base") or up.get("default_base") or "")
    key = str(up.get("key") or "")
    url = base.rstrip("/") + "/models"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    if not key:
        headers = {"Content-Type": "application/json"}
    try:
        data = _http_get_json(url, headers=headers, timeout=timeout_s)
    except Exception:
        return []
    items = data.get("data") if isinstance(data, dict) else data
    out = []
    for it in items or []:
        mid = str(it.get("id") or "")
        if not mid:
            continue
        p = _parse_pricing(pid, it.get("pricing"))
        out.append({"id": mid, "pricing": p})
    return out


def refresh_provider_prices(force: bool = False) -> dict[str, Any]:
    cur = _load()
    meta = cur.get("_meta") or {}
    last = meta.get("time")
    age_s = _CACHE_TTL_S + 1
    if last and not force:
        try:
            age_s = time.time() - datetime.strptime(str(last), "%Y-%m-%d %H:%M:%S").timestamp()
        except Exception:
            age_s = _CACHE_TTL_S + 1
        if age_s < _CACHE_TTL_S:
            out = {k: v for k, v in cur.items() if k != "_meta"}
            return {"ok": True, "cached": True, "age_s": int(age_s), **out}

    fetched: dict[str, Any] = {"_meta": {"time": datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S"),
                                         "source": "live"}}
    from concurrent.futures import ThreadPoolExecutor

    def _fetch_one(pid: str, timeout_s: int = 15) -> tuple[str, list[dict[str, Any]], int]:
        t0 = time.time()
        rows = _fetch_provider(pid, timeout_s=timeout_s)
        return pid, rows, int((time.time() - t0) * 1000)

    results: dict[str, Any] = {}
    with ThreadPoolExecutor(max_workers=3) as ex:
        futs = {ex.submit(_fetch_one, pid, 15): pid for pid in ("openrouter", "tokenlab", "requesty")}
        for fut in futs:
            pid = futs[fut]
            try:
                _pid, rows, ms = fut.result(timeout=30)
                fetched[pid] = rows
                results[pid] = {"ok": True, "count": len(rows), "ms": ms}
            except Exception as e:
                old = cur.get(pid)
                fetched[pid] = old if isinstance(old, list) else []
                results[pid] = {"ok": False, "error": str(e)[:120], "ms": -1, "fallback_old": isinstance(old, list)}
    # 保留已有 tokenlab_detail（TL models 接口不带价，detail 为已核价目）
    if isinstance(cur.get("tokenlab_detail"), dict) and cur["tokenlab_detail"]:
        fetched["tokenlab_detail"] = cur["tokenlab_detail"]
    else:
        fetched["tokenlab_detail"] = {}
    _save(fetched)
    out = {k: v for k, v in fetched.items() if k != "_meta"}
    return {"ok": True, "cached": False, "age_s": 0, "providers": results, **out}


# —— 比价 ——
def _tl_id(or_id: str) -> str:
    return str(or_id or "").rsplit("/", 1)[-1]


def _providers_for(pp: dict[str, Any], or_id: str) -> dict[str, Optional[tuple[float, float]]]:
    """返回 {or, tl, rq: (in,out)|None}。"""
    out: dict[str, Optional[tuple[float, float]]] = {"or": None, "tl": None, "rq": None}
    for x in pp.get("openrouter") or []:
        if x.get("id") == or_id and x.get("pricing"):
            p = x["pricing"]
            out["or"] = (p["in"], p["out"])
            break
    tl_id = _tl_id(or_id)
    detail = pp.get("tokenlab_detail") or {}
    if tl_id in detail and detail[tl_id]:
        p = detail[tl_id]
        out["tl"] = (float(p.get("in") or 0), float(p.get("out") or 0))
    else:
        for x in pp.get("tokenlab") or []:
            if x.get("id") == tl_id and x.get("pricing"):
                p = x["pricing"]
                out["tl"] = (p["in"], p["out"])
                break
    for x in pp.get("requesty") or []:
        if x.get("id") == or_id and x.get("pricing"):
            p = x["pricing"]
            out["rq"] = (p["in"], p["out"])
            break
    return out


def _market_min(prov: dict[str, Optional[tuple[float, float]]]) -> Optional[tuple[float, float]]:
    ins = [p[0] for p in prov.values() if p and p[0] > 0]
    outs = [p[1] for p in prov.values() if p and p[1] > 0]
    if not ins and not outs:
        return None
    return (min(ins) if ins else 0.0, min(outs) if outs else 0.0)


def _gm(sell: float, cost: float) -> Optional[float]:
    return round((sell - cost) / sell * 100, 1) if sell > 0 else None


# —— 快照 ——
def snapshot() -> dict[str, Any]:
    pp = _load()
    ref = float(mw.flash_ref_usd_per_m() or 0.35)
    rows: list[dict[str, Any]] = []
    for c in mw.catalog_merged():
        cid = str(c.get("id") or "")
        role = str(c.get("role") or "")
        if role not in _ROLES:
            continue
        if role == "vip_pick" and not bool(c.get("pick_enabled", True)):
            continue
        if role.startswith("default_"):
            layer = str(c.get("layer") or "").upper()
            layer_mult = mw.layer_cost_mult_for(layer)
            in_mult = out_mult = max(1, layer_mult)
        else:
            in_mult = max(1, int(c.get("in_mult") or c.get("billing_mult") or 1))
            out_mult = max(1, int(c.get("out_mult") or c.get("billing_mult") or 1))
        sell_in = round(ref * in_mult, 4)
        sell_out = round(ref * out_mult, 4)
        cost_in = float(c.get("cost_in") or 0)
        cost_out = float(c.get("cost_out") or 0)
        gm_in = _gm(sell_in, cost_in)
        gm_out = _gm(sell_out, cost_out)
        gm_blend = round((1 - (cost_in + cost_out) / (sell_in + sell_out)) * 100, 1) if (sell_in + sell_out) > 0 else None
        gm_1to4 = round((1 - (cost_in + 4 * cost_out) / (sell_in + 4 * sell_out)) * 100, 1) if (sell_in + 4 * sell_out) > 0 else None
        or_id = str(c.get("openrouter_id") or "")
        prov = _providers_for(pp, or_id)
        market = _market_min(prov)
        flags: list[str] = []
        level = "ok"
        if (gm_in is not None and gm_in < 0) or (gm_out is not None and gm_out < 0) or (gm_blend is not None and gm_blend < 0):
            level = "alarm"
            flags.append("倒挂")
        elif gm_blend is not None and gm_blend < red_gm():
            level = "alarm"
            flags.append("毛利低于红线")
        if level != "alarm":
            if gm_blend is not None and gm_blend < warn_gm():
                level = "warn"
                flags.append("混合毛利低")
            elif min(gm_in or 999, gm_out or 999) < 10:
                level = "warn"
                flags.append("单端毛利低")
        if market and (market[0] > 0 or market[1] > 0):
            mc = cost_in + cost_out
            mp = market[0] + market[1]
            if mp > 0 and mc > mp * cost_markup():
                flags.append(f"成本高于市场最低 {mc / mp:.0%}")
        if level == "ok" and flags:
            level = "info"  # 仅有降本机会（成本高于市场最低），不算风险，面板灰显、不推预警
        rows.append({
            "id": cid,
            "title": str(c.get("title") or cid),
            "role": role,
            "enabled": bool(c.get("pick_enabled", True)),
            "in_mult": in_mult,
            "out_mult": out_mult,
            "sell_in": sell_in,
            "sell_out": sell_out,
            "cost_in": round(cost_in, 4),
            "cost_out": round(cost_out, 4),
            "gm_in": gm_in,
            "gm_out": gm_out,
            "gm_blend": gm_blend,
            "gm_1to4": gm_1to4,
            "or": prov.get("or"),
            "tl": prov.get("tl"),
            "rq": prov.get("rq"),
            "market_min": market,
            "channels": c.get("channels") or [],
            "level": level,
            "flags": flags,
        })
    rows.sort(key=lambda r: ({"alarm": 0, "warn": 1, "info": 2, "ok": 3}[r["level"]], r["id"]))
    alarm_rows = [r for r in rows if r["level"] == "alarm"]
    warn_rows = [r for r in rows if r["level"] == "warn"]
    info_rows = [r for r in rows if r["level"] == "info"]
    return {
        "ok": True,
        "generated_cst": datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S"),
        "flash_ref": ref,
        "provider_prices_time": (pp.get("_meta") or {}).get("time"),
        "thresholds": {"gm_warn": warn_gm(), "gm_red": red_gm(), "cost_markup": cost_markup()},
        "summary": {
            "total": len(rows),
            "alarm": len(alarm_rows),
            "warn": len(warn_rows),
            "info": len(info_rows),
            "ok": len(rows) - len(alarm_rows) - len(warn_rows) - len(info_rows),
            "alarm_ids": [r["id"] for r in alarm_rows],
            "warn_ids": [r["id"] for r in warn_rows],
            "info_ids": [r["id"] for r in info_rows],
        },
        "rows": rows,
    }


def reset_cache() -> None:
    _save({"_meta": {"time": None, "source": "none"}})