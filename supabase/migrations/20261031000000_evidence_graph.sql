-- Add-on schema; existing Supabase migrations must be applied first.
-- Authenticated users are the only allowed readers/writers of their own data.
create table if not exists public.cv_targets (
  id uuid primary key default gen_random_uuid(),user_id uuid not null references auth.users(id) on delete cascade,
  title text not null, requirements jsonb not null, created_at timestamptz not null default now());
create table if not exists public.skill_evidence (
  id uuid primary key default gen_random_uuid(),user_id uuid not null references auth.users(id) on delete cascade,
  skill_id text not null, level numeric(3,1) not null check(level between 0 and 4),
  confidence numeric(4,3) not null check(confidence between 0 and 1),
  provenance text not null check(provenance in ('cv_claim','github_static','reviewed_project')),
  repo_full_name text, commit_sha text, file_path text, created_at timestamptz not null default now());
create table if not exists public.project_milestones (
  id uuid primary key default gen_random_uuid(),user_id uuid not null references auth.users(id) on delete cascade,
  target_id uuid not null references public.cv_targets(id) on delete cascade,
  skill_id text not null, criteria jsonb not null,
  status text not null default 'pending' check(status in ('pending','submitted','reviewed','rejected')),
  proof_uri text,reviewed_by uuid,reviewed_at timestamptz,created_at timestamptz not null default now());
create table if not exists public.readiness_snapshots (
  id uuid primary key default gen_random_uuid(),user_id uuid not null references auth.users(id) on delete cascade,
  target_id uuid not null references public.cv_targets(id) on delete cascade,
  score numeric(5,2) not null check(score between 0 and 100),
  breakdown jsonb not null,algorithm_version text not null,input_hash text not null,
  created_at timestamptz not null default now());
create table if not exists public.cv_files (
  id uuid primary key default gen_random_uuid(),user_id uuid not null references auth.users(id) on delete cascade,
  storage_path text not null,created_at timestamptz not null default now(),
  scheduled_delete_at timestamptz);
create table if not exists public.github_connections (
  id uuid primary key default gen_random_uuid(),user_id uuid not null references auth.users(id) on delete cascade,
  installation_id bigint not null, selected_repositories jsonb not null default '[]',
  created_at timestamptz not null default now(),unique(user_id,installation_id));
do $$ declare t text; begin
 foreach t in array array['cv_targets','skill_evidence','project_milestones','readiness_snapshots','cv_files','github_connections'] loop
  execute format('alter table public.%I enable row level security',t);
  execute format('drop policy if exists owner_select on public.%I',t);
  execute format('drop policy if exists owner_insert on public.%I',t);
  execute format('drop policy if exists owner_update on public.%I',t);
  execute format('drop policy if exists owner_delete on public.%I',t);
  execute format('create policy owner_select on public.%I for select to authenticated using ((select auth.uid()) = user_id)',t);
  execute format('create policy owner_insert on public.%I for insert to authenticated with check ((select auth.uid()) = user_id)',t);
  execute format('create policy owner_update on public.%I for update to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id)',t);
  execute format('create policy owner_delete on public.%I for delete to authenticated using ((select auth.uid()) = user_id)',t);
 end loop;
end $$;
-- Hardening: prevent users from self-asserting verified evidence or review status.
-- These writes should only occur through a trusted server-side function that validates the reviewer.
revoke insert,update,delete on public.skill_evidence from authenticated;
revoke update on public.project_milestones from authenticated;
revoke insert,update,delete on public.readiness_snapshots from authenticated;
-- Private storage: configure private bucket and owner-scoped Storage RLS before uploading CVs.
-- Do not grant public access to CV objects or private repository information.
