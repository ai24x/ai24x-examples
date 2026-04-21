from __future__ import annotations

from pydantic import BaseModel, Field


class DevLoginIn(BaseModel):
    dev_key: str = Field(min_length=1, max_length=128)


class DevLoginOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_days: int


class MeOut(BaseModel):
    id: int
    coins: int
    score: int
    rod_level: int
    spot_id: int
    spot_name: str
    inventory: dict[str, int]


class FishOut(BaseModel):
    species_id: int
    name: str
    currency: str
    unit_value: int
    cooldown_s: int
    inventory: dict[str, int]


class SellIn(BaseModel):
    sell_all: bool = False
    species_id: int | None = None
    quantity: int = 1


class SellOut(BaseModel):
    coins_delta: int
    score_delta: int
    coins: int
    score: int
    inventory: dict[str, int]
    sold: list[dict]
