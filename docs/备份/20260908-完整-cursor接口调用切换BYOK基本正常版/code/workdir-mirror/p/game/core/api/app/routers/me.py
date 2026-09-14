from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth_jwt import get_current_user
from ..db import get_db
from ..models import User
from ..schemas import UserOut

router = APIRouter(tags=["me"])


@router.get("/me")
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return {"user": UserOut.model_validate(user)}
