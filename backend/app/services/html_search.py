import asyncio
import json
from collections.abc import Iterable
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import httpx
from bs4 import BeautifulSoup, Tag

from app.models import SearchRequest, Vacancy
from app.security import UnsafeUrlError, validate_public_url
from app.services.matching import score_text, tokens
from app.services.site_adapters import (
    search_mts,
    search_yandex,
    supports_mts,
    supports_yandex,
)

DETAIL_SEGMENTS = {
    "job",
    "jobs",
    "vacancy",
    "vacancies",
    "position",
    "positions",
    "opening",
    "openings",
}
SEARCH_PARAMS = ("search", "q", "query", "keyword", "keywords", "searchTerm")
JOB_ID_PARAMS = {"gh_jid", "jobid", "job_id", "jid", "rid", "positionid"}
MAX_HTML_BYTES = 2_000_000


def _company_from_url(url: str) -> str:
    hostname = (urlsplit(url).hostname or "").removeprefix("www.")
    parts = hostname.split(".")
    if parts and parts[0] in {"career", "careers", "job", "jobs", "work"} and len(parts) > 2:
        return parts[1].replace("-", " ").title()
    return (parts[0] if parts else "").replace("-", " ").title() or "Неизвестная компания"


def _is_detail_url(url: str) -> bool:
    parsed = urlsplit(url)
    segments = [segment.lower() for segment in parsed.path.split("/") if segment]
    for index, segment in enumerate(segments):
        if (
            segment in DETAIL_SEGMENTS
            and index + 1 < len(segments)
            and segments[index + 1] not in DETAIL_SEGMENTS
        ):
            return True
    query_keys = {key.lower() for key, _ in parse_qsl(parsed.query)}
    if query_keys.intersection(JOB_ID_PARAMS):
        return True
    hostname = (parsed.hostname or "").split(".")[0]
    return hostname in {"job", "jobs", "careers"} and len(segments) >= 2


def _clean_text(value: str) -> str:
    return " ".join(value.split())


def _link_title(link: Tag, request: SearchRequest) -> str:
    selectors = (
        '[itemprop="title"]',
        '[class*="vacancy"][class*="title"]',
        '[class*="job"][class*="title"]',
        '[class*="position"][class*="title"]',
        '[class*="title"]',
        "h1",
        "h2",
        "h3",
        "h4",
    )
    role_tokens = tokens(request.role)
    candidates: list[str] = []
    for selector in selectors:
        for element in link.select(selector):
            value = _clean_text(element.get_text(" ", strip=True))
            if 3 <= len(value) <= 300:
                candidates.append(value)
    matching = [value for value in candidates if role_tokens.intersection(tokens(value))]
    if matching:
        return min(matching, key=len)
    if candidates:
        return min(candidates, key=len)
    return _clean_text(link.get_text(" ", strip=True))[:240]


def _nested_text(container: Tag, selectors: tuple[str, ...]) -> str | None:
    for selector in selectors:
        element = container.select_one(selector)
        if element:
            value = _clean_text(element.get_text(" ", strip=True))
            if value:
                return value[:240]
    return None


def _json_ld_vacancies(
    soup: BeautifulSoup, source_url: str, source_site: str, request: SearchRequest
) -> list[Vacancy]:
    found: list[Vacancy] = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            payload = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        queue = payload if isinstance(payload, list) else [payload]
        while queue:
            item = queue.pop()
            if not isinstance(item, dict):
                continue
            graph = item.get("@graph")
            if isinstance(graph, list):
                queue.extend(graph)
            item_type = item.get("@type")
            types = item_type if isinstance(item_type, list) else [item_type]
            if "JobPosting" not in types:
                continue
            title = _clean_text(str(item.get("title") or ""))
            description = BeautifulSoup(
                str(item.get("description") or ""), "html.parser"
            ).get_text(" ")
            scored = score_text(f"{title} {description}", request)
            if not title or not scored:
                continue
            organization = item.get("hiringOrganization") or {}
            location_data = item.get("jobLocation") or {}
            if isinstance(location_data, list):
                location_data = location_data[0] if location_data else {}
            address = location_data.get("address") or {} if isinstance(location_data, dict) else {}
            location = address.get("addressLocality") if isinstance(address, dict) else None
            score, reason = scored
            found.append(
                Vacancy(
                    title=title[:240],
                    company=str(organization.get("name") or _company_from_url(source_url)),
                    location=str(location) if location else None,
                    url=urljoin(source_url, str(item.get("url") or source_url)),
                    score=score,
                    reason=reason,
                    source_site=source_site,
                )
            )
    return found


def extract_vacancies(
    html: str, source_url: str, request: SearchRequest, *, source_site: str | None = None
) -> list[Vacancy]:
    source_site = source_site or source_url
    soup = BeautifulSoup(html, "html.parser")
    company = _company_from_url(source_url)
    found: dict[str, Vacancy] = {
        str(vacancy.url): vacancy
        for vacancy in _json_ld_vacancies(soup, source_url, source_site, request)
    }

    for link in soup.find_all("a", href=True):
        href = urljoin(source_url, str(link["href"]).strip())
        parsed = urlsplit(href)
        if parsed.scheme not in {"http", "https"} or not _is_detail_url(href):
            continue

        title = _link_title(link, request)
        if len(title) < 3:
            continue
        context = _clean_text(link.get_text(" ", strip=True))[:1200]
        scored = score_text(f"{title} {context}", request)
        if not scored:
            continue
        score, reason = scored
        found[href] = Vacancy(
            title=title[:240],
            company=_nested_text(
                link,
                ('[class*="company"]', '[class*="employer"]', '[class*="brand"]'),
            )
            or company,
            location=_nested_text(
                link, ('[class*="location"]', '[class*="city"]', '[class*="region"]')
            ),
            url=href,
            score=score,
            reason=reason,
            source_site=source_site,
        )

    if _is_detail_url(source_url):
        heading = soup.select_one(
            'h1, [itemprop="title"], [class*="vacancy"][class*="title"]'
        )
        title = _clean_text(heading.get_text(" ", strip=True)) if heading else ""
        scored = score_text(f"{title} {soup.get_text(' ', strip=True)[:5000]}", request)
        if title and scored:
            score, reason = scored
            found[source_url] = Vacancy(
                title=title[:240],
                company=company,
                location=None,
                url=source_url,
                score=score,
                reason=reason,
                source_site=source_site,
            )

    return sorted(found.values(), key=lambda vacancy: (-vacancy.score, vacancy.title.lower()))


