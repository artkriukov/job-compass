from uuid import UUID

from fastapi.testclient import TestClient

from app.main import (
    app,
    get_application_store,
    get_career_ops_provider,
    get_compatibility_report_store,
    get_search_service,
    get_settings_store,
)
from app.models import (
    CompatibilityReport,
    CompatibilityResult,
    CoverLetter,
    JobApplication,
    SearchResponse,
    SearchSettingsSnapshot,
    TailoredResume,
    Vacancy,
)
from app.services.application_store import ApplicationStorageError


class FakeService:
    async def search(self, request):  # noqa: ANN001
        return SearchResponse(
            provider="site_crawler",
            vacancies=[
                Vacancy(
                    title=request.role,
                    company="Example",
                    location="Remote",
                    url="https://example.com/jobs/1",
                    score=95,
                    reason="совпала должность",
                    source_site=request.sites[0],
                )
            ],
            warnings=[],
        )

    async def import_vacancy(self, url):  # noqa: ANN001, ANN201
        return Vacancy(
            title="Python Developer",
            company="Example",
            location="Remote",
            url=url,
            score=100,
            reason="Добавлено вручную по ссылке",
            source_site="https://example.com",
            description="FastAPI and PostgreSQL",
        )


class FailingService:
    async def search(self, _request):  # noqa: ANN001
        raise ValueError("bad request")


class FakeSettingsStore:
    def __init__(self) -> None:
        self.snapshot = SearchSettingsSnapshot()

    async def load(self) -> SearchSettingsSnapshot:
        return self.snapshot

    async def save(self, snapshot: SearchSettingsSnapshot) -> None:
        self.snapshot = snapshot


class FakeApplicationStore:
    def __init__(self) -> None:
        self.applications = []

    async def track_search(self, response):  # noqa: ANN001
        return response

    async def load(self):  # noqa: ANN201
        return self.applications

    async def create(self, payload):  # noqa: ANN001, ANN201
        application = JobApplication.model_validate({
            "id": "9bca2aaf-f083-469f-ac20-4a6fa1d443ea",
            "company": payload.company,
            "vacancy_title": payload.title,
            "vacancy_url": payload.vacancy_url,
            "hr_url": "",
            "stage": "review",
            "created_at": "2026-10-29T12:00:00Z",
            "updated_at": "2026-10-29T12:00:00Z",
        })
        self.applications = [application]
        return application

    async def update(self, application_id, payload):  # noqa: ANN001, ANN201
        current = self.applications[0]
        updated = current.model_copy(update={
            "stage": payload.stage or current.stage,
            "hr_url": payload.hr_url if payload.hr_url is not None else current.hr_url,
        })
        self.applications = [updated]
        return updated

    async def delete(self, application_id: UUID) -> None:
        self.applications = [item for item in self.applications if item.id != application_id]


class FailingApplicationTracker(FakeApplicationStore):
    async def track_search(self, response):  # noqa: ANN001
        raise ApplicationStorageError("database unavailable")


class FakeCareerOpsProvider:
    def list_reports(self):  # noqa: ANN201
        return [
            CompatibilityReport(
                id="report-1",
                vacancy=Vacancy(
                    title="Support engineer",
                    company="Example",
                    location="Remote",
                    url="https://example.com/jobs/1",
                    score=90,
                    reason="совпадает роль",
                    source_site="https://example.com/jobs",
                ),
                mode="quick",
                result=CompatibilityResult(
                    score=4.1,
                    decision="apply",
                    summary="Хорошее совпадение",
                ),
                created_at="2026-10-31T08:00:00Z",
            )
        ]

    def tailor_resume(self, report):  # noqa: ANN001, ANN201
        return TailoredResume(
            id="tailored-1",
            report_id=report.id,
            blocks=[{"title": "Обо мне", "content": "Работаю с Python."}],
            created_at="2026-10-31T09:00:00Z",
        )

    def load_cover_letter(self, _report_id):  # noqa: ANN001, ANN201
        return None

    def create_cover_letter(self, report):  # noqa: ANN001, ANN201
        return CoverLetter(
            id="letter-1",
            report_id=report.id,
            content="Здравствуйте! Меня заинтересовала роль Support engineer. "
            "Мой подтверждённый опыт соответствует задачам вакансии. "
            "Буду рад обсудить детали и рассказать о релевантных проектах.",
            created_at="2026-10-31T09:10:00Z",
            updated_at="2026-10-31T09:10:00Z",
        )

    def save_cover_letter(self, _letter):  # noqa: ANN001
        return None


