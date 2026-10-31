create table if not exists public.compatibility_reports (
    id text primary key,
    vacancy_id uuid not null references public.vacancies(id) on delete cascade,
    mode text not null check (mode in ('quick', 'full')),
    result jsonb not null,
    content text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists compatibility_reports_vacancy_created_idx
    on public.compatibility_reports (vacancy_id, created_at desc);
