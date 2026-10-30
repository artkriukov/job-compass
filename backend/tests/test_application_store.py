from datetime import UTC, datetime
from uuid import UUID

import pytest

from app.models import ApplicationCreate, ApplicationUpdate, SearchResponse, Vacancy
from app.services.application_store import SupabaseApplicationStore


class FakeDatabase:
    def __init__(self) -> None:
        self.vacancies = {}
        self.applications = {}


class FakeCursor:
    def __init__(self, database: FakeDatabase) -> None:
        self.database = database
        self.one = None
        self.all = []

    def __enter__(self):  # noqa: ANN204
        return self

    def __exit__(self, *_args):  # noqa: ANN002, ANN204
        return False

    def execute(self, query, params=None):  # noqa: ANN001, ANN201, PLR0912
        normalized = " ".join(query.split())
        params = params or ()
        if normalized.startswith("select id from public.vacancies"):
            vacancy = self.database.vacancies.get(params[0])
            self.one = (vacancy["id"],) if vacancy else None
        elif normalized.startswith("insert into public.vacancies"):
            url, title, company, location, source_site = params
            vacancy = self.database.vacancies.get(url)
            if vacancy is None:
                vacancy = {
                    "id": UUID("10000000-0000-0000-0000-000000000001"),
                    "url": url,
                    "seen_count": 1,
                }
                self.database.vacancies[url] = vacancy
            else:
                vacancy["seen_count"] += 1
            vacancy.update({
                "title": title, "company": company, "location": location,
                "source_site": source_site,
            })
            self.one = (vacancy["id"],)
        elif normalized.startswith("select exists"):
            applied = any(
                item["vacancy_id"] == params[0]
                for item in self.database.applications.values()
            )
            self.one = (applied,)
        elif normalized.startswith("insert into public.job_applications"):
            existing = next(
                (
                    item for item in self.database.applications.values()
                    if item["vacancy_id"] == params[0]
                ),
                None,
            )
            if existing is None:
                application_id = UUID("20000000-0000-0000-0000-000000000002")
                now = datetime(2026, 10, 29, 12, tzinfo=UTC)
                existing = {
                    "id": application_id, "vacancy_id": params[0], "hr_url": "",
                    "stage": "review", "created_at": now, "updated_at": now,
                }
                self.database.applications[application_id] = existing
            self.one = (existing["id"],)
        elif normalized.startswith("select a.id"):
            rows = [self._row(item) for item in self.database.applications.values()]
            if "where a.id" in normalized:
                row = next((row for row in rows if row[0] == params[0]), None)
                self.one = row
            else:
                self.all = rows
        elif normalized.startswith("update public.job_applications"):
            application = self.database.applications[params[-1]]
            offset = 0
            if "stage = %s" in normalized:
                application["stage"] = params[offset]
                offset += 1
            if "hr_url = %s" in normalized:
                application["hr_url"] = params[offset]
            application["updated_at"] = datetime(2026, 10, 29, 13, tzinfo=UTC)
        elif normalized.startswith("delete from public.job_applications"):
            self.database.applications.pop(params[0], None)

    def _row(self, application):  # noqa: ANN001, ANN202
        vacancy = next(
            item for item in self.database.vacancies.values()
            if item["id"] == application["vacancy_id"]
        )
        return (
            application["id"], vacancy["company"], vacancy["title"], vacancy["url"],
            application["hr_url"], application["stage"], application["created_at"],
            application["updated_at"],
        )

    def fetchone(self):  # noqa: ANN201
        return self.one

    def fetchall(self):  # noqa: ANN201
        return self.all


class FakeConnection:
    def __init__(self, database: FakeDatabase) -> None:
        self.database = database

    def __enter__(self):  # noqa: ANN204
        return self

    def __exit__(self, *_args):  # noqa: ANN002, ANN204
        return False

    def transaction(self):  # noqa: ANN201
        return self

    def cursor(self):  # noqa: ANN201
        return FakeCursor(self.database)


@pytest.mark.asyncio
async def test_application_store_tracks_and_manages_applications(monkeypatch) -> None:  # noqa: ANN001
    database = FakeDatabase()
    monkeypatch.setattr(
        "app.services.application_store.psycopg.connect",
        lambda *_args, **_kwargs: FakeConnection(database),
    )
    store = SupabaseApplicationStore("postgresql://example")
    vacancy = Vacancy(
        title="Support engineer", company="Example", location="Remote",
        url="https://example.com/jobs/1", score=90, reason="Matches",
        source_site="https://example.com/jobs",
    )
    response = SearchResponse(provider="site_crawler", vacancies=[vacancy])

    first = await store.track_search(response)
    second = await store.track_search(response)
    created = await store.create(ApplicationCreate(
        title=vacancy.title, company=vacancy.company, location=vacancy.location,
        vacancy_url=vacancy.url, source_site=vacancy.source_site,
    ))
    tracked_after_application = await store.track_search(response)
    listed = await store.load()
    updated = await store.update(created.id, ApplicationUpdate(
        stage="hr_interview", hr_url="https://t.me/recruiter",
    ))
    await store.delete(created.id)

    assert first.vacancies[0].seen_before is False
    assert second.vacancies[0].seen_before is True
    assert tracked_after_application.vacancies[0].applied is True
    assert listed[0].vacancy_url == vacancy.url
    assert updated.stage == "hr_interview"
    assert updated.hr_url == "https://t.me/recruiter"
    assert await store.load() == []
