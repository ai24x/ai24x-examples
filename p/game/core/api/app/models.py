from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class User(Base):
    __tablename__ = "gc_users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    appid: Mapped[str] = mapped_column(String(64), index=True)
    openid: Mapped[str] = mapped_column(String(64), index=True)
    unionid: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    nickname: Mapped[str] = mapped_column(String(64), default="")
    avatar: Mapped[str] = mapped_column(String(512), default="")
    stars: Mapped[int] = mapped_column(Integer, default=0)
    level: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Game(Base):
    __tablename__ = "gc_games"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(128))
    wx_appid: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(16), default="draft")  # draft/review/live/paused
    platform: Mapped[str] = mapped_column(String(16), default="wechat")


class Leaderboard(Base):
    __tablename__ = "gc_leaderboards"
    __table_args__ = (Index("ix_lb_query", "game_id", "scope", "period", "seed"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    game_id: Mapped[int] = mapped_column(Integer)
    scope: Mapped[str] = mapped_column(String(16), default="all")  # all/daily/friends
    period: Mapped[str] = mapped_column(String(16), default="")  # YYYY-MM-DD
    seed: Mapped[str] = mapped_column(String(64), default="")
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    score: Mapped[int] = mapped_column(Integer, default=0)
    payload: Mapped[str] = mapped_column(Text, default="{}")
    rank: Mapped[int] = mapped_column(Integer, default=0)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Challenge(Base):
    __tablename__ = "gc_challenges"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    game_id: Mapped[int] = mapped_column(Integer, index=True)
    seed: Mapped[str] = mapped_column(String(64))
    from_user: Mapped[int] = mapped_column(BigInteger, index=True)
    to_user: Mapped[int] = mapped_column(BigInteger, index=True)
    from_score: Mapped[int] = mapped_column(Integer, default=0)
    to_score: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="sent")  # sent/accepted/done/expired
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Event(Base):
    __tablename__ = "gc_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    appid: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True, default=0)
    event: Mapped[str] = mapped_column(String(64), index=True)
    params: Mapped[str] = mapped_column(Text, default="{}")
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AdReward(Base):
    __tablename__ = "gc_ad_rewards"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    game_id: Mapped[int] = mapped_column(Integer)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    slot_key: Mapped[str] = mapped_column(String(32))
    reward_type: Mapped[str] = mapped_column(String(16))
    reward_value: Mapped[int] = mapped_column(Integer, default=0)
    verify_token: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending/paid/void
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StarsTransaction(Base):
    __tablename__ = "gc_stars_transactions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    delta: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(32))
    ref: Mapped[str] = mapped_column(String(64), default="")
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
