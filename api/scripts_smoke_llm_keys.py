"""本机烟测：免费 Key 切开 / 管理台 / VIP 降级告警（不打印密钥明文）。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env", override=True)

from fastapi.testclient import TestClient

from config import settings
from free_shared import resolve_catalog_upstream
from llm_keys import get_key, recent_vip_degrades
from main import app
from model_router import _layer_upstream, _run_vip_pick_chat, _upstream_mode


def main() -> int:
    om, of_ = get_key("OPENROUTER_API_KEY"), get_key("OPENROUTER_API_KEY_FREE")
    sm, sf = get_key("SILICONFLOW_API_KEY"), get_key("SILICONFLOW_API_KEY_FREE")
    assert om and of_ and om != of_, "OR main/free not split"
    assert sm and sf and sm != sf, "Silicon main/free not split"
    assert _upstream_mode() == "openrouter"
    assert _layer_upstream("L0").get("provider") == "siliconflow"
    assert resolve_catalog_upstream("silicon-qwen")["key"] == sf
    assert resolve_catalog_upstream("or-auto")["key"] == of_

    c = TestClient(app)
    h = {"X-SMS-Internal-Key": (settings.sms_internal_key or "").strip()}
    for path in (
        "/v1/admin/token/llm_keys",
        "/v1/admin/token/alerts",
        "/v1/admin/token/model_warehouse",
        "/v1/admin/token/free_shared",
        "/v1/admin/users?limit=3",
    ):
        r = c.get(path, headers=h)
        assert r.status_code == 200, path

    pick = {
        "id": "vip-kimi",
        "openrouter_id": "moonshotai/__ai24x_smoke_missing__",
        "direct_id": None,
        "billing_mult": 1,
    }
    routed = _run_vip_pick_chat(
        pick=pick, prompt="Reply with OK only.", temperature=0.1, max_tokens=16
    )
    assert routed.ok, routed.error
    assert any(a.get("degraded") for a in (routed.attempts or []))
    assert recent_vip_degrades()
    alerts = c.get("/v1/admin/token/alerts", headers=h).json().get("alerts") or []
    assert any(x.get("code") == "vip_degraded" for x in alerts)

    print("SMOKE_OK llm_keys_split vip_degrade admin_routes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
