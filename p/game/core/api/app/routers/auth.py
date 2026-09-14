from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth_jwt import create_access_token
from ..config import settings
from ..db import get_db
from ..models import User
from ..schemas import LoginIn, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)) -> dict:
    """微信登录：v1 未配密钥时 code 直存为 openid（本地联调）；
    上线前接 code2session 换真实 openid/unionid。"""
    if settings.wx_appid and settings.wx_secret:
        raise HTTPException(status_code=501, detail="wx code2session not configured yet")
    openid = body.code
    user = db.query(User).filter(
        __import__("sqlalchemy").or_(User.openid == openid, User.unionid == openid)
    ).first()
    if user is None:
        user = User(appid=settings.wx_appid or "dev", openid=openid, unionid=openid)
        db.add(user)
        db.commit()
        db.refresh(user)
    user.last_seen_at = datetime.now(timezone.utc)
    db.commit()
    return {"token": create_access_token(sub=str(user.id)), "user": UserOut.model_validate(user)}
