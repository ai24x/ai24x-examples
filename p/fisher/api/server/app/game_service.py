"""核心游戏逻辑：钓鱼、售卖。鱼种数据从数据库动态查询，不再硬编码。"""

from __future__ import annotations

import json
import random
import time

from sqlalchemy.orm import Session

from .config import settings
from .db import inventory_dump, inventory_load
from .models import FishSpecies, Player


def _pool_for_spot(db: Session, spot_id: int) -> list[FishSpecies]:
    """按钓场 id 查询该钓场所有鱼种。"""
    return db.query(FishSpecies).filter(FishSpecies.spot_id == int(spot_id)).all()


def _species_by_id(db: Session, sid: int) -> FishSpecies | None:
    return db.query(FishSpecies).filter(FishSpecies.id == int(sid)).one_or_none()


def _weighted_choice(pool: list[FishSpecies], rod_level: int = 0) -> FishSpecies:
    """按稀有度加权随机选择鱼种，鱼竿等级提升稀有鱼出现率。

    rarity 权重: common=50, uncommon=25, rare=12, epic=5, legendary=1
    rod_level bonus: 每级 +10% 稀有+出现率 (rare/epic/legendary)
    """
    base_weights = {"common": 50, "uncommon": 25, "rare": 12, "epic": 5, "legendary": 1}
    bonus = 1.0 + (int(rod_level) * 0.10)
    items = list(pool)
    w = []
    for sp in items:
        bw = base_weights.get(sp.rarity, 10)
        if sp.rarity in ("rare", "epic", "legendary"):
            w.append(bw * bonus)
        else:
            w.append(bw)
    return random.choices(items, weights=w, k=1)[0]


def roll_fish(db: Session, spot_id: int, rod_level: int = 0) -> FishSpecies:
    pool = _pool_for_spot(db, spot_id)
    if not pool:
        pool = db.query(FishSpecies).all()
    if not pool:
        raise RuntimeError("no fish species in database")
    return _weighted_choice(pool, rod_level)


def do_fish(db: Session, player: Player) -> tuple[FishSpecies, int, dict[str, int]]:
    """校验冷却（鱼竿等级减少冷却）、随机鱼种（鱼竿等级提升稀有率）、写入库存。"""
    now = time.time()
    cd = int(settings.cast_cooldown_s)
    # Rod bonus: each level reduces cooldown by 1.5%, max 22.5%
    rod_bonus = 1.0 - min(0.225, int(player.rod_level) * ROD_SPEED_BONUS)
    cd = max(3, int(cd * rod_bonus))
    if player.last_cast_at is not None:
        elapsed = now - float(player.last_cast_at)
        if elapsed < cd:
            raise ValueError(f"cooldown:{cd - int(elapsed)}")

    sp = roll_fish(db, player.spot_id, int(player.rod_level))
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
            sp = _species_by_id(db, int(k))
            if not sp:
                continue
            c, sc = _apply_sale(sp, n)
            coins_delta += c
            score_delta += sc
            sold.append({"species_id": sp.id, "name": sp.name, "quantity": n, "coins": c, "score": sc})
            inv.pop(k, None)
    else:
        if species_id is None:
            raise ValueError("species_id_required")
        sp = _species_by_id(db, int(species_id))
        if not sp:
            raise ValueError("unknown_species")
        have = int(inv.get(str(sp.id), 0))
        if have < qty:
            raise ValueError("not_enough_fish")
        c, sc = _apply_sale(sp, qty)
        coins_delta += c
        score_delta += sc
        sold.append({"species_id": sp.id, "name": sp.name, "quantity": qty, "coins": c, "score": sc})
        left = have - qty
        if left <= 0:
            inv.pop(str(sp.id), None)
        else:
            inv[str(sp.id)] = left

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


# ── 鱼竿升级 ──

ROD_UPGRADE_COSTS: dict[int, tuple[int, int]] = {
    # level: (coins_cost, score_cost)
    1: (50, 0),
    2: (120, 0),
    3: (250, 0),
    4: (500, 0),
    5: (800, 10),
    6: (1200, 25),
    7: (1800, 50),
    8: (2500, 80),
    9: (3500, 120),
    10: (5000, 180),
    11: (7000, 250),
    12: (10000, 350),
    13: (15000, 500),
    14: (20000, 700),
    15: (30000, 1000),
}

ROD_BONUS_RATE = 0.03  # 每级提升 3% 稀有鱼出现率
ROD_SPEED_BONUS = 0.015  # 每级减少 1.5% 冷却时间

MAX_ROD_LEVEL = 15


def do_upgrade_rod(db: Session, player: Player) -> tuple[int, int, int]:
    """升级鱼竿。返回 (new_level, coins_spent, score_spent)。"""
    cur = int(player.rod_level)
    if cur >= MAX_ROD_LEVEL:
        raise ValueError("rod_max_level")
    next_lv = cur + 1
    cost = ROD_UPGRADE_COSTS.get(next_lv, (99999, 0))
    coins_cost, score_cost = cost
    if int(player.coins) < coins_cost:
        raise ValueError(f"insufficient_coins:need_{coins_cost}")
    if int(player.score) < score_cost:
        raise ValueError(f"insufficient_score:need_{score_cost}")
    player.coins = int(player.coins) - coins_cost
    player.score = int(player.score) - score_cost
    player.rod_level = next_lv
    db.add(player)
    db.commit()
    db.refresh(player)
    return next_lv, coins_cost, score_cost


def do_switch_rod(db: Session, player: Player, target_level: int) -> int:
    """自由切换鱼竿（仅限已解锁等级）。返回切换后的等级。"""
    cur = int(player.rod_level)
    target = int(target_level)
    if target > cur:
        raise ValueError(f"rod_not_unlocked:need_level_{target}")
    player.rod_level = target
    db.add(player)
    db.commit()
    db.refresh(player)
    return target


# ── 装备系统 ──

SHOP_ITEMS = {
    "torch": {"name": "手电筒", "price": 150, "desc": "夜钓照亮水面", "durability": 30},
    "bait": {"name": "鱼饵", "price": 50, "desc": "缩短等待时间22%", "durability": 20},
    "hook": {"name": "锋利钩", "price": 120, "desc": "提升稀有鱼概率+扬竿成功率", "durability": 15},
    "raincoat": {"name": "雨衣", "price": 80, "desc": "恶劣天气钓鱼不受影响", "durability": 25},
    "float_pro": {"name": "高级鱼漂", "price": 100, "desc": "咬钩提示更灵敏", "durability": 20},
}


def do_buy_equipment(db: Session, player: Player, item_key: str) -> dict:
    """购买装备（含耐久度）。返回装备信息。"""
    item = SHOP_ITEMS.get(item_key)
    if not item:
        raise ValueError("unknown_item")
    if int(player.coins) < item["price"]:
        raise ValueError(f"insufficient_coins:need_{item['price']}")
    eq = json.loads(player.equipment_json or "{}")
    eq[item_key] = {"name": item["name"], "durability": item["durability"], "max_durability": item["durability"]}
    player.coins = int(player.coins) - item["price"]
    player.equipment_json = json.dumps(eq, ensure_ascii=False, separators=(",", ":"))
    db.add(player)
    db.commit()
    db.refresh(player)
    return eq[item_key]
