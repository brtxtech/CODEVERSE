-- CODEVERSE: permanent signup role + owner-scoped journey + admin-only audit storage.
-- Apply after other project migrations in Supabase SQL editor / CLI.
create table if not exists public.codeverse_profiles (
 id uuid primary key references auth.users(id) on delete cascade,
 email text not null,
 role text not null check (role in ('developer','recruiter','security_admin')),
 display_name text not null default '', university text not null default '',
 github_username text not null default '', created_at timestamptz not null default now()
);
create table if not exists public.codeverse_journey_steps (
 user_id uuid not null references auth.users(id) on delete cascade,
 step smallint not null check (step between 1 and 7),
 status text not null default 'completed' check (status = 'completed'),
 result jsonb not null default '{}'::jsonb,
 completed_at timestamptz not null default now(),
 primary key (user_id,step)
);
create table if not exists public.codeverse_journeys (
 user_id uuid primary key references auth.users(id) on delete cascade,
 submitted_at timestamptz not null
);
create table if not exists public.codeverse_security_events (
 id uuid primary key default gen_random_uuid(),
 created_at timestamptz not null default now(),
 actor_id uuid references auth.users(id) on delete set null,
 role text not null check (role in ('anonymous','developer','recruiter','security_admin')),
 action text not null check (length(action) between 1 and 80),
 outcome text not null check (outcome in ('allowed','denied','error')),
 detail jsonb not null default '{}'::jsonb,
 review_status text not null default 'open' check (review_status in ('open','investigating','closed')),
 reviewed_by uuid references auth.users(id) on delete set null,
 review_note text not null default ''
);
create index if not exists codeverse_events_recent_idx on public.codeverse_security_events(created_at desc);
create index if not exists codeverse_events_outcome_idx on public.codeverse_security_events(outcome,created_at desc);

-- Only allow signup with developer/recruiter. SECURITY ADMIN is NEVER selectable at signup.
create or replace function public.codeverse_on_auth_signup()
returns trigger language plpgsql security definer set search_path = '' as $$
declare requested text;
begin
 requested := new.raw_user_meta_data ->> 'requested_role';
 insert into public.codeverse_profiles(id,email,role,display_name)
 values (new.id,coalesce(new.email,''),
         case when requested = 'recruiter' then 'recruiter' else 'developer' end,
         left(coalesce(new.raw_user_meta_data ->> 'display_name',''),120))
 on conflict (id) do nothing;
 return new;
end;$$;
drop trigger if exists codeverse_on_auth_signup_trigger on auth.users;
create trigger codeverse_on_auth_signup_trigger after insert on auth.users
for each row execute function public.codeverse_on_auth_signup();

-- Backfill existing profiles with least privilege: developer, never admin.
insert into public.codeverse_profiles (id,email,role,display_name)
select id,coalesce(email,''),'developer',left(coalesce(raw_user_meta_data ->> 'display_name',''),120)
from auth.users on conflict(id) do nothing;

alter table public.codeverse_profiles enable row level security;
alter table public.codeverse_journey_steps enable row level security;
alter table public.codeverse_journeys enable row level security;
alter table public.codeverse_security_events enable row level security;

-- Clients can see their profile, journey status, and submission only.
-- ALL writes are made by the authenticated backend after JWT, role and sequence checks.
revoke all on public.codeverse_profiles from anon, authenticated;
revoke all on public.codeverse_journey_steps from anon, authenticated;
revoke all on public.codeverse_journeys from anon, authenticated;
revoke all on public.codeverse_security_events from anon, authenticated;
grant select on public.codeverse_profiles to authenticated;
grant select on public.codeverse_journey_steps to authenticated;
grant select on public.codeverse_journeys to authenticated;
create policy "codeverse_profiles_own_read" on public.codeverse_profiles
 for select to authenticated using (id=(select auth.uid()));
create policy "codeverse_steps_own_read" on public.codeverse_journey_steps
 for select to authenticated using (user_id=(select auth.uid()));
create policy "codeverse_journeys_own_read" on public.codeverse_journeys
 for select to authenticated using (user_id=(select auth.uid()));
-- No RLS policy for codeverse_security_events: never readable directly by client tokens.
-- Backend accesses it through service_role only AFTER security_admin role verification.

comment on table public.codeverse_profiles is 'Signup role immutable from client. Admin promotion is a privileged operator action only.';
comment on table public.codeverse_security_events is 'Backend-generated authorization records; do not store full email/IP/CV or bearer tokens.';

-- Keep profile email in sync when the authenticated user updates their Auth email.
create or replace function public.codeverse_sync_auth_email()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
 update public.codeverse_profiles set email=coalesce(new.email,'') where id=new.id;
 return new;
end;$$;
drop trigger if exists codeverse_auth_email_changed on auth.users;
create trigger codeverse_auth_email_changed after update of email on auth.users
for each row when (old.email is distinct from new.email)
execute function public.codeverse_sync_auth_email();
