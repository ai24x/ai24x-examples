#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Token 平台自主烟测（本机 core-8000）。

用法（在 api/ 目录）:
  python scripts_token_smoke.py

退出码 0=全过；非 0=有失败。结果写入 _smoke_last.json
"""
from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8000"
OUT = Path(__file__).resolve().parent / "_smoke_last.json"
PASSWORD = "Test1234!"


def _ok(name: str, cond: bool, detail: str = "") -> dict:
    return {"name": name, "ok": bool(cond), "detail": detail}


def _write(rows: list[dict]) -> None:
    OUT.write_text(
        json.dumps({"ts": time.time(), "rows": rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> int:
    rows: list[dict] = []
    client = httpx.Client(base_url=BASE, timeout=60.0)
    stamp = uuid.uuid4().hex[:8]
    email_a = f"smoke-a-{stamp}@ai24x.local"
    email_b = f"smoke-b-{stamp}@ai24x.local"

    # —— 基础就绪 ——
    try:
        m = client.get("/v1/models").json()
        up = m.get("upstream") or {}
        rows.append(
            _ok(
                "models_live",
                up.get("mode") == "live" and bool(up.get("l1_ready") or up.get("direct_ready") or up.get("openrouter_ready")),
                json.dumps(up, ensure_ascii=False),
            )
        )
        rows.append(_ok("brand_flash", bool((m.get("brand") or {}).get("flash")), str(m.get("brand"))))
    except Exception as e:
        rows.append(_ok("models_live", False, str(e)))

    try:
        h = client.get("/health").json()
        rows.append(
            _ok(
                "health_upstream",
                h.get("status") == "healthy" and bool(h.get("upstream_mode")),
                f"mode={h.get('upstream_mode')} stamp={h.get('build_stamp')}",
            )
        )
    except Exception as e:
        rows.append(_ok("health_upstream", False, str(e)))

    try:
        es = client.get("/v1/auth/email/status").json()
        rows.append(_ok("email_status_api", es.get("ok") is True, str(es)))
        rows.append(_ok("email_smtp_configured", bool(es.get("smtp_configured")), str(es.get("smtp_host"))))
    except Exception as e:
        rows.append(_ok("email_status_api", False, str(e)))

    try:
        ps = client.get("/v1/billing/pay/status").json()
        rows.append(
            _ok(
                "pay_status_default_off",
                ps.get("ok") is True and ps.get("token_pay_enabled") is False,
                f"enabled={ps.get('token_pay_enabled')} mock={ps.get('token_pay_mock_enabled')}",
            )
        )
    except Exception as e:
        rows.append(_ok("pay_status_default_off", False, str(e)))

    def register(email: str, invite: str | None = None) -> tuple[bool, str, str]:
        s = client.post("/v1/auth/email/send", json={"email": email, "purpose": "register"}).json()
        if not s.get("ok"):
            return False, "", str(s)[:240]
        code = s.get("local_code") or s.get("dev_code")
        if not code:
            return False, "", f"no local_code channel={s.get('channel')} msg={s.get('message')}"
        payload = {"email": email, "email_code": code, "password": PASSWORD}
        if invite:
            payload["invite_code"] = invite
        r = client.post("/v1/auth/register", json=payload)
        if r.status_code >= 300:
            return False, "", r.text[:240]
        j = r.json()
        tok = j.get("access_token") or j.get("token") or ""
        return True, tok, email

    # —— 注册 A ——
    ok, tok_a, detail = register(email_a)
    rows.append(_ok("register_a", ok, detail))
    if not ok:
        _write(rows)
        print(json.dumps({"passed": 0, "failed": len(rows), "rows": rows}, ensure_ascii=False, indent=2))
        return 1
    h_a = {"Authorization": f"Bearer {tok_a}"}

    # —— 邀请码 / 余额 ——
    invite = ""
    try:
        invite = (client.get("/v1/referrals/code", headers=h_a).json().get("code") or "").strip()
        rows.append(_ok("invite_code", bool(invite), invite))
    except Exception as e:
        rows.append(_ok("invite_code", False, str(e)))

    bal_a0 = int(client.get("/v1/billing/balance", headers=h_a).json().get("balance_tokens") or 0)
    rows.append(_ok("balance_a_initial", bal_a0 >= 5000, f"balance={bal_a0}"))

    # —— Key + chat ——
    api_key = None
    try:
        k = client.post("/v1/keys", headers=h_a, json={"name": f"smoke-{stamp}"}).json()
        api_key = k.get("api_key")
        rows.append(_ok("create_key", bool(api_key and str(api_key).startswith("sk-")), k.get("key_prefix")))
    except Exception as e:
        rows.append(_ok("create_key", False, str(e)))

    if api_key:
        chat = client.post(
            "/v1/chat/run",
            headers={"X-API-Key": api_key},
            json={"prompt": "Reply with exactly: SMOKE_OK", "model": "flash"},
        )
        cj = chat.json() if chat.headers.get("content-type", "").startswith("application/json") else {}
        rows.append(
            _ok(
                "chat_deepseek",
                chat.status_code == 200 and cj.get("provider") == "deepseek",
                f"status={chat.status_code} provider={cj.get('provider')} model={cj.get('model')} tokens={cj.get('token_count')} resp={(cj.get('response') or '')[:60]}",
            )
        )
        bal_a0 = int(client.get("/v1/billing/balance", headers=h_a).json().get("balance_tokens") or 0)
    else:
        rows.append(_ok("chat_deepseek", False, "no api key"))

    # —— mock 支付 ——
    try:
        order = client.post(
            "/v1/billing/wechat/native",
            headers=h_a,
            json={"plan": "token_pack_10k"},
        ).json()
        otn = order.get("out_trade_no")
        if not otn:
            rows.append(_ok("mock_pay_fulfill", False, str(order)[:240]))
        else:
            ful = client.post(
                "/v1/billing/orders/mock_fulfill",
                headers=h_a,
                json={"out_trade_no": otn},
            )
            bal_a1 = int(client.get("/v1/billing/balance", headers=h_a).json().get("balance_tokens") or 0)
            rows.append(
                _ok(
                    "mock_pay_fulfill",
                    ful.status_code == 200 and bal_a1 >= bal_a0 + 10000,
                    f"order={otn} bal {bal_a0}->{bal_a1}",
                )
            )
            bal_a0 = bal_a1
    except Exception as e:
        rows.append(_ok("mock_pay_fulfill", False, str(e)))

    # —— 邀请注册双方奖励 ——
    if invite:
        bal_before_invite = int(client.get("/v1/billing/balance", headers=h_a).json().get("balance_tokens") or 0)
        ok_b, tok_b, detail_b = register(email_b, invite=invite)
        if not ok_b:
            rows.append(_ok("invite_register_bonus", False, detail_b))
        else:
            h_b = {"Authorization": f"Bearer {tok_b}"}
            bal_b = int(client.get("/v1/billing/balance", headers=h_b).json().get("balance_tokens") or 0)
            bal_a_after = int(client.get("/v1/billing/balance", headers=h_a).json().get("balance_tokens") or 0)
            rows.append(
                _ok(
                    "invite_register_bonus",
                    bal_a_after >= bal_before_invite + 5000 and bal_b >= 10000,
                    f"A {bal_before_invite}->{bal_a_after}; B={bal_b}",
                )
            )
    else:
        rows.append(_ok("invite_register_bonus", False, "no invite code"))

    # —— 日报 / 限额常量 ——
    try:
        from scripts_token_daily_report import build_report
        from database import SessionLocal

        db = SessionLocal()
        try:
            rep = build_report(db)
            rows.append(_ok("daily_report", "chat_requests" in rep, json.dumps(rep, ensure_ascii=False)[:180]))
        finally:
            db.close()
    except Exception as e:
        rows.append(_ok("daily_report", False, str(e)))

    try:
        from token_mvp_service import GATEWAY_FREE_DAILY_REQ, REFERRAL_REGISTER_BONUS_TOKENS
        from referral_abuse import allow_register_invite_bonus

        rows.append(_ok("free_daily_limit_100", GATEWAY_FREE_DAILY_REQ == 100, str(GATEWAY_FREE_DAILY_REQ)))
        rows.append(
            _ok(
                "invite_bonus_const_5000",
                REFERRAL_REGISTER_BONUS_TOKENS == 5000,
                str(REFERRAL_REGISTER_BONUS_TOKENS),
            )
        )
        # 进程内反作弊：同 IP 超过日帽应拒绝（不经过 HTTP，仅校验模块）
        abuse_ok = True
        reason = ""
        for i in range(10):
            allowed, reason = allow_register_invite_bonus(referrer_id=900000 + i, client_ip="203.0.113.9")
            if not allowed:
                abuse_ok = reason == "ip_day_cap" and i >= 8
                break
        else:
            abuse_ok = False
            reason = "never_capped"
        rows.append(_ok("invite_abuse_ip_cap", abuse_ok, f"reason={reason}"))
    except Exception as e:
        rows.append(_ok("free_daily_limit_100", False, str(e)))

    # —— a1 回归探活 ——
    try:
        a1 = httpx.get("http://127.0.0.1:18001/", timeout=10.0)
        rows.append(_ok("a1_web_alive", a1.status_code == 200, f"status={a1.status_code}"))
    except Exception as e:
        rows.append(_ok("a1_web_alive", False, str(e)))

    client.close()
    _write(rows)
    failed = [r for r in rows if not r["ok"]]
    summary = {
        "passed": len(rows) - len(failed),
        "failed": len(failed),
        "failed_names": [r["name"] for r in failed],
        "rows": rows,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
