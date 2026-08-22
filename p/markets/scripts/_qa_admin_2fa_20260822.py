"""AI24X 运营后台 · 双因素登录 QA（2026-08-22）。

覆盖两种模式：
- 生产模式（ADMIN_REQUIRE_SMS=1）：管理接口必须「密钥 + 管理员手机验证码会话」双通过；
  单凭密钥 / 单凭短信内部密钥 / 单凭验证码均 403；短信通道先验密钥。
- 本地模式（默认关闭）：ADMIN_API_KEY 或 SMS_INTERNAL_KEY 均可登录；短信通道 503。

短信发送用 monkeypatch 捕获验证码，不依赖真实短信通道。
运行：python p/markets/scripts/_qa_admin_2fa_20260822.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# 与真实服务一致：以 api/ 为 cwd 加载 api/.env（否则 DATABASE_URL 落到默认值）
os.chdir(str(Path(__file__).resolve().parents[3] / "api"))

# 本地 QA 专用密钥（不入库）；未配置 ADMIN_PHONE 时用默认本地测试号
_qa_env = Path(os.environ.get("TEMP", ".")) / "ai24x_admin_qa.env"
if _qa_env.is_file():
    for line in _qa_env.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())
os.environ.setdefault("ADMIN_PHONE", "18958992226")

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "api"))

from fastapi.testclient import TestClient  # noqa: E402

import main as app_main  # noqa: E402
from config import settings  # noqa: E402


def main() -> int:
    admin_key = (settings.admin_api_key or "").strip()
    sms_key = (settings.sms_internal_key or "").strip()
    phone = (settings.admin_phone or "").strip()
    assert admin_key, "ADMIN_API_KEY missing"
    assert phone, "ADMIN_PHONE missing"

    checks: list[tuple[str, bool, str]] = []

    def check(name: str, cond: bool, detail: str = "") -> None:
        checks.append((name, cond, detail))
        print(("PASS" if cond else "FAIL") + " | " + name + ((" | " + detail) if detail else ""))

    captured: dict[str, str] = {}

    async def fake_send_sms_106(endpoint=None, account=None, password=None, mobile=None, content=None, sign_name=None):
        # 从短信模板里提取 6 位验证码
        import re

        m = re.search(r"(\d{6})", content or "")
        captured["code"] = m.group(1) if m else ""
        captured["mobile"] = str(mobile or "")
        return True, "", "mock-ok"

    app_main.send_sms_106 = fake_send_sms_106  # type: ignore[assignment]
    c = TestClient(app_main.app)

    # ---------- 生产模式（双因素） ----------
    settings.admin_require_sms = True
    r = c.get("/v1/admin/auth/mode")
    m = r.json()
    check(
        "prod auth/mode require_sms=true",
        r.status_code == 200 and m.get("require_sms") is True and m.get("sms_enabled") is True,
        f"status={r.status_code} require_sms={m.get('require_sms')} sms_enabled={m.get('sms_enabled')}",
    )
    r = c.get("/v1/admin/token/summary")
    check("prod no-key -> 403", r.status_code == 403, f"status={r.status_code}")
    r = c.get("/v1/admin/token/summary", headers={"X-SMS-Internal-Key": sms_key})
    check("prod sms-key-only -> 403", r.status_code == 403, f"status={r.status_code}")
    r = c.get("/v1/admin/token/summary", headers={"X-Admin-Key": admin_key})
    check("prod admin-key-only -> 403 (需双因素)", r.status_code == 403, f"status={r.status_code}")

    r = c.post("/v1/admin/sms/send", json={"mobile": phone, "purpose": "login"})
    check("prod sms/send no-key -> 403", r.status_code == 403, f"status={r.status_code}")
    r = c.post(
        "/v1/admin/sms/send",
        json={"mobile": phone, "purpose": "login"},
        headers={"X-Admin-Key": "wrong-key"},
    )
    check("prod sms/send wrong-key -> 403", r.status_code == 403, f"status={r.status_code}")
    r = c.post(
        "/v1/admin/sms/send",
        json={"mobile": phone, "purpose": "login"},
        headers={"X-Admin-Key": admin_key},
    )
    check(
        "prod sms/send with-key -> 200 (mock)",
        r.status_code == 200 and bool(captured.get("code")),
        f"status={r.status_code} code_len={len(captured.get('code', ''))}",
    )
    r = c.post(
        "/v1/admin/sms/login",
        json={"mobile": phone, "code": "000000"},
        headers={"X-Admin-Key": admin_key},
    )
    check("prod sms/login wrong-code -> 403", r.status_code == 403, f"status={r.status_code}")
    r = c.post(
        "/v1/admin/sms/login",
        json={"mobile": phone, "code": captured.get("code", "")},
    )
    check("prod sms/login correct-code no-key -> 403", r.status_code == 403, f"status={r.status_code}")
    r = c.post(
        "/v1/admin/sms/login",
        json={"mobile": phone, "code": captured.get("code", "")},
        headers={"X-Admin-Key": admin_key},
    )
    session = r.json().get("key", "") if r.status_code == 200 else ""
    check("prod sms/login key+code -> 200 session", r.status_code == 200 and bool(session), f"status={r.status_code}")
    r = c.get("/v1/admin/token/summary", headers={"X-Admin-Key": session})
    check("prod summary with 2fa session -> 200", r.status_code == 200, f"status={r.status_code}")
    # 双因素会话透传 open 网关：core 应转发自身 ADMIN_API_KEY，而不是会话 token
    r = c.get("/v1/admin/products/open/plans", headers={"X-Admin-Key": session})
    plans = r.json().get("data", {}).get("plans", []) if r.status_code == 200 else []
    check(
        "prod open gateway with 2fa session -> 200",
        r.status_code == 200 and len(plans) >= 2,
        f"status={r.status_code} plans={len(plans)}",
    )

    # ---------- 本地模式（单密钥即可） ----------
    settings.admin_require_sms = False
    r = c.get("/v1/admin/auth/mode")
    m = r.json()
    check(
        "local auth/mode require_sms=false",
        r.status_code == 200 and m.get("require_sms") is False and m.get("sms_enabled") is False,
        f"status={r.status_code} require_sms={m.get('require_sms')} sms_enabled={m.get('sms_enabled')}",
    )
    r = c.get("/v1/admin/token/summary", headers={"X-Admin-Key": admin_key})
    check("local admin-key -> 200", r.status_code == 200, f"status={r.status_code}")
    r = c.get("/v1/admin/token/summary", headers={"X-SMS-Internal-Key": sms_key})
    check("local sms-internal-key(iamlei888) -> 200", r.status_code == 200, f"status={r.status_code}")
    r = c.post(
        "/v1/admin/sms/send",
        json={"mobile": phone, "purpose": "login"},
        headers={"X-Admin-Key": admin_key},
    )
    check("local sms/send -> 503 (未开启)", r.status_code == 503, f"status={r.status_code}")
    r = c.post(
        "/v1/admin/sms/login",
        json={"mobile": phone, "code": "123456"},
        headers={"X-Admin-Key": admin_key},
    )
    check("local sms/login -> 503 (未开启)", r.status_code == 503, f"status={r.status_code}")

    failed = [n for n, ok, _ in checks if not ok]
    print(f"---\nTOTAL={len(checks)} PASS={len(checks) - len(failed)} FAIL={len(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
