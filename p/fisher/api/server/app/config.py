from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


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


def load_settings() -> Settings:
    load_dotenv(override=False)
    return Settings(
        env=os.getenv("FISHER_ENV", "dev").strip().lower(),
        database_url=os.getenv("FISHER_DATABASE_URL", "sqlite:///./data/fisher.db").strip(),
        jwt_secret=os.getenv("FISHER_JWT_SECRET", "change-me-fisher-jwt").strip(),
        jwt_expire_days=max(1, _to_int(os.getenv("FISHER_JWT_EXPIRE_DAYS"), 7)),
        cast_cooldown_s=max(1, _to_int(os.getenv("FISHER_CAST_COOLDOWN_S"), 8)),
        cors_origins=os.getenv("FISHER_CORS_ORIGINS", "*").strip(),
    )


settings = load_settings()
