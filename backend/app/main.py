from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings, get_settings
from app.models import (
    ApplicationCreate,
    ApplicationUpdate,
    CompatibilityReport,
    CompatibilityRequest,
    CompatibilityResult,
    CoverLetter,
    CoverLetterRequest,
    CoverLetterUpdate,
    HealthResponse,
    JobApplication,
    ResumeSnapshot,
    SearchRequest,
    SearchResponse,
    SearchSettingsSnapshot,
    TailoredResume,
    TailoredResumeRequest,
)
from app.services.ai_job_search import AiJobSearchError
from app.services.application_store import ApplicationStorageError, SupabaseApplicationStore
from app.services.career_ops import CareerOpsError, CareerOpsProvider
from app.services.compatibility_report_store import (
    CompatibilityReportStorageError,
    SupabaseCompatibilityReportStore,
)
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
        quick_model=settings.career_ops_quick_model,
        groq_api_key=settings.groq_api_key,
        groq_model=settings.groq_model,
    )


CareerOpsDependency = Annotated[CareerOpsProvider, Depends(get_career_ops_provider)]


def get_compatibility_report_store(
    settings: SettingsDependency,
) -> SupabaseCompatibilityReportStore:
    return SupabaseCompatibilityReportStore(settings.supabase_url)


CompatibilityReportStoreDependency = Annotated[
    SupabaseCompatibilityReportStore,
    Depends(get_compatibility_report_store),
]


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
    payload: CompatibilityRequest,
    career_ops: CareerOpsDependency,
    report_store: CompatibilityReportStoreDependency,
) -> CompatibilityResult:
    try:
        result = career_ops.evaluate(payload)
    except CareerOpsError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if report_store.is_ready:
        try:
            report = next((
                item
                for item in career_ops.list_reports()
                if str(item.vacancy.url) == str(payload.vacancy.url)
                and item.mode == payload.mode
                and item.result == result
            ), None)
            if report:
                await report_store.save(report)
        except (CareerOpsError, CompatibilityReportStorageError):
            pass
    return result


@app.get("/api/career-ops/reports", response_model=list[CompatibilityReport])
async def read_compatibility_reports(
    career_ops: CareerOpsDependency,
    report_store: CompatibilityReportStoreDependency,
) -> list[CompatibilityReport]:
    try:
        local_reports = career_ops.list_reports()
    except CareerOpsError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not report_store.is_ready:
        return local_reports
    try:
        remote_reports = await report_store.load()
        remote_ids = {report.id for report in remote_reports}
        missing_reports = [report for report in local_reports if report.id not in remote_ids]
        if missing_reports:
            await report_store.save_many(missing_reports)
        merged = [*remote_reports, *missing_reports]
        return sorted(merged, key=lambda report: report.created_at, reverse=True)
    except CompatibilityReportStorageError:
        return local_reports


@app.post("/api/career-ops/tailored-resume", response_model=TailoredResume)
async def create_tailored_resume(
    payload: TailoredResumeRequest,
    career_ops: CareerOpsDependency,
    report_store: CompatibilityReportStoreDependency,
) -> TailoredResume:
    if report_store.is_ready:
        try:
            existing = await report_store.load_tailored_resume(payload.report_id)
            if existing:
                return existing
        except CompatibilityReportStorageError:
            pass
    try:
        reports = await report_store.load() if report_store.is_ready else career_ops.list_reports()
    except CompatibilityReportStorageError:
        reports = career_ops.list_reports()
    report = next((item for item in reports if item.id == payload.report_id), None)
    if report is None:
        raise HTTPException(status_code=404, detail="Отчёт для адаптации резюме не найден")
    try:
        result = career_ops.tailor_resume(report)
    except CareerOpsError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if report_store.is_ready:
        try:
            await report_store.save_tailored_resume(result)
        except CompatibilityReportStorageError:
            pass
    return result


@app.post("/api/career-ops/cover-letter", response_model=CoverLetter)
async def create_cover_letter(
    payload: CoverLetterRequest,
    career_ops: CareerOpsDependency,
    report_store: CompatibilityReportStoreDependency,
) -> CoverLetter:
    if report_store.is_ready:
        try:
            existing = await report_store.load_cover_letter(payload.report_id)
            if existing:
                return existing
        except CompatibilityReportStorageError:
            pass
    local_existing = career_ops.load_cover_letter(payload.report_id)
    if local_existing:
        if report_store.is_ready:
            try:
                await report_store.save_cover_letter(local_existing)
            except CompatibilityReportStorageError:
                pass
        return local_existing
    try:
        reports = await report_store.load() if report_store.is_ready else career_ops.list_reports()
    except CompatibilityReportStorageError:
        reports = career_ops.list_reports()
    report = next((item for item in reports if item.id == payload.report_id), None)
    if report is None:
        raise HTTPException(status_code=404, detail="Отчёт для сопроводительного письма не найден")
    try:
        result = career_ops.create_cover_letter(report)
    except CareerOpsError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if report_store.is_ready:
        try:
            await report_store.save_cover_letter(result)
        except CompatibilityReportStorageError:
            pass
    return result


@app.put("/api/career-ops/cover-letter/{report_id}", response_model=CoverLetter)
async def update_cover_letter(
    report_id: str,
    payload: CoverLetterUpdate,
    career_ops: CareerOpsDependency,
    report_store: CompatibilityReportStoreDependency,
) -> CoverLetter:
    existing = None
    if report_store.is_ready:
        try:
            existing = await report_store.load_cover_letter(report_id)
        except CompatibilityReportStorageError:
            pass
    existing = existing or career_ops.load_cover_letter(report_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Сопроводительное письмо не найдено")
    updated = existing.model_copy(update={
        "content": payload.content,
        "updated_at": datetime.now(UTC),
    })
    try:
        career_ops.save_cover_letter(updated)
    except CareerOpsError:
        pass
    if report_store.is_ready:
        try:
            await report_store.save_cover_letter(updated)
        except CompatibilityReportStorageError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
    return updated


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
