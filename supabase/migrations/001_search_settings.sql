create table if not exists public.career_sites (
    id uuid primary key default gen_random_uuid(),
    name text not null check (length(trim(name)) between 1 and 120),
    career_url text not null check (career_url ~ '^https?://'),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint career_sites_career_url_key unique (career_url)
);

create unique index if not exists career_sites_name_lower_key
    on public.career_sites (lower(trim(name)));

create table if not exists public.job_roles (
    id uuid primary key default gen_random_uuid(),
    title text not null check (length(trim(title)) between 2 and 160),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create unique index if not exists job_roles_title_lower_key
    on public.job_roles (lower(trim(title)));

create table if not exists public.include_keywords (
    id uuid primary key default gen_random_uuid(),
    value text not null check (length(trim(value)) between 1 and 120),
    created_at timestamptz not null default now()
);

create unique index if not exists include_keywords_value_lower_key
    on public.include_keywords (lower(trim(value)));

create table if not exists public.exclude_keywords (
    id uuid primary key default gen_random_uuid(),
    value text not null check (length(trim(value)) between 1 and 120),
    created_at timestamptz not null default now()
);

create unique index if not exists exclude_keywords_value_lower_key
    on public.exclude_keywords (lower(trim(value)));
