# CODEVERSE Engineering Release — 2026-10-31

This package is a **development release**, not a finished six-week commercial rollout.

## What you can run now

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r services/api/requirements.txt
python -m pytest tests_python -q
uvicorn services.api.main:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000/studio for the original local CV → job → readiness experience. For the original 3D city use Node.js 22+, `npm install && npm run dev` in a second terminal.

## What's new

- `/api/v1/targets` — authenticated target-role records
- `/api/v1/evidence` — authenticated CV-claim evidence ingestion with capped confidence
- `/api/v1/github/scan-and-store` — bounded public GitHub manifest collector, server-sourced evidence
- `/api/v1/targets/{id}/evaluate` — versioned local score snapshots with reproducibility input hash
- `/api/v1/targets/{id}/history` — scoped history
- `/api/v1/targets/{id}/milestones` — create acceptance criteria
- `/api/v1/milestones/{id}/submit` — submit reference; **not verified** until trusted review exists
- `DELETE /api/v1/account` — deletion from local ledger, **not** a global GDPR erasure request
- `supabase/migrations/20261031000000_evidence_graph.sql` — proposed evidence-graph schema with RLS, requiring real Supabase staging validation
- GitHub webhook HMAC utility with tamper-detection tests (not yet a fully implemented webhook service)

## Protected API configuration

The persistent local API fails closed until you set `CODEVERSE_JWT_ISSUER` to your trusted Supabase Auth issuer and `CODEVERSE_LEDGER_DB` to a writable local SQLite path. It accepts only validated asymmetric JWTs issued for the authenticated role. Configure issuer and region independently; do **not** hardcode credentials or store private keys in frontend bundles.

Example variables are in `.env.production.example`. SQLite is strictly a single-machine development backend; replace it with PostgreSQL for real customers.

## Warning about demos

The original `/api/cv/extract` and `/api/readiness/evaluate` routes are intentionally anonymous for localhost demonstration and are not safe to expose on a public host without authentication and rate limiting. Private CV contents should not be uploaded to an internet-facing demo.

Read `docs/PRODUCTION_GATES.md` and `docs/SIX_WEEK_TRACKER.md` before planning a launch.
