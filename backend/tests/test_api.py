from uuid import UUID

from fastapi.testclient import TestClient

from app.main import (
    app,
    get_application_store,
    get_career_ops_provider,
    get_search_service,
    get_settings_store,
)
from app.models import (
    CompatibilityReport,
    CompatibilityResult,
    JobApplication,
    SearchResponse,
    SearchSettingsSnapshot,
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
    app.dependency_overrides[get_career_ops_provider] = lambda: FakeCareerOpsProvider()
    client = TestClient(app)

    response = client.get("/api/career-ops/reports")

    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()[0]["vacancy"]["title"] == "Support engineer"
    assert response.json()[0]["result"]["score"] == 4.1

