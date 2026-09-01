"""Internal BYOK routes for core One API bridge (not public)."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, is_dataclass
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/internal/byok", tags=[], include_in_schema=False)


class InternalByokRouteIn(BaseModel):
    platform_user_id: int = Field(..., ge=1, description="core auth_users.id")
    model: str = Field(default="auto", max_length=100)
    prompt: Optional[str] = Field(default=None, max_length=120000)
    messages: Optional[list[dict[str, Any]]] = None
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1000, ge=1, le=128000)
    tools: Optional[list[dict[str, Any]]] = None
    tool_choice: Optional[Any] = None
    region_hint: Optional[str] = Field(default=None, max_length=32)
    project: Optional[str] = Field(default=None, max_length=64)


class InternalByokCoverageIn(BaseModel):
    platform_user_id: int = Field(..., ge=1)
    model: str = Field(default="auto", max_length=100)


def _require_internal_key(request: Request) -> None:
    from config import settings

    admin = (getattr(settings, "admin_api_key", "") or "").strip()
    sms_k = (settings.sms_internal_key or "").strip()
    if not (admin or sms_k):
        raise HTTPException(status_code=503, detail="服务暂不可用，请稍后再试。")
    provided = (
        (request.headers.get("X-Admin-Key") or "").strip()
        or (request.headers.get("X-SMS-Internal-Key") or "").strip()
    )
    if admin:
        if provided and provided == admin:
            return
        raise HTTPException(status_code=403, detail="禁止访问")
    if sms_k and provided == sms_k:
        return
    raise HTTPException(status_code=403, detail="禁止访问")


def _resolve_open_user(db: Session, platform_user_id: int):
    from auth_user_service import get_by_platform_user_id

    return get_by_platform_user_id(db, int(platform_user_id))


class _ReqNS:
    pass


def _request_from_body(body: InternalByokRouteIn) -> _ReqNS:
    o = _ReqNS()
    o.model = body.model
    o.prompt = body.prompt or ""
    o.messages = body.messages
    o.tools = body.tools
    o.tool_choice = body.tool_choice
    o.temperature = body.temperature
    o.max_tokens = body.max_tokens
    return o


def _serialize_result(res: Any) -> dict[str, Any]:
    if res is None:
        return {}
    if is_dataclass(res):
        d = asdict(res)
    elif isinstance(res, dict):
        d = dict(res)
    else:
        d = {
            "ok": bool(getattr(res, "ok", False)),
            "text": getattr(res, "text", ""),
            "model": getattr(res, "model", ""),
            "layer": getattr(res, "layer", "BYOK"),
            "provider": getattr(res, "provider", "byok"),
            "token_count": getattr(res, "token_count", 0),
            "prompt_tokens": getattr(res, "prompt_tokens", None),
            "completion_tokens": getattr(res, "completion_tokens", None),
            "attempts": getattr(res, "attempts", None) or [],
            "error": getattr(res, "error", None),
            "public_model": getattr(res, "public_model", None),
            "tool_calls": getattr(res, "tool_calls", None),
            "finish_reason": getattr(res, "finish_reason", None),
            "byok_key_id": getattr(res, "byok_key_id", None),
            "cached": getattr(res, "cached", False),
            "upstream_model": getattr(res, "upstream_model", ""),
            "project": getattr(res, "project", None),
        }
    return d


@router.post("/route")
async def internal_byok_route(
    request: Request,
    body: InternalByokRouteIn,
    db: Session = Depends(get_db),
):
    """Non-stream BYOK route for core bridge."""
    _require_internal_key(request)
    u = _resolve_open_user(db, body.platform_user_id)
    if not u:
        return {"status": "fallback"}
    req = _request_from_body(body)
    try:
        from byok import ByokEntitlementError, route_byok_chat

        result = route_byok_chat(
            db,
            auth_user_id=int(u.id),
            request=req,
            region_hint=body.region_hint,
            project=body.project,
        )
    except ByokEntitlementError as e:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={"code": e.code, "message": e.message},
        ) from e
    except Exception:
        logger.exception("internal byok route failed uid=%s", body.platform_user_id)
        return {"status": "fallback"}
    if result is None:
        return {"status": "fallback"}
    if not getattr(result, "ok", False):
        return {"status": "error", "result": _serialize_result(result)}
    return {"status": "routed", "result": _serialize_result(result)}


@router.post("/has-coverage")
async def internal_byok_has_coverage(
    request: Request,
    body: InternalByokCoverageIn,
    db: Session = Depends(get_db),
):
    _require_internal_key(request)
    u = _resolve_open_user(db, body.platform_user_id)
    if not u:
        return {"coverage": False}
    try:
        from byok import has_byok_coverage

        ok = has_byok_coverage(db, int(u.id), body.model)
    except Exception:
        ok = False
    return {"coverage": bool(ok)}


@router.post("/preflight")
async def internal_byok_preflight(
    request: Request,
    body: InternalByokCoverageIn,
    db: Session = Depends(get_db),
):
    """Entitlement + coverage check before opening a BYOK stream."""
    _require_internal_key(request)
    u = _resolve_open_user(db, body.platform_user_id)
    if not u:
        return {"ok": False}
    try:
        from byok import ByokEntitlementError, assert_byok_entitlement, has_byok_coverage

        assert_byok_entitlement(db, int(u.id))
        ok = has_byok_coverage(db, int(u.id), body.model)
    except ByokEntitlementError as e:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={"code": e.code, "message": e.message},
        ) from e
    except Exception:
        ok = False
    return {"ok": bool(ok)}


@router.post("/stream")
async def internal_byok_stream(
    request: Request,
    body: InternalByokRouteIn,
    db: Session = Depends(get_db),
):
    """Stream BYOK as NDJSON lines (meta/delta/done/error)."""
    _require_internal_key(request)
    u = _resolve_open_user(db, body.platform_user_id)
    if not u:
        return Response(status_code=204)
    req = _request_from_body(body)
    try:
        from byok import ByokEntitlementError, stream_byok_chat

        gen = stream_byok_chat(
            db,
            auth_user_id=int(u.id),
            request=req,
            region_hint=body.region_hint,
            project=body.project,
        )
    except ByokEntitlementError as e:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={"code": e.code, "message": e.message},
        ) from e
    except Exception:
        logger.exception("internal byok stream setup failed uid=%s", body.platform_user_id)
        return Response(status_code=204)
    if gen is None:
        return Response(status_code=204)

    def _ndjson():
        try:
            for ev in gen:
                yield json.dumps(ev, ensure_ascii=False) + "\n"
        except Exception:
            logger.exception("internal byok stream iter failed uid=%s", body.platform_user_id)

    return StreamingResponse(_ndjson(), media_type="application/x-ndjson")
