from app.models import SearchRequest, Vacancy
from app.services.html_search import _deduplicate, extract_vacancies


def test_extract_vacancies_filters_and_scores() -> None:
    request = SearchRequest(
        sites=["https://example.com/careers"],
        role="Python developer",
        include_keywords=["remote"],
        exclude_keywords=["senior"],
    )
    html = """
    <main>
      <article><a href="/jobs/python-developer">Python Developer — Remote</a></article>
      <article><a href="/jobs/senior-python">Senior Python Developer</a></article>
      <a href="/about">About us</a>
    </main>
    """

    results = extract_vacancies(html, "https://example.com/careers", request)

    assert len(results) == 1
    assert results[0].title == "Python Developer — Remote"
    assert str(results[0].url) == "https://example.com/jobs/python-developer"
    assert results[0].score == 100


def test_extract_vacancies_requires_job_like_link() -> None:
    request = SearchRequest(sites=["https://example.com"], role="Python developer")
    html = '<a href="/team/python-developer">Python Developer</a>'

    assert extract_vacancies(html, "https://example.com", request) == []


def test_deduplicate_keeps_highest_score() -> None:
    common = {
        "title": "Python Developer",
        "company": "Example",
        "location": None,
        "url": "https://example.com/jobs/1",
        "reason": "match",
        "source_site": "https://example.com/jobs",
    }

    results = _deduplicate(
        [Vacancy(**common, score=40), Vacancy(**common, score=90)]
    )

    assert len(results) == 1
    assert results[0].score == 90

