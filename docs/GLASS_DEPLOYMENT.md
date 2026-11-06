# CODEVERSE Glass — deployment and verification

This release is a deployable source package, not a claim of completed production activation. The real OAuth providers, database migrations, Docker builds and isolated worker need operator configuration and live acceptance testing. No credentials are bundled. Existing Grafana, Prometheus, evidence engine, webhook security, career pipeline and source datasets remain in the project.

## Requirements

- Node 22.12 or later (Node 20.11 cannot run this Vite version), Python 3.11+, Docker Compose v2.
- A Supabase project with asymmetric JWT signing (ES256 or RS256).
- A GitHub OAuth application configured in Supabase Auth.
- An HTTPS application domain and reverse proxy.
- Optional: Google OAuth client with Gmail API enabled; dedicated Python execution worker.

## Deploy the application

1. Copy `.env.deploy.example` to `.env.deploy`. Fill Supabase URL, public anon key, **server-only** service-role key and `CODEVERSE_JWT_ISSUER=https://YOURPROJECT.supabase.co/auth/v1`. Set `CODEVERSE_PUBLIC_URL=https://YOUR_DOMAIN`.
2. Generate the encryption key: `python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'`. Put it in `CODEVERSE_ENCRYPTION_KEY`. Back it up securely: rotating it without re-encrypting stored integration records disconnects those integrations.
3. Apply **all** migrations in `supabase/migrations`, in filename order. With a linked Supabase CLI project: `supabase db push`. The final migration creates owner-scoped workspace storage, encrypted integration storage, visitor-only signup and the 58-row repository reference database. Existing users keep their assigned roles. The 305-technology catalog is preserved and merged.
4. Enable GitHub in Supabase Auth. In the GitHub OAuth application, use Supabase's displayed callback URL. In Supabase's URL configuration, allow `https://YOUR_DOMAIN/` as a redirect. Use asymmetric signing; legacy HS256 is deliberately rejected.
5. Run `docker compose --env-file .env.deploy up --build -d` from the project directory. This starts one FastAPI service serving both the production Vite build and API. The local binding is `127.0.0.1:8000`; put your HTTPS reverse proxy in front. Do not deploy this as a static-only GitHub Pages app: protected features need the Python API.
6. Verify `/api/health`, then use the browser checklist below. Liveness is not a production security attestation. The API deliberately does not claim `production_ready=true`.

Use your reverse proxy for TLS, request body limits (4 MB), per-IP throttling and upstream timeouts of at least 60 seconds. Deploy one API worker initially: discovery throttling is process-local. Use shared throttling before scaling. Restrict API docs or remove them at the proxy if public API introspection is undesired. Supabase connection domains are allowed in the frontend CSP; add your trusted custom Auth domain if applicable.

## Roles and sign-in

Every **new signup** is Visitor, even if signup metadata requests Admin or Recruiter. Visitor users can complete the student career flow. The predefined role types are Visitor, Developer, Recruiter and Security Admin. No shared or default passwords are shipped.

For operator-managed accounts, create the Auth identities in Supabase's administrative console first, then run with server credentials loaded:

```
python tools/provision_role.py --user-id AUTH_USER_UUID --role developer
python tools/provision_role.py --user-id AUTH_USER_UUID --role recruiter
python tools/provision_role.py --user-id AUTH_USER_UUID --role security_admin
```

Privileged users also sign in through GitHub for the Glass workspace. Security Admin requests require Supabase MFA AAL2. The preserved `/secure` portal supports its existing MFA flow; complete MFA there before entering administration. The role provisioning script runs only on the operator machine. No role-switch button or role write endpoint is exposed to students. Existing legacy UI source is retained for provenance; secure mode blocks its demonstration API routes.

## GitHub repository creation

Login requests `read:user public_repo`. Only an explicit checked confirmation in the project dialog creates a public learning repository. The API validates that the provider token's `/user` identity matches the verified Supabase GitHub identity. The provider token is passed transiently in an authenticated request, is never added to workspace state, and is not saved server-side. Reconnect GitHub if it has expired.

Creation initializes an original README and checklist, referencing an upstream catalog project. It does **not** copy upstream source or assert an upstream license grants all uses. If creation succeeds but README initialization fails, the actual created URL is returned with a warning. The new stack appears only after GitHub returns success.

## Gmail setup

Set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and the encryption key. Enable Gmail API. Register exactly:

```
https://YOUR_DOMAIN/api/v1/glass/gmail/callback
```

If the Google application is in testing, add every authorized user as an OAuth test user. Production distribution may require Google's approval for the Gmail send scope. Connect Gmail from Jobs or its automation box, then use Test. Test refreshes authorization and sends nothing. OAuth state is short-lived and checked; refresh tokens are encrypted in server-only storage. Use a different Google OAuth client for each environment.

Emails require recipient/message review and a separate Send action. Gmail boxes default to **draft data**. Release 2.1 can send only after a box is explicitly configured for Send and the student confirms the per-run email review. No email or GitHub repository was created during this delivery. Recruiter addresses are extracted only when literally present in published job content; they are not guessed or verified as the hiring contact.

## Automation and isolated Python

