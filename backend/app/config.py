from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    search_provider: Literal["auto", "ai_job_search", "html"] = "auto"
    ai_job_search_root: Path | None = None
    career_ops_project_root: Path | None = None
    career_ops_data_dir: Path | None = None
    codex_bin: str = "codex"
    node_bin: str = "node"
    codex_timeout_seconds: int = Field(default=240, ge=30, le=900)
    career_ops_doctor_timeout_seconds: int = Field(default=15, ge=1, le=60)
    career_ops_analysis_timeout_seconds: int = Field(default=900, ge=60, le=1800)
    career_ops_quick_model: str = "gpt-6-luna"
    groq_api_key: str | None = None
    groq_model: str = "openai/gpt-oss-120b"
    max_sites: int = Field(default=20, ge=1, le=50)
    max_results: int = Field(default=100, ge=1, le=500)
    supabase_url: str | None = None

    @field_validator(
        "ai_job_search_root",
        "career_ops_project_root",
        "career_ops_data_dir",
        "supabase_url",
        "groq_api_key",
        mode="before",
    )
    @classmethod
    def empty_path_is_none(cls, value: object) -> object:
        return None if value == "" else value


@lru_cache
def get_settings() -> Settings:
    return Settings()

