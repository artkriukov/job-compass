import asyncio
from unittest.mock import AsyncMock

import httpx

from app.models import SearchRequest
from app.services.site_adapters import (
    search_mts,
    search_yandex,
    supports_mts,
    supports_yandex,
)


def test_supports_mts() -> None:
    assert supports_mts("https://job.mts.ru/vacancies")
    assert not supports_mts("https://careers.example.com/jobs")


def test_supports_yandex() -> None:
    assert supports_yandex("https://yandex.ru/jobs/vacancies")
    assert supports_yandex("https://yandex.com/jobs/vacancies")
    assert not supports_yandex("https://yandex.ru/search")


def test_search_mts_returns_direct_vacancy_links(monkeypatch) -> None:  # noqa: ANN001
    payload = {
        "data": [
            {
                "title": "Стажер Python разработчик",
                "displayTitle": "Стажер Python разработчик",
                "summary": "FastAPI",
                "externalUrl": "https://job.mts.ru/jobs/721846123253203203",
                "cities": [{"title": "Москва"}],
                "employer": {"title": "ООО МТС Веб Сервисы"},
                "professionalRoles": [{"title": "Backend"}],
            },
            {
                "title": "Java разработчик",
                "externalUrl": "https://job.mts.ru/jobs/111111111111111111",
                "cities": [],
                "employer": {"title": "МТС"},
                "professionalRoles": [],
            },
        ],
        "meta": {"pagination": {"total": 2}},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["q"] == "Python"
        return httpx.Response(200, json=payload)

    monkeypatch.setattr(
        "app.services.site_adapters.validate_public_url", AsyncMock(return_value=None)
    )
    request = SearchRequest(
        sites=["https://job.mts.ru/vacancies"],
        role="Python",
        include_keywords=["FastAPI"],
    )
    async_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    async def run_search():
        async with async_client as client:
            return await search_mts(
                client,
                "https://job.mts.ru/vacancies",
                request,
                max_results=100,
            )

    vacancies, warnings = asyncio.run(run_search())

    assert warnings == []
    assert len(vacancies) == 1
    assert vacancies[0].title == "Стажер Python разработчик"
    assert str(vacancies[0].url) == "https://job.mts.ru/vacancy/721846123253203203"
    assert vacancies[0].company == "ООО МТС Веб Сервисы"
    assert vacancies[0].location == "Москва"


def test_search_yandex_follows_pagination_and_returns_direct_links(monkeypatch) -> None:  # noqa: ANN001
    first_page = {
        "count": 2,
        "next": "/jobs/api/jobs/publications/?text=Python&page_size=20&cursor=next",
        "results": [
            {
                "title": "Python-разработчик",
                "short_summary": "FastAPI",
                "publication_slug_url": "python-razrabotchik-123",
                "public_service": {"name": "Yandex Cloud"},
                "vacancy": {
                    "cities": [{"name": "Москва"}],
                    "skills": [{"name": "Python"}],
                },
            }
        ],
    }
    second_page = {
        "count": 2,
        "next": None,
        "results": [
            {
                "title": "Backend-разработчик",
                "short_summary": "Разработка внутренних сервисов",
                "publication_slug_url": "backend-razrabotchik-456",
                "public_service": {"name": "Яндекс Go"},
                "vacancy": {"cities": [], "skills": []},
            }
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        payload = second_page if request.url.params.get("cursor") else first_page
        return httpx.Response(200, json=payload)

    monkeypatch.setattr(
        "app.services.site_adapters.validate_public_url", AsyncMock(return_value=None)
    )
    request = SearchRequest(sites=["https://yandex.ru/jobs/vacancies"], role="Python")

    async def run_search():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await search_yandex(
                client,
                "https://yandex.ru/jobs/vacancies",
                request,
                max_results=100,
            )

    vacancies, warnings = asyncio.run(run_search())

    assert warnings == []
    assert len(vacancies) == 2
    assert str(vacancies[0].url) == (
        "https://yandex.ru/jobs/vacancies/python-razrabotchik-123"
    )
    assert str(vacancies[1].url) == (
        "https://yandex.ru/jobs/vacancies/backend-razrabotchik-456"
    )

