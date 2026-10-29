import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from app.config import Settings
from app.models import SearchRequest, Vacancy
from app.services.ai_job_search import AiJobSearchError
from app.services.search import SearchService


def request() -> SearchRequest:
    return SearchRequest(sites=["https://example.com/jobs"], role="Developer")


def vacancy() -> Vacancy:
    return Vacancy(
        title="Developer",
        company="Example",
        location=None,
        url="https://example.com/jobs/1",
        score=80,
        reason="match",
        source_site="https://example.com/jobs",
    )


def test_html_mode_returns_results() -> None:
    service = SearchService(Settings(search_provider="html"))
    service.html.search = AsyncMock(return_value=([vacancy()], []))

    response = asyncio.run(service.search(request()))

    assert response.provider == "html"
    assert response.vacancies[0].title == "Developer"


def test_explicit_ai_mode_requires_ready_provider() -> None:
    service = SearchService(Settings(search_provider="ai_job_search"))

    with pytest.raises(AiJobSearchError, match="не готов"):
        asyncio.run(service.search(request()))


def test_auto_mode_uses_ai_provider(tmp_path) -> None:  # noqa: ANN001
    service = SearchService(Settings(search_provider="auto", ai_job_search_root=tmp_path))
    assert service.ai_job_search is not None
    service.ai_job_search.is_ready = Mock(return_value=True)
    service.ai_job_search.search = AsyncMock(return_value=([vacancy()], []))

    response = asyncio.run(service.search(request()))

    assert response.provider == "ai_job_search"


def test_auto_mode_falls_back_to_html(tmp_path) -> None:  # noqa: ANN001
    service = SearchService(Settings(search_provider="auto", ai_job_search_root=tmp_path))
    assert service.ai_job_search is not None
    service.ai_job_search.is_ready = Mock(return_value=True)
    service.ai_job_search.search = AsyncMock(side_effect=AiJobSearchError("failed"))
    service.html.search = AsyncMock(return_value=([vacancy()], []))

    response = asyncio.run(service.search(request()))

    assert response.provider == "html"
    assert response.warnings == [
        "AI Job Search недоступен, использован HTML-поиск: failed"
    ]
