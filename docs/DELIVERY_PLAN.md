# Roadmap: first 20 real end-to-end user journeys

## Implemented in this release
- Versioned deterministic skill evidence scoring and skill-gap recommendations
- Technology taxonomy (293 entries; inherited from CODEVERSE)
- Memory-only TXT/PDF/DOCX extraction with conservative taxonomy matching
- Public GitHub metadata and limited manifest inspection endpoint
- Browser-delivered local studio using same API
- Challenge acceptance-checklist engine explicitly requiring a reviewer
- 12 tests covering invalid inputs, scoring, CV upload, static detection and API flow
- Existing 3D city, n8n workflows and Supabase files retained as separate legacy components

## Sprint A — prove extraction quality
- Curate 30 consented CVs and manually label technologies; compute precision and recall.
- Build claim correction UI and provenance view, including original source snippets redacted by default.
- Add importable, versioned job skill requirements and reviewer editing.

## Sprint B — secure personal accounts
- Supabase Auth with backend JWT verification; EU region; user-owned RLS; private documents.
- Add verified GitHub App install flow and encrypted grant storage.
- Implement token rotation, privacy policy, retention and deletion cascade; test restore procedures.

## Sprint C — verified progress
- GitHub webhooks with signature validation, replay protection and incremental diff-based evidence.
- One or two curated skill challenges with CI checks and reviewer confirmation.
- Score snapshots with explanation and evidence revision IDs; calibration tests and anti-gaming measures.

## Sprint D — real-user validation
- Playwright E2E on desktop/mobile Safari, Chromium and Firefox.
- Security review, threat tests, a11y audit, monitoring and SLOs.
- Pilot with 20 consenting users, measure complete journey rate, extraction accuracy, verified progress, usefulness and repeat use.

**Success is not 20 signups: success is 20 completed, consented journeys that lead to attributable evidence improvements and qualitative feedback.**
