from __future__ import annotations

import json
import logging

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from . import db as dbmod
from .auth_jwt import create_access_token, get_current_player
from .config import settings
from .security import SecurityMiddleware
from .game_service import SHOP_ITEMS, do_buy_equipment, do_fish, do_sell, do_upgrade_rod, do_switch_rod
from .models import Asset, FishSpecies, Fishery, FisheryWorker, FishingSpot, Order, Player
from .fishery_service import (
    buy_asset, buy_fishery, collect_income, dismiss_worker,
    hire_worker, upgrade_fishery, ASSET_SHOP, FISHERY_SHOP,
)
from .schemas import (
    DevLoginIn,
    DevLoginOut,
    FishOut,
    MeOut,
    SellIn,
    SellOut,
    SpotOut,
    SpeciesOut,
    SwitchSpotIn,
)
from .seed_data import seed_catalog

logger = logging.getLogger(__name__)

app = FastAPI(title="山海渔 Fisher API", version="0.2.0")


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

# 安全中间件（域名校验 + 速率限制）
app.add_middleware(SecurityMiddleware)


@app.on_event("startup")
def _startup() -> None:
    dbmod.init_db()
    db = next(dbmod.get_db())
    try:
        seed_catalog(db)
    finally:
        db.close()
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
            "spots": "GET /v1/catalog/spots",
            "species": "GET /v1/catalog/species",
            "switch_spot": "POST /v1/game/spot",
            "upgrade_rod": "POST /v1/game/upgrade-rod",
            "switch_rod": "POST /v1/game/switch-rod",
            "shop": "GET /v1/game/shop",
            "buy_item": "POST /v1/game/buy-item",
        },
    }


# ── Auth ──

@app.post("/v1/auth/dev-login", response_model=DevLoginOut)
def dev_login(body: DevLoginIn, db: Session = Depends(dbmod.get_db)) -> DevLoginOut:
    try:
        p = dbmod.get_or_create_dev_player(db, body.dev_key)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid dev_key")
    token = create_access_token(sub=str(p.id), extra={"typ": "dev"})
    return DevLoginOut(access_token=token, expires_in_days=settings.jwt_expire_days)


@app.get("/v1/me", response_model=MeOut)
def me(player: Player = Depends(get_current_player), db: Session = Depends(dbmod.get_db)) -> MeOut:
    db.refresh(player)  # ensure fresh data after equipment buy in same session
    inv = dbmod.inventory_load(player.inventory_json)
    eq = json.loads(player.equipment_json or "{}")
    spot = db.query(FishingSpot).filter(FishingSpot.id == int(player.spot_id)).one_or_none()
    spot_name = spot.name if spot else "未知钓场"
    return MeOut(
        id=int(player.id),
        coins=int(player.coins),
        score=int(player.score),
        rod_level=int(player.rod_level),
        spot_id=int(player.spot_id),
        spot_name=spot_name,
        inventory=inv,
        equipment=eq,
    )


# ── Catalog (public, no auth needed during dev) ──

@app.get("/v1/catalog/spots", response_model=list[SpotOut])
def list_spots(db: Session = Depends(dbmod.get_db)) -> list[SpotOut]:
    spots = db.query(FishingSpot).order_by(FishingSpot.sort_order).all()
    return [SpotOut.model_validate(s) for s in spots]


@app.get("/v1/catalog/species", response_model=list[SpeciesOut])
def list_species(
    spot_id: int | None = Query(None),
    db: Session = Depends(dbmod.get_db),
) -> list[SpeciesOut]:
    q = db.query(FishSpecies)
    if spot_id is not None:
        q = q.filter(FishSpecies.spot_id == spot_id)
    rows = q.order_by(FishSpecies.id).all()
    return [SpeciesOut.model_validate(r) for r in rows]


# ── Game ──

