import re
from urllib.parse import urlencode, urljoin, urlsplit

import httpx

from app.models import SearchRequest, Vacancy
from app.security import validate_public_url
from app.services.matching import score_text


def supports_mts(site: str) -> bool:
    hostname = (urlsplit(site).hostname or "").lower()
    return hostname == "job.mts.ru" or hostname.endswith(".job.mts.ru")


def supports_yandex(site: str) -> bool:
    hostname = (urlsplit(site).hostname or "").lower()
    return hostname in {"yandex.ru", "yandex.com"} and "/jobs" in urlsplit(site).path


async def search_mts(
    client: httpx.AsyncClient,
    site: str,
    request: SearchRequest,
    *,
    max_results: int,
) -> tuple[list[Vacancy], list[str]]:
    api_url = "https://job.mts.ru/api/v2/catalog/v1/vacancies"
    await validate_public_url(api_url)
    response = await client.get(
        api_url,
        params={"q": request.role, "limit": min(max_results, 100), "offset": 0},
    )
    response.raise_for_status()
    data = response.json()
    items = data.get("data", [])
    if not isinstance(items, list):
        return [], [f"{site}: API вернул неожиданный формат"]

    vacancies: list[Vacancy] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        title = str(item.get("displayTitle") or item.get("title") or "").strip()
        company_data = item.get("employer") or {}
        cities = item.get("cities") or []
        roles = item.get("professionalRoles") or []
        context = " ".join(
            [
                title,
                str(item.get("summary") or ""),
                " ".join(
                    str(value.get("title") or "")
                    for value in roles
                    if isinstance(value, dict)
                ),
                " ".join(
                    str(value.get("title") or "")
                    for value in cities
                    if isinstance(value, dict)
                ),
            ]
        )
        scored = score_text(context, request)
        if not title or not scored:
            continue

        external_url = str(item.get("externalUrl") or "")
        job_id_match = re.search(r"(\d{12,})/?$", external_url)
        if job_id_match:
            job_url = f"https://job.mts.ru/vacancy/{job_id_match.group(1)}"
        else:
            slug = str(item.get("slug") or "")
            job_url = f"https://job.mts.ru/vacancy/{slug}"

        score, reason = scored
        vacancies.append(
            Vacancy(
                title=title[:240],
                company=str(company_data.get("title") or "МТС"),
                location=", ".join(
                    str(city.get("title") or "")
                    for city in cities
                    if isinstance(city, dict)
                )
                or None,
                url=job_url,
                score=score,
                reason=reason,
                source_site=site,
            )
        )

    total = data.get("meta", {}).get("pagination", {}).get("total")
    warnings = []
    if isinstance(total, int) and total > max_results:
        warnings.append(f"{site}: найдено {total}, показаны первые {max_results}")
    return vacancies[:max_results], warnings


async def search_yandex(
    client: httpx.AsyncClient,
    site: str,
    request: SearchRequest,
    *,
    max_results: int,
) -> tuple[list[Vacancy], list[str]]:
    parsed = urlsplit(site)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    query = urlencode({"text": request.role, "page_size": 20})
    api_url = f"{origin}/jobs/api/jobs/publications?{query}"
    await validate_public_url(api_url)

    vacancies: list[Vacancy] = []
    total: int | None = None
    next_url: str | None = api_url
    while next_url and len(vacancies) < max_results:
        await validate_public_url(next_url)
        response = await client.get(next_url)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
            return vacancies, [f"{site}: API Яндекса вернул неожиданный формат"]
        if isinstance(payload.get("count"), int):
            total = payload["count"]

        for item in payload["results"]:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            vacancy_data = item.get("vacancy") or {}
            service_data = item.get("public_service") or {}
            cities = vacancy_data.get("cities") or []
            skills = vacancy_data.get("skills") or []
            context = " ".join(
                [
                    title,
                    str(item.get("short_summary") or ""),
                    " ".join(
                        str(skill.get("name") or "")
                        for skill in skills
                        if isinstance(skill, dict)
                    ),
                ]
            )
            if any(keyword in context.lower() for keyword in request.exclude_keywords):
                continue
            scored = score_text(context, request) or (
                65,
                f"найдено поиском Яндекса по запросу: {request.role}",
            )
            slug = str(item.get("publication_slug_url") or "").strip("/")
            if not title or not slug:
                continue
            score, reason = scored
            vacancies.append(
                Vacancy(
                    title=title[:240],
                    company=str(service_data.get("name") or "Яндекс"),
                    location=", ".join(
                        str(city.get("name") or "")
                        for city in cities
                        if isinstance(city, dict)
                    )
                    or None,
                    url=f"{origin}/jobs/vacancies/{slug}",
                    score=score,
                    reason=reason,
                    source_site=site,
                )
            )
            if len(vacancies) >= max_results:
                break

        raw_next = payload.get("next")
        next_url = urljoin(origin, raw_next) if isinstance(raw_next, str) and raw_next else None
        if next_url:
            next_url = next_url.replace("/publications/?", "/publications?")

    warnings = []
    if total is not None and total > max_results:
        warnings.append(f"{site}: найдено {total}, показаны первые {max_results}")
    return vacancies[:max_results], warnings

