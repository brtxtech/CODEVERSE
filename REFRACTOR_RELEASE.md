# CODEVERSE — Evidence-Centered Career Studio Refactor

## What changed

- `apps/studio/index.html` — replaces single-page CV demonstration with 12-screen responsive navigation, clickable skill evidence drawers, repository discovery/selection, role recommendations, vacancy viewer, readiness explanations and inspectable CSV pipeline stages.
- `services/api/core.py` — per-page CV skill evidence with excerpts, distinct Angular/AngularJS, 5G/6G and conservative claim-only confidence states.
- `services/api/main.py` — CV PDF page extraction, DOCX tables, character-spaced PDF normalization, public GitHub listing/analysis, curated role suggestions, consolidated evidence, and best-effort live job-provider endpoint.
- `services/api/github_client.py` — discovers organizations and users, handles pagination/rate errors, pins scanned manifests to a real default-branch SHA; never claims unproven authorship.
- `services/api/role_recommender.py` — deterministic job-role archetype recommendations. These are NOT employer listings or hiring probabilities.
- `data/technology-taxonomy.json`, `public/technology-taxonomy.json` — expanded telecom taxonomy: 5G, 5G Core, 5G NR, 6G, LTE etc.
- `src/renderer.js` — fixed oblique camera; page wheel scrolling no longer zooms 3D; clicking selects buildings.
- `src/github.js` — organization-specific endpoint support.
- `src/model.js` — preserve forks (labeled) rather than silently discarding them.
- `index.html`, `src/main.js` — removed manual size/activity sliders, replaced orbit/zoom instructions, added Career Studio navigation.
- `tests_python/test_refactor.py` — focused CV/telecom/role/navigation regressions.

## Start locally on macOS

Node.js 22 or newer recommended.

Terminal 1, inside `codeverse/`:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r services/api/requirements.txt
uvicorn services.api.main:app --host 127.0.0.1 --port 8000
```

Visit http://127.0.0.1:8000/studio. **Start here.**

Terminal 2, for the existing Three.js city:

```bash
npm install
npm run dev -- --host 127.0.0.1 --port 3000
```

Visit http://127.0.0.1:3000. The studio's 3D City screen can embed this local app after you load your GitHub repository list.

## Suggested real-user testing

1. Open `My CV`, upload your own text-based PDF/DOCX and review the extracted claims, excerpts and page numbers. You should see `5G` when your CV contains 5G. `6G` is only detected when actually stated.
2. Select `GitHub Repositories`, enter a public GitHub username or organization, discover repos, check desired repos, and choose `Analyze selected repositories`. The scanner is limited to manifests/configuration and does not prove authorship.
3. Click a skill in `Skills & Evidence` to view its CV and GitHub references. If no scan was performed, you will see **not analyzed**, not **low competence**.
4. Open `Career Explorer`: select a suggested role without pasting a target description.
5. Inspect the per-requirement `Career Readiness` score, related `Skill Gaps`, and suggested `Learning Projects`.
6. Open `Pipeline Studio` and select nodes to see actual session inputs and outputs; download CSV files.
7. Optionally request `Job Offers`. This needs a reachable public provider. If unavailable, CODEVERSE shows an explicit error and **does not fabricate offers**.

## Important unfinished integration work

This release is a **local prototype**, not a production deployment. The career studio has no production account/session isolation, no authenticated GitHub App OAuth flow, no proven commit ownership, no trusted automatic project-completion verification or automatic rescoring based on externally verified milestones. The embedded 3D city remains a separate Vite application. The old optional Supabase module is preserved but is not automatically connected to the new studio. Readiness scores are provisional and their heuristic confidence coefficients have not been calibrated using real data.

Do not upload real third-party personal data to a public deployment until authentication, erasure controls, tenancy isolation, processor agreements and security review are completed.

## Tests performed

- `PYTHONPATH=. python -m pytest -q tests_python` — **34 passed** (warnings in existing HTTPX fixture tests).
- `npm test` — **12 passed**.
- JavaScript syntax checks on `src/main.js`, `src/github.js`, `src/renderer.js`, and the studio inline script — passed.
- Playwright rendering of the HTML using `page.set_content` verified navigation between My CV, GitHub Repositories and Career Explorer (browser local HTTP navigation blocked by the sandbox administrator).
- Actual user-provided test CVs: `Final-CV-11.pdf` and bilingual internship CV parsed locally; 5G recognized in both, 5G Core recognized where present. The original PDF's character-spaced text is repaired heuristically and flagged for review. Neither file is included in this ZIP.
- Vite production build and network-based GitHub/provider calls **not verified** in this sandbox; npm dependency installation timed out.
