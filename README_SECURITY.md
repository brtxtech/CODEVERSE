# CODEVERSE / Secure Identity + Sequential Career Journey + Grafana

This release adds a **separate secure application** at `/secure` on top of the previous Vite/Three.js demo source. It does **not** convert the old 7-slider demo into secure authorization. In Docker (`CODEVERSE_SECURE_MODE=1`), the old demo endpoints `/career-journey`, `/workspace`, `/studio` and unauthenticated legacy APIs are blocked. The secure portal uses Supabase user JWTs and Postgres RLS.

## 1. Prerequisites

- Docker Engine / Docker Desktop with Docker Compose v2, or run the Python API locally.
- An existing Supabase project, with **asymmetric JWT signing keys** active (the API checks JWKS, issuer, audience and signature; it does not accept unverified JWT claims).
- Supabase Auth Email enabled. Enable Google / GitHub providers with their OAuth credentials only if you intend to offer them.
- SQL migrations applied. First use the existing `/supabase/migrations/` files as appropriate for your database, then run `20261101000000_codeverse_security.sql`. If your DB is new, use `supabase db push` from this folder and check migrations.
- Add `http://localhost:8000/secure` to Supabase Auth URL Configuration > redirect allow list. Use a real HTTPS domain for any public deployment.

## 2. Configure and run

```bash
cd codeverse
cp .env.security.example .env.security
# edit .env.security with Supabase project URL, PUBLIC ANON key, server-only SERVICE ROLE key,
# CODEVERSE_JWT_ISSUER and Grafana admin password.
./ops/setup_security.sh
```

The setup script generates an independent random token for the internal Prometheus scraper and starts three Docker services. Secret files are ignored by Git. Grafana and Prometheus listen on `127.0.0.1` only, not publicly.

- CODEVERSE: http://127.0.0.1:8000/secure
- Grafana: http://127.0.0.1:3000/d/codeverse-security
- Prometheus: http://127.0.0.1:9090

**Docker is optional:** use `pip install -r services/api/requirements.txt` then `uvicorn services.api.main:app --port 8000` for API-only local work with env variables already set. Grafana still needs its own installation or Compose.

## 3. Four immutable account branches

| Account | Origin | Allowed after login | Denied |
| --- | --- | --- | --- |
| Guest | No session | Login, registration, public catalog metadata | Private records, jobs, recruiter, admin |
| Developer | Email signup or social OAuth | Own profile, career journey 1→7, own evidence, jobs after final submission | Security events, recruiter-only data, other user records |
| Recruiter | **Select at email registration** | Own profile, consented candidate endpoint (empty until implemented) | Developer journey, security admin, private candidates |
| Security admin | Privileged Supabase SQL assignment by operator | Server-checked security event logs, investigations, Grafana link | Developer private CV records, recruiter data |

No UI role switcher. Client cannot update the `role` field: RLS exposes only `SELECT` to authenticated clients, while the backend allows updates only to `display_name`, `university` and `github_username`. A malicious client sending a different role in a PATCH cannot change it. **Do not expose the service-role key in HTML/JavaScript.**

To promote a **previously registered** administrator, an operator with privileged database access must run a controlled one-off SQL statement using the target user's UUID (never accept a user-supplied email from an untrusted request):

```sql
update public.codeverse_profiles
set role = 'security_admin'
where id = 'REPLACE-WITH-VERIFIED-USER-UUID'::uuid;
```

Use MFA for both the Supabase operator account and Grafana administrator. The secure Docker profile **requires Supabase MFA AAL2 for security_admin**. The UI supports TOTP enrollment/challenge. A dedicated administrator invitation/approval workflow is not implemented; role assignment remains a privileged SQL operation.

## 4. Seven stages, enforced in order

1. **Upload CV:** server parses PDF/DOCX/TXT, detects source-linked claims, and saves result in `cvs` table (not log content).
2. **Connect GitHub:** validates username and scans public repos, then stores GitHub profile metadata and repository count.
3. **Review skill evidence:** explicit acknowledgement about limitations of static evidence.
4. **Choose career:** select one curated career profile.
5. **Understand gaps:** confirm reviewing requirements without supporting evidence.
6. **Build verifiable proof:** scan a real public repository with manifest evidence. **This does NOT prove authorship/proficiency, and the step is marked submitted signals, not certified mastery.**
7. **Track readiness:** explicitly acknowledge score interpretation; no simulated hiring probability.

Every completed step stores a durable server-generated result and completion timestamp in `codeverse_journey_steps`. Server rejects skipping or repeating stages (HTTP 409). Only after all seven are complete can `POST /api/secure/journey/submit` set the submission timestamp and unblock `GET /api/secure/jobs`. Old client-side sliders are **not** a security control.

## 5. Grafana administration

Dashboard includes authorization denials/minute, allowed actions/minute, journey completion, target uptime, and trends. Alerts are provisioned for **>10 denied requests in 5 min** and API target unavailable; a rule firing needs investigation and is not a diagnosis of attack. Grafana supports YAML provisioning of data sources, dashboards and alert rules. See the official [Grafana provisioning guide](https://grafana.com/docs/grafana/latest/administration/provisioning/) and [alerting guide](https://grafana.com/docs/grafana/latest/alerting/set-up/provision-alerting-resources/file-provisioning/).

**What is actually monitored:** CODEVERSE API role denials, attempted early job access, journey actions and reviews. **What is not covered:** failed passwords that never reach CODEVERSE (handled inside Supabase Auth), external OAuth failures, full geo/device anomaly detection, centralized intrusion prevention. To cover those you must enable an explicit Supabase Auth audit-log export or a trusted webhook/log pipeline; do not rely on user-reported login data. Grafana is a monitoring tool, not an authentication provider or access-control enforcement engine.

## 6. Critical production gates

- Place API behind HTTPS reverse proxy with a real domain and strict allowed hosts; local Compose binds to loopback.
- Add rate limiting / abuse protection at your ingress, especially GitHub scan and registration. Prometheus counts denials but does not block attacks.
- Validate Supabase JWT configuration and migration in a real project; this package has no Supabase credentials and cannot remotely deploy migrations.
- Protect Supabase Service Role key in secret storage, rotate credentials, configure backups, retention, and GDPR obligations.
- CODEVERSE security_admin requires Supabase MFA AAL2; activate Supabase Auth MFA TOTP in project settings. Set up dedicated admin invite approvals and action-specific reauthentication for a public production deployment.
- Evaluate CV parser safety (upload size and supported formats), GitHub API rate limits, and worker isolation before internet exposure.
- Extend immutable audit event trail (log shipping, append-only storage) beyond DB service-role semantics.
- Build real project acceptance criteria and authorship attribution before advertising any skill as "verified".
- Job portal links are real destinations, **not verified live vacancies**. Recruiter has no candidates until consent sharing is built.
- Gmail send-only MCP connector is not deployed; the demo Pipeline Studio displays this limitation.

## 7. Tests

```bash
python -m pip install -r services/api/requirements.txt pytest
python -m pytest -q tests_python tests_ops
npm install
npm test
npm run build
```

Unit tests mock the Supabase adapter/GitHub interface. They do **not** prove a live Supabase deployment, Docker image availability, Grafana rule evaluation, or OAuth provider configuration. Review `SECURITY_AUDIT.md` before serving real users.
