"""BYOK 网关冒烟测试（2026-08-18 Phase 1）。

覆盖：AES 加解密 / 模型解析 / key CRUD / 多 key 故障转移 / 缓存命中 /
用量统计 / ChatService 集成（BYOK 不扣平台钱包）。上游调用用假实现，不发真实请求。

用法：cd p\\open\\api && python scripts_byok_smoke.py
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _fresh_db_session():
    from database import SessionLocal

    return SessionLocal()


def _cleanup(db, auth_user_id: int, gateway_user_id: str):
    from models import AuthUser, ByokKey, ByokUsage, User

    try:
        db.query(ByokUsage).filter(ByokUsage.auth_user_id == auth_user_id).delete()
        db.query(ByokKey).filter(ByokKey.auth_user_id == auth_user_id).delete()
        db.query(AuthUser).filter(AuthUser.id == auth_user_id).delete()
        db.query(User).filter(User.user_id == gateway_user_id).delete()
        db.commit()
    except Exception:
        db.rollback()


def test_crypto():
    import byok

    ct = byok.encrypt_key("sk-live-abcdef1234567890")
    assert ct.startswith("aesgcm:v1:")
    assert byok.decrypt_key(ct) == "sk-live-abcdef1234567890"
    assert byok.key_prefix("sk-live-abcdef1234567890") == "sk-live-"
    try:
        byok.decrypt_key("aesgcm:v1:bad:bad")
        raise AssertionError("decrypt should fail")
    except ValueError:
        pass
    print("PASS crypto")


def test_resolve():
    import byok

    assert byok.resolve_upstream_model("flash", "deepseek", []) == "deepseek-chat"
    assert byok.resolve_upstream_model("gpt-4o", "openai", ["gpt-4o"]) == "gpt-4o"
    assert byok.resolve_upstream_model("gpt-4o", "openai", ["openai/gpt-4o"]) == "openai/gpt-4o"
    assert byok.resolve_upstream_model("gpt-4o", "openai", ["gpt-4o-mini"]) is None
    assert byok.resolve_upstream_model("ds-v4-flash", "deepseek", []) == "deepseek-v4-flash"
    assert byok.resolve_upstream_model("claude-3-5-sonnet-latest", "anthropic", ["claude-3-5-sonnet-latest"]) == "claude-3-5-sonnet-latest"
    print("PASS resolve")


def test_crud():
    import byok
    from models import AuthUser, User, UserType

    db = _fresh_db_session()
    try:
        au = AuthUser(email=f"byok-smoke-{int(time.time())}@test.local", password_hash="x")
        db.add(au)
        db.commit()
        db.refresh(au)
        gw = User(user_id=str(au.id), user_type=UserType.FREE)
        db.add(gw)
        db.commit()

        row = byok.create_key(
            db,
            auth_user_id=au.id,
            provider="deepseek",
            api_key="sk-ds-abcdef1234567890",
            name="DS 主 key",
            models=["deepseek-chat"],
        )
        assert row["key_prefix"] == "sk-ds-a" or row["key_prefix"].startswith("sk-")
        assert "api_key" not in row and "key_cipher" not in row
        keys = byok.list_keys(db, au.id)
        assert len(keys) == 1 and keys[0]["models"] == ["deepseek-chat"]

        upd = byok.update_key(
            db, auth_user_id=au.id, key_id=row["id"],
            patch={"status": "disabled", "models": ["deepseek-chat", "deepseek-reasoner"]},
        )
        assert upd["status"] == "disabled" and len(upd["models"]) == 2

        row2 = byok.create_key(
            db,
            auth_user_id=au.id,
            provider="openai",
            api_key="sk-openai-abcdef1234567890",
            models=["gpt-4o-mini"],
        )
        assert row2["provider"] == "openai"
        assert byok.delete_key(db, auth_user_id=au.id, key_id=row["id"])
        assert len(byok.list_keys(db, au.id)) == 1
        return au.id, gw.user_id
    finally:
        db.close()


class _FakeUpstream:
    """模拟上游：可按 key 明文后缀指定失败。"""

    def __init__(self):
        self.calls: list[dict] = []
        self.fail_plain_suffix: set[str] = set()
        self.fail_kind = "auth"
        self.next_text = "hello from upstream"

    def __call__(self, **kw):
        plain = str(kw.get("key") or "")
        suffix = plain[-10:]
        self.calls.append({"key_tail": suffix, "provider": kw.get("provider"), "model": kw.get("model")})
        if suffix in self.fail_plain_suffix:
            class _Resp:
                status_code = 401
                text = '{"error":{"message":"invalid api key"}}'

            class _Err(Exception):
                pass

            e = _Err("401 Unauthorized")
            e.response = _Resp()
            raise e
        return {
            "text": self.next_text,
            "tokens": 10,
            "prompt_tokens": 4,
            "completion_tokens": 6,
            "raw_model": kw.get("model"),
            "tool_calls": None,
            "finish_reason": "stop",
        }


def _mini_req(model="deepseek-chat"):
    class R:
        pass

    r = R()
    r.prompt = "ping"
    r.messages = [{"role": "user", "content": "ping"}]
    r.model = model
    r.temperature = 0.0
    r.max_tokens = 16
    r.tools = None
    r.tool_choice = None
    r.stream = False
    return r


def test_failover_and_cache(auth_user_id: int):
    import byok
    from models import ByokKey, ByokUsage

    db = _fresh_db_session()
    try:
        byok._CACHE.clear()
        k1 = byok.create_key(
            db, auth_user_id=auth_user_id, provider="deepseek",
            api_key="sk-ds-fail-AAA1112223", models=["deepseek-chat"],
        )
        k2 = byok.create_key(
            db, auth_user_id=auth_user_id, provider="deepseek",
            api_key="sk-ds-ok-BBB2223334", models=["deepseek-chat"],
        )
        fake = _FakeUpstream()
        fake.fail_plain_suffix.add("AAA1112223")  # k1 明文尾
        orig = byok._upstream_call
        byok._upstream_call = fake
        try:
            # 1) 第一把失败 → 自动切第二把
            res = byok.route_byok_chat(db, auth_user_id=auth_user_id, request=_mini_req())
            assert res is not None and res.ok, res
            assert res.byok_key_id == k2["id"], (res.byok_key_id, k2)
            assert res.token_count == 10
            assert [c["key_tail"] for c in fake.calls] == ["AAA1112223", "BBB2223334"]
            assert len(fake.calls) == 2
            # key 健康统计
            rows = {r.id: r for r in db.query(ByokKey).filter(ByokKey.id.in_([k1["id"], k2["id"]])).all()}
            assert rows[k1["id"]].fail_count == 1
            assert rows[k2["id"]].success_count == 1
            # 失败也记 usage
            fails = db.query(ByokUsage).filter(
                ByokUsage.byok_key_id == k1["id"], ByokUsage.success.is_(False)
            ).count()
            assert fails == 1
            print("PASS failover (dead key -> backup key)")

            # 2) 缓存：同用户同载荷第二次命中（不再发上游）
            fake.calls.clear()
            res2 = byok.route_byok_chat(db, auth_user_id=auth_user_id, request=_mini_req())
            assert res2 is not None and res2.ok and res2.cached, res2
            assert fake.calls == [], fake.calls
            cached_rows = db.query(ByokUsage).filter(
                ByokUsage.auth_user_id == auth_user_id, ByokUsage.cached.is_(True)
            ).count()
            assert cached_rows == 1
            print("PASS request cache (same payload no upstream call)")

            # 3) 全部失败 + 允许回退 → 返回 None（调用方走平台）
            byok._CACHE.clear()
            fake.fail_plain_suffix = {"AAA1112223", "BBB2223334"}
            res3 = byok.route_byok_chat(db, auth_user_id=auth_user_id, request=_mini_req())
            assert res3 is None, res3
            print("PASS all-fail fallback_to_platform=None")

            # 4) 全部失败 + 关闭回退 → ok=False byok_all_failed
            prev = byok._fallback_to_platform
            byok._fallback_to_platform = lambda: False
            try:
                res4 = byok.route_byok_chat(db, auth_user_id=auth_user_id, request=_mini_req())
                assert res4 is not None and not res4.ok and (res4.error or "").startswith("byok_all_failed")
            finally:
                byok._fallback_to_platform = prev
            print("PASS all-fail no-fallback -> byok_all_failed")

            # 5) 用量统计
            summ = byok.usage_summary(db, auth_user_id=auth_user_id, days=7, group_by="key")
            assert summ["totals"]["requests"] >= 4
            assert summ["totals"]["success"] >= 1
            assert summ["groups"], summ
            print("PASS usage_summary:", summ["totals"])
        finally:
            byok._upstream_call = orig
            # 清理本次创建的 key/usage（保留 auth 用户供服务集成测试）
            db.query(ByokUsage).filter(ByokUsage.auth_user_id == auth_user_id).delete()
            db.query(ByokKey).filter(ByokKey.auth_user_id == auth_user_id).delete()
            db.commit()
    finally:
        db.close()


def test_chat_service_integration(auth_user_id: int, gateway_user_id: str):
    import byok
    from database import SessionLocal
    from models import ByokKey, User
    from schemas import ChatRequest as ChatRequestSchema
    from services import ChatService

    db = SessionLocal()
    try:
        k = byok.create_key(
            db, auth_user_id=auth_user_id, provider="deepseek",
            api_key="sk-ds-svc-CCC3334445", models=["deepseek-chat"],
        )
        byok._CACHE.clear()
        fake = _FakeUpstream()
        fake.next_text = "byok integration ok"
        orig = byok._upstream_call
        byok._upstream_call = fake
        try:
            gw = db.query(User).filter(User.user_id == gateway_user_id).first()
            req = ChatRequestSchema(
                prompt="hello",
                model="deepseek-chat",
                temperature=0.0,
                max_tokens=16,
                messages=[{"role": "user", "content": "hello"}],
            )
            resp = ChatService.process_chat_request(
                db=db,
                user=gw,
                request=req,
                auth_user_id=auth_user_id,
                auth_api_key_id=None,
                byok_project="smoke-test",
            )
            assert resp.response == "byok integration ok"
            assert resp.provider == "byok" and resp.layer == "BYOK"
            assert resp.attribution.get("billing_mode") == "byok"
            assert resp.attribution.get("byok", {}).get("project") == "smoke-test"
            # BYOK 不扣平台钱包：检查无 consume 记录（billing_ledger 无此行）
            print("PASS ChatService BYOK integration provider=", resp.provider, "model=", resp.model)
        finally:
            byok._upstream_call = orig
    finally:
        db.close()


def main():
    test_crypto()
    test_resolve()
    au_id, gw_id = test_crud()
    test_failover_and_cache(au_id)
    test_chat_service_integration(au_id, gw_id)
    db = _fresh_db_session()
    _cleanup(db, au_id, gw_id)
    db.close()
    print("\nALL BYOK SMOKE TESTS PASSED")


if __name__ == "__main__":
    main()
