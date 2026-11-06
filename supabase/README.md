# Supabase setup

```
supabase db push                                   # schema, functions, 179 jobs (timestamped migrations)
supabase secrets set ANTHROPIC_API_KEY=sk-ant-...
supabase functions deploy process-cv
```
`supabase db reset` (local) also loads `seed.sql`: sample cities, companies and repos. It never runs in production.
Load your real companies, offices, cities and repos with your own import (service role).

## Client
```js
await supabase.storage.from('cvs').upload(`${user.id}/cv.pdf`, file)
const { data } = await supabase.functions.invoke('process-cv', { body: { path: `${user.id}/cv.pdf` } })
// data = { cv_id, cv, location, jobs, companies, skills, repos }
```
Single steps: `supabase.rpc('recommend_jobs', { p_skills: ['python','sql'] })`. Signed-in users only.

## Layout
- `migrations/…_schema.sql`     tables, constraints, indexes, RLS, storage bucket
- `migrations/…_functions.sql`  resolve_place, recommend_jobs/companies/repos, skill_gap, run_pipeline
- `migrations/…_seed_jobs.sql`  reference data
- `functions/process-cv/`       handler.ts (flow) · repository.ts (data) · claude-extractor.ts (LLM adapter) · cv.ts (schema + port) · http.ts · config.ts

## Production checklist
- Set `ALLOWED_ORIGIN` to your site (default `*`). Tune `MAX_CV_RUNS_PER_HOUR` (default 10).
- CVs are personal data (GDPR): add a retention job, and offer "delete my CV" (the delete policies exist).
- Company and repo scoring weights are my assumptions (in the SQL comments); align them with your original matchers.
- DOCX is not supported (PDF/TXT only).
