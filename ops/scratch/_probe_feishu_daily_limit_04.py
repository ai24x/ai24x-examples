# -*- coding: utf-8 -*-
"""Inspect gateway user daily limits for Feishu OpenClaw AI24X key (auth_user_id=40)."""
import sys
from pathlib import Path

sys.path.insert(0, r"C:\ai24x01\api")
from database import SessionLocal
from models import User, AuthUser
from token_mvp_service import get_api_key_row

# load key from agent models without printing full
import json
am = json.loads(Path(r"C:\Users\Administrator\.openclaw\agents\main\agent\models.json").read_text(encoding="utf-8"))
key = am["providers"]["ai24x"]["apiKey"]

db = SessionLocal()
try:
    row = get_api_key_row(db, key)
    print("api_key_id=", getattr(row, "id", None), "auth_user_id=", getattr(row, "auth_user_id", None))
    au = db.query(AuthUser).filter(AuthUser.id == 40).first()
    print("auth_email=", getattr(au, "email", None))
    # gateway user linked
    from models import User as GU
    # find by ensuring gateway user
    from token_mvp_service import ensure_gateway_user
    u = ensure_gateway_user(db, 40)
    print(
        "user_id=", u.user_id,
        "user_type=", getattr(u.user_type, "value", u.user_type),
        "daily_limit=", u.daily_request_limit,
        "daily_used=", u.current_daily_requests,
        "monthly_limit=", u.monthly_request_limit,
        "monthly_used=", u.current_monthly_requests,
        "updated_at=", u.updated_at,
    )
finally:
    db.close()
