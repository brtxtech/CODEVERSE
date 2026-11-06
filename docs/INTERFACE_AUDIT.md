# CODEVERSE interface requirements audit — release 2.1

The audit compares the 2.0 Glass interface and API with the requested student journey, repository stacks, job tools and automation workspace. It records **41 missing, partial, defective or unverified requirements**. The CSV preserves the original finding and records the resulting implementation, source location, check, and remaining dependency.

- **37 implementation gaps addressed.**
- **2 configuration dependencies:** real provider credentials and operator-provisioned privileged identities.
- **2 live verification boundaries:** Docker/isolated-worker execution and external provider responses in the deployment network.

`interface-requirements-audit.csv` is the machine-readable report. `status_before` describes the audited 2.0 behavior, while `status_after` describes this release. “Implemented” means source behavior exists and the cited checks apply; it does not imply every external integration has been activated against a real account.

## Changes that matter

The student profile now has structured education, experience, availability and portfolio fields. Students can save drafts, review readable step summaries, reopen previous steps and export their profile. Reopening invalidates later approvals without deleting applications or workflow data. Full original CV text is not retained by draft or submission storage.

C, C++ and C# previously shared an identifier. They are now distinct, with all 305 catalog technologies retained. Skill evidence lists its provenance and related repositories. Optional self-ratings are explicitly unverified and do not become a calculated mastery or hiring score. Learning roadmaps have saved milestones and optional proof links.

New GitHub projects include original starter files, tests, run instructions and a target learning plan; creation results and actual initialization commit counts are retained. No upstream source is copied. Repository stacks can be paged across all loaded repositories, missing commit counts can be fetched explicitly, and real fetched stars can be used for sorting. Discovery still caps at 100 repositories and automatic commit requests at 12; these limits remain visible.

Companies can be edited, removed or imported from a CSV with quoted/multiline fields. Job matching now uses published technology requirements and the selected locations, with unknown scores preserved. An optional company chart reflects fetched offers. Applications remain “opened” until the student marks them submitted; status changes record timestamps.

The automation workspace has a reusable Python inventory and independent dataset inventory. CSV and JSON become typed inputs, text stays text, and opaque binary files round-trip as metadata/base64. Uploaded files are limited to 500 KB each. Python tests accept sample inputs. Connections use touch-friendly checkboxes. Dependency graphs are validated on import/save/preflight, boxes can run with their ancestors, and completed/failed run history retains bounded outputs and named downloadable files.

Gmail boxes have recipient, subject, body and draft/send settings. Start requires a review for configured send actions. Sending remains an explicit external action; no email was sent during this audit. Gmail authorization can be inspected and locally disconnected. Re-testing an API connector with an empty key preserves its existing key only for the same allowed host. Secret values are not displayed or exported.

Mobile users have a visible sign-out control. Modal labels are associated with inputs, nodes can be moved with arrow keys, view hashes retain navigation, and stale-tab conflicts have a reload action. The development launcher starts frontend and backend together. A browser check confirmed API connectivity; outbound GitHub DNS was unavailable, so that boundary is reported rather than represented as working.

## Verification

Backend tests cover profile editing/drafts, role/state restrictions, technology identity, matching, progress persistence, graph validation, execution history, partial failures, binary and named output files, explicit Gmail confirmation, credential retention and original starter behavior. Provider calls and worker execution use isolated mocks in these tests.

Browser inspection used an **explicitly labeled local UI fixture**, excluded from the deliverable and production build, to traverse all seven profile steps and inspect the career dashboard, reusable skill editor, inventory placement, dataset preview/save, and navigation. Its fabricated account/test data do not demonstrate real login or provider connectivity. The real landing page separately confirmed that the combined local API is reachable; its GitHub request failed on environment DNS resolution.

No real OAuth account was connected, no GitHub repository was created, no email was sent, and no public deployment was performed. Run the live acceptance checklist in `GLASS_DEPLOYMENT.md` after adding credentials and provisioning the worker. Docker is unavailable in this execution environment.

## Deployment updates

Existing database migrations still apply. These additions use the existing owner-scoped workspace JSON, so no extra migration is needed beyond the 2.0 Glass migration. Back up existing state before deployment. The corrected taxonomy IDs are in both the server and public catalogs; earlier source versions remain preserved in the archive.

Install Python requirements into `.venv`, then run `npm run dev`: it now launches both the API (port 8000) and Vite. Activate `.env.deploy` settings for live sign-in. Production still uses `docker compose --env-file .env.deploy up --build -d` behind HTTPS.

Gmail workflow sending is optional and disabled unless configured by the student and confirmed at Start. A failed downstream box does not undo already-sent email or other completed external operations. Review the recorded run before retrying a partially completed workflow. Worker outputs are bounded; up to ten runs are retained within a 900 KB run-history budget. The whole workspace remains limited to 3 MB. General HTTP boxes remain read-only GET requests to operator-allowed hosts.
