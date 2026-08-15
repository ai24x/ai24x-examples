#!/usr/bin/env python3
"""
上游通道余额监控（2026-08-15 新增）。

职责：逐通道调用官方余额接口，返回结构化余额快照，供 ops_alert 巡检告警。

通道支持（currency=USD 用美元阈值，CNY 用人民币阈值）：
  - deepseek          GET /user/balance                          (CNY)
  - openrouter        GET /api/v1/key  （usage/limit，free 档无余额）(USD)
  - siliconflow_cn    GET https://api.siliconflow.cn/v1/user/info (CNY，余额字段已停用→人工台账)
  - siliconflow_com   GET https://api.siliconflow.com/v1/user/info (USD，totalBalance 真实)
  - siliconflow_free  同 .com 账号（免费通道 key，alias 不单独告警）(USD)
  - tokenlab          GET /v1/management/balance（需 mt- 管理 key，否则不可查）(USD)
  - mimo              官方 API 无余额接口（需控制台 cookie）→ 跳过并标注
  - requesty          GET https://api-v2.requesty.ai/v1/manage/apikey/self（monthly_limit/spend，限 0=未设上限）
  - quickrouter       无 API 余额接口（/balance 是控制台网页）→ 人工台账

纪律：
  - 余额查询频率低（巡检 15 分钟一次即可），失败静默降级、不重试轰炸
  - 日志/告警只显示通道名 + 数值，绝不输出 key
"""
from __future__ import annotations

import json
from typing import Any, Optional

import httpx

from llm_keys import get_key

_TIMEOUT = 8.0


