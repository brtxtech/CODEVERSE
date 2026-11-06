# CODEVERSE — GitHub-first user onboarding + CI/CD

## New default experience

Start with `npm install && npm run dev` (Node.js 22.12+ recommended), then open **http://localhost:5173/** or the actual Vite URL. The landing page is **Introduce your GitHub link**, and after a successful public GitHub lookup, it shows:

1. Three.js 3D city with one visible building per available repository (scene capacity ~40; result metadata limited to first 64 repos).
2. Public repo list with language, stars, fork markings and GitHub links.
3. Technology evidence grid with primary language signals; click **Check public dependency manifests** for bounded manifest detection (max 8 repos, 24 GitHub API calls).
4. Seven-step career journey at `./career-journey.html` (existing 7 sliders, CV evidence, roles, offers and readiness simulator).

The original cinematic city interface remains at `./city-explorer.html`. The FastAPI evidence studio remains at `http://127.0.0.1:8000/studio` when separately running `uvicorn services.api.main:app --port 8000`.

### How to demo

Use `https://github.com/octocat` or any public profile URL. The user can enter an organization URL too. When no network or API quota is available, **Preview demo** creates a city explicitly labeled synthetic. GitHub lookup uses the public REST API only and never accesses private repositories or authenticates as the user.

### Evidence validity

A GitHub primary language is only a **metadata signal**. A `package.json` dependency proves only that a file references that framework. Neither is a credible proficiency level, proof of authorship or skill mastery. This release deliberately shows **language metadata only** and **dependency/config signal** instead of fabricating a numeric level for Angular, Python etc. Repository URLs and source file names appear in expandable evidence sections.

### CI/CD

- `.github/workflows/ci.yml`: GitHub Actions Node 22 frontend unit test + Vite build + artifact, and Python 3.11 backend tests. Runs on push, pull request and manual dispatch.
- `.github/workflows/deploy-pages.yml`: after tests, builds and deploys static Vite frontend to GitHub Pages from the `main` branch. **Set GitHub Pages source to GitHub Actions**.
- For local frontend: `npm install`, `npm test`, `npm run build`. Backend: `pip install -r services/api/requirements.txt pytest httpx`, `python -m pytest -q tests_python tests_ops`.

The repository did **not** include a `package-lock.json`, so the workflows currently use `npm install`, not `npm ci`. Commit a generated lock file after running npm install on a connected machine, then switch CI to npm ci for reproducibility.

### Boundaries

- Public GitHub API has rate limits and might not return all repos; city uses up to 64 repositories with scene capacity lower than that.
- No private repos, OAuth, trusted skills scoring, production persistence or employer verification.
- The seven-slider journey is intentionally preserved as an interactive local prototype, with client-side completion logic, not server-enforced permissions.
- The automatic GitHub Pages release deploys **static frontend only**, not FastAPI or Supabase services.
- The old project `README.md` describes older navigation and may include now-outdated screenshots; this document is authoritative for the GitHub-first release.
