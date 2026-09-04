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

# TokenLab /models 接口不带价；此为 2026-08-06 实拉验证的 TL 价表（$/1M），
# 作为 tokenlab_detail 兜底，确保 refresh 后 TL 比价不丢（后续实拉可覆盖）。
_DEFAULT_TL_DETAIL: dict[str, dict[str, float]] = {
    "gpt-5.4": {"in": 0.75, "out": 4.5},
    "gpt-5": {"in": 1.25, "out": 10.0},
    "gpt-5-mini": {"in": 0.25, "out": 2.0},
    "gpt-4o": {"in": 2.5, "out": 10.0},
    "gpt-4o-mini": {"in": 0.15, "out": 0.6},
    "gpt-5.6-terra": {"in": 0.6, "out": 3.6},
    "gpt-5.6-luna": {"in": 0.06, "out": 0.36},
    "claude-opus-5": {"in": 3.25, "out": 16.25},
    "claude-sonnet-5": {"in": 1.95, "out": 9.75},
    "claude-haiku-4.5": {"in": 0.65, "out": 3.25},
    "gemini-3.6-flash": {"in": 0.75, "out": 3.75},
    "gemini-3.1-pro-preview": {"in": 1.0, "out": 6.0},
    "grok-4.20": {"in": 0.625, "out": 1.25},
    "kimi-k3": {"in": 3.0, "out": 15.0},
    "kimi-k2.7": {"in": 0.95, "out": 4.0},
    "deepseek-v4-flash": {"in": 0.14705882, "out": 0.29411765},
    "deepseek-v4-pro": {"in": 0.44117647, "out": 0.88235294},
    "mimo-pro": {"in": 0.435, "out": 0.87},
    "minimax-m3": {"in": 0.3, "out": 1.2},
    "qwen3-max": {"in": 0.35294117, "out": 1.4117647},
    "glm-5.2": {"in": 1.17647059, "out": 4.11764706},
    "qwen3.5-122b": {"in": 0.0882353, "out": 0.70588236},
    "hunyuan-3": {"in": 0.14705882, "out": 0.58823529},
    # TL API 命名别名（与 _TOKENLAB_MODEL_MAP 对齐）
    "mimo-v2.5-pro": {"in": 0.435, "out": 0.87},
    "qwen3.7-max": {"in": 0.35294117, "out": 1.4117647},
    "hy3": {"in": 0.14705882, "out": 0.58823529},
    "kimi-k2.7-code": {"in": 0.95, "out": 4.0},
}

_CACHE_TTL_S = 12 * 3600
_ROLES = {"default_flash", "default_pro", "default_ultra", "vip_pick"}

# 2026-08-14: 已知上游官方涨价日程（DeepSeek 8/17 峰谷定价）。
# 闲时价按官方人民币 ÷ 7.14 折算美元；高峰为闲时 2 倍。
# 作用：① 生效前在后台/飞书提前预警「涨价后毛利」；② 生效后自动按新价算毛利。
# 2026-08-15 修正：L1/L2 默认档已切 MiMo（xiaomi/mimo-v2.5 / -pro），不背 DS 8/17 新成本，
#   涨价日程只保留 VIP 点名（vip-ds-*，真正按 DS 官方价扣费），避免默认档误报倒挂。
_HIKE_SCHEDULE: dict[str, dict[str, Any]] = {
    "vip-ds-flash": {
        "effective": "2026-08-17",
        "in": 0.21,
        "out": 0.63,
        "peak_in": 0.42,
        "peak_out": 1.26,
        "note": "DeepSeek 官方涨价（闲时价）",
    },
    "vip-ds-pro": {
        "effective": "2026-08-17",
        "in": 0.63,
        "out": 1.89,
        "peak_in": 1.26,
        "peak_out": 3.78,
        "note": "DeepSeek 官方涨价（闲时价）",
    },
}