def _with_query(url: str, name: str, value: str) -> str:
    parsed = urlsplit(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query[name] = value
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), ""))


def _search_urls(url: str, html: str, role: str) -> list[str]:
    candidates: list[str] = []
    soup = BeautifulSoup(html, "html.parser")
    for form in soup.find_all("form"):
        if str(form.get("method") or "get").lower() != "get":
            continue
        action = urljoin(url, str(form.get("action") or url))
        for field in form.find_all(["input", "textarea"]):
            name = str(field.get("name") or "")
            if name and any(hint in name.lower() for hint in SEARCH_PARAMS):
                candidates.append(_with_query(action, name, role))
    candidates.extend(_with_query(url, name, role) for name in SEARCH_PARAMS)
    return list(dict.fromkeys(candidate for candidate in candidates if candidate != url))


class SiteCrawlerProvider:
    name = "site_crawler"

    def __init__(self, *, max_results: int, timeout_seconds: float = 20) -> None:
        self.max_results = max_results
        self.timeout = httpx.Timeout(timeout_seconds, connect=8)

    async def _fetch_html(
        self, client: httpx.AsyncClient, url: str
    ) -> tuple[str | None, str, str | None]:
        current_url = url
        try:
            for _ in range(5):
                await validate_public_url(current_url)
                async with client.stream("GET", current_url, follow_redirects=False) as response:
                    if response.is_redirect:
                        location = response.headers.get("location")
                        if not location:
                            break
                        current_url = urljoin(current_url, location)
                        continue
                    response.raise_for_status()
                    if "html" not in response.headers.get("content-type", "").lower():
                        return None, current_url, f"{url}: страница не вернула HTML"
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > MAX_HTML_BYTES:
                            return None, current_url, f"{url}: HTML превышает лимит 2 МБ"
                    encoding = response.encoding or "utf-8"
                    return bytes(body).decode(encoding, errors="replace"), current_url, None
            return None, current_url, f"{url}: слишком много перенаправлений"
        except (httpx.HTTPError, UnsafeUrlError) as exc:
            return None, current_url, f"{url}: {exc}"

    async def _search_generic_site(
        self, client: httpx.AsyncClient, site: str, request: SearchRequest
    ) -> tuple[list[Vacancy], list[str]]:
        html, current_url, warning = await self._fetch_html(client, site)
        if html is None:
            return [], [warning] if warning else []

        vacancies = extract_vacancies(html, current_url, request, source_site=site)
        tried = [current_url]
        for search_url in _search_urls(current_url, html, request.role):
            search_html, final_url, search_warning = await self._fetch_html(client, search_url)
            tried.append(search_url)
            if search_html:
                matches = extract_vacancies(
                    search_html, final_url, request, source_site=site
                )
                if matches:
                    vacancies.extend(matches)
                    break
            if search_warning:
                warning = search_warning

        vacancies = _deduplicate(vacancies)
        warnings = []
        if warning:
            warnings.append(warning)
        if not vacancies:
            warnings.append(
                f"{site}: прямые вакансии не найдены; проверены страница и "
                f"{len(tried) - 1} вариантов поиска"
            )
        return vacancies[: self.max_results], warnings

    async def _search_one(
        self, client: httpx.AsyncClient, site: str, request: SearchRequest
    ) -> tuple[list[Vacancy], list[str]]:
        try:
            if supports_mts(site):
                return await search_mts(
                    client, site, request, max_results=self.max_results
                )
            if supports_yandex(site):
                return await search_yandex(
                    client, site, request, max_results=self.max_results
                )
            return await self._search_generic_site(client, site, request)
        except (httpx.HTTPError, UnsafeUrlError, json.JSONDecodeError) as exc:
            return [], [f"{site}: {exc}"]

    async def search(self, request: SearchRequest) -> tuple[list[Vacancy], list[str]]:
        headers = {
            "User-Agent": "JobCompass/0.2 (+local personal vacancy search)",
            "Accept": "text/html,application/xhtml+xml,application/json",
        }
        async with httpx.AsyncClient(timeout=self.timeout, headers=headers) as client:
            results = await asyncio.gather(
                *(self._search_one(client, str(site), request) for site in request.sites)
            )
        vacancies = _deduplicate(vacancy for items, _ in results for vacancy in items)
        warnings = [warning for _, site_warnings in results for warning in site_warnings]
        return vacancies[: self.max_results], warnings


def _deduplicate(vacancies: Iterable[Vacancy]) -> list[Vacancy]:
    unique: dict[str, Vacancy] = {}
    for vacancy in vacancies:
        key = str(vacancy.url).rstrip("/")
        current = unique.get(key)
        if current is None or vacancy.score > current.score:
            unique[key] = vacancy
    return sorted(unique.values(), key=lambda vacancy: (-vacancy.score, vacancy.title.lower()))
