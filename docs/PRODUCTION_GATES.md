# CODEVERSE engineering release: verified implementation vs launch blockers

## Implemented and locally testable
- Deterministic CV/job taxonomy extraction and readiness computation.
- Existing 3D repository visualization and career studio.
- GitHub public static manifest inspection (no execution; authorship unproven).
- Append-only local SQLite evidence history with ownership-scoped operations.
- Submitted milestones remain *unverified* until an independently trusted review system is added.
- Optional protected API, disabled without trusted JWT issuer and storage configuration.
- Supabase Postgres tables and row-level policies as a migration to review on staging.
- Local data erasure for evidence ledger; per-user snapshot history.

## Not complete / not claimed
- Protected API uses local SQLite for testing, NOT a production multi-instance storage layer.
- The new Postgres schema is not yet connected to the FastAPI ledger.
- No real GitHub App OAuth installation, secure token storage, webhook delivery verification, author attribution or reliable automatic project verification.
- No automatic removal from Supabase Storage, downstream AI processors or backups.
- No verified job-offer provider or job market integration in this new module.
- No audited sandbox, full CV malware-scanning pipeline, privacy review or independent security testing.
- No browser E2E pass or production staging release verified.
- No 20-user research study; cannot manufacture human outcomes.

## Required production go/no-go
1. Configure EU region, DPA, retention notices, lawful bases, DPIA assessment, request handling and incident procedures.
2. Deploy Postgres migrations and run cross-user RLS tests on a real Supabase staging instance.
3. Replace SQLite ledger with PostgreSQL + service-scoped, transactionally verified evidence writes.
4. Implement/verify GitHub App authorization, webhooks, signature verification, retry queues and rate-limit backoff.
5. Use private CV bucket, signed URLs, content-sniffing, malware controls, and deletion propagation.
6. Add hosted authenticated E2E test covering signup, CV import, job matching, evidence, project review, deletion.
7. Validate ranking quality and user impact with 20 consenting, real pilot users.

## Safe usage
Run the existing `/studio` for local prototype only. Never expose the unauthenticated `/api/cv/extract`,
`/api/github/public-scan`, or `/api/readiness/evaluate` routes publicly without authorization, throttling
and abuse testing. Do not paste a `service_role` key into browser code.