def _hike_applied(cid: str) -> Optional[dict[str, Any]]:
    """返回已生效的涨价日程（今天 >= effective），未生效返回 None。"""
    h = _HIKE_SCHEDULE.get(cid)
    if not h or not h.get("effective"):
        return None
    try:
        eff = datetime.strptime(str(h["effective"]), "%Y-%m-%d").date()
    except Exception:
        return None
    return h if datetime.now().date() >= eff else None


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
                td = raw.get("tokenlab_detail")
                if not isinstance(td, dict) or not td:
                    raw["tokenlab_detail"] = dict(_DEFAULT_TL_DETAIL)
                else:
                    merged = dict(_DEFAULT_TL_DETAIL)
                    merged.update(td)
                    raw["tokenlab_detail"] = merged
                return raw
    except Exception:
        pass
    return {"_meta": {"time": None, "source": "none"}, "tokenlab_detail": dict(_DEFAULT_TL_DETAIL)}


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


def _providers_for(pp: dict[str, Any], or_id: str, cid: Optional[str] = None) -> dict[str, Optional[tuple[float, float]]]:
    """返回 {or, tl, rq: (in,out)|None}。"""
    out: dict[str, Optional[tuple[float, float]]] = {"or": None, "tl": None, "rq": None}
    for x in pp.get("openrouter") or []:
        if x.get("id") == or_id and x.get("pricing"):
            p = x["pricing"]
            out["or"] = (p["in"], p["out"])
            break
    tl_candidates = [_tl_id(or_id)]
    if cid:
        try:
            from model_router import _TOKENLAB_MODEL_MAP
            m = _TOKENLAB_MODEL_MAP.get(str(cid))
            if m:
                tl_candidates.append(str(m))
        except Exception:
            pass
    detail = pp.get("tokenlab_detail") or {}
    for cand in tl_candidates:
        if cand in detail and detail[cand]:
            p = detail[cand]
            out["tl"] = (float(p.get("in") or 0), float(p.get("out") or 0))
            break
    if out["tl"] is None:
        for x in pp.get("tokenlab") or []:
            if x.get("id") in tl_candidates and x.get("pricing"):
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


# —— 主打建议（对内作战台：最省钱 × 最稳 × 当前成本/毛利）——
_PROVIDER_LABEL = {
    "or": "OpenRouter",
    "tl": "TokenLab",
    "rq": "Requesty",
    "openrouter": "OpenRouter",
    "tokenlab": "TokenLab",
    "requesty": "Requesty",
    "siliconflow": "SiliconFlow",
    "deepseek": "DeepSeek官方",
    "qwen_intl": "Qwen国际",
    "openai_compatible": "兼容直连",
}
_HEALTH_PID = {"or": "openrouter", "tl": "tokenlab", "rq": "requesty"}
_TIER_ROLE = {
    "default_flash": "flash",
    "default_pro": "pro",
    "default_ultra": "ultra",
}


def _pair_sum(pair: Optional[tuple[float, float]]) -> Optional[float]:
    if not pair:
        return None
    return float(pair[0] or 0) + float(pair[1] or 0)


def _cheapest_supplier(row: dict[str, Any]) -> Optional[dict[str, Any]]:
    cands: list[tuple[float, str, tuple[float, float]]] = []
    for key in ("or", "tl", "rq"):
        pair = row.get(key)
        if not pair:
            continue
        s = _pair_sum(pair)
        if s is None or s <= 0:
            continue
        cands.append((s, key, (float(pair[0] or 0), float(pair[1] or 0))))
    if not cands:
        return None
    cands.sort(key=lambda x: x[0])
    s, key, pair = cands[0]
    return {
        "key": key,
        "provider": _HEALTH_PID.get(key, key),
        "label": _PROVIDER_LABEL.get(key, key),
        "in": pair[0],
        "out": pair[1],
        "sum": round(s, 4),
    }


def _provider_health(health: dict[str, Any], pid: str) -> dict[str, Any]:
    pid = str(pid or "").strip()
    circuit = (health.get("circuit") or {}).get(pid) or {}
    rec = (health.get("recs") or {}).get(pid) or {}
    win = rec.get("window") or {}
    total = int(win.get("total") or 0)
    fail = int(win.get("fail") or 0)
    rate = float(win.get("rate") if win.get("rate") is not None else (fail / max(1, total)))
    open_c = bool(circuit.get("open"))
    # 分数：熔断=0；样本不足=None；否则 1-失败率
    score: Optional[float]
    if open_c:
        score = 0.0
    elif total < 5:
        score = None
    else:
        score = round(max(0.0, 1.0 - rate), 4)
    return {
        "provider": pid,
        "label": _PROVIDER_LABEL.get(pid, pid),
        "circuit_open": open_c,
        "sample": total,
        "fail": fail,
        "fail_rate": round(rate, 3),
        "score": score,
        "reason": str(circuit.get("reason") or ""),
    }


