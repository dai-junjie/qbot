from __future__ import annotations

from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="QBOT_",
        extra="ignore",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    enabled_groups: Annotated[list[str], NoDecode] = Field(default_factory=list)
    db_path: Path = Path("data/qbot.sqlite3")
    history_window_hours: int = 24
    retention_days: int = 30
    font_path: str | None = None

    @field_validator("enabled_groups", mode="before")
    @classmethod
    def _parse_groups(cls, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, int):
            return [str(value)]
        if isinstance(value, str):
            chunks = [p.strip() for p in value.split(",") if p.strip()]
            return chunks
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        raise ValueError("QBOT_ENABLED_GROUPS must be comma separated string or list")


settings = Settings()
