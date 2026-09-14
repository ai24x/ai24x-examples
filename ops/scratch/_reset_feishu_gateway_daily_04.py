# -*- coding: utf-8 -*-
"""Reset Feishu OpenClaw gateway daily counter (auth_user_id=40) after deploy."""
from __future__ import annotations

import sys
from pathlib import Path

API = Path(r"C:\ai24x01\api")
sys.path.insert(0, str(API))
from dotenv import load_dotenv

load_dotenv(API / ".env")

from database import SessionLocal  # noqa: E402
from token_mvp_service import ensure_gateway_user  # noqa: E402


def main() -> None:
    db = SessionLocal()
    try:
        u = ensure_gateway_user(db, 40)
        u.current_daily_requests = 0
        db.commit()
        db.refresh(u)
        print(
            "feishu_auth40",
            "type=",
            getattr(u.user_type, "value", u.user_type),
            "daily_limit=",
            u.daily_request_limit,
            "daily_used=",
            u.current_daily_requests,
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
