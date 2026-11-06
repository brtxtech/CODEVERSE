-- Use the same model/version for indexing and querying; 384 dims for multilingual-e5-small.
create extension if not exists vector with schema extensions;
create table if not exists public.job_vectors (
 id uuid primary key default gen_random_uuid(),
 source text not null, external_id text not null,
 title text not null, description text not null,
 source_url text, fetched_at timestamptz not null default now(),
 model_id text not null default 'intfloat/multilingual-e5-small',
 embedding extensions.vector(384) not null,
 unique(source,external_id,model_id)
);
alter table public.job_vectors enable row level security;
-- Public client cannot directly query job vectors; server uses a trusted database role.
revoke all on public.job_vectors from anon,authenticated;
create index if not exists job_vectors_model_idx on public.job_vectors(model_id);
-- Small pilot: exact vector scan first; benchmark before adding ANN indexing.
