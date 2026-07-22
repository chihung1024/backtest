from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BACKTEST_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"
    api_key: str | None = None
    cors_origins: str = "http://localhost:5173,https://chihung1024.github.io"
    fred_api_key: str | None = None
    cache_ttl_seconds: int = Field(default=21_600, ge=60, le=604_800)
    max_assets_per_request: int = Field(default=64, ge=1, le=100)

    @property
    def cors_origin_list(self) -> list[str]:
        return [
            origin.strip().rstrip("/")
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
