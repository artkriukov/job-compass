import asyncio
from unittest.mock import AsyncMock

import httpx

from app.models import SearchRequest
from app.services.html_search import (
    SiteCrawlerProvider,
    _is_detail_url,
    _search_urls,
    extract_single_vacancy,
    extract_vacancies,
)


def test_detail_url_detection() -> None:
    assert _is_detail_url("https://example.com/vacancies/python-developer")
    assert _is_detail_url("https://yandex.ru/jobs/vacancies/python-developer-123")
    assert _is_detail_url("https://boards.greenhouse.io/acme?gh_jid=123")
    assert not _is_detail_url("https://example.com/vacancies")
    assert not _is_detail_url("https://yandex.ru/jobs/vacancies?skills=34")


def test_search_urls_discovers_form_and_common_parameters() -> None:
    html = '<form action="/vacancies"><input name="term_search"></form>'

    urls = _search_urls("https://example.com/vacancies", html, "Python developer")

    assert urls[0] == "https://example.com/vacancies?term_search=Python+developer"
    assert "https://example.com/vacancies?search=Python+developer" in urls
    assert "https://example.com/vacancies?q=Python+developer" in urls


def test_extracts_clean_card_title_and_direct_link() -> None:
    html = """
    <a href="/vacancies/python-developer" class="vacancy-card">
      <div class="vacancy-card__date">29 октября</div>
      <div class="vacancy-card__title">Python разработчик</div>
      <div class="vacancy-card__company">Example Corp</div>
      <div class="vacancy-card__location">Москва</div>
    </a>
    """
    request = SearchRequest(sites=["https://example.com/vacancies"], role="Python")

    vacancies = extract_vacancies(html, "https://example.com/vacancies", request)

    assert vacancies[0].title == "Python разработчик"
    assert vacancies[0].company == "Example Corp"
    assert vacancies[0].location == "Москва"
    assert str(vacancies[0].url) == "https://example.com/vacancies/python-developer"


def test_extracts_job_posting_json_ld() -> None:
    html = """
    <script type="application/ld+json">
    {
      "@type": "JobPosting",
      "title": "Python Backend Developer",
      "description": "FastAPI and PostgreSQL",
      "url": "/jobs/python-backend",
      "hiringOrganization": {"name": "Example Corp"},
      "jobLocation": {"address": {"addressLocality": "Remote"}}
    }
    </script>
    """
    request = SearchRequest(
        sites=["https://example.com/careers"],
        role="Python Backend",
        include_keywords=["FastAPI"],
    )

    vacancies = extract_vacancies(html, "https://example.com/careers", request)

    assert len(vacancies) == 1
    assert vacancies[0].score == 100
    assert vacancies[0].location == "Remote"


def test_extracts_single_vacancy_from_direct_url() -> None:
    html = """
    <script type="application/ld+json">
    {
      "@type": "JobPosting",
      "title": "Python Backend Developer",
      "description": "<p>FastAPI and PostgreSQL</p>",
      "hiringOrganization": {"name": "Example Corp"},
      "jobLocation": {"address": {"addressLocality": "Remote"}}
    }
    </script>
    """

    vacancy = extract_single_vacancy(html, "https://jobs.example.com/openings/42")

    assert vacancy.title == "Python Backend Developer"
    assert vacancy.company == "Example Corp"
    assert vacancy.location == "Remote"
    assert vacancy.description == "FastAPI and PostgreSQL"
    assert str(vacancy.source_site) == "https://jobs.example.com/"


def test_extracts_single_vacancy_from_visible_page_content() -> None:
    html = """
    <main>
      <h1>Инженер технической поддержки</h1>
      <div class="company-name">Example Telecom</div>
      <div class="job-location">Москва</div>
      <p>Поддержка Linux-систем и диагностика TCP/IP.</p>
    </main>
    """

    vacancy = extract_single_vacancy(html, "https://example.com/vacancy/42")

    assert vacancy.title == "Инженер технической поддержки"
    assert vacancy.company == "Example Telecom"
    assert vacancy.location == "Москва"
    assert "диагностика TCP/IP" in (vacancy.description or "")


def test_import_vacancy_fetches_direct_page(monkeypatch) -> None:  # noqa: ANN001
    provider = SiteCrawlerProvider(max_results=20)
    html = '<h1>Python Developer</h1><div class="company">Example</div>'
    monkeypatch.setattr(
        provider,
        "_fetch_html",
        AsyncMock(return_value=(html, "https://example.com/jobs/42", None)),
    )

    vacancy = asyncio.run(provider.import_vacancy("https://example.com/jobs/42"))

    assert vacancy.title == "Python Developer"
    assert vacancy.company == "Example"


def test_generic_crawler_uses_site_search_and_returns_direct_link(monkeypatch) -> None:  # noqa: ANN001
    listing = '<form action="/vacancies"><input name="search"></form>'
    result = """
    <a href="/vacancies/python-developer">
      <h3>Python Developer</h3>
    </a>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        html = result if request.url.params.get("search") == "Python" else listing
        return httpx.Response(200, text=html, headers={"content-type": "text/html; charset=utf-8"})

    monkeypatch.setattr(
        "app.services.html_search.validate_public_url", AsyncMock(return_value=None)
    )
    provider = SiteCrawlerProvider(max_results=20)
    request = SearchRequest(sites=["https://example.com/vacancies"], role="Python")

    async def run_search():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await provider._search_generic_site(
                client, "https://example.com/vacancies", request
            )

    vacancies, warnings = asyncio.run(run_search())

    assert warnings == []
    assert len(vacancies) == 1
    assert str(vacancies[0].url) == "https://example.com/vacancies/python-developer"

