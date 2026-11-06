# CODEVERSE Secure Grafana Edition

**For the current protected application, start with [START_SECURE_CODEVERSE.md](START_SECURE_CODEVERSE.md).** The instructions below describe the older demo/frontend and do not provide secure roles or Grafana.

---

# START HERE — CODEVERSE GitHub-first Onboarding

1. Use Node.js **22.12+**.
2. `npm install`
3. `npm run dev`
4. Open the URL printed by Vite (usually `http://localhost:5173/`).
5. Paste `https://github.com/<username>` and press **Generate my 3D city**.
6. The city, technology evidence and public repository links appear on the same page.
7. Continue through the preserved **7-step Career Journey** using the button at the bottom.

To see the original 3D explorer, open `/city-explorer.html`. To test without network, use **Preview demo**, which is clearly marked as synthetic.

## CI/CD

`.github/workflows/ci.yml` runs Node tests, Vite build, Python tests and uploads a build artifact. `.github/workflows/deploy-pages.yml` deploys the static frontend to GitHub Pages from `main` after frontend tests. Enable **Settings → Pages → Source: GitHub Actions**. This does not deploy the FastAPI backend.

`npm test` and `python -m pytest -q tests_python tests_ops` run locally.

**Verification in this environment:** 16 Node tests and 39 Python tests passed. Frontend npm install/build could not be run here because npm registry requests timed out. GitHub Actions workflows have been authored but are not yet executed on your GitHub repository.
