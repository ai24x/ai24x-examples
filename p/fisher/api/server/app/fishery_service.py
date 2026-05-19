"""渔场经营：买地、升级、雇工、资产、收租"""

from __future__ import annotations

import time

from sqlalchemy.orm import Session

from .models import Asset, Fishery, FisheryWorker, Player

# ── 渔场价格表 ──
FISHERY_SHOP = [
    {"type": "pond", "name": "私人鱼塘", "price": 500, "income": 5, "workers_max": 2, "desc": "一块安静的私人鱼塘"},
    {"type": "lake", "name": "湖畔渔场", "price": 2000, "income": 15, "workers_max": 4, "desc": "湖边的中型渔场"},
    {"type": "sea", "name": "近海渔场", "price": 8000, "income": 50, "workers_max": 6, "desc": "近海的商业渔场"},
    {"type": "private", "name": "秘境渔场", "price": 30000, "income": 200, "workers_max": 10, "desc": "只属于你的秘密钓点"},
]

FISHERY_UPGRADE_MULTIPLIER = 2.5  # 每升一级价格 ×2.5
FISHERY_INCOME_MULTIPLIER = 1.6  # 每升一级收入 ×1.6

# ── 资产商店 ──
ASSET_SHOP = [
    {"type": "dock", "name": "木质码头", "price": 3000, "bonus": 10, "desc": "渔获收购价+10%"},
    {"type": "boat", "name": "小型渔船", "price": 8000, "bonus": 20, "desc": "渔场收入+20%"},
    {"type": "yacht", "name": "豪华游艇", "price": 25000, "bonus": 40, "desc": "渔场收入+40%，解锁专属鱼种"},
    {"type": "resort", "name": "度假村", "price": 80000, "bonus": 80, "desc": "渔场收入+80%，可接待NPC游客"},
    {"type": "island", "name": "私人海岛", "price": 500000, "bonus": 150, "desc": "终极资产，渔场收入+150%"},
]

# ── 渔工名字池 ──
WORKER_NAMES = ["老张", "小李", "阿强", "海哥", "渔伯", "浪子", "船头", "阿福", "老船长", "小陈"]


def buy_fishery(db: Session, player: Player, land_type: str) -> Fishery:
    """购买新渔场。"""
    shop_item = next((s for s in FISHERY_SHOP if s["type"] == land_type), None)
    if not shop_item:
        raise ValueError("unknown_land_type")
    if int(player.coins) < shop_item["price"]:
        raise ValueError(f"insufficient_coins:need_{shop_item['price']}")

    fishery = Fishery(
        owner_id=player.id,
        name=f"{player.nickname or '渔隐'}的{shop_item['name']}",
        land_type=land_type,
        level=1,
        income_per_hour=shop_item["income"],
        upgrade_cost_coins=int(shop_item["price"] * FISHERY_UPGRADE_MULTIPLIER),
        workers_max=shop_item["workers_max"],
        created_at=time.time(),
    )
    player.coins = int(player.coins) - shop_item["price"]
    db.add(player)
    db.add(fishery)
    db.commit()
    db.refresh(fishery)
    return fishery


def upgrade_fishery(db: Session, player: Player, fishery_id: int) -> Fishery:
    """升级渔场。"""
    fishery = db.query(Fishery).filter(Fishery.id == fishery_id, Fishery.owner_id == player.id).one_or_none()
    if not fishery:
        raise ValueError("fishery_not_found")
    cost = int(fishery.upgrade_cost_coins)
    if int(player.coins) < cost:
        raise ValueError(f"insufficient_coins:need_{cost}")

    fishery.level += 1
    fishery.income_per_hour = int(fishery.income_per_hour * FISHERY_INCOME_MULTIPLIER)
    fishery.upgrade_cost_coins = int(cost * FISHERY_UPGRADE_MULTIPLIER)
    player.coins = int(player.coins) - cost
    db.add(player)
    db.add(fishery)
    db.commit()
    db.refresh(fishery)
    return fishery


def hire_worker(db: Session, player: Player, fishery_id: int) -> FisheryWorker:
    """雇佣渔工。"""
    fishery = db.query(Fishery).filter(Fishery.id == fishery_id, Fishery.owner_id == player.id).one_or_none()
    if not fishery:
        raise ValueError("fishery_not_found")
    worker_count = db.query(FisheryWorker).filter(FisheryWorker.fishery_id == fishery_id).count()
    if worker_count >= fishery.workers_max:
        raise ValueError("workers_full")
    hire_cost = 200 + (fishery.level * 100)
    if int(player.coins) < hire_cost:
        raise ValueError(f"insufficient_coins:need_{hire_cost}")

    import random
    name = random.choice(WORKER_NAMES)
    skill = min(10, 1 + fishery.level + random.randint(0, 2))
    worker = FisheryWorker(
        fishery_id=fishery_id,
        name=name,
        skill_level=skill,
        catch_rate=fishery.income_per_hour // 3 + skill,
        salary_per_hour=max(1, skill // 2),
        hired_at=time.time(),
    )
    player.coins = int(player.coins) - hire_cost
    db.add(player)
    db.add(worker)
    db.commit()
    db.refresh(worker)
    return worker


def dismiss_worker(db: Session, worker_id: int) -> None:
    """解雇渔工。"""
    w = db.query(FisheryWorker).filter(FisheryWorker.id == worker_id).one_or_none()
    if not w:
        raise ValueError("worker_not_found")
    db.delete(w)
    db.commit()


def buy_asset(db: Session, player: Player, asset_type: str) -> Asset:
    """购买资产（码头/船/游艇等）。"""
    shop_item = next((a for a in ASSET_SHOP if a["type"] == asset_type), None)
    if not shop_item:
        raise ValueError("unknown_asset_type")
    if int(player.coins) < shop_item["price"]:
        raise ValueError(f"insufficient_coins:need_{shop_item['price']}")

    existing = db.query(Asset).filter(Asset.owner_id == player.id, Asset.asset_type == asset_type).first()
    if existing:
        raise ValueError("already_owned")

    asset = Asset(
        owner_id=player.id,
        asset_type=asset_type,
        name=shop_item["name"],
        level=1,
        income_bonus_pct=shop_item["bonus"],
        purchase_price=shop_item["price"],
        purchased_at=time.time(),
    )
    player.coins = int(player.coins) - shop_item["price"]
    db.add(player)
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


def collect_income(db: Session, player: Player) -> dict:
    """收租：计算所有渔场+渔工+资产的总收入。"""
    fisheries = db.query(Fishery).filter(Fishery.owner_id == player.id).all()
    asset_bonus = sum(a.income_bonus_pct for a in
                       db.query(Asset).filter(Asset.owner_id == player.id).all())
    total = 0
    details = []
    for f in fisheries:
        workers = db.query(FisheryWorker).filter(FisheryWorker.fishery_id == f.id).all()
        worker_income = sum(w.catch_rate for w in workers)
        worker_salary = sum(w.salary_per_hour for w in workers)
        net = max(0, f.income_per_hour + worker_income - worker_salary)
        if asset_bonus > 0:
            net = int(net * (1 + asset_bonus / 100))
        total += net
        details.append({
            "fishery_id": f.id, "name": f.name, "level": f.level,
            "base_income": f.income_per_hour, "worker_income": worker_income,
            "worker_salary": worker_salary, "asset_bonus_pct": asset_bonus, "net": net,
        })
    player.coins = int(player.coins) + total
    player.score = int(player.score) + max(1, total // 10)
    db.add(player)
    db.commit()
    db.refresh(player)
    return {"total_income": total, "details": details, "coins": int(player.coins), "score": int(player.score)}
