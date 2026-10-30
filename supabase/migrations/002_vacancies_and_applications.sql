create table if not exists public.vacancies (
    id uuid primary key default gen_random_uuid(),
    url text not null unique check (url ~ '^https?://'),
    title text not null check (length(trim(title)) between 1 and 300),
    company text,
    location text,
    source_site text not null check (source_site ~ '^https?://'),
    first_seen_at timestamptz not null default now(),
    last_seen_at timestamptz not null default now(),
    seen_count integer not null default 1 check (seen_count > 0)
);

create table if not exists public.job_applications (
    id uuid primary key default gen_random_uuid(),
    vacancy_id uuid not null unique references public.vacancies(id) on delete cascade,
    stage text not null default 'review'
        check (stage in ('review', 'hr_interview', 'technical_interview', 'offer')),
    hr_url text not null default '',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
