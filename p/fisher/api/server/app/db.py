from __future__ import annotations

import json
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from .config import settings
from .models import Base, Player


def _ensure_sqlite_dir(url: str) -> None:
    if url.startswith("sqlite:///"):
        path = url.replace("sqlite:///", "", 1)
        if path and path != ":memory:":
            p = Path(path)
            if not p.is_absolute():
                p = Path.cwd() / p
            p.parent.mkdir(parents=True, exist_ok=True)


_ensure_sqlite_dir(settings.database_url)

connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


@event.listens_for(engine, "connect")
def _sqlite_pragma(dbapi_connection, connection_record):  # noqa: ARG001
    if settings.database_url.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


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
