import asyncio

import psycopg

from app.models import SearchSettingsSnapshot


class SettingsStorageError(RuntimeError):
    pass


class SupabaseSettingsStore:
    def __init__(self, dsn: str | None) -> None:
        self.dsn = dsn

    @property
    def is_ready(self) -> bool:
        return bool(self.dsn)

    def _connect(self) -> psycopg.Connection:
        if not self.dsn:
            raise SettingsStorageError("SUPABASE_URL не настроен")
        try:
            return psycopg.connect(self.dsn, connect_timeout=8)
        except psycopg.Error as exc:
            raise SettingsStorageError("Не удалось подключиться к Supabase") from exc

    def _load(self) -> SearchSettingsSnapshot:
        try:
            with self._connect() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "select id, name, career_url from public.career_sites "
                        "order by lower(name)"
                    )
                    sites = [
                        {"id": row[0], "name": row[1], "url": row[2]}
                        for row in cursor.fetchall()
                    ]
                    cursor.execute(
                        "select id, title from public.job_roles order by lower(title)"
                    )
                    roles = [
                        {"id": row[0], "title": row[1]} for row in cursor.fetchall()
                    ]
                    cursor.execute(
                        "select value from public.include_keywords order by lower(value)"
                    )
                    include_keywords = [row[0] for row in cursor.fetchall()]
                    cursor.execute(
                        "select value from public.exclude_keywords order by lower(value)"
                    )
                    exclude_keywords = [row[0] for row in cursor.fetchall()]
        except psycopg.Error as exc:
            raise SettingsStorageError("Не удалось прочитать настройки из Supabase") from exc

        return SearchSettingsSnapshot.model_validate(
            {
                "sites": sites,
                "roles": roles,
                "include_keywords": include_keywords,
                "exclude_keywords": exclude_keywords,
            }
        )

    async def load(self) -> SearchSettingsSnapshot:
        return await asyncio.to_thread(self._load)

    def _save(self, snapshot: SearchSettingsSnapshot) -> None:
        try:
            with self._connect() as connection:
                with connection.transaction(), connection.cursor() as cursor:
                    cursor.execute("delete from public.career_sites")
                    cursor.execute("delete from public.job_roles")
                    cursor.execute("delete from public.include_keywords")
                    cursor.execute("delete from public.exclude_keywords")

                    if snapshot.sites:
                        cursor.executemany(
                            "insert into public.career_sites (id, name, career_url) "
                            "values (%s, %s, %s)",
                            [
                                (site.id, site.name, str(site.url))
                                for site in snapshot.sites
                            ],
                        )
                    if snapshot.roles:
                        cursor.executemany(
                            "insert into public.job_roles (id, title) values (%s, %s)",
                            [(role.id, role.title) for role in snapshot.roles],
                        )
                    if snapshot.include_keywords:
                        cursor.executemany(
                            "insert into public.include_keywords (value) values (%s)",
                            [(value,) for value in snapshot.include_keywords],
                        )
                    if snapshot.exclude_keywords:
                        cursor.executemany(
                            "insert into public.exclude_keywords (value) values (%s)",
                            [(value,) for value in snapshot.exclude_keywords],
                        )
        except psycopg.Error as exc:
            raise SettingsStorageError("Не удалось сохранить настройки в Supabase") from exc

    async def save(self, snapshot: SearchSettingsSnapshot) -> None:
        await asyncio.to_thread(self._save, snapshot)
