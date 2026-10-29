from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings, get_settings
from app.models import HealthResponse, SearchRequest, SearchResponse, SearchSettingsSnapshot
from app.services.ai_job_search import AiJobSearchError
from app.services.search import SearchService
from app.services.settings_store import SettingsStorageError, SupabaseSettingsStore

app = FastAPI(title="Job Compass API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["Content-Type"],
)


SettingsDependency = Annotated[Settings, Depends(get_settings)]


def get_search_service(settings: SettingsDependency) -> SearchService:
    return SearchService(settings)


SearchServiceDependency = Annotated[SearchService, Depends(get_search_service)]


def get_settings_store(settings: SettingsDependency) -> SupabaseSettingsStore:
    return SupabaseSettingsStore(settings.supabase_url)


SettingsStoreDependency = Annotated[SupabaseSettingsStore, Depends(get_settings_store)]


@app.get("/api/health", response_model=HealthResponse)
async def health(settings: SettingsDependency) -> HealthResponse:
    service = SearchService(settings)
    return HealthResponse(
        configured_provider=settings.search_provider,
        ai_job_search_ready=service.ai_job_search_ready,
        settings_storage_ready=bool(settings.supabase_url),
    )


@app.post("/api/search", response_model=SearchResponse)
async def search(
    request: SearchRequest, service: SearchServiceDependency
) -> SearchResponse:
    try:
        return await service.search(request)
    except (ValueError, AiJobSearchError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/settings", response_model=SearchSettingsSnapshot)
async def read_search_settings(store: SettingsStoreDependency) -> SearchSettingsSnapshot:
    try:
        return await store.load()
    except SettingsStorageError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.put("/api/settings", response_model=SearchSettingsSnapshot)
async def write_search_settings(
    snapshot: SearchSettingsSnapshot, store: SettingsStoreDependency
) -> SearchSettingsSnapshot:
    try:
        await store.save(snapshot)
        return snapshot
    except SettingsStorageError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

