-- Run once in Supabase SQL Editor. Separate from the "posts" (company blogs) table.
create table if not exists social_items (
  id            bigint generated always as identity primary key,
  source        text not null check (source in ('github', 'slack')),
  source_ref    text not null,          -- GitHub org/repo, or Slack channel id
  external_id   text not null unique,   -- GitHub URL, or "channel:timestamp" for Slack
  title         text not null,
  link          text,
  body          text,
  author        text,
  posted_at     timestamptz,
  content_hash  text not null,          -- changes when the content changes
  first_seen_at timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

create index if not exists social_source_idx on social_items (source);
create index if not exists social_posted_idx on social_items (posted_at desc);

-- IMPORTANT: only GitHub rows are readable with the public (anon) key.
-- Slack messages are private workspace content, so they stay hidden.
alter table social_items enable row level security;
drop policy if exists "public read github only" on social_items;
create policy "public read github only" on social_items
  for select to anon, authenticated using (source = 'github');
revoke all on public.social_items from anon, authenticated;
grant select on public.social_items to anon, authenticated;