def _most_stable(row: dict[str, Any], health: dict[str, Any]) -> Optional[dict[str, Any]]:
    keys = [k for k in ("or", "tl", "rq") if row.get(k)]
    if not keys:
        # 无供货商价目时，仍可看 failover / channels 对应健康
        extra = []
        for ch in row.get("channels") or []:
            extra.append(str(ch))
        for ch in row.get("failover_hint") or []:
            extra.append(str(ch))
        pids = []
        for x in extra:
            xl = x.lower()
            if "openrouter" in xl or xl == "or":
                pids.append("openrouter")
            elif "tokenlab" in xl or xl == "tl":
                pids.append("tokenlab")
            elif "requesty" in xl or xl == "rq":
                pids.append("requesty")
            elif "silicon" in xl:
                pids.append("siliconflow")
            elif "deepseek" in xl:
                pids.append("deepseek")
        seen = set()
        ranked = []
        for pid in pids:
            if pid in seen:
                continue
            seen.add(pid)
            ranked.append(_provider_health(health, pid))
    else:
        ranked = [_provider_health(health, _HEALTH_PID[k]) for k in keys]
    if not ranked:
        return None
    # 优先：未熔断 + 有分数的最高分；否则样本不足但未熔断
    scored = [h for h in ranked if h.get("score") is not None and not h.get("circuit_open")]
    if scored:
        scored.sort(key=lambda h: (-float(h["score"]), -int(h.get("sample") or 0)))
        return scored[0]
    soft = [h for h in ranked if not h.get("circuit_open")]
    if soft:
        soft.sort(key=lambda h: -int(h.get("sample") or 0))
        return soft[0]
    ranked.sort(key=lambda h: (1 if h.get("circuit_open") else 0, float(h.get("fail_rate") or 1)))
    return ranked[0]


def _suggest_action(row: dict[str, Any], cheap: Optional[dict[str, Any]], stable: Optional[dict[str, Any]]) -> dict[str, Any]:
    level = str(row.get("level") or "ok")
    flags = list(row.get("flags") or [])
    our_sum = float(row.get("cost_in") or 0) + float(row.get("cost_out") or 0)
    actions: list[str] = []
    action = "keep"
    if level == "alarm":
        action = "fix_margin"
        actions.append("毛利告警：优先调倍率/换上游或暂停下架点名")
    elif level == "warn":
        action = "fix_margin"
        actions.append("毛利偏低：复查成本与售价倍率")
    if cheap and our_sum > 0 and float(cheap.get("sum") or 0) > 0:
        if our_sum > float(cheap["sum"]) * cost_markup():
            actions.append(f"可切更省：{cheap['label']} 合计 ${cheap['sum']}/1M（当前账本成本 ${round(our_sum, 4)}）")
            if action == "keep":
                action = "switch_cheaper"
    if stable:
        if stable.get("circuit_open"):
            actions.append(f"避开熔断：{stable['label']} 电路开路")
            if action == "keep":
                action = "avoid_unstable"
        elif stable.get("score") is not None and float(stable["score"]) < 0.9 and int(stable.get("sample") or 0) >= 20:
            actions.append(f"稳健优先：{stable['label']} 窗口失败率 {stable.get('fail_rate')}")
            if action == "keep":
                action = "prefer_stable"
    if not actions:
        actions.append("主打保持：毛利与通道健康正常")
    # 合成一句主文案
    headline = actions[0]
    if cheap and stable and cheap.get("provider") == stable.get("provider") and action in ("keep", "switch_cheaper", "prefer_stable"):
        headline = f"主打建议：{cheap['label']}（同通道兼最省+较稳）"
        if action == "keep":
            action = "hero"
    return {"action": action, "headline": headline, "notes": actions, "flags": flags}


