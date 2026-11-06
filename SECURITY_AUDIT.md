# CODEVERSE security and design audit — 2026-11-01

## Four role-access use cases

| Actor | Login/registration | Allowed branch | Denied branch | Audit signal |
| --- | --- | --- | --- | --- |
| Guest | Public auth page, OAuth/email signup | Registration and sign-in only; developer/recruiter choices | Secure API, profile, jobs, admin | HTTP 401 metric (unverified requests) |
| Developer | Registered developer, verified Supabase JWT | Own profile, CV/GitHub → evidence → career → gaps → proof → readiness → submitted jobs | Admin security events; recruiter candidate list; skip stage | `role_access denied`, `journey_out_of_order denied`, `jobs_view denied` |
| Recruiter | Registered recruiter, verified Supabase JWT | Own role metadata and consented candidate list (empty today) | Developer journey, jobs, admin events | `role_access denied` |
| Security Administrator | Operator-promoted account, JWT plus **Supabase AAL2 MFA** | Authorization audit, incident review, Grafana link | CV text, private portfolio, developer journey, recruiter info | `admin_events_view allowed`, `security_event_review allowed` |

### Scenario A — Developer attempts to open Admin Security

Expected 403. UI does not show admin link; directly calling `/api/secure/admin/events` fails server role policy. Audit records attempted role access. **Automated test:** `test_developer_cannot_access_admin`.

### Scenario B — Recruiter attempts to open a private CV or developer journey

Expected 403. The candidate sharing endpoint returns no candidate data until consent and sharing are implemented. **Automated test:** `test_recruiter_cannot_use_developer_steps`.

### Scenario C — Developer tries to access Job Opportunities after only three steps

Expected 403 from `/api/secure/jobs`, regardless of localStorage/front-end state. Attempt to submit before all 7 complete returns 409. Attempt to complete step 4 before 1–3 returns 409. **Tests:** `test_submission_gate_controls_jobs`, `test_sequence_enforced_prevents_skip`.

### Scenario D — Administrator investigates suspicious denials

Expected Security Audit page, authenticated server-side event retrieval, and review status change with reason. Prometheus counts denied actions with bounded labels; provisioned Grafana rule fires after >10 denials in 5 minutes. **Limits:** legitimate misclicks can trigger rules; need investigation before restriction. Supabase Auth password failures do not reach this API, so they are not claimed as monitored.

## Architecture controls and residual risks

| Control | This package | Severity / remaining work |
| --- | --- | --- |
| Permanent signup role | SQL trigger restricts signup to developer/recruiter; admin promotion privileged | Low residual if DB credentials protected |
| Backend JWT verification | Pinned HTTPS issuer, JWKS, RS/ES algorithms, exp/iat/sub/aud | Requires Supabase asymmetric signing key and real integration testing |
| MFA for Security Admin | AAL2 requirement when secure mode and MFA env flag active; TOTP UI | Real Supabase MFA TOTP provider configuration untested; consider action-specific reauth |
| Row Level Security | Owner-only SELECT; writes through verified server-side API | Admin service role must be kept server-only; review migrations before production |
| Stage order | Each step consults DB; only next stage allowed; all 7 needed to submit | Stage 6 proves repository signals only, **not** authorship or proficiency |
| Job discovery | Locked until server-side finalized timestamp | Portal links and suggested roles, not verified live open positions |
| Admin telemetry | Bounded-cardinality Prometheus counters + DB audit events | Auth events inside Supabase require separate trusted log ingestion; absent |
| Alerting | Grafana rule provisioning for excessive denials and API outage | Rule provisioning not runtime-tested in Docker in this environment; test with Grafana before rollout |
| Anti-abuse | 2 MB CV limit, restricted GitHub paths, mandatory auth for state changes | Add ingress rate limits, threat-based lockout and CDN/WAF |
| Privacy | No token, email/IP/CV content inside security events; stored per-user claims | Define deletion/export, backup retention and consent management |
| Recruiter access | No candidates returned without sharing implementation | Build explicit consent and revocation records before enabling |
| Pipeline Studio | Outbound proposal mock, no Gmail read | Actual MCP/Gmail send-only connector not implemented |
| Static routes | Legacy demo routes blocked in secure mode; Pages deploy manual | Ensure old demo URL is not promoted as protected production app |

## Release gates

1. Run migration on a **test** Supabase project with Auth signup and JWT asymmetric keys; verify role trigger and RLS under anon and authenticated database roles.
2. Complete actual Gmail/GitHub OAuth provider setup in Supabase Auth; test redirect and email confirmation on your HTTPS domain.
3. Start Docker Compose and verify Grafana dashboard data sources and both provisioned alert rules actually reach `Normal` and `Firing` states.
4. Configure production HTTPS, rate limiting, secrets, MFA and monitoring of full Supabase Auth logs via a trusted ingestion path.
5. Perform multi-user manual tests: two developers cannot read one another's records; recruiter cannot read CV records; developer cannot access admin; admin requires AAL2.
6. Enforce database retention, account export/deletion procedures, and privacy review.

This is an **implementation-and-static-test audit**, not a penetration test or proof of production deployment.