@app.post("/v1/game/spot")
def switch_spot(
    body: SwitchSpotIn,
    player: Player = Depends(get_current_player),
    db: Session = Depends(dbmod.get_db),
) -> dict:
    """切换钓场：检查解锁条件，满足后更新玩家的 spot_id。"""
    spot = db.query(FishingSpot).filter(FishingSpot.id == body.spot_id).one_or_none()
    if not spot:
        raise HTTPException(status_code=404, detail="spot not found")
    if int(player.coins) < spot.unlock_coins:
        raise HTTPException(status_code=400, detail=f"insufficient coins: need {spot.unlock_coins}")
    if int(player.score) < spot.unlock_score:
        raise HTTPException(status_code=400, detail=f"insufficient score: need {spot.unlock_score}")
    if int(player.rod_level) < spot.unlock_rod_level:
        raise HTTPException(status_code=400, detail=f"rod level too low: need {spot.unlock_rod_level}")

    if int(player.spot_id) == spot.id:
        return {"ok": True, "spot_id": spot.id, "spot_name": spot.name, "message": "already in this spot"}

    old_spot_id = int(player.spot_id)
    player.spot_id = spot.id
    db.add(player)
    db.commit()
    db.refresh(player)
    logger.info("player %d switched spot %d -> %d", player.id, old_spot_id, spot.id)
    return {"ok": True, "spot_id": spot.id, "spot_name": spot.name, "old_spot_id": old_spot_id}


@app.post("/v1/game/fish", response_model=FishOut)
def fish_one(
    player: Player = Depends(get_current_player),
    db: Session = Depends(dbmod.get_db),
) -> FishOut:
    try:
        sp, cd, inv = do_fish(db, player)
    except ValueError as e:
        msg = str(e)
        if msg.startswith("cooldown:"):
            rem = int(msg.split(":", 1)[1])
            raise HTTPException(status_code=429, detail={"code": "cooldown", "retry_after_s": rem})
        raise HTTPException(status_code=400, detail=msg)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    return FishOut(
        species_id=sp.id,
        name=sp.name,
        currency=sp.currency,
        unit_value=sp.price,
        cooldown_s=int(settings.cast_cooldown_s),
        inventory=inv,
    )


