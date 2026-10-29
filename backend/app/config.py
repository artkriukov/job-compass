from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    search_provider: Literal["auto", "ai_job_search", "html"] = "auto"
    ai_job_search_root: Path | None = None
    codex_bin: str = "codex"
    codex_timeout_seconds: int = Field(default=240, ge=30, le=900)
    max_sites: int = Field(default=20, ge=1, le=50)
    max_results: int = Field(default=100, ge=1, le=500)

    @field_validator("ai_job_search_root", mode="before")
    @classmethod
    def empty_path_is_none(cls, value: object) -> object:
        return None if value == "" else value


@lru_cache
def get_settings() -> Settings:
    return Settings()

