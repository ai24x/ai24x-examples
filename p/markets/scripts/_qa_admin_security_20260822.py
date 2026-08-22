"""AI24X 运营后台 · 管理安全 + markets 产品网关 QA（2026-08-22）。

前置：本地 core(8000) 与 markets(18012) 已带 ADMIN_API_KEY / MARKETS_FULFILL_SECRET 重启；
密钥从 %TEMP%\\ai24x_admin_qa.env 读取（本地 QA 专用，不入库）。

覆盖：
1. markets /api/admin/* 直连：无密钥 403 / 错密钥 403 / 正确密钥 200（回环）
2. core 网关 /v1/admin/products/markets/*：无密钥 403 / 仅 SMS 密钥 403（配独立管理密钥后不再放行）
3. 正确管理密钥 → summary/subs/orders/plans 200 且数据形状正确
4. 非法 kind 404（防开放代理）
5. 管理接口限速：连续请求超过阈值返回 429
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx

CORE = "http://127.0.0.1:8000"
MK = "http://127.0.0.1:18012"


def load_keys() -> tuple[str, str]:
    env_path = Path(os.environ.get("TEMP", ".")) / "ai24x_admin_qa.env"
    admin = ""
    secret = ""
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("ADMIN_API_KEY="):
            admin = line.split("=", 1)[1].strip()
        elif line.startswith("MARKETS_FULFILL_SECRET="):
            secret = line.split("=", 1)[1].strip()
    assert admin and secret, "keys missing from QA env file"
    return admin, secret


def main() -> int:
    admin_key, mk_secret = load_keys()
    checks: list[tuple[str, bool, str]] = []

    def check(name: str, cond: bool, detail: str = "") -> None:
        checks.append((name, cond, detail))
        print(("PASS" if cond else "FAIL") + " | " + name + ((" | " + detail) if detail else ""))

    # 1) markets 直连
    r = httpx.get(MK + "/api/admin/summary", timeout=10)
    check("markets admin no-secret -> 403", r.status_code == 403, f"status={r.status_code}")
    r = httpx.get(MK + "/api/admin/summary", headers={"X-Markets-Secret": "wrong"}, timeout=10)
    check("markets admin wrong-secret -> 403", r.status_code == 403, f"status={r.status_code}")
    h = {"X-Markets-Secret": mk_secret}
    r = httpx.get(MK + "/api/admin/summary", headers=h, timeout=10)
    ok = r.status_code == 200 and r.json().get("code") == 0 and "data" in r.json()
    check("markets admin correct-secret -> 200 code=0", ok, f"status={r.status_code}")

    # 2) core 网关鉴权
    r = httpx.get(CORE + "/v1/admin/products/markets/summary", timeout=10)
    check("core gateway no-key -> 403", r.status_code == 403, f"status={r.status_code}")
    r = httpx.get(
        CORE + "/v1/admin/products/markets/summary",
        headers={"X-SMS-Internal-Key": "iamlei888"},
        timeout=10,
    )
    check(
        "core gateway sms-key-only -> 403 (独立管理密钥已配)",
        r.status_code == 403,
        f"status={r.status_code}",
    )
    hc = {"X-Admin-Key": admin_key, "X-SMS-Internal-Key": admin_key}
    r = httpx.get(CORE + "/v1/admin/products/markets/summary", headers=hc, timeout=15)
    ok = r.status_code == 200 and r.json().get("code") == 0 and "data" in r.json()
    check("core gateway admin-key -> 200 code=0", ok, f"status={r.status_code}")

    # 3) 四个子接口数据形状
    for kind, key_path in (
        ("summary", "data"),
        ("subs", "data.rows"),
        ("orders", "data.rows"),
        ("plans", "data.plans"),
    ):
        r = httpx.get(CORE + f"/v1/admin/products/markets/{kind}", headers=hc, timeout=15)
        node = r.json().get("data", {}) if r.status_code == 200 else {}
        good = r.status_code == 200
        for seg in key_path.split(".")[1:]:
            node = (node or {}).get(seg, None) if isinstance(node, dict) else None
            good = good and node is not None
        check(f"gateway {kind} shape ok", good, f"status={r.status_code}")

    # 过滤参数透传
    r = httpx.get(CORE + "/v1/admin/products/markets/subs?plan=monthly&limit=5", headers=hc, timeout=15)
    rows = r.json().get("data", {}).get("rows", []) if r.status_code == 200 else []
    check(
        "gateway subs plan=monthly filter",
        r.status_code == 200 and rows and all(x.get("plan") == "monthly" for x in rows),
        f"rows={len(rows)}",
    )

    # 4) 非法 kind 防开放代理
    r = httpx.get(CORE + "/v1/admin/products/markets/delete", headers=hc, timeout=10)
    check("gateway unknown kind -> 404", r.status_code == 404, f"status={r.status_code}")
    # 越权跳转：即使路径归一化，kind 白名单仍挡住非 markets 子接口
    r = httpx.get(CORE + "/v1/admin/products/markets/summary/../../admin/token/wallet", headers=hc, timeout=10)
    check("gateway path escape -> 404", r.status_code == 404, f"status={r.status_code}")
    r = httpx.get(CORE + "/v1/admin/products/markets/summary/../../billing/plans", headers=hc, timeout=10)
    check("gateway path escape billing -> 404", r.status_code == 404, f"status={r.status_code}")

    # 5) 限速（进程内每 IP 每分钟阈值 60；发 66 次应出现 429）
    got_429 = False
    last = 0
    for _ in range(66):
        r = httpx.get(CORE + "/v1/admin/products/markets/plans", headers=hc, timeout=10)
        last = r.status_code
        if r.status_code == 429:
            got_429 = True
            break
    check("core admin rate limit -> 429", got_429, f"last_status={last}")

    failed = [c for c in checks if not c[1]]
    print("---")
    print(f"TOTAL={len(checks)} PASS={len(checks) - len(failed)} FAIL={len(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
