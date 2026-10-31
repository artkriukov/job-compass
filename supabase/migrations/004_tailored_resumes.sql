create table if not exists public.tailored_resumes (
    id text primary key,
    report_id text not null unique
        references public.compatibility_reports(id) on delete cascade,
    blocks jsonb not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
