from __future__ import annotations

from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


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
    last_cast_at: Mapped[float | None] = mapped_column(Float, nullable=True)
