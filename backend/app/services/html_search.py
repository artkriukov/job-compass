import asyncio
import re
from collections.abc import Iterable
from urllib.parse import urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup

from app.models import SearchRequest, Vacancy
from app.security import UnsafeUrlError, validate_public_url

JOB_HINTS = (
    "job",
    "jobs",
    "career",
    "careers",
    "vacancy",
    "vacancies",
    "position",
    "opening",
    "вакан",
)
TOKEN_RE = re.compile(r"[\w+#.-]+", re.UNICODE)
MAX_HTML_BYTES = 2_000_000


def _tokens(value: str) -> set[str]:
    return {token.lower() for token in TOKEN_RE.findall(value) if len(token) > 1}


def _score(text: str, request: SearchRequest) -> tuple[int, str] | None:
    haystack = text.lower()
    if any(keyword in haystack for keyword in request.exclude_keywords):
        return None

    role_tokens = _tokens(request.role)
    found_role = role_tokens.intersection(_tokens(haystack))
    role_score = int(70 * len(found_role) / max(len(role_tokens), 1))
    included = [keyword for keyword in request.include_keywords if keyword in haystack]
    include_score = int(25 * len(included) / max(len(request.include_keywords), 1))
    score = min(100, role_score + include_score + (5 if found_role else 0))
    if not found_role or score < 25:
        return None

    parts = [f"совпали слова должности: {', '.join(sorted(found_role))}"]
    if included:
        parts.append(f"ключевые слова: {', '.join(included)}")
    return score, "; ".join(parts)


def _company_from_url(url: str) -> str:
    hostname = (urlsplit(url).hostname or "").removeprefix("www.")
    return hostname.split(".")[0].replace("-", " ").title() or "Неизвестная компания"


def extract_vacancies(html: str, source_url: str, request: SearchRequest) -> list[Vacancy]:
    soup = BeautifulSoup(html, "html.parser")
    company = _company_from_url(source_url)
    found: dict[str, Vacancy] = {}

    for link in soup.find_all("a", href=True):
        href = urljoin(source_url, str(link["href"]).strip())
        parsed = urlsplit(href)
        if parsed.scheme not in {"http", "https"}:
            continue

        title = " ".join(link.get_text(" ", strip=True).split())
        if len(title) < 3:
            continue

        context = " ".join(link.parent.get_text(" ", strip=True).split())[:600]
        looks_like_job = any(hint in f"{parsed.path} {title}".lower() for hint in JOB_HINTS)
        scored = _score(f"{title} {context}", request)
        if not scored or not looks_like_job:
            continue

        score, reason = scored
        found[href] = Vacancy(
            title=title[:240],
            company=company,
            location=None,
            url=href,
            score=score,
            reason=reason,
            source_site=source_url,
        )

    return sorted(found.values(), key=lambda vacancy: (-vacancy.score, vacancy.title.lower()))


class HtmlSearchProvider:
    name = "html"

    def __init__(self, *, max_results: int, timeout_seconds: float = 20) -> None:
        self.max_results = max_results
        self.timeout = httpx.Timeout(timeout_seconds, connect=8)

    async def _fetch_one(
        self, client: httpx.AsyncClient, site: str, request: SearchRequest
    ) -> tuple[list[Vacancy], str | None]:
        current_url = site
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
                    content_type = response.headers.get("content-type", "")
                    if "html" not in content_type.lower():
                        return [], f"{site}: страница не вернула HTML"

                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > MAX_HTML_BYTES:
                            return [], f"{site}: HTML превышает лимит 2 МБ"
                    encoding = response.encoding or "utf-8"
                    html = bytes(body).decode(encoding, errors="replace")
                    return extract_vacancies(html, current_url, request), None
            return [], f"{site}: слишком много перенаправлений"
        except (httpx.HTTPError, UnsafeUrlError) as exc:
            return [], f"{site}: {exc}"

    async def search(self, request: SearchRequest) -> tuple[list[Vacancy], list[str]]:
        headers = {
            "User-Agent": "JobCompass/0.1 (+local personal vacancy search)",
            "Accept": "text/html,application/xhtml+xml",
        }
        async with httpx.AsyncClient(timeout=self.timeout, headers=headers) as client:
            results = await asyncio.gather(
                *(self._fetch_one(client, str(site), request) for site in request.sites)
            )

        vacancies = _deduplicate(vacancy for items, _ in results for vacancy in items)
        warnings = [warning for _, warning in results if warning]
        return vacancies[: self.max_results], warnings


def _deduplicate(vacancies: Iterable[Vacancy]) -> list[Vacancy]:
    unique: dict[str, Vacancy] = {}
    for vacancy in vacancies:
        key = str(vacancy.url)
        current = unique.get(key)
        if current is None or vacancy.score > current.score:
            unique[key] = vacancy
    return sorted(unique.values(), key=lambda vacancy: (-vacancy.score, vacancy.title.lower()))