def build_hero_picks(rows: list[dict[str, Any]], health: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """按档位给出「主打建议」：最省供货商 / 最稳上游 / 账本毛利 / 动作。"""
    health = health or {"circuit": {}, "recs": {}}
    by_role: dict[str, dict[str, Any]] = {}
    vip_rows: list[dict[str, Any]] = []
    for r in rows:
        role = str(r.get("role") or "")
        # 附带 failover 提示供稳定评估
        r = dict(r)
        try:
            cat = next((c for c in mw.catalog_merged() if str(c.get("id")) == str(r.get("id"))), None)
            if cat:
                r["failover_hint"] = list(cat.get("failover_to") or [])
                if not r.get("channels"):
                    ch = []
                    if cat.get("openrouter_id"):
                        ch.append("openrouter")
                    if cat.get("siliconflow_id"):
                        ch.append("siliconflow")
                    if cat.get("direct_id"):
                        ch.append("direct")
                    r["channels"] = ch
        except Exception:
            pass
        if role in _TIER_ROLE:
            # 同档取 priority 最高（catalog 已按角色筛过，通常一条）
            prev = by_role.get(role)
            if prev is None or int(r.get("priority") or 0) >= int(prev.get("priority") or 0):
                by_role[role] = r
        elif role == "vip_pick":
            vip_rows.append(r)

    def _pack(tier: str, r: dict[str, Any]) -> dict[str, Any]:
        cheap = _cheapest_supplier(r)
        stable = _most_stable(r, health)
        sug = _suggest_action(r, cheap, stable)
        return {
            "tier": tier,
            "id": r.get("id"),
            "title": r.get("title"),
            "level": r.get("level"),
            "gm_blend": r.get("gm_blend"),
            "gm_1to4": r.get("gm_1to4"),
            "cost_in": r.get("cost_in"),
            "cost_out": r.get("cost_out"),
            "sell_in": r.get("sell_in"),
            "sell_out": r.get("sell_out"),
            "channels": r.get("channels") or [],
            "cheapest": cheap,
            "most_stable": stable,
            "suggest": sug,
        }

    tiers = []
    for role, tier in (("default_flash", "flash"), ("default_pro", "pro"), ("default_ultra", "ultra")):
        if role in by_role:
            tiers.append(_pack(tier, by_role[role]))

    # VIP：优先告警/预警，其次有降本机会，最多 6 条
    vip_rows.sort(
        key=lambda x: (
            {"alarm": 0, "warn": 1, "info": 2, "ok": 3}.get(str(x.get("level")), 9),
            -(float(x.get("gm_1to4") or 0) if x.get("gm_1to4") is not None else 999),
            str(x.get("id") or ""),
        )
    )
    vip_watch = [_pack("vip", r) for r in vip_rows[:6]]

    open_circuits = [
        {"provider": pid, "label": _PROVIDER_LABEL.get(pid, pid), **(info or {})}
        for pid, info in (health.get("circuit") or {}).items()
        if (info or {}).get("open")
    ]
    return {
        "note": "对内作战台：对外仍主推 flash/pro/auto 档位；通道名仅管理端可见。",
        "tiers": tiers,
        "vip_watch": vip_watch,
        "health": {
            "open_circuits": open_circuits,
            "circuit_enabled": bool(health.get("circuit_enabled")),
        },
    }


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
        # 2026-08-15 峰谷：8/17 官方峰谷生效后，售价与成本都按时段取（峰时走 peak 倍率/peak 成本）
        from model_router import current_period

        period = current_period()
        cost_in = float(c.get("cost_in") or 0)
        cost_out = float(c.get("cost_out") or 0)
        # 已生效的官方涨价：按日程覆盖成本（8/17 后自动切新价，无需改代码）
        hike_now = _hike_applied(cid)
        if hike_now:
            if period == "peak" and hike_now.get("peak_in") is not None:
                cost_in = float(hike_now.get("peak_in") or cost_in)
                cost_out = float(hike_now.get("peak_out") or cost_out)
                # 售价同步切峰值倍率（仅官方峰谷生效后，避免生效前毛利虚高）
                _pin = c.get("peak_in_mult")
                _pout = c.get("peak_out_mult")
                if _pin is not None or _pout is not None:
                    in_mult = max(1, int(_pin if _pin is not None else in_mult))
                    out_mult = max(1, int(_pout if _pout is not None else out_mult))
            else:
                cost_in = float(hike_now.get("in") or cost_in)
                cost_out = float(hike_now.get("out") or cost_out)
        sell_in = round(ref * in_mult, 4)
        sell_out = round(ref * out_mult, 4)
        gm_in = _gm(sell_in, cost_in)
        gm_out = _gm(sell_out, cost_out)
        gm_blend = round((1 - (cost_in + cost_out) / (sell_in + sell_out)) * 100, 1) if (sell_in + sell_out) > 0 else None
        gm_1to4 = round((1 - (cost_in + 4 * cost_out) / (sell_in + 4 * sell_out)) * 100, 1) if (sell_in + 4 * sell_out) > 0 else None
        or_id = str(c.get("openrouter_id") or "")
        prov = _providers_for(pp, or_id, cid)
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
        # 未生效的涨价日程：提前预警「涨价后毛利」，避免 8/17 被打个措手不及
        hike_meta = None
        if not hike_now:
            hike = _HIKE_SCHEDULE.get(cid)
            if hike:
                hin = float(hike.get("in") or 0)
                hout = float(hike.get("out") or 0)
                pin = float(hike.get("peak_in") or hin)
                pout = float(hike.get("peak_out") or hout)
                # 预判用「8/17 后实际售价倍率」（峰时走已拍板 peak_in/out_mult），
                # 避免拿旧倍率误报「峰时贴线/倒挂」（如 vip-ds-flash 峰 out 4→6 后峰 GM 实为 40%）
                f_in_mult = in_mult
                f_out_mult = out_mult
                _pin_m = c.get("peak_in_mult")
                _pout_m = c.get("peak_out_mult")
                if _pin_m is not None:
                    f_in_mult = max(1, int(_pin_m))
                if _pout_m is not None:
                    f_out_mult = max(1, int(_pout_m))
                f_sell_in = round(ref * f_in_mult, 4)
                f_sell_out = round(ref * f_out_mult, 4)
                denom = f_sell_in + 4 * f_sell_out
                g1_off = (
                    round((1 - (hin + 4 * hout) / denom) * 100, 1)
                    if denom > 0
                    else None
                )
                g1_peak = (
                    round((1 - (pin + 4 * pout) / denom) * 100, 1)
                    if denom > 0
                    else None
                )
                eff = str(hike.get("effective") or "")
                hike_meta = {
                    "effective": eff,
                    "gm_1to4_off": g1_off,
                    "gm_1to4_peak": g1_peak,
                    "note": str(hike.get("note") or ""),
                }
                txt = (
                    f"{eff} 起{hike.get('note', '官方涨价')}: "
                    f"1:4 毛利预计 {g1_off}%(闲时)/{g1_peak}%(高峰)"
                )
                if g1_off is not None and g1_off < 0:
                    flags.append(txt + " → 涨价后倒挂")
                    level = "alarm"
                elif g1_peak is not None and g1_peak < red_gm():
                    flags.append(txt + " → 高峰倒挂")
                    level = "alarm"
                elif (g1_off is not None and g1_off < warn_gm()) or (
                    g1_peak is not None and g1_peak < warn_gm()
                ):
                    if level != "alarm":
                        level = "warn"
                    flags.append(txt)
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
            "priority": int(c.get("priority") or 0),
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
            "hike": hike_meta,
            "level": level,
            "flags": flags,
        })
    rows.sort(key=lambda r: ({"alarm": 0, "warn": 1, "info": 2, "ok": 3}[r["level"]], r["id"]))
    alarm_rows = [r for r in rows if r["level"] == "alarm"]
    warn_rows = [r for r in rows if r["level"] == "warn"]
    info_rows = [r for r in rows if r["level"] == "info"]
    hike_rows = [r for r in rows if r.get("hike")]
    health: dict[str, Any] = {}
    try:
        from upstream_health import snapshot as _uh_snapshot

        health = _uh_snapshot() or {}
    except Exception:
        health = {"circuit": {}, "recs": {}, "circuit_enabled": False}
    hero = build_hero_picks(rows, health)
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
            "hike": len(hike_rows),
            "hike_ids": [r["id"] for r in hike_rows],
        },
        "rows": rows,
        "hero_picks": hero,
    }


def reset_cache() -> None:
    _save({"_meta": {"time": None, "source": "none"}})