The workspace starts empty. Add or drag Python, Dataset, HTTPS API or Gmail boxes. Use each box's multiselect to link inputs, move boxes on the canvas and export/import flow JSON. Up to 40 boxes and 30 text datasets per workspace; each upload is at most 500 KB, and the complete workspace is limited to 3 MB. Boxes exchange JSON values. Release 2.1 retains run results and supports individual named JSON/CSV/text/binary output downloads as well as the consolidated run result. Release 2.1 also accepts opaque binary files in the independent dataset inventory; Python receives their metadata and base64 bytes. Arbitrary package installation is not implemented.

Python receives an array of upstream values as JSON on stdin and must print valid JSON to stdout. Test the code before Start. Editing code invalidates its stored test hash. The separate runner executes every invocation in a new offline, unprivileged, read-only container with no host mounts, dropped capabilities, no new privileges, 128 MB RAM, 0.5 CPU, 32 processes and a 30-second timeout. Standard library only. Output is limited. These containers are not a substitute for a hardened VM boundary on a hostile public code-execution service.

On a **dedicated worker VM** with Docker:

```
docker build -t codeverse-skill:1 -f services/runner/Dockerfile.skill services/runner
# Set a long random CODEVERSE_RUNNER_TOKEN in this worker environment.
docker compose -f ops/compose.worker.yml up --build -d
```

The runner orchestrator needs the Docker socket, which grants it control over that dedicated host. Do not run it on a sensitive or shared host. Keep it behind a private network or authenticated HTTPS tunnel, never directly exposed publicly. Set `CODEVERSE_RUNNER_URL` and the same token in the application environment. The runner binds to loopback by default; an operator must arrange private connectivity between application and worker. The main app deliberately has no Docker socket. Without a worker, Python Test/Start returns an explicit configuration error and never executes code in the API process.

HTTPS API boxes support tested, read-only GET requests to hosts in `CODEVERSE_CONNECTOR_HOSTS`. Configure the host, path and optional Bearer key in the box dialog. A successful test stores encrypted configuration; keys never enter workflow exports. Redirects, arbitrary hosts and oversized responses are rejected. Other auth schemes, POST APIs and generic n8n workflow imports are not implemented. The preserved n8n JSON examples remain separate from this purpose-built canvas.

## Jobs, application tracking, and data integrity

- Suggested companies are career-page references, not asserted live vacancies.
- Greenhouse/Lever fetch requires a valid public board ID. Sites without supported feeds remain link-only. Live general jobs come from the existing Arbeitnow integration.
- Opening an offer creates an `opened` record. Only a user status change records `submitted`; opening a link cannot prove a completed application.
- Workspace writes are owner-scoped and use revision checks to prevent one tab silently overwriting another. A conflict requires reload.
- The seven stages are enforced on the API. Full CV text is parsed transiently; only extracted skill claims are stored by the new flow. Existing legacy evidence records are retained.
- A new learning plan does not demonstrate mastery. The score is deterministic coverage of curated target technologies from CV/language signals, not a hiring prediction. No fabricated proficiency levels are used.
- Repository catalog star counts and licenses start unknown. Refresh fetches the real current GitHub values. The seed is a curated discovery collection, not a continuously ranked global GitHub leaderboard.
- Discovery caps at 100 public repositories; the first 24 are visualized. Commit counts are fetched for up to 12 repositories, for the default branch. Counts are not the user's authored commits. Missing counts use an explicitly unknown baseline. Heights and widths use bounded logarithmic scales for readability. Release 2.1 pages the scene over loaded repositories and allows explicit fetches of missing commit counts.

## Preserved source and features

`docs/MERGE_MANIFEST.json` records additions and differing release-candidate files. Conflicting older variants remain in `preserved-release-candidate/`; latest security/redesign files take precedence. The earlier data had 293 technology entries, the newer one 305; merging by ID retains all 305. Existing schema, seed jobs, social source tools, operations automation, webhook processing, Grafana dashboards/alerts, Prometheus configuration, studio and workspace source are retained. They are not all exposed as default student navigation.

## Checks to run

```
npm ci
npm test
npm run build
python -m venv .venv
.venv/bin/pip install -r services/api/requirements.txt pytest
.venv/bin/python -m pytest -q tests_python tests_ops
```

Development: after installing Python requirements into `.venv`, run `npm run dev`. The launcher starts the API on port 8000 and Vite with an `/api` proxy. Production uses the unified Docker service. Node >=22.12 is declared in package metadata and `.nvmrc`.

Live acceptance checklist (requires your accounts): visitor signup; verify GitHub username; complete all seven stages; resume after reload; attempt role escalation; create one disposable confirmed repository; connect/test Gmail and send a reviewed test message; fetch a real company board; open an offer and mark submitted separately; configure/test HTTPS connector; test/run Python on the isolated worker; reject cycles; verify cross-user storage isolation and admin MFA; inspect Grafana audit metrics. Do not consider the deployment activated before these pass.

The GitHub evidence stage also attempts supported manifest scans in up to two non-fork repositories and records their commit SHA and technology evidence. Quota/provider failures are recorded as warnings and leave the language signals available. Scanning third-party public code does not prove personal authorship.
