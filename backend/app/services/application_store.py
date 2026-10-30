import asyncio
from uuid import UUID

import psycopg

from app.models import ApplicationCreate, ApplicationUpdate, JobApplication, SearchResponse


class ApplicationStorageError(RuntimeError):
    pass


class SupabaseApplicationStore:
    def __init__(self, dsn: str | None) -> None:
        self.dsn = dsn

    def _connect(self) -> psycopg.Connection:
        if not self.dsn:
            raise ApplicationStorageError("SUPABASE_URL не настроен")
        try:
            return psycopg.connect(self.dsn, connect_timeout=8)
        except psycopg.Error as exc:
            raise ApplicationStorageError("Не удалось подключиться к Supabase") from exc

    def _track_search(self, response: SearchResponse) -> SearchResponse:
        tracked = []
        try:
            with (
                self._connect() as connection,
                connection.transaction(),
                connection.cursor() as cursor,
            ):
                for vacancy in response.vacancies:
                    url = str(vacancy.url)
                    cursor.execute("select id from public.vacancies where url = %s", (url,))
                    existing = cursor.fetchone()
                    cursor.execute(
                        "insert into public.vacancies (url, title, company, location, source_site) "
                        "values (%s, %s, %s, %s, %s) "
                        "on conflict (url) do update set title = excluded.title, "
                        "company = excluded.company, location = excluded.location, "
                        "source_site = excluded.source_site, last_seen_at = now(), "
                        "seen_count = public.vacancies.seen_count + 1 returning id",
                        (
                            url,
                            vacancy.title,
                            vacancy.company,
                            vacancy.location,
                            str(vacancy.source_site),
                        ),
                    )
                    vacancy_id = cursor.fetchone()[0]
                    cursor.execute(
                        "select exists(select 1 from public.job_applications "
                        "where vacancy_id = %s)",
                        (vacancy_id,),
                    )
                    tracked.append(
                        vacancy.model_copy(
                            update={
                                "seen_before": existing is not None,
                                "applied": cursor.fetchone()[0],
                            }
                        )
                    )
        except psycopg.Error as exc:
            raise ApplicationStorageError("Не удалось сохранить найденные вакансии") from exc
        return response.model_copy(update={"vacancies": tracked})

    async def track_search(self, response: SearchResponse) -> SearchResponse:
        return await asyncio.to_thread(self._track_search, response)

    @staticmethod
    def _application_from_row(row: tuple) -> JobApplication:
        return JobApplication.model_validate(
            {
                "id": row[0],
                "company": row[1] or "Компания не указана",
                "vacancy_title": row[2],
                "vacancy_url": row[3],
                "hr_url": row[4],
                "stage": row[5],
                "created_at": row[6],
                "updated_at": row[7],
            }
        )

    def _load(self) -> list[JobApplication]:
        try:
            with self._connect() as connection, connection.cursor() as cursor:
                cursor.execute(
                    "select a.id, v.company, v.title, v.url, a.hr_url, a.stage, "
                    "a.created_at, a.updated_at from public.job_applications a "
                    "join public.vacancies v on v.id = a.vacancy_id "
                    "order by a.updated_at desc"
                )
                return [self._application_from_row(row) for row in cursor.fetchall()]
        except psycopg.Error as exc:
            raise ApplicationStorageError("Не удалось прочитать отклики из Supabase") from exc

    async def load(self) -> list[JobApplication]:
        return await asyncio.to_thread(self._load)

    def _create(self, payload: ApplicationCreate) -> JobApplication:
        try:
            with (
                self._connect() as connection,
                connection.transaction(),
                connection.cursor() as cursor,
            ):
                cursor.execute(
                    "insert into public.vacancies (url, title, company, location, source_site) "
                    "values (%s, %s, %s, %s, %s) on conflict (url) do update set "
                    "title = excluded.title, company = excluded.company, "
                    "location = excluded.location, "
                    "source_site = excluded.source_site returning id",
                    (
                        str(payload.vacancy_url),
                        payload.title,
                        payload.company,
                        payload.location,
                        str(payload.source_site),
                    ),
                )
                vacancy_id = cursor.fetchone()[0]
                cursor.execute(
                    "insert into public.job_applications (vacancy_id) values (%s) "
                    "on conflict (vacancy_id) do update set "
                    "updated_at = public.job_applications.updated_at "
                    "returning id",
                    (vacancy_id,),
                )
                application_id = cursor.fetchone()[0]
                return self._get_with_cursor(cursor, application_id)
        except psycopg.Error as exc:
            raise ApplicationStorageError("Не удалось сохранить отклик в Supabase") from exc

    def _get_with_cursor(self, cursor: psycopg.Cursor, application_id: UUID) -> JobApplication:
        cursor.execute(
            "select a.id, v.company, v.title, v.url, a.hr_url, a.stage, "
            "a.created_at, a.updated_at from public.job_applications a "
            "join public.vacancies v on v.id = a.vacancy_id where a.id = %s",
            (application_id,),
        )
        row = cursor.fetchone()
        if row is None:
            raise ApplicationStorageError("Отклик не найден")
        return self._application_from_row(row)

    async def create(self, payload: ApplicationCreate) -> JobApplication:
        return await asyncio.to_thread(self._create, payload)

    def _update(self, application_id: UUID, payload: ApplicationUpdate) -> JobApplication:
        assignments = []
        values = []
        if "stage" in payload.model_fields_set:
            assignments.append("stage = %s")
            values.append(payload.stage)
        if "hr_url" in payload.model_fields_set:
            assignments.append("hr_url = %s")
            values.append(payload.hr_url)
        if not assignments:
            raise ApplicationStorageError("Нет изменений для сохранения")
        assignments.append("updated_at = now()")
        try:
            with (
                self._connect() as connection,
                connection.transaction(),
                connection.cursor() as cursor,
            ):
                cursor.execute(
                    f"update public.job_applications set {', '.join(assignments)} where id = %s",  # noqa: S608
                    (*values, application_id),
                )
                return self._get_with_cursor(cursor, application_id)
        except psycopg.Error as exc:
            raise ApplicationStorageError("Не удалось обновить отклик в Supabase") from exc

    async def update(self, application_id: UUID, payload: ApplicationUpdate) -> JobApplication:
        return await asyncio.to_thread(self._update, application_id, payload)

    def _delete(self, application_id: UUID) -> None:
        try:
            with self._connect() as connection, connection.cursor() as cursor:
                cursor.execute(
                    "delete from public.job_applications where id = %s", (application_id,)
                )
        except psycopg.Error as exc:
            raise ApplicationStorageError("Не удалось удалить отклик из Supabase") from exc

    async def delete(self, application_id: UUID) -> None:
        await asyncio.to_thread(self._delete, application_id)
