from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="QBOT_", extra="ignore")

    enabled_groups: list[int] = Field(default_factory=list)
    db_path: Path = Path("data/qbot.sqlite3")
    history_window_hours: int = 24
    retention_days: int = 30
    font_path: str | None = None

    @field_validator("enabled_groups", mode="before")
    @classmethod
    def _parse_groups(cls, value: object) -> list[int]:
        if value is None:
            return []
        if isinstance(value, str):
            chunks = [p.strip() for p in value.split(",") if p.strip()]
            return [int(part) for part in chunks]
        if isinstance(value, list):
            return [int(v) for v in value]
        raise ValueError("QBOT_ENABLED_GROUPS must be comma separated string or list")


settings = Settings()
