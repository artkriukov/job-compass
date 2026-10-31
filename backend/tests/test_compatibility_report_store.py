from datetime import UTC, datetime

import psycopg
import pytest

from app.models import (
    CompatibilityReport,
    CompatibilityResult,
    CoverLetter,
    TailoredResume,
    Vacancy,
)
from app.services.compatibility_report_store import (
    CompatibilityReportStorageError,
    SupabaseCompatibilityReportStore,
)

DEFAULT_ROW = object()


class FakeCursor:
    def __init__(
        self,
        rows: list[tuple] | None = None,
        one: tuple | None | object = DEFAULT_ROW,
    ) -> None:
        self.rows = rows or []
        self.one = one
        self.queries: list[tuple[str, tuple | None]] = []

    def __enter__(self):  # noqa: ANN204
        return self

    def __exit__(self, *_args):  # noqa: ANN204
        return None

    def execute(self, query: str, params: tuple | None = None) -> None:
        self.queries.append((query, params))

    def fetchall(self) -> list[tuple]:
        return self.rows

    def fetchone(self) -> tuple | None:
        if self.one is DEFAULT_ROW:
            return ("9bca2aaf-f083-469f-ac20-4a6fa1d443ea",)
        return self.one  # type: ignore[return-value]


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


def make_tailored_resume() -> TailoredResume:
    return TailoredResume(
        id="tailored-1",
        report_id="report-1",
        blocks=[
            {"title": "Целевая позиция", "content": "Example — Backend developer"},
            {"title": "Обо мне", "content": "Работаю с Python и SQL."},
        ],
        created_at=datetime(2026, 10, 31, 9, tzinfo=UTC),
    )


def make_cover_letter() -> CoverLetter:
    return CoverLetter(
        id="letter-1",
        report_id="report-1",
        content="Здравствуйте! Меня заинтересовала роль Backend developer. "
        "Мой подтверждённый опыт соответствует задачам вакансии. "
        "Буду рад обсудить детали и рассказать о релевантных проектах.",
        created_at=datetime(2026, 10, 31, 9, tzinfo=UTC),
        updated_at=datetime(2026, 10, 31, 9, tzinfo=UTC),
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


@pytest.mark.asyncio
async def test_report_store_round_trips_tailored_resume(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resume = make_tailored_resume()
    row = (
        resume.id,
        resume.report_id,
        [block.model_dump(mode="json") for block in resume.blocks],
        resume.created_at,
    )
    load_cursor = FakeCursor(one=row)
    store = SupabaseCompatibilityReportStore("postgresql://example")
    monkeypatch.setattr(store, "_connect", lambda: FakeConnection(load_cursor))

    loaded = await store.load_tailored_resume("report-1")

    assert loaded == resume
    save_cursor = FakeCursor()
    monkeypatch.setattr(store, "_connect", lambda: FakeConnection(save_cursor))
    await store.save_tailored_resume(resume)
    assert "insert into public.tailored_resumes" in save_cursor.queries[0][0]


@pytest.mark.asyncio
async def test_report_store_returns_none_for_missing_tailored_resume(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cursor = FakeCursor(one=None)
    store = SupabaseCompatibilityReportStore("postgresql://example")
    monkeypatch.setattr(store, "_connect", lambda: FakeConnection(cursor))

    assert await store.load_tailored_resume("missing") is None


@pytest.mark.asyncio
async def test_report_store_round_trips_cover_letter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    letter = make_cover_letter()
    row = (
        letter.id,
        letter.report_id,
        letter.content,
        letter.created_at,
        letter.updated_at,
    )
    load_cursor = FakeCursor(one=row)
    store = SupabaseCompatibilityReportStore("postgresql://example")
    monkeypatch.setattr(store, "_connect", lambda: FakeConnection(load_cursor))

    loaded = await store.load_cover_letter("report-1")

    assert loaded == letter
    save_cursor = FakeCursor()
    monkeypatch.setattr(store, "_connect", lambda: FakeConnection(save_cursor))
    await store.save_cover_letter(letter)
    assert "insert into public.cover_letters" in save_cursor.queries[0][0]


def test_report_store_wraps_tailored_resume_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = SupabaseCompatibilityReportStore("postgresql://example")
    monkeypatch.setattr(
        store,
        "_connect",
        lambda: (_ for _ in ()).throw(psycopg.OperationalError()),
    )

    with pytest.raises(CompatibilityReportStorageError, match="прочитать адаптированное"):
        store._load_tailored_resume("report-1")
    with pytest.raises(CompatibilityReportStorageError, match="сохранить адаптированное"):
        store._save_tailored_resume(make_tailored_resume())


def test_report_store_wraps_cover_letter_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = SupabaseCompatibilityReportStore("postgresql://example")
    monkeypatch.setattr(
        store,
        "_connect",
        lambda: (_ for _ in ()).throw(psycopg.OperationalError()),
    )

    with pytest.raises(CompatibilityReportStorageError, match="прочитать сопроводительное"):
        store._load_cover_letter("report-1")
    with pytest.raises(CompatibilityReportStorageError, match="сохранить сопроводительное"):
        store._save_cover_letter(make_cover_letter())


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