def _hdr(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


def _get_json(url: str, key: str, *, headers: Optional[dict[str, str]] = None) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    """GET + JSON 解析；返回 (data, error)。"""
    try:
        h = dict(headers or _hdr(key))
        h.setdefault("Authorization", f"Bearer {key}")
        h.setdefault("Accept", "application/json")
        h.setdefault("User-Agent", "Mozilla/5.0 (AI24X balance monitor)")
        r = httpx.get(url, headers=h, timeout=_TIMEOUT, follow_redirects=False)
    except Exception as e:
        return None, f"request fail: {e.__class__.__name__}"
    if r.status_code >= 400:
        body = r.text[:200].replace("\n", " ")
        return None, f"HTTP {r.status_code}: {body}"
    try:
        return r.json(), None
    except Exception as e:
        return None, f"bad json: {e.__class__.__name__}: {r.text[:120]}"


def _num(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        return float(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _fetch_deepseek(key: str) -> dict[str, Any]:
    data, err = _get_json("https://api.deepseek.com/user/balance", key)
    if err:
        return {"ok": False, "error": err}
    total: Optional[float] = None
    for info in data.get("balance_infos") or []:
        if str(info.get("currency") or "").upper() == "CNY":
            total = _num(info.get("total_balance"))
            break
    if total is None:
        total = _num(data.get("total_balance"))
    return {"ok": total is not None, "balance": total, "currency": "CNY", "raw_note": json.dumps(data, ensure_ascii=False)[:120]}


def _fetch_openrouter(key: str) -> dict[str, Any]:
    data, err = _get_json("https://openrouter.ai/api/v1/key", key)
    if err:
        return {"ok": False, "error": err}
    d = data.get("data") or {}
    usage = _num(d.get("usage"))
    limit = _num(d.get("limit"))
    is_free = bool(d.get("is_free_tier"))
    if is_free or limit is None:
        return {
            "ok": True,
            "balance": None,
            "currency": "USD",
            "unmetered": True,
            "raw_note": f"free_tier={is_free} limit={limit} usage={usage}",
        }
    return {
        "ok": True,
        "balance": max(0.0, limit - (usage or 0.0)),
        "currency": "USD",
        "raw_note": f"limit={limit} usage={usage}",
    }


def _fetch_siliconflow(key: str, endpoint: str, currency: str, title: str) -> dict[str, Any]:
    data, err = _get_json(f"{endpoint}/v1/user/info", key)
    if err:
        return {"ok": False, "error": err}
    d = data.get("data") if isinstance(data, dict) and isinstance(data.get("data"), dict) else data
    total = _num(d.get("totalBalance"))
    charge = _num(d.get("chargeBalance"))
    if total is None:
        total = _num(d.get("balance"))
    if total is None:
        total = _num(data.get("totalBalance"))
    return {
        "ok": total is not None,
        "balance": total,
        "currency": currency,
        "title": title,
        "charge_balance": charge,
        "raw_note": json.dumps({k: v for k, v in (d or {}).items() if k != "email"}, ensure_ascii=False)[:160],
    }


def _fetch_tokenlab(key: str) -> dict[str, Any]:
    """TokenLab 管理余额接口：需要 mt- 管理 token（普通 API key 会 401）。"""
    data, err = _get_json("https://api.tokenlab.sh/v1/management/balance", key)
    if err:
        return {"ok": False, "error": err}
    bal = _num(data.get("balance"))
    if bal is None:
        bal = _num(data.get("total"))
    return {"ok": bal is not None, "balance": bal, "currency": "USD", "raw_note": json.dumps(data, ensure_ascii=False)[:120]}


def _fetch_requesty(key: str) -> dict[str, Any]:
    """Requesty 无账户余额 API；用 key 自身的月额度/已用额度近似监控。
    monthly_limit=0/空 = 未设上限（不告警），>0 时剩余 = limit - spend。"""
    data, err = _get_json("https://api-v2.requesty.ai/v1/manage/apikey/self", key)
    if err:
        return {"ok": False, "error": err}
    limit = _num(data.get("monthly_limit"))
    spend = _num(data.get("monthly_spend")) or 0.0
    if not limit or limit <= 0:
        return {
            "ok": True,
            "balance": None,
            "currency": "USD",
            "unmetered": True,
            "raw_note": f"monthly_limit={limit} spend={spend}（未设月上限，余额走控制台）",
        }
    return {
        "ok": True,
        "balance": max(0.0, limit - spend),
        "currency": "USD",
        "raw_note": f"monthly_limit={limit} spend={spend}",
    }


# 通道 id → 采集器；只列已配 key 且需要监控的通道
def _channel_defs() -> list[dict[str, Any]]:
    return [
        {
            "id": "deepseek",
            "title": "DeepSeek 官方",
            "currency": "CNY",
            "key_env": "DEEPSEEK_API_KEY",
            "fetch": lambda k: _fetch_deepseek(k),
        },
        {
            "id": "openrouter",
            "title": "OpenRouter 主",
            "currency": "USD",
            "key_env": "OPENROUTER_API_KEY",
            "fetch": lambda k: _fetch_openrouter(k),
        },
        {
            "id": "openrouter_free",
            "title": "OpenRouter 免费通道",
            "currency": "USD",
            "key_env": "OPENROUTER_API_KEY_FREE",
            "fetch": lambda k: _fetch_openrouter(k),
        },
        {
            "id": "siliconflow_cn",
            "title": "硅基 .cn",
            "currency": "CNY",
            "key_env": "SILICONFLOW_API_KEY",
            "fetch": lambda k: {**_fetch_siliconflow(k, "https://api.siliconflow.cn", "CNY", "硅基 .cn"), "deprecated": True},
        },
        {
            "id": "siliconflow_com",
            "title": "硅基国际 .com",
            "currency": "USD",
            "key_env": "SILICONFLOW_COM_API_KEY",
            "fetch": lambda k: _fetch_siliconflow(k, "https://api.siliconflow.com", "USD", "硅基国际 .com"),
        },
        {
            "id": "siliconflow_free",
            "title": "硅基免费通道",
            "currency": "USD",
            "key_env": "SILICONFLOW_API_KEY_FREE",
            "fetch": lambda k: {
                **_fetch_siliconflow(k, "https://api.siliconflow.com", "USD", "硅基免费通道"),
                "alias_of": "siliconflow_com",
                "skip_alert": True,  # 与 .com 同一账号，以 siliconflow_com 为准，避免重复告警
            },
        },
        {
            "id": "tokenlab",
            "title": "TokenLab",
            "currency": "USD",
            "key_env": "TOKENLAB_MANAGEMENT_API_KEY",
            "fetch": lambda k: (
                _fetch_tokenlab(k)
                if k
                else {
                    "ok": False,
                    "unavailable": True,
                    "error": "缺 TOKENLAB_MANAGEMENT_API_KEY（mt- 管理 key，需在 TokenLab 控制台生成）",
                }
            ),
        },
        {
            "id": "mimo",
            "title": "小米 MiMo 官方直连",
            "currency": "USD",
            "key_env": "MIMO_API_KEY",
            "fetch": lambda k: {"ok": False, "unavailable": True, "error": "官方 API 无余额接口（需控制台 cookie），走人工台账"},
        },
        {
            "id": "mimo_free",
            "title": "小米 MiMo 免费通道",
            "currency": "USD",
            "key_env": "MIMO_API_KEY_FREE",
            "fetch": lambda k: {"ok": False, "unavailable": True, "error": "官方 API 无余额接口，走人工台账"},
        },
        {
            "id": "requesty",
            "title": "Requesty",
            "currency": "USD",
            "key_env": "REQUESTY_API_KEY",
            "fetch": lambda k: _fetch_requesty(k),
        },
        {
            "id": "quickrouter",
            "title": "QuickRouter",
            "currency": "USD",
            "key_env": "QUICKROUTER_API_KEY",
            "fetch": lambda k: {"ok": False, "unavailable": True, "error": "无 API 余额接口（/balance 为控制台网页），走人工台账"},
        },
    ]


def snapshot() -> dict[str, Any]:
    """全通道余额快照。失败/无接口的通道不炸、标注原因。"""
    rows: list[dict[str, Any]] = []
    for c in _channel_defs():
        key = (get_key(c["key_env"], "") or "").strip()
        if c.get("key_env") == "TOKENLAB_MANAGEMENT_API_KEY":
            # 管理 key 不一定在常规 catalog：环境直读优先，再回退 get_key
            import os

            mgmt = (os.getenv("TOKENLAB_MANAGEMENT_API_KEY") or "").strip()
            key = mgmt or key
        if not key:
            rows.append(
                {
                    "id": c["id"],
                    "title": c["title"],
                    "currency": c["currency"],
                    "balance": None,
                    "ok": False,
                    "error": (
                        "缺 TOKENLAB_MANAGEMENT_API_KEY（mt- 管理 key，需在 TokenLab 控制台生成）"
                        if c.get("key_env") == "TOKENLAB_MANAGEMENT_API_KEY"
                        else "no key"
                    ),
                    "unavailable": c.get("key_env") == "TOKENLAB_MANAGEMENT_API_KEY",
                }
            )
            continue
        try:
            r = c["fetch"](key)
        except Exception as e:
            r = {"ok": False, "error": f"unexpected: {e.__class__.__name__}: {str(e)[:100]}"}
        r.setdefault("title", c["title"])
        r.setdefault("currency", c["currency"])
        r.setdefault("id", c["id"])
        rows.append(r)
    return {"ok": True, "checked_at": __import__("datetime").datetime.now(__import__("datetime").timezone(__import__("datetime").timedelta(hours=8))).isoformat(), "rows": rows}


if __name__ == "__main__":
    print(json.dumps(snapshot(), ensure_ascii=False, indent=2, default=str))
