# CODEVERSE local integration and launch gates

## Scope

This repository contains an existing local career API, 3D city, taxonomy, pilot tracker, source of Supabase migrations and n8n examples. `tools/codeverse.py` is an **operations assistant**, not a substitute for real production implementation, credentials, legal assessment, independent browser verification, or 20 humans in a pilot.

**Nothing is deployed by `doctor`, `test`, or `status`.** Remote migrations require explicit flags and an interactive confirmation. Do not run remote migrations without a backup and reviewing all SQL files, especially the older supplied schema.

## 1. Mac local setup

Install Python 3.11+, Node 22+, and optionally the [Supabase CLI](https://supabase.com/docs/guides/local-development/cli/getting-started), PostgreSQL client and Playwright.

```bash
./setup_local.sh
# or independently:
python3 tools/codeverse.py doctor
python3 tools/codeverse.py test
python3 tools/codeverse.py status --with-tests --output reports/readiness.json
```

`setup_local.sh` creates `.venv`, installs dependencies and runs tests. It requires network/package availability. The existing Vite city and FastAPI studio are separate local interfaces, not yet a unified Next.js app.

## 2. Supabase database

Create a **separate development Supabase project in an EU region**, not the eventual production database. Configure public URL and publishable key locally; retain all confidential values outside source control. Supabase is **not** the same as GitHub OAuth App credentials. Use the Supabase *Sign In / Providers* page for GitHub login. `/oauth/consent` is for operating your own OAuth authorization server, not for connecting GitHub.

For local Supabase CLI: `supabase start` to start local services, then `python3 tools/codeverse.py migrate --mode local --reset --confirm-data-loss` to reset the disposable local DB. Note: DB reset DESTROYS local data. Read migrations before applying.

For hosted development project: run `supabase login` and `supabase link --project-ref YOUR_REF` interactively, set `SUPABASE_PROJECT_REF`, review `supabase/migrations`, make a backup, then run:

```bash
python3 tools/codeverse.py migrate --mode remote --confirm-remote
```

This runs the Supabase CLI's migration push against the linked remote instance only after you type `DEPLOY`. **It does not verify user isolation**, which requires authenticating as at least two distinct users and testing unauthorized read/write operations. `rls-inspect` reads PostgreSQL metadata if `DATABASE_URL` is configured, but that is insufficient to prove RLS isolation. Set `DATABASE_URL` via a local secret manager and run `python3 tools/codeverse.py rls-inspect` only on a test DB.

## 3. GitHub App

At GitHub Developer Settings, create a **GitHub App** (not just a GitHub OAuth App) that users can install on selected repositories. Start with minimum read-only metadata, contents, and commit permissions and relevant subscribed push/installation events. Configure a reachable HTTPS webhook URL when remote; GitHub cannot send webhooks to `localhost` without a secure tunnel. Store webhook secret and private key only server-side. 

**Current gap:** The included service implements a static public scan and a webhook signature helper, but does not fully implement App install-token exchange, installation repository pagination, webhook replay-proof delivery persistence or worker-triggered synchronization. These must be built and tested before marking the GitHub integration operational. Do not use a GitHub OAuth client ID as if it were a GitHub App installation identifier.

## 4. GitHub skill verification / project completion

A listed dependency proves presence, not developer ownership. Require attributable commits, non-generated source diffs, manifests + actual imports, and verifiable acceptance criteria. Challenge results need trusted server-side checks, with score snapshots recomputed from the evidence ledger. Existing checklist endpoints are *not trusted automatic project verification*. Running arbitrary repository code requires isolated, no-network, short-lived sandboxing and independent security review.

## 5. CV and jobs evaluation

Create an explicit consented test corpus with manual ground truth. Measure span-level precision/recall/F1 across technology aliases, multilingual formats, tables and PDF extraction errors. Inspect false positives (e.g. Java vs JavaScript), log only anonymized aggregate metrics. Evaluate job provider freshness, URL validity, normalized titles, duplicate rate and coverage separately. Never fabricate job listings. pgvector semantic matching requires a real installed database extension, embedding pipeline and evaluation benchmark; neither dependency installation nor a local API test proves its effectiveness.

## 6. 3D city and workflow UI

Existing source contains Vite/Three.js and a career workspace. The complete authenticated evidence-to-geometry link and a reliable node editor with CSV input/output require browser-level checks. Suggested E2E gates: locked camera angle; no scroll zoom; selected building opens evidence; unauthorized data never appears; workflow nodes receive and pass validated tabular rows; CSV injection protection for spreadsheet exports; accessible keyboard interactions.

## 7. GDPR and production

Required before any real-user pilot: data processing inventory, lawful-basis review, privacy notice, retention, private buckets and storage RLS, deletion of database+objects+vectors+cache, backup retention and restore deletion tests, data processor agreements, DPIA screening, security incident workflow. A SQL RLS policy is not GDPR certification.

Run Playwright on Chromium, Firefox and WebKit, cross-user auth tests, dependency scans, secret detection, and penetration testing; add production observability with redaction. No real user CVs in logs or unapproved AI processors. Pilot recruitment, informed consent, verified completion, and willingness-to-pay interviews cannot be automatically generated.

## 8. Readiness report

```bash
python3 tools/codeverse.py status --with-tests --output reports/readiness.json
python3 tools/codeverse.py pilot-report --input pilot/journeys.csv --output pilot/report.json
```

The report deliberately marks production tasks **unvalidated**, even if source code exists. Do not modify statuses manually to imply successful deployment. Keep secret credentials in your own local environment. Never send passwords, API secrets or GitHub App private keys into chat.
