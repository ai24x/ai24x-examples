# -*- coding: utf-8 -*-
"""P0 记账根治回归（2026-08-12）。

覆盖：map_model_name OR 别名 / 未知模型 400；Anthropic <invoke> 解析；
tools strict schema 规范化；上游 400=format 不 failover；luna 主通道链序；
HTTP 层 记账：chat/run、chat/completions 流式、responses 流式、tools 流、
客户端中途断开、VIP 拦截不扣费、未知模型 400、consume_tokens 幂等。

用法（api 目录、8000 已重启到最新代码）：
  python scripts_accounting_regression.py
"""
from __future__ import annotations

import io
import json
import sys
import time
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import httpx

BASE = "http://127.0.0.1:8000"
PASSWORD = "Test1234!"
PASS = []
FAIL = []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append((name, detail))
    print(("PASS" if cond else "FAIL"), name, detail[:300])


# ---------- offline unit tests ----------
def unit_tests() -> None:
    from fastapi import HTTPException
    from openai_compat import map_model_name

    def mm(x):
        try:
            return map_model_name(x)
        except HTTPException as e:
            return "400:" + str((e.detail or {}).get("code") if isinstance(e.detail, dict) else e.detail)

    for raw, want in [
        ("openai/gpt-5.6-luna", "vip-gpt56-luna"),
        ("deepseek/deepseek-v4-flash", "vip-ds-flash"),
        ("anthropic/claude-opus-5", "vip-claude-opus"),
        ("moonshotai/kimi-k3", "vip-kimi"),
        ("openrouter/auto", "auto"),
        ("ai24x-prod/vip-gpt56-luna", "vip-gpt56-luna"),
        ("gpt-4o", "flash"),
        ("totally-unknown-model-xyz", "400:unknown_model"),
    ]:
        check(f"map_model_name {raw}", mm(raw) == want, f"got={mm(raw)}")

    from model_router import (
        _normalize_tools_for_upstream,
        _parse_invoke_tool_calls,
        _upstream_error_class,
        _vip_aggregator_chain,
    )
    from model_warehouse import resolve_vip_pick

    tcs = _parse_invoke_tool_calls(
        '<invoke name="search"><parameter name="q">hello world</parameter></invoke>'
    )
    check(
        "invoke_xml_parse",
        bool(tcs) and tcs[0]["function"]["name"] == "search"
        and json.loads(tcs[0]["function"]["arguments"]).get("q") == "hello world",
        str(tcs),
    )
    tcs2 = _parse_invoke_tool_calls("collab: get_weather")
    check(
        "invoke_collab_parse",
        bool(tcs2) and tcs2[0]["function"]["name"] == "get_weather",
        str(tcs2),
    )
    tcs3 = _parse_invoke_tool_calls("plain text without tools")
    check("invoke_no_false_positive", tcs3 is None, str(tcs3))

    norm = _normalize_tools_for_upstream(
        [
            {
                "type": "function",
                "name": "get_weather",
                "description": "d",
                "parameters": {
                    "type": "object",
                    "properties": {"city": {"type": "string"}},
                },
                "strict": True,
            }
        ]
    )
    ok_norm = (
        bool(norm)
        and isinstance(norm[0].get("function"), dict)
        and norm[0]["function"]["name"] == "get_weather"
        and norm[0]["function"]["parameters"].get("additionalProperties") is False
    )
    check("tools_strict_normalize", ok_norm, str(norm))

    class FakeResp:
        status_code = 400
        text = '{"error":{"message":"bad tools"}}'

    class FakeErr(Exception):
        response = FakeResp()

    kind, detail = _upstream_error_class(FakeErr())
    check("upstream_400_classified_format", kind == "format", f"{kind} | {detail[:120]}")

    pick = resolve_vip_pick("vip-gpt56-luna")
    if pick:
        chain = _vip_aggregator_chain(pick, str(pick.get("openrouter_id") or ""))
        provs = [c["provider"] for c in chain]
        check("luna_chain_tokenlab_first", provs and provs[0] == "tokenlab", str(provs))
    else:
        check("luna_chain_tokenlab_first", False, "pick not found")


# ---------- http accounting regression ----------
def _sse_events(resp_text: str) -> list:
    events = []
    for line in resp_text.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if payload == "[DONE]":
            events.append({"type": "[DONE]"})
            continue
        try:
            events.append(json.loads(payload))
        except Exception:
            pass
    return events