@app.post("/v1/game/sell", response_model=SellOut)
def sell(
    body: SellIn,
    player: Player = Depends(get_current_player),
    db: Session = Depends(dbmod.get_db),
) -> SellOut:
    try:
        c_delta, s_delta, inv, sold = do_sell(
            db, player, sell_all=bool(body.sell_all), species_id=body.species_id, quantity=int(body.quantity)
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


# ── 鱼竿升级 ──

@app.post("/v1/game/upgrade-rod")
def upgrade_rod(
    player: Player = Depends(get_current_player),
    db: Session = Depends(dbmod.get_db),
) -> dict:
    try:
        new_lv, coins_cost, score_cost = do_upgrade_rod(db, player)
    except ValueError as e:
        msg = str(e)
        if msg == "rod_max_level":
            raise HTTPException(status_code=400, detail="鱼竿已达最高等级(15级)")
        if msg.startswith("insufficient_coins"):
            need = msg.split(":need_")[1] if ":need_" in msg else "?"
            raise HTTPException(status_code=400, detail=f"金币不足，需要{need}")
        if msg.startswith("insufficient_score"):
            need = msg.split(":need_")[1] if ":need_" in msg else "?"
            raise HTTPException(status_code=400, detail=f"阅历不足，需要{need}")
        raise HTTPException(status_code=400, detail=msg)
    return {"ok": True, "rod_level": new_lv, "coins_spent": coins_cost, "score_spent": score_cost,
            "coins": int(player.coins), "score": int(player.score)}


# ── 鱼竿自由切换（仅限已解锁等级） ──

@app.post("/v1/game/switch-rod")
def switch_rod(
    body: dict,
    player: Player = Depends(get_current_player),
    db: Session = Depends(dbmod.get_db),
) -> dict:
    target_level = int(body.get("rod_level", 0))
    try:
        new_lv = do_switch_rod(db, player, target_level)
    except ValueError as e:
        msg = str(e)
        if msg.startswith("rod_not_unlocked"):
            need = msg.split("_")[-1]
            raise HTTPException(status_code=400, detail=f"该鱼竿尚未解锁，需要先升级到Lv.{need}")
        raise HTTPException(status_code=400, detail=msg)
    return {"ok": True, "rod_level": new_lv, "coins": int(player.coins), "score": int(player.score)}


# ── 商店/装备 ──

@app.get("/v1/game/shop")
def list_shop() -> dict:
    return {"items": SHOP_ITEMS}


@app.post("/v1/game/buy-item")
def buy_item(
    body: dict,
    player: Player = Depends(get_current_player),
    db: Session = Depends(dbmod.get_db),
) -> dict:
    item_key = str(body.get("item_key", "")).strip()
    if not item_key:
        raise HTTPException(status_code=400, detail="item_key required")
    try:
        eq_info = do_buy_equipment(db, player, item_key)
    except ValueError as e:
        msg = str(e)
        if msg == "unknown_item":
            raise HTTPException(status_code=404, detail="未知道具")
        if msg.startswith("insufficient_coins"):
            need = msg.split(":need_")[1]
            raise HTTPException(status_code=400, detail=f"金币不足，需要{need}")
        raise HTTPException(status_code=400, detail=msg)
    return {"ok": True, "item_key": item_key, "equipment": eq_info, "coins": int(player.coins)}


# ── 渔场经营 ──

@app.get("/v1/fishery/shop")
def fishery_shop_info() -> dict:
    return {"fisheries": FISHERY_SHOP, "assets": ASSET_SHOP}


@app.get("/v1/fishery/my")
def my_fisheries(
    player: Player = Depends(get_current_player),
    db: Session = Depends(dbmod.get_db),
) -> dict:
    fisheries = db.query(Fishery).filter(Fishery.owner_id == player.id).all()
    assets = db.query(Asset).filter(Asset.owner_id == player.id).all()
    fishery_list = []
    for f in fisheries:
        workers = db.query(FisheryWorker).filter(FisheryWorker.fishery_id == f.id).all()
        fishery_list.append({
            "id": f.id, "name": f.name, "land_type": f.land_type, "level": f.level,
            "income_per_hour": f.income_per_hour, "upgrade_cost": f.upgrade_cost_coins,
            "workers_max": f.workers_max, "worker_count": len(workers),
            "workers": [{"id": w.id, "name": w.name, "skill": w.skill_level, "catch_rate": w.catch_rate} for w in workers],
        })
    asset_list = [{"id": a.id, "type": a.asset_type, "name": a.name, "bonus_pct": a.income_bonus_pct, "price": a.purchase_price} for a in assets]
    return {"fisheries": fishery_list, "assets": asset_list, "coins": int(player.coins)}


@app.post("/v1/fishery/buy")
def buy_fishery_endpoint(
    body: dict,
    player: Player = Depends(get_current_player),
    db: Session = Depends(dbmod.get_db),
) -> dict:
    land_type = str(body.get("land_type", "")).strip()
    if not land_type:
        raise HTTPException(status_code=400, detail="land_type required")
    try:
        fishery = buy_fishery(db, player, land_type)
    except ValueError as e:
        msg = str(e)
        if msg == "unknown_land_type":
            raise HTTPException(status_code=400, detail="未知渔场类型")
        if msg.startswith("insufficient_coins"):
            raise HTTPException(status_code=400, detail=f"金币不足，需要{msg.split(':need_')[1]}")
        raise HTTPException(status_code=400, detail=msg)
    return {"ok": True, "fishery_id": fishery.id, "name": fishery.name, "coins": int(player.coins)}


@app.post("/v1/fishery/upgrade/{fishery_id}")
def upgrade_fishery_endpoint(
    fishery_id: int,
    player: Player = Depends(get_current_player),
    db: Session = Depends(dbmod.get_db),
) -> dict:
    try:
        fishery = upgrade_fishery(db, player, fishery_id)
    except ValueError as e:
        msg = str(e)
        if msg == "fishery_not_found":
            raise HTTPException(status_code=404, detail="渔场不存在")
        if msg.startswith("insufficient_coins"):
            raise HTTPException(status_code=400, detail=f"金币不足，需要{msg.split(':need_')[1]}")
        raise HTTPException(status_code=400, detail=msg)
    return {"ok": True, "fishery_id": fishery.id, "level": fishery.level, "income": fishery.income_per_hour, "coins": int(player.coins)}


@app.post("/v1/fishery/hire/{fishery_id}")
def hire_worker_endpoint(
    fishery_id: int,
    player: Player = Depends(get_current_player),
    db: Session = Depends(dbmod.get_db),
) -> dict:
    try:
        worker = hire_worker(db, player, fishery_id)
    except ValueError as e:
        msg = str(e)
        if msg == "fishery_not_found":
            raise HTTPException(status_code=404, detail="渔场不存在")
        if msg == "workers_full":
            raise HTTPException(status_code=400, detail="渔工已满，请升级渔场")
        if msg.startswith("insufficient_coins"):
            raise HTTPException(status_code=400, detail=f"金币不足，需要{msg.split(':need_')[1]}")
        raise HTTPException(status_code=400, detail=msg)
    return {"ok": True, "worker_id": worker.id, "name": worker.name, "skill": worker.skill_level, "coins": int(player.coins)}


@app.delete("/v1/fishery/worker/{worker_id}")
def dismiss_worker_endpoint(
    worker_id: int,
    player: Player = Depends(get_current_player),
    db: Session = Depends(dbmod.get_db),
) -> dict:
    try:
        dismiss_worker(db, worker_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="渔工不存在")
    return {"ok": True}


@app.post("/v1/fishery/collect")
def collect_income_endpoint(
    player: Player = Depends(get_current_player),
    db: Session = Depends(dbmod.get_db),
) -> dict:
    try:
        result = collect_income(db, player)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True, **result}


