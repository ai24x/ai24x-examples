from __future__ import annotations

import logging

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from . import db as dbmod
from .auth_jwt import create_access_token, get_current_player
from .config import settings
from .fish_catalog import SPOT_NAMES, species_by_id
from .game_service import do_fish, do_sell
from .models import Player
from .schemas import DevLoginIn, DevLoginOut, FishOut, MeOut, SellIn, SellOut

logger = logging.getLogger(__name__)

app = FastAPI(title="山海渔 Fisher API", version="0.1.0")


def _cors_allow_origins() -> list[str]:
    raw = (settings.cors_origins or "").strip()
    if raw in ("*", ""):
        return ["*"]
    return [p.strip() for p in raw.split(",") if p.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_allow_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    dbmod.init_db()
    logger.info("Fisher DB ready url=%s", settings.database_url.split("@")[-1])


@app.get("/health")
def health() -> dict:
    return {"ok": True, "service": "fisher-api", "env": settings.env}


@app.get("/")
def root() -> dict:
    return {
        "ok": True,
        "service": "fisher-api",
        "docs": "/docs",
        "health": "/health",
        "paths": {
            "dev_login": "POST /v1/auth/dev-login",
            "me": "GET /v1/me",
            "fish": "POST /v1/game/fish",
            "sell": "POST /v1/game/sell",
        },
    }


@app.post("/v1/auth/dev-login", response_model=DevLoginOut)
def dev_login(body: DevLoginIn, db: Session = Depends(dbmod.get_db)) -> DevLoginOut:
    """开发期联调：用固定 dev_key 创建/识别玩家并签发 JWT。生产替换为微信 code2session。"""
    try:
        p = dbmod.get_or_create_dev_player(db, body.dev_key)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid dev_key")
    token = create_access_token(sub=str(p.id), extra={"typ": "dev"})
    return DevLoginOut(access_token=token, expires_in_days=settings.jwt_expire_days)


@app.get("/v1/me", response_model=MeOut)
def me(player: Player = Depends(get_current_player)) -> MeOut:
    inv = dbmod.inventory_load(player.inventory_json)
    spot_name = SPOT_NAMES.get(int(player.spot_id), "未知钓场")
    return MeOut(
        id=int(player.id),
        coins=int(player.coins),
        score=int(player.score),
        rod_level=int(player.rod_level),
        spot_id=int(player.spot_id),
        spot_name=spot_name,
        inventory=inv,
    )


@app.post("/v1/game/fish", response_model=FishOut)
def fish_one(player: Player = Depends(get_current_player), db: Session = Depends(dbmod.get_db)) -> FishOut:
    try:
        sp, cd, inv = do_fish(db, player)
    except ValueError as e:
        msg = str(e)
        if msg.startswith("cooldown:"):
            rem = int(msg.split(":", 1)[1])
            raise HTTPException(status_code=429, detail={"code": "cooldown", "retry_after_s": rem})
        raise HTTPException(status_code=400, detail=msg)
    return FishOut(
        species_id=sp.id,
        name=sp.name,
        currency=sp.currency,
        unit_value=sp.price,
        cooldown_s=int(settings.cast_cooldown_s),
        inventory=inv,
    )


@app.post("/v1/game/sell", response_model=SellOut)
def sell(body: SellIn, player: Player = Depends(get_current_player), db: Session = Depends(dbmod.get_db)) -> SellOut:
    try:
        c_delta, s_delta, inv, sold = do_sell(
            db,
            player,
            sell_all=bool(body.sell_all),
            species_id=body.species_id,
            quantity=int(body.quantity),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return SellOut(
        coins_delta=c_delta,
        score_delta=s_delta,
        coins=int(player.coins),
        score=int(player.score),
        inventory=inv,
        sold=sold,
    )
