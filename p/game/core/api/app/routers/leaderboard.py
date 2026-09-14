from __future__ import annotations

import json
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Game, Leaderboard, User
from ..schemas import ScoreIn

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])


def _get_game(db: Session, key: str) -> Game:
    game = db.query(Game).filter(Game.key == key).first()
    if game is None:
        raise HTTPException(status_code=404, detail="game not found")
    return game


@router.post("/submit")
def submit_score(body: ScoreIn, db: Session = Depends(get_db)) -> dict:
    game = _get_game(db, body.game_key)
    period = date.today().isoformat() if body.scope == "daily" else ""
    row = Leaderboard(game_id=game.id, scope=body.scope, period=period, seed=body.seed,
                      user_id=0, score=body.score, payload=json.dumps(body.payload, ensure_ascii=False))
    db.add(row)
    db.commit()
    return {"ok": True}


@router.get("")
def top(game_key: str, scope: str = "all", seed: str = "", limit: int = 50, db: Session = Depends(get_db)) -> dict:
    game = _get_game(db, game_key)
    period = date.today().isoformat() if scope == "daily" else ""
    rows = (
        db.query(Leaderboard)
        .filter(Leaderboard.game_id == game.id, Leaderboard.scope == scope,
                Leaderboard.period == period, Leaderboard.seed == seed)
        .order_by(Leaderboard.score.desc())
        .limit(limit)
        .all()
    )
    uids = [r.user_id for r in rows]
    users = {u.id: u for u in db.query(User).filter(User.id.in_(uids)).all()} if uids else {}
    items = [{"rank": i + 1, "score": r.score,
              "nickname": users.get(r.user_id).nickname if users.get(r.user_id) else "",
              "payload": json.loads(r.payload)} for i, r in enumerate(rows)]
    return {"items": items}