@app.post("/v1/fishery/buy-asset")
def buy_asset_endpoint(
    body: dict,
    player: Player = Depends(get_current_player),
    db: Session = Depends(dbmod.get_db),
) -> dict:
    asset_type = str(body.get("asset_type", "")).strip()
    if not asset_type:
        raise HTTPException(status_code=400, detail="asset_type required")
    try:
        asset = buy_asset(db, player, asset_type)
    except ValueError as e:
        msg = str(e)
        if msg == "unknown_asset_type":
            raise HTTPException(status_code=400, detail="未知资产类型")
        if msg == "already_owned":
            raise HTTPException(status_code=400, detail="已拥有该资产")
        if msg.startswith("insufficient_coins"):
            raise HTTPException(status_code=400, detail=f"金币不足，需要{msg.split(':need_')[1]}")
        raise HTTPException(status_code=400, detail=msg)
    return {"ok": True, "asset_id": asset.id, "name": asset.name, "bonus_pct": asset.income_bonus_pct, "coins": int(player.coins)}


# ── 鱼市交易 ──

import time as _time

@app.get("/v1/market/orders")
def market_orders(
    player: Player = Depends(get_current_player),
    db: Session = Depends(dbmod.get_db),
) -> dict:
    """获取所有活跃挂单 + 我的订单"""
    active = db.query(Order).filter(Order.status == "active").order_by(Order.created_at.desc()).limit(50).all()
    mine = db.query(Order).filter(Order.seller_id == player.id).order_by(Order.created_at.desc()).limit(20).all()
    return {
        "active": [{"id": o.id, "species_name": o.species_name, "order_type": o.order_type,
                     "quantity": o.quantity, "price_per_unit": o.price_per_unit, "total_price": o.total_price,
                     "seller_id": o.seller_id} for o in active],
        "my_orders": [{"id": o.id, "species_name": o.species_name, "order_type": o.order_type,
                        "quantity": o.quantity, "price_per_unit": o.price_per_unit, "status": o.status} for o in mine],
    }


