from __future__ import annotations

import random
import time
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from .config import settings
from .db import inventory_dump, inventory_load
from .fish_catalog import SPECIES, species_by_id
from .models import Player

if TYPE_CHECKING:
    from .fish_catalog import FishSpecies


def _pool_for_spot(spot_id: int) -> list[FishSpecies]:
    sid = int(spot_id)
    return [s for s in SPECIES if s.spot_id == sid]


def roll_fish(player: Player) -> FishSpecies:
    pool = _pool_for_spot(player.spot_id)
    if not pool:
        pool = list(SPECIES)
    return random.choice(pool)


def do_fish(db: Session, player: Player) -> tuple[FishSpecies, int, dict[str, int]]:
    """校验冷却、随机鱼种、写入库存与 last_cast。返回 (species, cooldown_s, new_inventory)。"""
    now = time.time()
    cd = int(settings.cast_cooldown_s)
    if player.last_cast_at is not None:
        elapsed = now - float(player.last_cast_at)
        if elapsed < cd:
            raise ValueError(f"cooldown:{cd - int(elapsed)}")

    sp = roll_fish(player)
    inv = inventory_load(player.inventory_json)
    k = str(sp.id)
    inv[k] = int(inv.get(k, 0)) + 1

    player.inventory_json = inventory_dump(inv)
    player.last_cast_at = now
    db.add(player)
    db.commit()
    db.refresh(player)
    return sp, cd, inv


def do_sell(db: Session, player: Player, *, sell_all: bool, species_id: int | None, quantity: int) -> tuple[int, int, dict[str, int], list[dict]]:
    inv = inventory_load(player.inventory_json)
    coins_delta = 0
    score_delta = 0
    sold: list[dict] = []
    qty = max(1, int(quantity))

    if sell_all:
        keys = list(inv.keys())
        for k in keys:
            n = int(inv.get(k, 0))
            if n <= 0:
                continue
            sid = int(k)
            sp = species_by_id(sid)
            if not sp:
                continue
            c, sc = _apply_sale(sp, n)
            coins_delta += c
            score_delta += sc
            sold.append({"species_id": sid, "name": sp.name, "quantity": n, "coins": c, "score": sc})
            inv.pop(k, None)
    else:
        if species_id is None:
            raise ValueError("species_id_required")
        sid = int(species_id)
        sp = species_by_id(sid)
        if not sp:
            raise ValueError("unknown_species")
        have = int(inv.get(str(sid), 0))
        if have < qty:
            raise ValueError("not_enough_fish")
        c, sc = _apply_sale(sp, qty)
        coins_delta += c
        score_delta += sc
        sold.append({"species_id": sid, "name": sp.name, "quantity": qty, "coins": c, "score": sc})
        left = have - qty
        if left <= 0:
            inv.pop(str(sid), None)
        else:
            inv[str(sid)] = left

    player.coins = int(player.coins) + coins_delta
    player.score = int(player.score) + score_delta
    player.inventory_json = inventory_dump(inv)
    db.add(player)
    db.commit()
    db.refresh(player)
    return coins_delta, score_delta, inv, sold


def _apply_sale(sp: FishSpecies, n: int) -> tuple[int, int]:
    if sp.currency == "coin":
        return sp.price * n, 0
    if sp.currency == "score":
        return 0, sp.price * n
    return 0, 0
