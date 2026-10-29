from fastapi.testclient import TestClient

from app.main import app, get_search_service, get_settings_store
from app.models import SearchResponse, SearchSettingsSnapshot, Vacancy


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


def test_search_endpoint() -> None:
    app.dependency_overrides[get_search_service] = lambda: FakeService()
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
    client = TestClient(app)

    response = client.post(
        "/api/search",
        json={"sites": ["https://example.com/jobs"], "role": "Developer"},
    )

    app.dependency_overrides.clear()
    assert response.status_code == 422
    assert response.json()["detail"] == "bad request"


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

