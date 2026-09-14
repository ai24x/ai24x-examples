from __future__ import annotations

from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    code: str = Field(..., description="wx.login 的 code，服务端换 openid")


class UserOut(BaseModel):
    id: int
    openid: str
    nickname: str = ""
    avatar: str = ""
    stars: int = 0
    level: int = 1

    model_config = {"from_attributes": True}


class EventIn(BaseModel):
    event: str
    params: dict = {}


class EventsIn(BaseModel):
    events: list[EventIn] = []


class ScoreIn(BaseModel):
    game_key: str
    scope: str = "all"  # all/daily
    seed: str = ""
    score: int
    payload: dict = {}


class ChallengeIn(BaseModel):
    game_key: str
    seed: str
    to_openid: str
    from_score: int = 0


class ChallengeOut(BaseModel):
    id: int
    game_key: str
    seed: str
    from_openid: str = ""
    to_openid: str = ""
    from_score: int = 0
    to_score: int = 0
    status: str = "sent"