class FakeCompatibilityReportStore:
    is_ready = True

    def __init__(self) -> None:
        self.reports = []
        self.tailored_resume = None
        self.cover_letter = None

    async def save_many(self, reports):  # noqa: ANN001
        self.reports = reports

    async def load(self):  # noqa: ANN201
        return self.reports

    async def load_tailored_resume(self, _report_id):  # noqa: ANN001, ANN201
        return self.tailored_resume

    async def save_tailored_resume(self, resume):  # noqa: ANN001
        self.tailored_resume = resume

    async def load_cover_letter(self, _report_id):  # noqa: ANN001, ANN201
        return self.cover_letter

    async def save_cover_letter(self, letter):  # noqa: ANN001
        self.cover_letter = letter


def test_search_endpoint() -> None:
    app.dependency_overrides[get_search_service] = lambda: FakeService()
    app.dependency_overrides[get_application_store] = lambda: FakeApplicationStore()
    client = TestClient(app)

    response = client.post(
        "/api/search",
        json={"sites": ["https://example.com/careers"], "role": "Python developer"},
    )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["vacancies"][0]["score"] == 95


def test_import_vacancy_endpoint() -> None:
    app.dependency_overrides[get_search_service] = lambda: FakeService()
    app.dependency_overrides[get_application_store] = lambda: FakeApplicationStore()
    client = TestClient(app)

    response = client.post(
        "/api/vacancies/import",
        json={"url": "https://example.com/jobs/42"},
    )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["title"] == "Python Developer"
    assert response.json()["description"] == "FastAPI and PostgreSQL"


def test_search_rejects_invalid_url() -> None:
    client = TestClient(app)
    response = client.post("/api/search", json={"sites": ["not-a-url"], "role": "Developer"})

    assert response.status_code == 422


def test_health_endpoint() -> None:
    client = TestClient(app)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_search_converts_service_error_to_422() -> None:
    app.dependency_overrides[get_search_service] = lambda: FailingService()
    app.dependency_overrides[get_application_store] = lambda: FakeApplicationStore()
    client = TestClient(app)

    response = client.post(
        "/api/search",
        json={"sites": ["https://example.com/jobs"], "role": "Developer"},
    )

    app.dependency_overrides.clear()
    assert response.status_code == 422
    assert response.json()["detail"] == "bad request"


def test_search_succeeds_when_application_tracking_is_unavailable() -> None:
    app.dependency_overrides[get_search_service] = lambda: FakeService()
    app.dependency_overrides[get_application_store] = lambda: FailingApplicationTracker()
    client = TestClient(app)

    response = client.post(
        "/api/search",
        json={"sites": ["https://example.com/jobs"], "role": "Developer"},
    )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["vacancies"][0]["seen_before"] is False


def test_settings_endpoints_round_trip_snapshot() -> None:
    store = FakeSettingsStore()
    app.dependency_overrides[get_settings_store] = lambda: store
    client = TestClient(app)
    payload = {
        "sites": [
            {
                "id": "9bca2aaf-f083-469f-ac20-4a6fa1d443ea",
                "name": "Яндекс",
                "url": "https://yandex.ru/jobs",
            }
        ],
        "roles": [
            {
                "id": "eb66ad46-99ea-403a-96e8-1d007b7257b4",
                "title": "Support engineer",
            }
        ],
        "include_keywords": ["Linux"],
        "exclude_keywords": ["Продажи"],
    }

    put_response = client.put("/api/settings", json=payload)
    get_response = client.get("/api/settings")

    app.dependency_overrides.clear()
    assert put_response.status_code == 200
    assert get_response.status_code == 200
    assert get_response.json()["include_keywords"] == ["linux"]
    assert get_response.json()["exclude_keywords"] == ["продажи"]