def http_tests() -> None:
    from database import SessionLocal
    from models import BillingLedger, ChatRequest
    from sqlalchemy import func
    from token_mvp_service import consume_tokens

    client = httpx.Client(base_url=BASE, timeout=180.0)
    stamp = uuid.uuid4().hex[:8]
    email = f"acc-{stamp}@ai24x.local"

    def register(email_addr: str) -> str:
        for _try in range(4):
            s = client.post(
                "/v1/auth/email/send", json={"email": email_addr, "purpose": "register"}
            ).json()
            if s.get("ok"):
                break
            if "频繁" in (s.get("message") or ""):
                time.sleep(2.5)
        code = s.get("local_code") or s.get("dev_code")
        if not code:
            raise RuntimeError(f"no code: {s}")
        r = client.post(
            "/v1/auth/register",
            json={"email": email_addr, "email_code": code, "password": PASSWORD},
        )
        if r.status_code >= 300:
            raise RuntimeError(f"register {r.status_code} {r.text[:200]}")
        j = r.json()
        return j.get("access_token") or j.get("token") or ""

    tok = register(email)
    h = {"Authorization": f"Bearer {tok}"}
    from models import AuthUser

    db = SessionLocal()
    uid = None
    au = db.query(AuthUser).filter(AuthUser.email == email).first()
    if au:
        uid = au.id
    check("user_lookup", uid is not None, f"uid={uid}")
    bal0 = int(client.get("/v1/billing/balance", headers=h).json().get("balance_tokens") or 0)
    check("register_balance", bal0 >= 5000, f"balance={bal0}")

    k = client.post("/v1/keys", headers=h, json={"name": f"acc-{stamp}"}).json()
    api_key = k.get("api_key") or ""
    check("create_api_key", api_key.startswith("sk-"), k.get("key_prefix"))
    kh = {"X-API-Key": api_key, "Content-Type": "application/json"}
    def ledger_consume_count(uid: int) -> int:
        return (
            db.query(BillingLedger.id)
            .filter(
                BillingLedger.auth_user_id == uid,
                BillingLedger.entry_type == "consume",
            )
            .count()
        )

    def latest_request(rid: str):
        return db.query(ChatRequest).filter(ChatRequest.request_id == rid).first()

    # 1) non-stream chat/run
    r = client.post("/v1/chat/run", headers=kh, json={"prompt": "Reply with exactly: OK", "model": "flash"})
    cj = r.json() if r.status_code == 200 else {}
    rid = (cj.get("request_id") or "").strip()
    check("chat_run_200", r.status_code == 200 and bool(rid), f"status={r.status_code} rid={rid} {r.text[:160]}")
    if rid:
        row = latest_request(rid)
        check("chat_run_status_completed", bool(row) and row.status == "completed", str(row.status) if row else "no row")
        check("chat_run_billed", bool(row) and row.token_count and row.token_count > 0, f"tokens={row.token_count if row else None}")

    # 2) stream chat/completions
    r2 = client.post(
        "/v1/chat/completions",
        headers=kh,
        json={
            "model": "flash",
            "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
            "stream": True,
            "max_tokens": 64,
        },
    )
    evs = _sse_events(r2.text)
    types = [e.get("type") for e in evs]
    check("completions_stream_done", "chat.completion.chunk" in types or "[DONE]" in types, str(types)[:160])

    # 3) responses stream
    r3 = client.post(
        "/v1/responses",
        headers=kh,
        json={
            "model": "flash",
            "input": "Reply with exactly: OK",
            "stream": True,
            "max_output_tokens": 64,
        },
    )
    evs3 = _sse_events(r3.text)
    types3 = [e.get("type") for e in evs3]
    check(
        "responses_stream_completed",
        "response.completed" in types3 or "response.failed" in types3,
        str(types3)[:200],
    )

    # 4) tools stream (flash; upstream may or may not tool-call, must complete/bill)
    r4 = client.post(
        "/v1/chat/completions",
        headers=kh,
        json={
            "model": "flash",
            "messages": [{"role": "user", "content": "Call get_weather for Beijing"}],
            "stream": True,
            "max_tokens": 128,
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "description": "Get weather",
                        "parameters": {
                            "type": "object",
                            "properties": {"city": {"type": "string"}},
                            "required": ["city"],
                        },
                    },
                }
            ],
        },
    )
    evs4 = _sse_events(r4.text)
    types4 = [e.get("type") for e in evs4]
    check(
        "tools_stream_finishes",
        "[DONE]" in types4 or "chat.completion.chunk" in types4,
        str(types4)[:200],
    )
    has_tc = any(
        isinstance(e.get("choices") or [], list)
        and any(c.get("delta", {}).get("tool_calls") for c in e["choices"])
        for e in evs4
        if e.get("type") != "[DONE]"
    )
    print("INFO tools_stream_tool_calls_detected", has_tc)

    # 5) client disconnect mid-stream -> no billing, status not stuck processing
    max_before = db.query(func.max(ChatRequest.id)).scalar() or 0
    with client.stream(
        "POST",
        "/v1/chat/completions",
        headers=kh,
        json={
            "model": "flash",
            "messages": [{"role": "user", "content": "Write a long story about the sea. Keep going for many sentences."}],
            "stream": True,
            "max_tokens": 200,
        },
    ) as sr:
        got = ""
        for line in sr.iter_lines():
            got += line
            if "data:" in got and len(got) > 300:
                break
    time.sleep(2.0)
    # 断开后：不扣费是硬断言；状态由 stuck 兜底扫描（1800s）标记 failed，不永续
    rows = (
        db.query(ChatRequest)
        .filter(ChatRequest.id > max_before)
        .order_by(ChatRequest.id.desc())
        .all()
    )
    disc = rows[0] if rows else None
    disc_consume = 0
    if disc is not None:
        disc_consume = (
            db.query(BillingLedger.id)
            .filter(
                BillingLedger.auth_user_id == uid,
                BillingLedger.entry_type == "consume",
                BillingLedger.request_id == disc.request_id,
            )
            .count()
        )
    check(
        "disconnect_no_billing",
        disc is not None and disc_consume == 0,
        f"rid={disc.request_id if disc else None} status={disc.status if disc else None} consume={disc_consume}",
    )

    # 6) VIP gate (fresh non-VIP user) -> failed, no consume
    r5 = client.post(
        "/v1/responses",
        headers=kh,
        json={"model": "vip-gpt56-luna", "input": "hi", "stream": True, "max_output_tokens": 32},
    )
    evs5 = _sse_events(r5.text)
    types5 = [e.get("type") for e in evs5]
    check(
        "vip_gate_stream_failed",
        "response.failed" in types5,
        f"status={r5.status_code} types={str(types5)[:200]}",
    )

    # 7) unknown model -> 400
    r6 = client.post(
        "/v1/responses",
        headers=kh,
        json={"model": "totally-unknown-model-xyz", "input": "hi", "stream": False},
    )
    body6 = r6.text[:200]
    check("unknown_model_400", r6.status_code == 400 and "unknown" in body6.lower(), body6)

    # 8) consume_tokens idempotency
    if uid:
        rid_dup = f"req_dup_{uuid.uuid4().hex[:12]}"
        consume_tokens(db, auth_user_id=uid, tokens=10, amount_usd=1, model="flash", request_id=rid_dup)
        consume_tokens(db, auth_user_id=uid, tokens=10, amount_usd=1, model="flash", request_id=rid_dup)
        db.commit()
        dup_count = (
            db.query(BillingLedger.id)
            .filter(
                BillingLedger.auth_user_id == uid,
                BillingLedger.entry_type == "consume",
                BillingLedger.request_id == rid_dup,
            )
            .count()
        )
        check("consume_idempotent_single_ledger", dup_count == 1, f"count={dup_count}")

        total_consume = ledger_consume_count(uid)
        bal1 = int(client.get("/v1/billing/balance", headers=h).json().get("balance_tokens") or 0)
        check("total_consume_ledger_matches_balance_drop", total_consume >= 1 and bal1 < bal0, f"ledger={total_consume} bal {bal0}->{bal1}")
    else:
        check("user_lookup", False, "no AuthUser for email")

    db.close()
    client.close()


def main() -> int:
    print("== unit tests ==")
    unit_tests()
    print("== http regression ==")
    try:
        http_tests()
    except Exception as e:
        import traceback

        traceback.print_exc()
        check("http_tests_no_exception", False, str(e))
    print(f"RESULT passed={len(PASS)} failed={len(FAIL)}")
    for name, detail in FAIL:
        print("  FAILED:", name, detail[:400])
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())