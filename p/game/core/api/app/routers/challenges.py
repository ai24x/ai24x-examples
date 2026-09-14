from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Challenge, Game, User
from ..schemas import ChallengeIn

router = APIRouter(prefix="/challenges", tags=["challenges"])


@router.post("")
def create_challenge(body: ChallengeIn, db: Session = Depends(get_db)) -> dict:
    game = db.query(Game).filter(Game.key == body.game_key).first()
    if game is None:
        raise HTTPException(status_code=404, detail="game not found")
    to_user = db.query(User).filter(User.openid == body.to_openid).first()
    if to_user is None:
        raise HTTPException(status_code=404, detail="to_user not found (openid)")
    c = Challenge(game_id=game.id, seed=body.seed, from_user=0, to_user=to_user.id, from_score=body.from_score)
    db.add(c)
    db.commit()
    db.refresh(c)
    return {"ok": True, "challenge_id": c.id}
