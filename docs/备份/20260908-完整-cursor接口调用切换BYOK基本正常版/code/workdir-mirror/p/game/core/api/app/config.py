from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "game-core"
    debug: bool = True
    jwt_secret: str = "change-me-in-env"
    jwt_expire_days: int = 30
    # 本机 PG15 测试库（可先用 a1 预发库，见 core/docs/schema.md）
    database_url: str = "postgresql+psycopg2://postgres:postgres@127.0.0.1:5432/game_core"
    wx_appid: str = ""
    wx_secret: str = ""


settings = Settings()
