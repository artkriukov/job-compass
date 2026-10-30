from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings, get_settings
from app.models import (
    ApplicationCreate,
    ApplicationUpdate,
    CompatibilityRequest,
    CompatibilityResult,
    HealthResponse,
    JobApplication,
    ResumeSnapshot,
    SearchRequest,
    SearchResponse,
    SearchSettingsSnapshot,
)
from app.services.ai_job_search import AiJobSearchError
from app.services.application_store import ApplicationStorageError, SupabaseApplicationStore
from app.services.career_ops import CareerOpsError, CareerOpsProvider
from app.services.resume_store import (
    MAX_RESUME_BYTES,
    ResumeStorageError,
    ResumeStore,
    ResumeValidationError,
)
from app.services.search import SearchService
from app.services.settings_store import SettingsStorageError, SupabaseSettingsStore

app = FastAPI(title="Job Compass API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
)


SettingsDependency = Annotated[Settings, Depends(get_settings)]


def get_search_service(settings: SettingsDependency) -> SearchService:
    return SearchService(settings)


SearchServiceDependency = Annotated[SearchService, Depends(get_search_service)]


def get_settings_store(settings: SettingsDependency) -> SupabaseSettingsStore:
    return SupabaseSettingsStore(settings.supabase_url)


SettingsStoreDependency = Annotated[SupabaseSettingsStore, Depends(get_settings_store)]


def get_application_store(settings: SettingsDependency) -> SupabaseApplicationStore:
    return SupabaseApplicationStore(settings.supabase_url)


ApplicationStoreDependency = Annotated[SupabaseApplicationStore, Depends(get_application_store)]


def get_career_ops_provider(settings: SettingsDependency) -> CareerOpsProvider:
    return CareerOpsProvider(
        project_root=settings.career_ops_project_root,
        data_dir=settings.career_ops_data_dir,
        codex_bin=settings.codex_bin,
        node_bin=settings.node_bin,
        doctor_timeout_seconds=settings.career_ops_doctor_timeout_seconds,
        analysis_timeout_seconds=settings.career_ops_analysis_timeout_seconds,
    )


CareerOpsDependency = Annotated[CareerOpsProvider, Depends(get_career_ops_provider)]


def get_resume_store(settings: SettingsDependency) -> ResumeStore:
    return ResumeStore(settings.career_ops_data_dir)


ResumeStoreDependency = Annotated[ResumeStore, Depends(get_resume_store)]


@app.get("/api/health", response_model=HealthResponse)
async def health(
    settings: SettingsDependency, career_ops: CareerOpsDependency
) -> HealthResponse:
    service = SearchService(settings)
    return HealthResponse(
        configured_provider=settings.search_provider,
        ai_job_search_ready=service.ai_job_search_ready,
        settings_storage_ready=bool(settings.supabase_url),
        career_ops=career_ops.health(),
    )


@app.get("/api/career-ops/resume", response_model=ResumeSnapshot)
async def read_resume(store: ResumeStoreDependency) -> ResumeSnapshot:
    try:
        return store.load()
    except ResumeStorageError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/career-ops/resume", response_model=ResumeSnapshot)
async def upload_resume(
    store: ResumeStoreDependency, file: Annotated[UploadFile, File()]
) -> ResumeSnapshot:
    try:
        payload = await file.read(MAX_RESUME_BYTES + 1)
        return store.save(
            filename=file.filename or "resume",
            content_type=file.content_type,
            payload=payload,
        )
    except ResumeValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ResumeStorageError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/career-ops/compatibility", response_model=CompatibilityResult)
async def check_compatibility(
    payload: CompatibilityRequest, career_ops: CareerOpsDependency
) -> CompatibilityResult:
    try:
        return career_ops.evaluate(payload)
    except CareerOpsError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/search", response_model=SearchResponse)
async def search(
    request: SearchRequest, service: SearchServiceDependency, store: ApplicationStoreDependency
) -> SearchResponse:
    try:
        response = await service.search(request)
    except (ValueError, AiJobSearchError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        return await store.track_search(response)
    except ApplicationStorageError:
        return response


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


@app.get("/api/applications", response_model=list[JobApplication])
async def read_applications(store: ApplicationStoreDependency) -> list[JobApplication]:
    try:
        return await store.load()
    except ApplicationStorageError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/applications", response_model=JobApplication)
async def create_application(
    payload: ApplicationCreate, store: ApplicationStoreDependency
) -> JobApplication:
    try:
        return await store.create(payload)
    except ApplicationStorageError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.put("/api/applications/{application_id}", response_model=JobApplication)
async def write_application(
    application_id: UUID, payload: ApplicationUpdate, store: ApplicationStoreDependency
) -> JobApplication:
    try:
        return await store.update(application_id, payload)
    except ApplicationStorageError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.delete("/api/applications/{application_id}", status_code=204)
async def delete_application(application_id: UUID, store: ApplicationStoreDependency) -> None:
    try:
        await store.delete(application_id)
    except ApplicationStorageError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
