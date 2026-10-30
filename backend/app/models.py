from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, field_validator


class SearchRequest(BaseModel):
    sites: Annotated[list[HttpUrl], Field(min_length=1, max_length=50)]
    role: Annotated[str, Field(min_length=2, max_length=160)]
    include_keywords: Annotated[list[str], Field(max_length=20)] = Field(default_factory=list)
    exclude_keywords: Annotated[list[str], Field(max_length=20)] = Field(default_factory=list)

    @field_validator("sites")
    @classmethod
    def unique_sites(cls, sites: list[HttpUrl]) -> list[HttpUrl]:
        unique: dict[str, HttpUrl] = {}
        for site in sites:
            unique[str(site)] = site
        return list(unique.values())

    @field_validator("role")
    @classmethod
    def clean_role(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("include_keywords", "exclude_keywords")
    @classmethod
    def clean_keywords(cls, values: list[str]) -> list[str]:
        cleaned = {" ".join(value.split()).lower() for value in values if value.strip()}
        return sorted(cleaned)


class Vacancy(BaseModel):
    title: str
    company: str | None = None
    location: str | None = None
    url: HttpUrl
    score: int = Field(ge=0, le=100)
    reason: str
    source_site: HttpUrl
    seen_before: bool = False
    applied: bool = False


class SearchResponse(BaseModel):
    provider: Literal["ai_job_search", "site_crawler"]
    vacancies: list[Vacancy]
    warnings: list[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    configured_provider: Literal["auto", "ai_job_search", "html"]
    ai_job_search_ready: bool
    settings_storage_ready: bool


class SavedCareerSite(BaseModel):
    id: UUID
    name: Annotated[str, Field(min_length=1, max_length=120)]
    url: HttpUrl


class SavedJobRole(BaseModel):
    id: UUID
    title: Annotated[str, Field(min_length=2, max_length=160)]


class SearchSettingsSnapshot(BaseModel):
    sites: Annotated[list[SavedCareerSite], Field(max_length=50)] = Field(default_factory=list)
    roles: Annotated[list[SavedJobRole], Field(max_length=50)] = Field(default_factory=list)
    include_keywords: Annotated[list[str], Field(max_length=50)] = Field(default_factory=list)
    exclude_keywords: Annotated[list[str], Field(max_length=50)] = Field(default_factory=list)

    @field_validator("include_keywords", "exclude_keywords")
    @classmethod
    def clean_saved_keywords(cls, values: list[str]) -> list[str]:
        return sorted({" ".join(value.split()).lower() for value in values if value.strip()})


ApplicationStage = Literal["review", "hr_interview", "technical_interview", "offer"]


class ApplicationCreate(BaseModel):
    title: Annotated[str, Field(min_length=1, max_length=300)]
    company: Annotated[str, Field(min_length=1, max_length=200)]
    location: str | None = None
    vacancy_url: HttpUrl
    source_site: HttpUrl


class ApplicationUpdate(BaseModel):
    stage: ApplicationStage | None = None
    hr_url: Annotated[str, Field(max_length=500)] | None = None


class JobApplication(BaseModel):
    id: UUID
    company: str
    vacancy_title: str
    vacancy_url: HttpUrl
    hr_url: str
    stage: ApplicationStage
    created_at: datetime
    updated_at: datetime

