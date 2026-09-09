"""
BYOK 控制台 API（/v1/byok/*）。

鉴权：由 main.py 以 `include_router(..., dependencies=[Depends(get_current_user)])`
统一挂载；路由内通过 request.state.auth_user_id 取登录用户。
合规红线：任何响应/日志都不含上游 key 明文，只暴露 key_prefix。
"""
from __future__ import annotations

from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from database import get_db

router = APIRouter()

_NO_STORE = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
}


class ByokKeyCreateBody(BaseModel):
    provider: str = Field(..., description="openai/anthropic/deepseek/openrouter/...")
    api_key: str = Field(..., min_length=8, description="用户自有上游 key（仅本次请求明文，落库即加密）")
    name: str = Field(default="", max_length=64)
    models: Optional[List[str]] = Field(default=None, description="可服务的上游模型名；空=全部")
    base_url: Optional[str] = Field(default=None, description="自定义 OpenAI 兼容端点（custom 必填）")
    priority: int = Field(default=100, ge=0, le=999, description="选路优先级：越小越优先")


class ByokKeyUpdateBody(BaseModel):
    name: Optional[str] = Field(default=None, max_length=64)
    status: Optional[str] = Field(default=None, description="active / disabled")
    priority: Optional[int] = Field(default=None, ge=0, le=999)
    models: Optional[List[str]] = Field(default=None)
    base_url: Optional[str] = Field(default=None)
    provider: Optional[str] = Field(default=None)
    api_key: Optional[str] = Field(default=None, min_length=8, description="换 key 时传入新明文")


class ByokKeyTestBody(BaseModel):
    provider: str = Field(default="openai")
    api_key: Optional[str] = Field(default=None, description="不落库的临时 key；与 key_id 二选一")
    base_url: Optional[str] = Field(default=None)
    model: Optional[str] = Field(default=None)
    key_id: Optional[int] = Field(default=None, description="测试已保存的 key")


def _auth_user_id(request: Request) -> int:
    uid = getattr(request.state, "auth_user_id", None)
    if uid is None:
        raise HTTPException(status_code=401, detail="未登录")
    return int(uid)


@router.get("/byok/status")
def byok_status(request: Request):
    from byok import service_status, subscription_status
    from database import SessionLocal
    from byok_plans import public_byok_plans

    uid = _auth_user_id(request)
    try:
        db = SessionLocal()
        try:
            sub = subscription_status(db, uid)
        finally:
            db.close()
    except Exception:
        sub = {"plan": None, "tier": "free", "status": "none", "active": False}
    return {**service_status(), "subscription": sub, "plans": public_byok_plans()}


@router.get("/byok/plans")
def byok_plans_catalog(request: Request):
    """BYOK 服务费套餐目录 + 支付通道就绪状态（无密钥信息）。"""
    from byok_plans import public_byok_plans
    from token_pay_service import token_pay_enabled, token_pay_mock_allowed, pay_settings_ns
    from pay_alipay_wap import alipay_configured
    from pay_creem import creem_configured
    from pay_paypal import paypal_configured
    from pay_wechat_v3 import wechat_pay_configured

    cfg = pay_settings_ns()
    wx = wechat_pay_configured(cfg)
    ali = alipay_configured(cfg)
    pp = paypal_configured(cfg)
    creem = creem_configured(cfg)
    enabled = token_pay_enabled()
    return {
        "plans": public_byok_plans(),
        "pay": {
            "enabled": enabled,
            "mock_allowed": token_pay_mock_allowed(),
            "wechat_ready": bool(enabled and wx),
            "alipay_ready": bool(enabled and ali),
            "paypal_ready": bool(enabled and pp),
            "paypal_mode": str(getattr(cfg, "paypal_mode", "sandbox") or "sandbox"),
            "creem_ready": bool(enabled and creem),
            "creem_mode": str(getattr(cfg, "creem_mode", "test") or "test"),
        },
        "service_fee_note": "Gateway service fee only — no markup on your keys. You are billed by your provider at their rates.",
    }


@router.get("/byok/keys")
def byok_keys_list(request: Request, db=Depends(get_db)):
    from byok import list_keys

    return JSONResponse(
        content={"keys": list_keys(db, _auth_user_id(request))},
        headers=_NO_STORE,
    )


@router.post("/byok/keys")
def byok_keys_create(body: ByokKeyCreateBody, request: Request, db=Depends(get_db)):
    from byok import create_key

    try:
        row = create_key(
            db,
            auth_user_id=_auth_user_id(request),
            provider=body.provider,
            api_key=body.api_key,
            name=body.name,
            models=body.models,
            base_url=body.base_url,
            priority=body.priority,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return JSONResponse(content={"key": row}, headers=_NO_STORE)


@router.post("/byok/keys/test")
def byok_keys_test(body: ByokKeyTestBody, request: Request, db=Depends(get_db)):
    from byok import test_key

    try:
        return test_key(
            db,
            auth_user_id=_auth_user_id(request),
            provider=body.provider,
            api_key=body.api_key,
            base_url=body.base_url,
            model=body.model,
            key_id=body.key_id,
        )
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


@router.patch("/byok/keys/{key_id}")
def byok_keys_update(key_id: int, body: ByokKeyUpdateBody, request: Request, db=Depends(get_db)):
    from byok import update_key

    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        row = update_key(db, auth_user_id=_auth_user_id(request), key_id=key_id, patch=patch)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if row is None:
        raise HTTPException(status_code=404, detail="key not found")
    return JSONResponse(content={"key": row}, headers=_NO_STORE)


@router.delete("/byok/keys/{key_id}")
def byok_keys_delete(key_id: int, request: Request, db=Depends(get_db)):
    from byok import delete_key

    ok = delete_key(db, auth_user_id=_auth_user_id(request), key_id=key_id)
    if not ok:
        raise HTTPException(status_code=404, detail="key not found")
    return {"ok": True}


@router.get("/byok/models")
def byok_models(request: Request):
    from byok import models_catalog

    return models_catalog()


@router.get("/byok/usage")
def byok_usage(request: Request, days: int = 7, group_by: str = "key", db=Depends(get_db)):
    from byok import usage_summary

    if group_by not in ("key", "model", "project", "provider"):
        group_by = "key"
    return usage_summary(db, auth_user_id=_auth_user_id(request), days=days, group_by=group_by)


@router.get("/byok/usage/daily")
def byok_usage_daily(request: Request, days: int = 7, db=Depends(get_db)):
    from byok import usage_daily

    return usage_daily(db, auth_user_id=_auth_user_id(request), days=days)


@router.get("/byok/cache/stats")
def byok_cache_stats(request: Request):
    from byok import cache_stats

    return cache_stats()