def test_application_endpoints_round_trip() -> None:
    store = FakeApplicationStore()
    app.dependency_overrides[get_application_store] = lambda: store
    client = TestClient(app)
    payload = {
        "title": "Support engineer",
        "company": "Example",
        "location": "Remote",
        "vacancy_url": "https://example.com/jobs/1",
        "source_site": "https://example.com/jobs",
    }

    created = client.post("/api/applications", json=payload)
    listed = client.get("/api/applications")
    updated = client.put(
        "/api/applications/9bca2aaf-f083-469f-ac20-4a6fa1d443ea",
        json={"stage": "hr_interview", "hr_url": "https://t.me/recruiter"},
    )
    deleted = client.delete("/api/applications/9bca2aaf-f083-469f-ac20-4a6fa1d443ea")

    app.dependency_overrides.clear()
    assert created.status_code == 200
    assert listed.json()[0]["vacancy_title"] == "Support engineer"
    assert updated.json()["stage"] == "hr_interview"
    assert deleted.status_code == 204


def test_compatibility_reports_endpoint() -> None:
    store = FakeCompatibilityReportStore()
    app.dependency_overrides[get_career_ops_provider] = lambda: FakeCareerOpsProvider()
    app.dependency_overrides[get_compatibility_report_store] = lambda: store
    client = TestClient(app)

    response = client.get("/api/career-ops/reports")

    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()[0]["vacancy"]["title"] == "Support engineer"
    assert response.json()[0]["result"]["score"] == 4.1


def test_tailored_resume_endpoint_generates_and_reuses_result() -> None:
    store = FakeCompatibilityReportStore()
    provider = FakeCareerOpsProvider()
    store.reports = provider.list_reports()
    app.dependency_overrides[get_career_ops_provider] = lambda: provider
    app.dependency_overrides[get_compatibility_report_store] = lambda: store
    client = TestClient(app)

    created = client.post(
        "/api/career-ops/tailored-resume",
        json={"report_id": "report-1"},
    )
    reused = client.post(
        "/api/career-ops/tailored-resume",
        json={"report_id": "report-1"},
    )

    app.dependency_overrides.clear()
    assert created.status_code == 200
    assert created.json()["blocks"][0]["title"] == "Обо мне"
    assert reused.json() == created.json()


def test_cover_letter_endpoints_generate_reuse_and_update() -> None:
    store = FakeCompatibilityReportStore()
    provider = FakeCareerOpsProvider()
    store.reports = provider.list_reports()
    app.dependency_overrides[get_career_ops_provider] = lambda: provider
    app.dependency_overrides[get_compatibility_report_store] = lambda: store
    client = TestClient(app)

    created = client.post(
        "/api/career-ops/cover-letter",
        json={"report_id": "report-1"},
    )
    reused = client.post(
        "/api/career-ops/cover-letter",
        json={"report_id": "report-1"},
    )
    edited_content = created.json()["content"].replace("Support engineer", "инженера поддержки")
    updated = client.put(
        "/api/career-ops/cover-letter/report-1",
        json={"content": edited_content},
    )

    app.dependency_overrides.clear()
    assert created.status_code == 200
    assert created.json()["content"].startswith("Здравствуйте!")
    assert reused.json() == created.json()
    assert updated.status_code == 200
    assert updated.json()["content"] == edited_content


def test_cover_letter_endpoints_report_missing_artifacts() -> None:
    store = FakeCompatibilityReportStore()
    provider = FakeCareerOpsProvider()
    app.dependency_overrides[get_career_ops_provider] = lambda: provider
    app.dependency_overrides[get_compatibility_report_store] = lambda: store
    client = TestClient(app)

    create_response = client.post(
        "/api/career-ops/cover-letter",
        json={"report_id": "missing"},
    )
    update_response = client.put(
        "/api/career-ops/cover-letter/missing",
        json={"content": "Достаточно длинный текст отсутствующего сопроводительного письма "
        "для проверки корректного ответа API при попытке сохранить неизвестный материал."},
    )

    app.dependency_overrides.clear()
    assert create_response.status_code == 404
    assert update_response.status_code == 404


def test_cover_letter_endpoint_syncs_local_artifact_to_store() -> None:
    store = FakeCompatibilityReportStore()
    provider = FakeCareerOpsProvider()
    local_letter = provider.create_cover_letter(provider.list_reports()[0])
    provider.load_cover_letter = lambda _report_id: local_letter  # type: ignore[method-assign]
    app.dependency_overrides[get_career_ops_provider] = lambda: provider
    app.dependency_overrides[get_compatibility_report_store] = lambda: store
    client = TestClient(app)

    response = client.post(
        "/api/career-ops/cover-letter",
        json={"report_id": "report-1"},
    )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["id"] == "letter-1"
    assert store.cover_letter == local_letter

