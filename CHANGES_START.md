# New front door: /start

Open `http://127.0.0.1:8000/start` (same server as `/secure`).

## What changed
- **Demo removed:** `/career-journey`, `apps/career-journey/` and `public/career-journey.html` are deleted. No fictional data is served.
- **3D houses always on top:** a fixed WebGL hero (Three.js 0.160, loaded from jsDelivr). Houses are your repositories, a ring closes as the 7 steps are completed, windows light up with progress. Before sign-in it shows a neutral skyline.
- **GitHub name only:** step 2 takes a username (`github_username`). The legacy `github_url` field still works for old clients.
- **All technologies listed:** the API no longer cuts the CV list at 30. Everything is stored, grouped by category, searchable in the UI, and exported.
- **Slide-by-slide form:** CV, GitHub, Evidence, Career, Gaps, Proof, Readiness, then Review and Submit. Progress is resumed from the server.
- **One file per user:** `POST /api/secure/journey/submit` generates it; `GET /api/secure/journey/file?format=json|csv` downloads it. It is rebuilt from stored steps, so it survives redeploys. Set `CODEVERSE_EXPORT_DIR` to also keep a server copy per user (`exports/` is gitignored).
- New: `GET /api/secure/journey/options`, `GET /start`.

## Deploy checklist
1. Add `<your-url>/start` to the Supabase Auth redirect allowlist (OAuth and email confirmation).
2. Keep `CODEVERSE_SECURE_MODE=1`. `/start` and `/secure` are the only public pages.
3. Optional: mount a volume and set `CODEVERSE_EXPORT_DIR`.
4. `pytest tests_python tests_ops` (58 pass) and `node --test tests/*.test.js` (16 pass).

## Not verified yet
The 3D scene and slide flow were syntax-checked but not run in a browser against live Supabase. Test sign-up, CV upload, scan and submit once on staging before inviting users.

## Admin console: /admin (real data, no demo)
- Security Admins are redirected from `/secure` to `/admin`. Same Supabase session.
- `GET /api/secure/admin/analytics` aggregates real rows: events per hour (24h), denials, open reviews, accounts by role, 7-step funnel, submissions, completion rate. Empty tables show zeros and empty states, never sample data.
- Event table with search, outcome and role filters, review workflow (investigating or closed, reason kept in audit), CSV export, 30 s auto refresh.
- Grafana and Prometheus links come from `CODEVERSE_GRAFANA_URL` and `CODEVERSE_PROMETHEUS_URL` (no hardcoded localhost). Add both to your env.
- Limits: Supabase Auth login failures are not in this data (only API events). Aggregates read up to 5,000 events and 20,000 rows; move to SQL views or RPC counts before large scale.
- Tests: 60 pass.
