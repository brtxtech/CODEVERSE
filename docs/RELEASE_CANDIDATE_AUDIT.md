# CODEVERSE: engineering release candidate, NOT a production authorization

## Changes in this package
- Added a real HMAC SHA-256 GitHub webhook route with 256 KB maximum body, event allowlist, mandatory installation ID, and SQLite-based delivery-ID idempotency. The route records a pending delivery; it does **not** grant skill evidence or do repository synchronization automatically.
- Added server-side GitHub App JWT and installation token exchange with an existing PEM path; credentials never belong in browser source.
- Added pgvector 384-dimensional schema for multilingual-e5-small. Rows are backend-only by default; external DB deployment is not attempted.
- Added local embedding smoke test (optional dependency and model download) and Playwright smoke-test source.
- Existing 3D city, CV matching, authenticated workflow prototype, pilot tracker, and 293-item catalog retained.

## Commands from project root
```bash
python -m pytest -q tests_python tests_ops
npm test
npm install --no-audit --no-fund
npm run build
# optional: use the supported Node version; Playwright binaries/install needed
npx playwright test e2e/local-smoke.spec.ts
# optional: model download may consume substantial disk
python -m pip install sentence-transformers
python tools/embedding_smoke.py
```

## Private local .env (NEVER paste secrets into chats)
- `GITHUB_APP_ID` numeric GitHub App ID
- `GITHUB_PRIVATE_KEY_PATH` absolute path to GitHub App private PEM, stored outside repository
- `CODEVERSE_SECRETS_ROOT` parent directory allowed to hold secret PEM files
- `GITHUB_WEBHOOK_SECRET` random shared secret configured in GitHub App
- `CODEVERSE_WEBHOOK_DB` local SQLite queue path (e.g. `./var/webhook-deliveries.db`)
- `CODEVERSE_JWT_ISSUER`, `CODEVERSE_JWT_AUDIENCE` trusted Supabase issuer and audience
- `DATABASE_URL` local development Supabase connection string, not used by SQLite ledger

For public delivery on localhost, configure a verified HTTPS tunnel (or a reachable staging host). Restrict tunnel ingress and do not publish debug endpoints. The webhook receiver accepts external traffic only after explicitly setting the above secret and queue path. Do not treat the webhook as a completed pipeline: a separate authenticated installation-to-user mapping and background worker must process pending events securely.

## Blocking items, regardless of test pass
1. Live Supabase migration, database role/permissions review, RLS tests with **two real test users**, and actual PostgreSQL-backed user evidence persistence.
2. GitHub App installation and callback/CSRF flow, binding installations to verified users, API budget handling, queue worker, commit attribution, and trusted project completion checks.
3. Real-world document benchmark, proper malware defense, CV retention, robust model evaluations, and vector similarity relevance benchmarks using labeled job/CV pairs.
4. Unified authenticated UI connection to real source-of-truth skill evidence, browser E2E in Chrome/Firefox/WebKit, and accessibility/performance review.
5. GDPR governance: processing register, legal basis, privacy notice, DPA, deletion propagation, backup retention, incident response and independent review.
6. 20 consented users completing the whole journey. No pilot outcome has been collected here.

**NO GO-LIVE SIGNOFF.** Automated source checks are necessary but insufficient.