@app.post("/v1/market/list")
def market_list(
    body: dict,
    player: Player = Depends(get_current_player),
    db: Session = Depends(dbmod.get_db),
) -> dict:
    """挂单出售鱼获"""
    species_name = str(body.get("species_name", "")).strip()
    quantity = max(1, int(body.get("quantity", 1)))
    price = max(1, int(body.get("price_per_unit", 1)))
    if not species_name:
        raise HTTPException(status_code=400, detail="species_name required")
    # Check inventory
    inv = dbmod.inventory_load(player.inventory_json)
    have = 0
    target_key = None
    for k, v in inv.items():
        sp = db.query(FishSpecies).filter(FishSpecies.id == int(k)).one_or_none()
        if sp and sp.name == species_name:
            have = v
            target_key = k
            break
    if have < quantity:
        raise HTTPException(status_code=400, detail="库存不足")
    # Deduct from inventory
    left = have - quantity
    if left <= 0:
        inv.pop(target_key, None)
    else:
        inv[target_key] = left
    player.inventory_json = dbmod.inventory_dump(inv)
    # Create order
    order = Order(
        seller_id=player.id, species_id=int(target_key or 0), species_name=species_name,
        order_type="sell", quantity=quantity, price_per_unit=price,
        total_price=price * quantity, status="active", created_at=_time.time(),
    )
    db.add(player)
    db.add(order)
    db.commit()
    db.refresh(order)
    return {"ok": True, "order_id": order.id, "quantity": quantity, "total_price": order.total_price}


@app.post("/v1/market/buy/{order_id}")
def market_buy(
    order_id: int,
    player: Player = Depends(get_current_player),
    db: Session = Depends(dbmod.get_db),
) -> dict:
    """购买挂单"""
    order = db.query(Order).filter(Order.id == order_id, Order.status == "active").one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在或已成交")
    if order.seller_id == player.id:
        raise HTTPException(status_code=400, detail="不能买自己的订单")
    if int(player.coins) < order.total_price:
        raise HTTPException(status_code=400, detail=f"金币不足，需要{order.total_price}")
    # Transfer coins
    seller = db.get(Player, order.seller_id)
    player.coins = int(player.coins) - order.total_price
    if seller:
        seller.coins = int(seller.coins) + order.total_price
        db.add(seller)
    # Give fish to buyer
    inv = dbmod.inventory_load(player.inventory_json)
    k = str(order.species_id or order.species_name)
    inv[k] = inv.get(k, 0) + order.quantity
    player.inventory_json = dbmod.inventory_dump(inv)
    # Mark order filled
    order.status = "filled"
    order.buyer_id = player.id
    order.filled_at = _time.time()
    db.add(player)
    db.add(order)
    db.commit()
    return {"ok": True, "species_name": order.species_name, "quantity": order.quantity, "paid": order.total_price, "coins": int(player.coins)}


@app.delete("/v1/market/cancel/{order_id}")
def market_cancel(
    order_id: int,
    player: Player = Depends(get_current_player),
    db: Session = Depends(dbmod.get_db),
) -> dict:
    """撤单（退还鱼获）"""
    order = db.query(Order).filter(Order.id == order_id, Order.seller_id == player.id, Order.status == "active").one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在或已成交")
    # Return fish to inventory
    inv = dbmod.inventory_load(player.inventory_json)
    k = str(order.species_id or order.species_name)
    inv[k] = inv.get(k, 0) + order.quantity
    player.inventory_json = dbmod.inventory_dump(inv)
    order.status = "cancelled"
    db.add(player)
    db.add(order)
    db.commit()
    return {"ok": True}
