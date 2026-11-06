# CODEVERSE — Security status and threat model

**Status: LOCAL EXPERIMENTAL PROTOTYPE, NOT PRODUCTION READY.**

## Boundaries
- Run with `uvicorn ... --host 127.0.0.1`. No authentication or multi-user tenant isolation is implemented in the FastAPI prototype. Do **not** expose this service to the public internet or upload other people's CVs.
- The FastAPI CV endpoint reads files in memory and does not deliberately persist them, use AI, or transmit them to third-party inference providers. The supplied older Supabase module remains **separate** and can have different behavior if configured and enabled.
- API returns recognized skill names, not original document text. Avoid request-body logging, tracing uploads, or adding analytics until retention policies are defined.
- CV size capped at 2 MB; PDF pages capped at 25. This does not replace sandboxing and malware scanning for a production service. File parsers must be isolated and kept patched before public launch.
- The public GitHub reader uses a fixed API host and reads only a limited set of manifest paths. It does not execute any repository code. It cannot verify who authored the source, whether tests pass, or whether claimed skills demonstrate professional proficiency.
- GitHub API quotas apply. The scanner currently makes bounded live requests; production requires caching, queue quotas, webhook signature verification, retries/backoff, installation permissions, and user authorization.
- The scoring endpoint is user-supplied and not tamper-resistant. It reports **evidence alignment**, not hiring probability. A completion checklist merely marks ready for review, never verified automatically.

## Production release blockers
1. Authenticated identities and per-user authorization policies; negative access-control tests.
2. EU-hosted Postgres schema with RLS, tenant key management and encrypted private object storage.
3. Virus scanning, sandboxed parsers, immutable evidence provenance, size/time/resource limits.
4. GitHub App installation permission flow, token encryption, webhook HMAC validation, deduplication and incremental sync.
5. Privacy notices, lawful basis assessment, DPA/subprocessor inventory, retention schedule, export, erasure and backup recovery tests.
6. Abuse prevention, request throttles, user quotas, structured audit logs with PII redaction, incident response and backup restores.
7. Continuous testing: browser E2E, security scanning, accessibility, cross-tenant isolation and independent penetration testing prior to taking payment.
8. Validate scoring against human-reviewed skill evidence and watch for disparate impact. Do not use to make hiring decisions.

## GDPR
EU-region hosting is necessary for the proposed deployment model but not sufficient for GDPR compliance. Obtain legal review of lawful bases, Art. 13 notices, processor agreements, data subject request handling and DPIA need. Consent to public portfolio publication must be separate from career-analysis processing. Derived embeddings may contain personal information and must be included in erasure design.
