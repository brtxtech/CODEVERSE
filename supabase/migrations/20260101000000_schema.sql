-- =====================================================================
-- Schema: reference data (public read), user data (owner only), storage
-- Conventions: all search terms are lower-case, trimmed and de-duplicated
-- (enforced by CHECK constraints via norm_terms), so matching is a plain
-- array operation that GIN indexes can serve.
-- =====================================================================

create or replace function public.norm_terms(p text[])
returns text[]
language sql immutable parallel safe
set search_path = ''
as $$
  select coalesce(array_agg(t order by first_pos), '{}')
  from (select lower(btrim(x)) as t, min(pos) as first_pos
        from unnest(p) with ordinality as u(x, pos)
        where btrim(x) <> ''
        group by 1) s;
$$;

-- ---------- Reference data -------------------------------------------

create table public.jobs (
  id            text primary key check (id ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
  title         text not null,
  title_es      text,
  family        text not null,
  summary       text,
  skills        text[] not null check (cardinality(skills) > 0 and skills = public.norm_terms(skills)),
  github_topics text[] not null default '{}' check (github_topics = public.norm_terms(github_topics)),
  company_focus text[] not null default '{}' check (company_focus = public.norm_terms(company_focus)),
  entry_level   boolean not null default true
);
create index jobs_skills_gin on public.jobs using gin (skills);

create table public.geo_places (
  city    text primary key check (city = lower(btrim(city))),
  country text not null check (country ~ '^[A-Z]{2}$'),
  region  text not null,
  area    text
);

create table public.companies (
  id          bigint generated always as identity primary key,
  name        text not null unique,
  focus       text[] not null default '{}' check (focus = public.norm_terms(focus)),
  careers_url text check (careers_url is null or careers_url ~ '^https://')
);

create table public.company_offices (
  company_id bigint not null references public.companies on delete cascade,
  city       text   not null check (city = lower(btrim(city))),
  country    text   not null check (country ~ '^[A-Z]{2}$'),
  area       text,
  region     text,
  is_hq      boolean not null default false,
  primary key (company_id, city)
);
-- one index per proximity level used by recommend_companies
create index company_offices_city    on public.company_offices (city);
create index company_offices_area    on public.company_offices (area) where area is not null;
create index company_offices_country on public.company_offices (country);
create index company_offices_region  on public.company_offices (region) where region is not null;

create table public.repos (
  full_name         text primary key check (full_name ~ '^[^/]+/[^/]+$'),
  description       text,
  language          text,
  topics            text[] not null default '{}' check (topics = public.norm_terms(topics)),
  stars             int  not null default 0 check (stars >= 0),
  license           text,
  pushed_at         timestamptz,
  good_first_issues int  not null default 0 check (good_first_issues >= 0),
  synced_at         timestamptz not null default now()
);
create index repos_topics_gin on public.repos using gin (topics);

create view public.skill_vocabulary with (security_invoker = true) as
  select distinct unnest(skills) as skill from public.jobs;

-- ---------- User data ------------------------------------------------

create table public.cvs (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid not null default auth.uid() references auth.users on delete cascade,
  storage_path text,
  parsed       jsonb,
  result       jsonb,
  created_at   timestamptz not null default now()
);
create index cvs_user_recent on public.cvs (user_id, created_at desc);  -- list + rate-limit query

-- ---------- RLS -------------------------------------------------------
-- (select auth.uid()) is evaluated once per query instead of once per row.

alter table public.jobs            enable row level security;
alter table public.geo_places      enable row level security;
alter table public.companies       enable row level security;
alter table public.company_offices enable row level security;
alter table public.repos           enable row level security;
alter table public.cvs             enable row level security;

create policy "public read" on public.jobs            for select to anon, authenticated using (true);
create policy "public read" on public.geo_places      for select to anon, authenticated using (true);
create policy "public read" on public.companies       for select to anon, authenticated using (true);
create policy "public read" on public.company_offices for select to anon, authenticated using (true);
create policy "public read" on public.repos           for select to anon, authenticated using (true);

create policy "owner select" on public.cvs for select to authenticated using (user_id = (select auth.uid()));
create policy "owner insert" on public.cvs for insert to authenticated with check (user_id = (select auth.uid()));
create policy "owner delete" on public.cvs for delete to authenticated using (user_id = (select auth.uid()));
-- no update policy: results are immutable; re-run the pipeline to create a new row

-- ---------- Storage ---------------------------------------------------

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('cvs', 'cvs', false, 5242880, array['application/pdf', 'text/plain'])
on conflict (id) do nothing;

create policy "cv own folder insert" on storage.objects for insert to authenticated
  with check (bucket_id = 'cvs' and (storage.foldername(name))[1] = (select auth.uid())::text);
create policy "cv own folder select" on storage.objects for select to authenticated
  using (bucket_id = 'cvs' and (storage.foldername(name))[1] = (select auth.uid())::text);
create policy "cv own folder delete" on storage.objects for delete to authenticated
  using (bucket_id = 'cvs' and (storage.foldername(name))[1] = (select auth.uid())::text);
