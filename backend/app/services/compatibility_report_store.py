import asyncio

import psycopg
from psycopg.types.json import Jsonb

from app.models import CompatibilityReport, TailoredResume


class CompatibilityReportStorageError(RuntimeError):
    pass


class SupabaseCompatibilityReportStore:
    def __init__(self, dsn: str | None) -> None:
        self.dsn = dsn

    @property
    def is_ready(self) -> bool:
        return bool(self.dsn)

    def _connect(self) -> psycopg.Connection:
        if not self.dsn:
            raise CompatibilityReportStorageError("SUPABASE_URL не настроен")
        try:
            return psycopg.connect(self.dsn, connect_timeout=8)
        except psycopg.Error as exc:
            raise CompatibilityReportStorageError("Не удалось подключиться к Supabase") from exc

    @staticmethod
    def _from_row(row: tuple) -> CompatibilityReport:
        result = row[8]
        return CompatibilityReport.model_validate({
            "id": row[0],
            "vacancy": {
                "title": row[1],
                "company": row[2],
                "location": row[3],
                "url": row[4],
                "score": round(float(result["score"]) * 20),
                "reason": "Сохранённый отчёт совместимости",
                "source_site": row[5],
            },
            "mode": row[6],
            "created_at": row[7],
            "result": result,
            "content": row[9],
        })

    def _load(self) -> list[CompatibilityReport]:
        try:
            with self._connect() as connection, connection.cursor() as cursor:
                cursor.execute(
                    "select r.id, v.title, v.company, v.location, v.url, v.source_site, "
                    "r.mode, r.created_at, r.result, r.content "
                    "from public.compatibility_reports r "
                    "join public.vacancies v on v.id = r.vacancy_id "
                    "order by r.created_at desc"
                )
                return [self._from_row(row) for row in cursor.fetchall()]
        except psycopg.Error as exc:
            raise CompatibilityReportStorageError(
                "Не удалось прочитать отчёты из Supabase"
            ) from exc

    async def load(self) -> list[CompatibilityReport]:
        return await asyncio.to_thread(self._load)

    def _save_many(self, reports: list[CompatibilityReport]) -> None:
        if not reports:
            return
        try:
            with (
                self._connect() as connection,
                connection.transaction(),
                connection.cursor() as cursor,
            ):
                for report in reports:
                    vacancy = report.vacancy
                    cursor.execute(
                        "insert into public.vacancies "
                        "(url, title, company, location, source_site) "
                        "values (%s, %s, %s, %s, %s) "
                        "on conflict (url) do update set title = excluded.title, "
                        "company = excluded.company, location = excluded.location, "
                        "source_site = excluded.source_site returning id",
                        (
                            str(vacancy.url),
                            vacancy.title,
                            vacancy.company,
                            vacancy.location,
                            str(vacancy.source_site),
                        ),
                    )
                    vacancy_id = cursor.fetchone()[0]
                    cursor.execute(
                        "insert into public.compatibility_reports "
                        "(id, vacancy_id, mode, result, content, created_at) "
                        "values (%s, %s, %s, %s, %s, %s) "
                        "on conflict (id) do update set vacancy_id = excluded.vacancy_id, "
                        "mode = excluded.mode, result = excluded.result, "
                        "content = excluded.content, updated_at = now()",
                        (
                            report.id,
                            vacancy_id,
                            report.mode,
                            Jsonb(report.result.model_dump(mode="json")),
                            report.content,
                            report.created_at,
                        ),
                    )
        except psycopg.Error as exc:
            raise CompatibilityReportStorageError(
                "Не удалось сохранить отчёты в Supabase"
            ) from exc

    async def save_many(self, reports: list[CompatibilityReport]) -> None:
        await asyncio.to_thread(self._save_many, reports)

    async def save(self, report: CompatibilityReport) -> None:
        await self.save_many([report])

    def _load_tailored_resume(self, report_id: str) -> TailoredResume | None:
        try:
            with self._connect() as connection, connection.cursor() as cursor:
                cursor.execute(
                    "select id, report_id, blocks, created_at "
                    "from public.tailored_resumes where report_id = %s",
                    (report_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                return TailoredResume.model_validate({
                    "id": row[0],
                    "report_id": row[1],
                    "blocks": row[2],
                    "created_at": row[3],
                })
        except psycopg.Error as exc:
            raise CompatibilityReportStorageError(
                "Не удалось прочитать адаптированное резюме из Supabase"
            ) from exc

    async def load_tailored_resume(self, report_id: str) -> TailoredResume | None:
        return await asyncio.to_thread(self._load_tailored_resume, report_id)

    def _save_tailored_resume(self, resume: TailoredResume) -> None:
        try:
            with self._connect() as connection, connection.cursor() as cursor:
                cursor.execute(
                    "insert into public.tailored_resumes "
                    "(id, report_id, blocks, created_at) values (%s, %s, %s, %s) "
                    "on conflict (report_id) do update set id = excluded.id, "
                    "blocks = excluded.blocks, created_at = excluded.created_at, "
                    "updated_at = now()",
                    (
                        resume.id,
                        resume.report_id,
                        Jsonb([block.model_dump(mode="json") for block in resume.blocks]),
                        resume.created_at,
                    ),
                )
        except psycopg.Error as exc:
            raise CompatibilityReportStorageError(
                "Не удалось сохранить адаптированное резюме в Supabase"
            ) from exc

    async def save_tailored_resume(self, resume: TailoredResume) -> None:
        await asyncio.to_thread(self._save_tailored_resume, resume)
