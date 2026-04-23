from __future__ import annotations

import json
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .config import settings
from .models import Base, Player

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def inventory_load(raw: str) -> dict[str, int]:
    try:
        d = json.loads(raw or "{}")
    except Exception:
        return {}
    out: dict[str, int] = {}
    for k, v in d.items():
        try:
            n = int(v)
        except Exception:
            continue
        if n > 0:
            out[str(k)] = n
    return out


def inventory_dump(inv: dict[str, int]) -> str:
    return json.dumps(inv, ensure_ascii=False, separators=(",", ":"))


def get_or_create_dev_player(db: Session, dev_key: str) -> Player:
    key = (dev_key or "").strip()
    if not key:
        raise ValueError("empty dev_key")
    p = db.query(Player).filter(Player.dev_key == key).one_or_none()
    if p:
        return p
    p = Player(dev_key=key, coins=100, score=0, rod_level=0, spot_id=0, inventory_json="{}")
    db.add(p)
    db.commit()
    db.refresh(p)
    return p
