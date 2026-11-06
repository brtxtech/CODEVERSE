-- =====================================================================
-- Pipeline functions. All are STABLE, SECURITY INVOKER (RLS applies),
-- search_path-pinned and callable only by signed-in users.
-- =====================================================================

create or replace function public.resolve_place(p_text text)
returns setof public.geo_places
language sql stable parallel safe set search_path = ''
as $$
  select g.* from public.geo_places g
  where lower(coalesce(p_text, '')) like '%' || g.city || '%'
  order by length(g.city) desc
  limit 1;
$$;

-- score = 0.7 * coverage + 0.3 * min(1, hits / 4)   (same as job_matcher.py)
create or replace function public.recommend_jobs(
  p_skills text[], p_top int default 10, p_entry_only boolean default true)
returns table (id text, title text, title_es text, family text, score numeric,
               you_have text[], to_learn text[], github_topics text[], company_focus text[])
language sql stable parallel safe set search_path = ''
as $$
  with mine as (select public.norm_terms(p_skills) as sk)
  select j.id, j.title, j.title_es, j.family,
         round(100 * (0.7 * cardinality(m.hit)::numeric / cardinality(j.skills)
                    + 0.3 * least(1::numeric, cardinality(m.hit) / 4.0)), 1) as score,
         m.hit, m.miss, j.github_topics, j.company_focus
  from public.jobs j
  cross join mine
  cross join lateral (
    select array(select x from unnest(j.skills) x where x =  any (mine.sk) order by x) as hit,
           array(select x from unnest(j.skills) x where x <> all (mine.sk) order by x) as miss) m
  where j.skills && mine.sk                       -- GIN-friendly pre-filter
    and (not p_entry_only or j.entry_level)
  order by score desc, j.title
  limit least(greatest(p_top, 1), 50);
$$;

create or replace function public.skill_gap(
  p_skills text[], p_top int default 5, p_entry_only boolean default true)
returns table (skill text, needed_by text[])
language sql stable parallel safe set search_path = ''
as $$
  select t.skill, array_agg(r.title order by r.score desc)
  from public.recommend_jobs(p_skills, p_top, p_entry_only) r
  cross join lateral unnest(r.to_learn) as t(skill)
  group by t.skill
  order by count(*) desc, t.skill;
$$;

-- proximity: same city 80 | same area 75 | same country 60 | same region 40, +10 focus match
-- Each company is ranked by its CLOSEST office.
create or replace function public.recommend_companies(
  p_city text, p_country text, p_area text, p_region text,
  p_focus text[] default '{}', p_top int default 10)
returns table (name text, near_you text, score int, careers_url text)
language sql stable parallel safe set search_path = ''
as $$
  with closest as (
    select distinct on (c.id) c.name, c.focus, c.careers_url, m.label, m.base
    from public.company_offices o
    join public.companies c on c.id = o.company_id
    cross join lateral (
      select case when o.city = lower(p_city)             then 'same city'
                  when o.area = p_area                    then 'same area (' || p_area || ')'
                  when o.country = p_country              then 'same country'
                  when o.region = p_region                then 'same region' end as label,
             case when o.city = lower(p_city)             then 80
                  when o.area = p_area                    then 75
                  when o.country = p_country              then 60
                  when o.region = p_region                then 40 end as base) m
    where m.base is not null
    order by c.id, m.base desc
  )
  select k.name, k.label, least(100, k.base + case when k.focus && p_focus then 10 else 0 end),
         k.careers_url
  from closest k
  order by 3 desc, k.name
  limit least(greatest(p_top, 1), 50);
$$;

-- relevance 60 (topic overlap) + activity 25 (pushed in last 12 months) + beginner 15
create or replace function public.recommend_repos(
  p_skills text[], p_topics text[], p_top int default 10)
returns table (full_name text, score numeric, matched_on text[], stars int)
language sql stable parallel safe set search_path = ''
as $$
  with want as (select public.norm_terms(p_skills || p_topics) as w)
  select r.full_name,
         round(60 * least(1::numeric, cardinality(m.hit) / 4.0)
             + 25 * greatest(0::numeric, 1 - extract(epoch from now() - r.pushed_at) / 31536000)
             + 15 * ((r.good_first_issues > 0)::int * 0.6 + (r.license is not null)::int * 0.4), 1) as score,
         m.hit, r.stars
  from public.repos r
  cross join want
  cross join lateral (select array(select t from unnest(r.topics) t where t = any (want.w) order by t) as hit) m
  where r.topics && want.w                         -- uses repos_topics_gin
  order by score desc, r.stars desc
  limit least(greatest(p_top, 1), 50);
$$;

create or replace function public.run_pipeline(p_cv jsonb, p_top_jobs int default 5)
returns jsonb
language plpgsql stable set search_path = ''
as $$
declare
  v_skills text[] := public.norm_terms(array(
    select jsonb_array_elements_text(
      case when jsonb_typeof(p_cv -> 'skills') = 'array' then p_cv -> 'skills' else '[]'::jsonb end)
    limit 100));
  v_place  public.geo_places;
  v_jobs   jsonb;
  v_focus  text[];
  v_topics text[];
begin
  select * into v_place from public.resolve_place(p_cv #>> '{contact,location,city}');

  select coalesce(jsonb_agg(to_jsonb(r)), '[]') into v_jobs
  from public.recommend_jobs(v_skills, p_top_jobs) r;

  v_focus  := array(select distinct f from jsonb_array_elements(v_jobs) j, jsonb_array_elements_text(j -> 'company_focus') f);
  v_topics := array(select distinct t from jsonb_array_elements(v_jobs) j, jsonb_array_elements_text(j -> 'github_topics') t);

  return jsonb_build_object(
    'location',  case when v_place.city is not null then to_jsonb(v_place) end,
    'jobs',      v_jobs,
    'companies', (select coalesce(jsonb_agg(to_jsonb(c)), '[]')
                  from public.recommend_companies(v_place.city, v_place.country, v_place.area, v_place.region, v_focus) c),
    'skills',    (select coalesce(jsonb_agg(to_jsonb(s)), '[]') from public.skill_gap(v_skills, p_top_jobs) s),
    'repos',     (select coalesce(jsonb_agg(to_jsonb(r)), '[]') from public.recommend_repos(v_skills, v_topics) r));
end;
$$;

-- Only signed-in users may call the pipeline (default Supabase grants also include anon)
do $$
declare f regprocedure;
begin
  for f in select p.oid::regprocedure from pg_proc p
           where p.pronamespace = 'public'::regnamespace
             and p.proname in ('resolve_place','recommend_jobs','skill_gap','recommend_companies','recommend_repos','run_pipeline')
  loop
    execute format('revoke all on function %s from public, anon', f);
    execute format('grant execute on function %s to authenticated, service_role', f);
  end loop;
end $$;
