# -*- coding: utf-8 -*-
"""上游通道健康统计 + 熔断（默认关）。

- record_attempt(provider, model, ok, ms, err)：路由层每次上游尝试后调用（成功/失败都记）
- circuit_skip(provider)：True 表示该聚合通道处于熔断冷却，路由链应跳过它（自动切走主通道）
- snapshot()：窗口失败率 / 连续失败 / 熔断状态（供管理端接口与 ops_alert 预警）
- 数据落盘 api/data/upstream_health.json（gitignored；写盘节流 5s，避免高并发拖慢请求）

开关（env）：
- TOKEN_CIRCUIT_ENABLED：熔断总开关，默认 0（关）
- TOKEN_CIRCUIT_TRIP_N：连续失败多少次触发熔断，默认 8
- TOKEN_CIRCUIT_COOL_S：熔断冷却秒数，默认 300（5 分钟后自动恢复探测）
- TOKEN_UPSTREAM_HEALTH_WINDOW_S：失败率统计窗口秒数，默认 600（10 分钟）
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_DATA_PATH = Path(__file__).resolve().parent / "data" / "upstream_health.json"

# 熔断只作用于聚合通道（OR/TL/Requesty）；官方直连/硅基/降级不走熔断，避免误伤底仓
_AGGREGATORS = frozenset({"openrouter", "tokenlab", "requesty"})

_recording = True


def set_recording(v: bool) -> None:
    """评测/冒烟脚本可关闭记录，避免污染线上健康统计。"""
    global _recording
    _recording = bool(v)


def _cfg(key: str, default: Any) -> Any:
    v = (os.getenv(key) or "").strip()
    if not v:
        return default
    try:
        if isinstance(default, bool):
            return v.lower() not in ("0", "false", "no", "off")
        return int(v)
    except (TypeError, ValueError):
        return default


def _enabled() -> bool:
    return bool(_cfg("TOKEN_CIRCUIT_ENABLED", False))


def trip_n() -> int:
    return max(2, int(_cfg("TOKEN_CIRCUIT_TRIP_N", 8)))


def cool_s() -> int:
    return max(30, int(_cfg("TOKEN_CIRCUIT_COOL_S", 300)))


def window_s() -> int:
    return max(60, int(_cfg("TOKEN_UPSTREAM_HEALTH_WINDOW_S", 600)))


def _now() -> int:
    return int(time.time())


def _cst(ts: int) -> str:
    try:
        dt = datetime.fromtimestamp(int(ts), tz=timezone.utc).astimezone()
        return dt.strftime("%Y-%m-%d %H:%M:%S")
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
    return {"recs": {}, "circuit": {}}


def _save(data: dict[str, Any]) -> None:
    try:
        _DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        _DATA_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    except Exception:
        pass


_state: dict[str, Any] = _load()
_last_save = 0.0


def _persist() -> None:
    global _last_save
    now = time.time()
    if now - _last_save < 5.0:
        return
    _last_save = now
    _save(_state)


def record_attempt(provider: str, model: str, *, ok: bool, ms: int = 0, err: str = "") -> None:
    if not _recording:
        return
    pid = (provider or "").strip() or "unknown"
    mid = (model or "").strip() or "?"
    now = _now()
    recs = _state.setdefault("recs", {})
    st = recs.setdefault(
        pid, {"total": 0, "fail": 0, "consec": 0, "last_ts": 0, "models": {}}
    )
    st["total"] = int(st.get("total") or 0) + 1
    st["last_ts"] = now
    win = st.setdefault("window", {"start": now, "total": 0, "fail": 0})
    if now - int(win.get("start") or now) >= window_s():
        win["start"] = now
        win["total"] = 0
        win["fail"] = 0
    win["total"] = int(win.get("total") or 0) + 1
    if ok:
        st["consec"] = 0
    else:
        st["fail"] = int(st.get("fail") or 0) + 1
        win["fail"] = int(win.get("fail") or 0) + 1
        st["consec"] = int(st.get("consec") or 0) + 1
    m = st.setdefault("models", {}).setdefault(
        mid, {"total": 0, "fail": 0, "consec": 0, "last_ts": 0}
    )
    m["total"] = int(m.get("total") or 0) + 1
    m["last_ts"] = now
    if ok:
        m["consec"] = 0
    else:
        m["fail"] = int(m.get("fail") or 0) + 1
        m["consec"] = int(m.get("consec") or 0) + 1
    # 熔断触发（仅聚合通道；连续失败达阈值）
    if (not ok) and _enabled() and pid in _AGGREGATORS:
        consec = int(st.get("consec") or 0)
        circ = _state.setdefault("circuit", {}).get(pid)
        if consec >= trip_n() and (not circ or not circ.get("open")):
            _state.setdefault("circuit", {})[pid] = {
                "open": True,
                "since": now,
                "until": now + cool_s(),
                "reason": f"consecutive_fail_{consec}",
            }
    _persist()


def circuit_open(provider: str) -> bool:
    """返回 True 表示该聚合通道熔断冷却中，调用链应跳过（自动切走主通道）。"""
    if not _enabled():
        return False
    pid = (provider or "").strip()
    if pid not in _AGGREGATORS:
        return False
    st = _state.get("circuit", {}).get(pid)
    if not st or not st.get("open"):
        return False
    if _now() >= int(st.get("until") or 0):
        # 冷却到期自动恢复（下次失败会重新触发）
        st["open"] = False
        _persist()
        return False
    return True


def wrap(fn):
    """给非流式上游调用函数加健康记录（成功/异常都记，异常照常抛出）。"""
    import functools

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        provider = str(kwargs.get("provider") or "")
        model = str(kwargs.get("model") or "")
        t0 = time.time()
        try:
            out = fn(*args, **kwargs)
        except Exception as e:  # noqa: BLE001
            record_attempt(
                provider,
                model,
                ok=False,
                ms=int((time.time() - t0) * 1000),
                err=str(e)[:160],
            )
            raise
        record_attempt(provider, model, ok=True, ms=int((time.time() - t0) * 1000), err="")
        return out

    return wrapper


def snapshot() -> dict[str, Any]:
    recs: dict[str, Any] = {}
    for pid, st in (_state.get("recs") or {}).items():
        win = st.get("window") or {}
        w_total = int(win.get("total") or 0)
        w_fail = int(win.get("fail") or 0)
        recs[pid] = {
            "total": int(st.get("total") or 0),
            "fail": int(st.get("fail") or 0),
            "consec": int(st.get("consec") or 0),
            "window": {
                "start_cst": _cst(int(win.get("start") or 0)),
                "total": w_total,
                "fail": w_fail,
                "rate": round(w_fail / max(1, w_total), 3),
            },
            "models": {
                mid: {
                    "total": int(m.get("total") or 0),
                    "fail": int(m.get("fail") or 0),
                    "consec": int(m.get("consec") or 0),
                    "last_ts": int(m.get("last_ts") or 0),
                }
                for mid, m in (st.get("models") or {}).items()
            },
        }
    return {
        "ok": True,
        "recording": _recording,
        "circuit_enabled": _enabled(),
        "trip_n": trip_n(),
        "cool_s": cool_s(),
        "window_s": window_s(),
        "circuit": {
            pid: {
                "open": bool(s.get("open")),
                "since_cst": _cst(int(s.get("since") or 0)),
                "until_cst": _cst(int(s.get("until") or 0)),
                "reason": s.get("reason") or "",
            }
            for pid, s in (_state.get("circuit") or {}).items()
        },
        "recs": recs,
    }


def reset() -> None:
    """清空统计与熔断（运维用）。"""
    global _state
    _state = {"recs": {}, "circuit": {}}
    _save(_state)
