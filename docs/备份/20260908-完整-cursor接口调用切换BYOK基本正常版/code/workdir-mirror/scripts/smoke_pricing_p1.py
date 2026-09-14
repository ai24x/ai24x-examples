#!/usr/bin/env python3
"""Local smoke for pricing P1 acceptance (items 1–4 + static copy).

Usage (from repo root or anywhere):
  python scripts/smoke_pricing_p1.py
  python scripts/smoke_pricing_p1.py --base http://127.0.0.1:8000

Optional end-to-end (item 3 HTTP):
  set SMOKE_API_KEY=sk-...
  python scripts/smoke_pricing_p1.py
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "api"
WEB_DIR = ROOT / "web"


def _ok(msg: str) -> None:
    print(f"OK  {msg}")


def _fail(msg: str) -> None:
    print(f"FAIL {msg}")


def _http_json(url: str, *, method: str = "GET", headers: dict | None = None, body: dict | None = None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Accept", "application/json")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        return resp.status, json.loads(raw) if raw else {}


def check_plans(base: str) -> bool:
    try:
        status, data = _http_json(f"{base.rstrip('/')}/v1/billing/plans")
    except Exception as e:
        _fail(f"plans HTTP: {e}")
        return False
    if status != 200:
        _fail(f"plans status={status}")
        return False
    plans = {p.get("plan"): p for p in (data.get("plans") or [])}
    expect = {
        "token_pack_10k": (2.0, 1_000_000),
        "token_pack_100k": (20.0, 50_000_000),
        "token_pack_mid": (49.0, 140_000_000),
        "token_vip_month": (15.0, 0),
        "token_vip_month_50w": (99.0, 200_000_000),
    }
    ok = True
    for pid, (usd, tokens) in expect.items():
        p = plans.get(pid)
        if not p:
            _fail(f"plans missing {pid}")
            ok = False
            continue
        got_usd = float(p.get("price_usd") or 0)
        got_tok = int(p.get("credit_tokens") or 0)
        if abs(got_usd - usd) > 0.01 or got_tok != tokens:
            _fail(f"{pid} usd={got_usd} tokens={got_tok} expect {usd}/{tokens}")
            ok = False
        else:
            _ok(f"plans {pid}: ${got_usd:g} / {got_tok}")
    return ok


def check_vip_daily_logic() -> bool:
    sys.path.insert(0, str(API_DIR))
    from token_mvp_service import model_allows_vip_daily  # noqa: WPS433
    from model_warehouse import CATALOG  # noqa: WPS433

    cases = [
        ("flash", True),
        ("auto", True),
        ("shared", True),
        ("pro", False),
        ("ultra", False),
        ("vip-kimi", False),
        ("vip-gpt5", False),
    ]
    ok = True
    for model, expect in cases:
        got = bool(model_allows_vip_daily(model))
        if got != expect:
            _fail(f"model_allows_vip_daily({model!r})={got} expect={expect}")
            ok = False
        else:
            _ok(f"vip_daily allow {model}={got}")

    ref = float(os.getenv("TOKEN_FLASH_REF_USD_PER_M") or "0.35")
    kimi = next((c for c in CATALOG if c.get("id") == "vip-kimi"), None)
    if not kimi:
        _fail("catalog missing vip-kimi")
        return False
    mult = int(kimi.get("billing_mult") or 0)
    est = round(ref * mult, 2)
    if abs(ref - 0.35) > 1e-9 or mult != 39 or abs(est - 13.65) > 0.01:
        _fail(f"vip-picks est ref={ref} mult={mult} est={est} expect 0.35/39/13.65")
        ok = False
    else:
        _ok(f"vip-picks Kimi ~${est}/M (flash ${ref}/M × {mult})")

    # 中国 VIP 硅基映射 + 贴地 mult
    expect_sf = {
        "vip-kimi": "moonshotai/Kimi-K3",
        "vip-minimax": "MiniMaxAI/MiniMax-M2.5",
        "vip-qwen-max": "Qwen/Qwen3-235B-A22B-Instruct-2507",
        "vip-glm": "zai-org/GLM-5.1",
        "vip-ds-flash": "deepseek-ai/DeepSeek-V4-Flash",
    }
    for pid, sf in expect_sf.items():
        row = next((c for c in CATALOG if c.get("id") == pid), None)
        got = (row or {}).get("siliconflow_id")
        if got != sf:
            _fail(f"{pid} siliconflow_id={got!r} expect {sf!r}")
            ok = False
        else:
            _ok(f"{pid} siliconflow_id ok")
    glm = next((c for c in CATALOG if c.get("id") == "vip-glm"), {})
    gpt4o = next((c for c in CATALOG if c.get("id") == "vip-gpt4o"), {})
    if int(glm.get("billing_mult") or 0) != 10:
        _fail(f"vip-glm billing_mult={glm.get('billing_mult')} expect 10")
        ok = False
    else:
        _ok("vip-glm billing_mult=10")
    if int(gpt4o.get("billing_mult") or 0) != 27:
        _fail(f"vip-gpt4o billing_mult={gpt4o.get('billing_mult')} expect 27")
        ok = False
    else:
        _ok("vip-gpt4o billing_mult=27")
    mimo = next((c for c in CATALOG if c.get("id") == "vip-mimo"), {})
    if mimo.get("siliconflow_id"):
        _fail("vip-mimo should keep siliconflow_id=None (no stable SF twin)")
        ok = False
    else:
        _ok("vip-mimo no silicon twin (OR)")
    return ok


def check_static_copy() -> bool:
    ok = True
    console = (WEB_DIR / "js" / "console.js").read_text(encoding="utf-8")
    for needle in ("Flash $0.35/百万 · Pro $1.05/百万", "Flash $0.35/M · Pro $1.05/M"):
        if needle not in console:
            _fail(f"console.js missing {needle!r}")
            ok = False
        else:
            _ok(f"console.js has {needle!r}")
    vip = (WEB_DIR / "models" / "vip-picks.html").read_text(encoding="utf-8")
    if "REF_USD_PER_M = 0.35" not in vip:
        _fail("vip-picks.html REF_USD_PER_M != 0.35")
        ok = False
    else:
        _ok("vip-picks.html REF_USD_PER_M = 0.35")
    return ok


def check_api_key_e2e(base: str, api_key: str) -> bool:
    """Item 3 HTTP path when SMOKE_API_KEY is set (needs VIP-daily-only wallet to assert 402)."""
    url = f"{base.rstrip('/')}/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}"}
    ok = True
    for model in ("flash", "pro", "vip-kimi"):
        try:
            status, data = _http_json(
                url,
                method="POST",
                headers=headers,
                body={
                    "model": model,
                    "messages": [{"role": "user", "content": "ping"}],
                    "max_tokens": 8,
                },
            )
            code = ((data.get("error") or {}).get("code") if isinstance(data, dict) else None) or data.get(
                "code"
            )
            _ok(f"completions model={model} HTTP {status} code={code}")
            if model in ("pro", "vip-kimi") and status == 402:
                detail = data.get("detail") if isinstance(data.get("detail"), dict) else data
                err_code = None
                if isinstance(detail, dict):
                    err_code = (detail.get("error") or {}).get("code") or detail.get("code")
                if err_code == "prepaid_required":
                    _ok(f"{model} → 402 prepaid_required")
                else:
                    # FastAPI may wrap detail
                    raw = json.dumps(data, ensure_ascii=False)
                    if "prepaid_required" in raw:
                        _ok(f"{model} → 402 prepaid_required (in body)")
                    else:
                        _fail(f"{model} 402 but body missing prepaid_required: {raw[:240]}")
                        ok = False
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            if model in ("pro", "vip-kimi") and e.code == 402 and "prepaid_required" in body:
                _ok(f"{model} → 402 prepaid_required")
            elif model == "flash" and e.code in (401, 402, 429):
                _fail(f"flash unexpected HTTP {e.code}: {body[:240]}")
                ok = False
            else:
                _fail(f"completions model={model} HTTP {e.code}: {body[:240]}")
                ok = False
        except Exception as e:
            _fail(f"completions model={model}: {e}")
            ok = False
    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=os.getenv("SMOKE_BASE", "http://127.0.0.1:8000"))
    args = ap.parse_args()
    print(f"== smoke_pricing_p1 base={args.base}")
    results = [
        check_plans(args.base),
        check_vip_daily_logic(),
        check_static_copy(),
    ]
    key = (os.getenv("SMOKE_API_KEY") or "").strip()
    if key:
        print("-- SMOKE_API_KEY set: running completions e2e")
        results.append(check_api_key_e2e(args.base, key))
    else:
        print("SKIP completions e2e (set SMOKE_API_KEY for item-3 HTTP)")
    failed = not all(results)
    print("== RESULT", "FAIL" if failed else "PASS")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
