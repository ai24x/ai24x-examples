from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import Event
from ..schemas import EventsIn

router = APIRouter(prefix="/events", tags=["events"])


@router.post("")
def report_events(body: EventsIn, db: Session = Depends(get_db)) -> dict:
    rows = [
        Event(appid=settings.wx_appid or "dev", user_id=0, event=e.event,
              params=json.dumps(e.params, ensure_ascii=False))
        for e in body.events
    ]
    if rows:
        db.add_all(rows)
        db.commit()
    return {"ok": True, "count": len(rows)}
