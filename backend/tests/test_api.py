from fastapi.testclient import TestClient

from app.main import app, get_search_service
from app.models import SearchResponse, Vacancy


class FakeService:
    async def search(self, request):  # noqa: ANN001
        return SearchResponse(
            provider="html",
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

