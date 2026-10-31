from datetime import UTC, datetime

import psycopg
import pytest

from app.models import CompatibilityReport, CompatibilityResult, Vacancy
from app.services.compatibility_report_store import (
    CompatibilityReportStorageError,
    SupabaseCompatibilityReportStore,
)


class FakeCursor:
    def __init__(self, rows: list[tuple] | None = None) -> None:
        self.rows = rows or []
        self.queries: list[tuple[str, tuple | None]] = []

    def __enter__(self):  # noqa: ANN204
        return self

    def __exit__(self, *_args):  # noqa: ANN204
        return None

    def execute(self, query: str, params: tuple | None = None) -> None:
        self.queries.append((query, params))

    def fetchall(self) -> list[tuple]:
        return self.rows

    def fetchone(self) -> tuple[str]:
        return ("9bca2aaf-f083-469f-ac20-4a6fa1d443ea",)


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self.fake_cursor = cursor

    def __enter__(self):  # noqa: ANN204
        return self

    def __exit__(self, *_args):  # noqa: ANN204
        return None

    def cursor(self) -> FakeCursor:
        return self.fake_cursor

    def transaction(self):  # noqa: ANN201
        return self


def make_report() -> CompatibilityReport:
    return CompatibilityReport(
        id="report-1",
        vacancy=Vacancy(
            title="Backend developer",
            company="Example",
            location="Remote",
            url="https://example.com/jobs/1",
            score=90,
            reason="совпадает роль",
            source_site="https://example.com/jobs",
        ),
        mode="quick",
        result=CompatibilityResult(
            score=4.2,
            decision="apply",
            summary="Хорошее совпадение",
        ),
        created_at=datetime(2026, 10, 31, 8, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_report_store_loads_reports(monkeypatch: pytest.MonkeyPatch) -> None:
    report = make_report()
    row = (
        report.id,
        report.vacancy.title,
        report.vacancy.company,
        report.vacancy.location,
        str(report.vacancy.url),
        str(report.vacancy.source_site),
        report.mode,
        report.created_at,
        report.result.model_dump(mode="json"),
        None,
    )
    cursor = FakeCursor([row])
    store = SupabaseCompatibilityReportStore("postgresql://example")
    monkeypatch.setattr(store, "_connect", lambda: FakeConnection(cursor))

    loaded = await store.load()

    assert loaded[0].id == report.id
    assert loaded[0].result.score == 4.2
    assert "order by r.created_at desc" in cursor.queries[0][0]


@pytest.mark.asyncio
async def test_report_store_saves_reports(monkeypatch: pytest.MonkeyPatch) -> None:
    cursor = FakeCursor()
    store = SupabaseCompatibilityReportStore("postgresql://example")
    monkeypatch.setattr(store, "_connect", lambda: FakeConnection(cursor))

    await store.save(make_report())
    await store.save_many([])

    assert store.is_ready is True
    assert len(cursor.queries) == 2
    assert "insert into public.vacancies" in cursor.queries[0][0]
    assert "insert into public.compatibility_reports" in cursor.queries[1][0]


def test_report_store_without_dsn_is_not_ready() -> None:
    store = SupabaseCompatibilityReportStore(None)

    assert store.is_ready is False
    with pytest.raises(CompatibilityReportStorageError, match="SUPABASE_URL"):
        store._connect()


def test_report_store_wraps_connection_error(monkeypatch: pytest.MonkeyPatch) -> None:
    store = SupabaseCompatibilityReportStore("postgresql://example")
    monkeypatch.setattr(
        "app.services.compatibility_report_store.psycopg.connect",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(psycopg.OperationalError()),
    )

    with pytest.raises(CompatibilityReportStorageError, match="подключиться"):
        store._connect()
