"""AI24X Markets · 子服务管理只读 API（供 core 运营后台网关代理调用）。

安全模型（P1 只读）：
- 仅接受 X-Markets-Secret 签名（与 /api/subscribe/fulfill 同一密钥）；
- 仅允许本机回环来源（core 网关同机代理，公网不可直达）；
- P2 如需写操作（延期/补发/改套餐），沿用同一守卫增量扩展。
"""
from __future__ import annotations

import os
import sys
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from . import billing

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _guard(request: Request) -> None:
    secret = os.environ.get("MARKETS_FULFILL_SECRET", "")
    got = (request.headers.get("x-markets-secret") or "").strip()
    if not secret or got != secret:
        raise HTTPException(status_code=403, detail="bad_secret")
    host = (request.client.host if request.client else "") or ""
    if host not in ("127.0.0.1", "::1", "localhost"):
        raise HTTPException(status_code=403, detail="loopback_only")
    # nginx 反代下 TCP peer 恒为回环：若 nginx 设置了 X-Real-IP（真实远端 IP），
    # 公网用户经反代访问也会带公网 IP → 直接拒绝，堵住「反代伪装回环」绕行
    xri = (request.headers.get("x-real-ip") or "").strip()
    if xri and xri not in ("127.0.0.1", "::1", "localhost"):
        raise HTTPException(status_code=403, detail="non_loopback_real_ip")


@router.get("/summary")
async def admin_summary(request: Request):
    _guard(request)
    try:
        return {"code": 0, "data": billing.admin_summary()}
    except Exception as e:
        print(f"[markets] /api/admin/summary error: {e!r}", file=sys.stderr)
        return JSONResponse(status_code=500, content={"code": -1, "msg": "internal_error"})


@router.get("/subs")
async def admin_subs(
    request: Request,
    uid: Optional[str] = Query(default=None, max_length=64),
    status: Optional[str] = Query(default=None, max_length=16),
    plan: Optional[str] = Query(default=None, max_length=16),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    _guard(request)
    try:
        data = billing.admin_list_subscriptions(
            user_id=(uid or "").strip() or None,
            status=(status or "").strip() or None,
            plan=(plan or "").strip() or None,
            limit=limit,
            offset=offset,
        )
        return {"code": 0, "data": data}
    except Exception as e:
        print(f"[markets] /api/admin/subs error: {e!r}", file=sys.stderr)
        return JSONResponse(status_code=500, content={"code": -1, "msg": "internal_error"})


@router.get("/orders")
async def admin_orders(
    request: Request,
    status: Optional[str] = Query(default=None, max_length=16),
    channel: Optional[str] = Query(default=None, max_length=16),
    q: Optional[str] = Query(default=None, max_length=120),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    _guard(request)
    try:
        data = billing.admin_list_orders(
            status=(status or "").strip() or None,
            channel=(channel or "").strip() or None,
            q=(q or "").strip() or None,
            limit=limit,
            offset=offset,
        )
        return {"code": 0, "data": data}
    except Exception as e:
        print(f"[markets] /api/admin/orders error: {e!r}", file=sys.stderr)
        return JSONResponse(status_code=500, content={"code": -1, "msg": "internal_error"})


@router.get("/plans")
async def admin_plans(request: Request):
    _guard(request)
    try:
        out = []
        for pid, p in billing.PLANS.items():
            out.append(
                {
                    "plan": pid,
                    "label": p.get("label"),
                    "usd": p.get("usd"),
                    "days": p.get("days"),
                    "description": p.get("description"),
                }
            )
        return {"code": 0, "data": {"plans": out}}
    except Exception as e:
        print(f"[markets] /api/admin/plans error: {e!r}", file=sys.stderr)
        return JSONResponse(status_code=500, content={"code": -1, "msg": "internal_error"})
