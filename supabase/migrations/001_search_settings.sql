-- Job Compass search settings.
-- Run this file in Supabase SQL Editor once for a new project.
--
-- The schema is in third normal form:
--   * every row represents one company, role, keyword, or exclusion;
--   * every non-key column depends on the whole primary key;
--   * no table stores derived or transitively dependent values.

create extension if not exists pgcrypto;

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

create or replace function public.set_updated_at()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists career_sites_set_updated_at on public.career_sites;
create trigger career_sites_set_updated_at
before update on public.career_sites
for each row execute function public.set_updated_at();

drop trigger if exists job_roles_set_updated_at on public.job_roles;
create trigger job_roles_set_updated_at
before update on public.job_roles
for each row execute function public.set_updated_at();

-- The public schema is exposed by Supabase REST by default. Job Compass uses a
-- direct Session Pooler connection, so browser roles must not access these rows.
alter table public.career_sites enable row level security;
alter table public.job_roles enable row level security;
alter table public.include_keywords enable row level security;
alter table public.exclude_keywords enable row level security;

revoke all on public.career_sites from anon, authenticated;
revoke all on public.job_roles from anon, authenticated;
revoke all on public.include_keywords from anon, authenticated;
revoke all on public.exclude_keywords from anon, authenticated;

comment on table public.career_sites is 'One normalized company career source per row.';
comment on table public.job_roles is 'One normalized target job title per row.';
comment on table public.include_keywords is 'One optional positive search term per row.';
comment on table public.exclude_keywords is 'One vacancy exclusion term per row.';
