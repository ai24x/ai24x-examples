from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class FishingSpot(Base):
    __tablename__ = "fisher_spots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(32), default="")
    unlock_coins: Mapped[int] = mapped_column(Integer, default=0)
    unlock_score: Mapped[int] = mapped_column(Integer, default=0)
    unlock_rod_level: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[str] = mapped_column(String(256), default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    species: Mapped[list[FishSpecies]] = relationship(
        "FishSpecies", back_populates="spot", lazy="selectin"
    )


class FishSpecies(Base):
    __tablename__ = "fisher_species"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(32))
    price: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(8), default="coin")
    spot_id: Mapped[int] = mapped_column(Integer, ForeignKey("fisher_spots.id"), index=True)
    rarity: Mapped[str] = mapped_column(String(16), default="common")
    description: Mapped[str] = mapped_column(String(256), default="")
    min_rod_level: Mapped[int] = mapped_column(Integer, default=0)
    weight_min: Mapped[float] = mapped_column(Float, default=0.1)
    weight_max: Mapped[float] = mapped_column(Float, default=5.0)

    spot: Mapped[FishingSpot] = relationship("FishingSpot", back_populates="species")


class Player(Base):
    __tablename__ = "fisher_players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dev_key: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True, index=True)
    openid: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    nickname: Mapped[str] = mapped_column(String(64), default="", server_default="")
    coins: Mapped[int] = mapped_column(Integer, default=100, server_default="100")
    score: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    rod_level: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    spot_id: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    inventory_json: Mapped[str] = mapped_column(Text, default="{}", server_default="{}")
    equipment_json: Mapped[str] = mapped_column(Text, default="{}", server_default="{}")
    last_cast_at: Mapped[float | None] = mapped_column(Float, nullable=True)

    fisheries: Mapped[list["Fishery"]] = relationship("Fishery", back_populates="owner", lazy="selectin")
    assets: Mapped[list["Asset"]] = relationship("Asset", back_populates="owner", lazy="selectin")


class Fishery(Base):
    """玩家拥有的私人渔场"""
    __tablename__ = "fisher_fisheries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("fisher_players.id"), index=True)
    name: Mapped[str] = mapped_column(String(64), default="")
    land_type: Mapped[str] = mapped_column(String(16), default="pond")  # pond/lake/sea/private
    level: Mapped[int] = mapped_column(Integer, default=1)
    income_per_hour: Mapped[int] = mapped_column(Integer, default=5)
    upgrade_cost_coins: Mapped[int] = mapped_column(Integer, default=500)
    workers_max: Mapped[int] = mapped_column(Integer, default=3)
    created_at: Mapped[float | None] = mapped_column(Float, nullable=True)

    owner: Mapped[Player] = relationship("Player", back_populates="fisheries")
    workers: Mapped[list["FisheryWorker"]] = relationship("FisheryWorker", back_populates="fishery", lazy="selectin")


class FisheryWorker(Base):
    """渔场雇佣的AI渔工"""
    __tablename__ = "fisher_workers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fishery_id: Mapped[int] = mapped_column(Integer, ForeignKey("fisher_fisheries.id"), index=True)
    name: Mapped[str] = mapped_column(String(32), default="渔工")
    skill_level: Mapped[int] = mapped_column(Integer, default=1)
    catch_rate: Mapped[int] = mapped_column(Integer, default=3)  # fish/hour
    salary_per_hour: Mapped[int] = mapped_column(Integer, default=2)
    hired_at: Mapped[float | None] = mapped_column(Float, nullable=True)

    fishery: Mapped[Fishery] = relationship("Fishery", back_populates="workers")


class Asset(Base):
    """玩家拥有的资产（码头/船/游艇/度假村）"""
    __tablename__ = "fisher_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("fisher_players.id"), index=True)
    asset_type: Mapped[str] = mapped_column(String(16))  # dock/boat/yacht/resort/island
    name: Mapped[str] = mapped_column(String(64), default="")
    level: Mapped[int] = mapped_column(Integer, default=1)
    income_bonus_pct: Mapped[int] = mapped_column(Integer, default=5)  # % boost to all fishery income
    purchase_price: Mapped[int] = mapped_column(Integer, default=1000)
    purchased_at: Mapped[float | None] = mapped_column(Float, nullable=True)

    owner: Mapped[Player] = relationship("Player", back_populates="assets")


class Order(Base):
    """玩家鱼市挂单"""
    __tablename__ = "fisher_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    seller_id: Mapped[int] = mapped_column(Integer, ForeignKey("fisher_players.id"), index=True)
    buyer_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("fisher_players.id"), nullable=True)
    species_id: Mapped[int] = mapped_column(Integer, default=0)
    species_name: Mapped[str] = mapped_column(String(32), default="")
    order_type: Mapped[str] = mapped_column(String(8), default="sell")  # sell/buy
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    price_per_unit: Mapped[int] = mapped_column(Integer, default=1)
    total_price: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="active")  # active/filled/cancelled
    created_at: Mapped[float | None] = mapped_column(Float, nullable=True)
    filled_at: Mapped[float | None] = mapped_column(Float, nullable=True)
