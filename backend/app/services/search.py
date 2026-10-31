from app.config import Settings
from app.models import SearchRequest, SearchResponse, Vacancy
from app.services.ai_job_search import AiJobSearchError, AiJobSearchProvider
from app.services.html_search import SiteCrawlerProvider


class SearchService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.crawler = SiteCrawlerProvider(max_results=settings.max_results)
        self.ai_job_search = (
            AiJobSearchProvider(
                root=settings.ai_job_search_root,
                codex_bin=settings.codex_bin,
                timeout_seconds=settings.codex_timeout_seconds,
                max_results=settings.max_results,
            )
            if settings.ai_job_search_root
            else None
        )

    @property
    def ai_job_search_ready(self) -> bool:
        return bool(self.ai_job_search and self.ai_job_search.is_ready())

    async def search(self, request: SearchRequest) -> SearchResponse:
        if len(request.sites) > self.settings.max_sites:
            raise ValueError(f"Можно проверить не более {self.settings.max_sites} сайтов")

        should_use_ai_job_search = self.settings.search_provider == "ai_job_search" or (
            self.settings.search_provider == "auto" and self.ai_job_search_ready
        )
        if should_use_ai_job_search:
            if not self.ai_job_search_ready or not self.ai_job_search:
                if self.settings.search_provider == "ai_job_search":
                    raise AiJobSearchError(
                        "AI Job Search не готов: проверьте AI_JOB_SEARCH_ROOT и codex"
                    )
            else:
                try:
                    vacancies, warnings = await self.ai_job_search.search(request)
                    return SearchResponse(
                        provider="ai_job_search", vacancies=vacancies, warnings=warnings
                    )
                except AiJobSearchError as exc:
                    if self.settings.search_provider == "ai_job_search":
                        raise
                    vacancies, warnings = await self.crawler.search(request)
                    warnings.insert(
                        0, f"AI Job Search недоступен, использован поиск по карьерным сайтам: {exc}"
                    )
                    return SearchResponse(
                        provider="site_crawler", vacancies=vacancies, warnings=warnings
                    )

        vacancies, warnings = await self.crawler.search(request)
        return SearchResponse(provider="site_crawler", vacancies=vacancies, warnings=warnings)

    async def import_vacancy(self, url: str) -> Vacancy:
        return await self.crawler.import_vacancy(url)

