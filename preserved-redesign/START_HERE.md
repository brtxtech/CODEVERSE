# CODEVERSE — Career Readiness MVP

This release **adds** a working local-first Career Readiness Studio to the existing CODEVERSE 3D city, technology catalog, Supabase source and automation assets. It does not replace them.

## Run the new Career Readiness Studio (Python 3.11+)

```bash
cd codeverse
python3 -m venv .venv
source .venv/bin/activate
pip install -r services/api/requirements.txt
pip install pytest httpx
uvicorn services.api.main:app --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000/studio**. Open **http://127.0.0.1:8000/api/docs** for request schemas.

Try **sample profile → evaluate readiness** or upload your own TXT/PDF/DOCX CV. Paste any target job description. The studio shows skill claims, per-skill matches, suggested projects and an explainable score. CVs are not persisted by the new prototype server.

### Existing city (separate development process)

```bash
npm install
npm run dev
```

The city remains a Vite/Three.js app. This release does not yet wire the career-readiness API into the 3D geometry. That is a post-MVP integration task; see `docs/DELIVERY_PLAN.md`.

## Available API routes
- `POST /api/cv/extract` — upload file; structured CV technology claims
- `POST /api/jobs/parse` — identify technologies in a job description (review required)
- `POST /api/readiness/evaluate` — deterministic scored comparison
- `POST /api/projects/check` — acceptance-criteria checklist, not proof of completion
- `POST /api/github/public-scan` — public GitHub repo manifest inspection (internet access needed)
- `POST /api/github/static-evidence` — analyze supplied manifest excerpts
- `GET /api/taxonomy` — original technology catalog
- `GET /api/health` — explicit deployment status

## Tests

```bash
PYTHONPATH=. pytest -q tests_python
npm test
```

**Do not expose the Python API to the public internet.** This prototype has no user authentication, rate-limiting or multitenant policy layer. Read `docs/SECURITY_AND_LIMITATIONS.md` before use beyond local development.
