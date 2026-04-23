from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv
from sqlalchemy.engine import make_url


def _to_int(v: str | None, default: int) -> int:
    try:
        return int(v) if v is not None else default
    except Exception:
        return default


@dataclass(frozen=True)
class Settings:
    env: str
    database_url: str
    jwt_secret: str
    jwt_expire_days: int
    cast_cooldown_s: int
    cors_origins: str


def _assert_postgres_url(url: str) -> str:
    s = (url or "").strip()
    if not s:
        raise ValueError("FISHER_DATABASE_URL is required (PostgreSQL, e.g. postgresql+psycopg2://user:pass@127.0.0.1:5432/fisher)")
    try:
        u = make_url(s)
    except Exception as e:  # noqa: BLE001
        raise ValueError(f"Invalid FISHER_DATABASE_URL: {e}") from e
    d = (u.drivername or "").lower()
    if d in ("sqlite", "pysqlite") or d.startswith("sqlite+"):
        raise ValueError("SQLite is not supported. Set FISHER_DATABASE_URL to a PostgreSQL URL.")
    if d not in ("postgres", "postgresql") and not d.startswith("postgresql+"):
        raise ValueError("FISHER_DATABASE_URL must use the PostgreSQL driver (e.g. postgresql+psycopg2://...).")
    return s


def load_settings() -> Settings:
    load_dotenv(override=False)
    raw = os.getenv(
        "FISHER_DATABASE_URL",
        "postgresql+psycopg2://fisher:fisher@127.0.0.1:5432/fisher",
    )
    return Settings(
        env=os.getenv("FISHER_ENV", "dev").strip().lower(),
        database_url=_assert_postgres_url(raw),
        jwt_secret=os.getenv("FISHER_JWT_SECRET", "change-me-fisher-jwt").strip(),
        jwt_expire_days=max(1, _to_int(os.getenv("FISHER_JWT_EXPIRE_DAYS"), 7)),
        cast_cooldown_s=max(1, _to_int(os.getenv("FISHER_CAST_COOLDOWN_S"), 8)),
        cors_origins=os.getenv("FISHER_CORS_ORIGINS", "*").strip(),
    )


settings = load_settings()
