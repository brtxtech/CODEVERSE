# CODEVERSE — Your code has a skyline.

A responsive, interactive WebGL city generated from public GitHub repositories and recent public events. Built with Three.js, Vite, and deterministic data transformations. **Not a static mockup.**

## Quick start

Requires **Node.js 22+**.

```bash
npm install
npm run dev
```

Open the printed local URL, enter any **public GitHub username**, and click **GENERATE CITY**. Without an account the app uses a clearly marked, reproducible synthetic demo. Drag to orbit, scroll to zoom, click buildings, scrub/play timeline, and use **RECORD 12s VIDEO** or **PNG** to export.

For production:

```bash
npm run test
npm run build
npm run preview
```

## Publish on GitHub Pages

1. Push this project into a new public GitHub repository (e.g. `codeverse`). Ensure the default branch is `main`.
2. Go to **Settings → Pages → Build and deployment → Source: GitHub Actions**.
3. Optional: in **Settings → Secrets and variables → Actions → Variables**, add `CODEVERSE_USERNAME` with your GitHub handle. The scheduled workflow then refreshes a static **public** JSON snapshot every night. Otherwise visitors may enter their own username in the UI.
4. Push to `main`, or run the workflow manually. Publish your Pages URL, e.g. `https://YOUR_USERNAME.github.io/codeverse/`.

## Sharing on LinkedIn

1. Open the hosted site in Chrome (recommended for WebM), use a landscape desktop viewport, and click **RECORD 12s VIDEO**. Browser compatibility differs; Safari may record MP4 while Chrome may export WebM. If your LinkedIn upload requires MP4, convert WebM with `ffmpeg -i input.webm -c:v libx264 -pix_fmt yuv420p -movflags +faststart codeverse-linkedin.mp4`.
2. Upload the video **as a native LinkedIn video post** with a link to your live demo. LinkedIn feed posts do **not** embed arbitrary WebGL applications.
3. Sample caption:

   > I turned GitHub into a living 3D city. Every building represents a repository; its height reflects the project's scale and stars, and its color reveals its primary programming language. Recent public activity drives the energy of the streets. Built with Three.js and a deterministic data engine, then deployed automatically with GitHub Actions. Explore your own skyline: [YOUR_URL] #ThreeJS #OpenSource #SoftwareEngineering

## Architecture

```
GitHub REST API (public repos + recent public events)
      ↓
src/github.js / scripts/snapshot.mjs
      ↓
src/model.js (validation, event scoring, deterministic demo, time model)
      ↓
src/renderer.js (WebGL city, orbit, interactions, animated traffic)
      ↓
src/main.js (UI, loading, recording, replay)
      ↓
GitHub Pages + video export
```

## Technical caveats and scientific integrity

- Public GitHub Events API returns **recent public events only** (usually at most 90 days and at most 300 events per user); this is **not** the user's all-time contribution count. The UI correctly labels them **recent events**.
- The timeline replays *available event activity*. Repo positions and heights represent a **current** public repo snapshot, not historical GitHub states; during replay only building visibility and city energy evolve. It should **not** be presented as historical repository growth.
- Building height uses reported GitHub repo size and stargazers; no unsupported claim about code quality or contributions.
- Private activity, deleted repos, and full historical contribution calendars are **not** fetched.
- `demo` is **synthetic and explicitly labeled**; it is never presented as actual GitHub data.
- Unauthenticated API usage is rate limited; static snapshot via Action avoids repeated client requests for your own page. In-browser users can still enter another public username.
- Performance: displays up to 45–49 buildings and a capped set of animated elements; pixel ratio capped at 2. Mobile devices may have lower frame rates.
- MIT license applies to original CODEVERSE source; no code from the supplied `git-koi` repository is copied.

## Tests

`npm test` exercises username validation, determinism, transformations, timeline consistency, and color fallback. Manual browser smoke-testing is recommended after deploying, especially for WebGL, touch input, permissions, and recording MIME variants.

## Roadmap

Potential further work: complete commit-history backfill using authenticated GraphQL, contributions calendar, instanced geometry, GPU profiling, accessible non-WebGL fallback, server-side rendering of posters, deterministic CI video export, and full runtime integration tests.

**License:** MIT.

## Project campus explorer & technology dataset

The app provides a campus explorer for every public repository, plus three **clearly marked synthetic** example architectures (including AI Assistant Campus). Select a campus to see its technology-specific buildings and verified/demo connections. For real repositories, use **Scan public manifests** to inspect a bounded set of public dependency/configuration files. The scanner cannot prove mastery, completed project status, or exhaustive dependency discovery; it does not invent service relationships.

`data/technology-taxonomy.json` is a structured JSON taxonomy of 293 technology names with category, family, landmark, color and detection metadata. A copy at `public/technology-taxonomy.json` is downloadable from the in-app catalog. Missing detection rules for a technology mean the dataset catalogs it but the scanner cannot yet automatically recognize it.

### City visual metric rules

- **Height:** `4 + (maxHeight - 4) * sqrt(repoSizeKB / largestRepoSizeKB)`. Adjust maximum height in the UI; repository size is a proxy for volume, not objective project complexity.
- **Width/depth:** `2.4 + 1.75 * starInfluence * log1p(repoStars) / log1p(maxRepoStars)`. Adjust star influence in the UI. Widths are intentionally bounded to prevent overlapping neighboring buildings.
- **Green:** last public `pushed_at` is within the selected 7–180-day window.
- **Blue:** no known recent push, which does not establish that the project is finished.

The mapping is **relative within the loaded repository set**, and public event availability is limited by GitHub's APIs. The demo has simulated push dates and is labeled synthetic. The catalog is a knowledge base, not automatically discovered technologies from every account.


## Optional CV → Jobs → Repositories career module (user-supplied integration)

The added `supabase/` folder is the complete supplied pipeline, including schema and SQL functions, **179 seeded job profiles**, private CV storage and the `process-cv` Edge Function. The original interactive diagram is at `public/career-pipeline-architecture.html` and works **without** a database. The existing city and technology taxonomy continue working with no Supabase configuration.

1. Create a Supabase project and install Supabase CLI. Run `supabase link --project-ref YOUR_REF` and `supabase db push` from this project root. `supabase/seed.sql` only runs with local reset; import your real company/repository reference data separately.
2. Configure Edge Function secrets server-side: `supabase secrets set ANTHROPIC_API_KEY=...` and `supabase functions deploy process-cv`. Review the original `supabase/README.md` and privacy/security requirements before going live.
3. Copy `.env.example` to `.env`; set **only** `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` (a public client key). Restart Vite. Sign in by email from the Career Intelligence section and analyze a PDF or TXT CV.

**Security and accuracy:** The CV extractor sends the file to Anthropic through a server-side Edge Function. CVs contain personal data; do not advertise production readiness until you have assessed lawful basis, consent, deletion, retention, CORS, rate limits, accessibility, and privacy policy. Scores are heuristic matches, not guaranteed vacancies or hiring outcomes. Existing Supabase SQL and functions are supplied as received; deployment has **not** been audited or executed against a real Supabase project. Never use an Anthropic API key or Supabase service-role key in `VITE_` environment variables.


## Social automation + enterprise reliability (integrated from files-5.zip)

**Inside the app:** Open **04 / Automation & Reliability** and enter `OWNER/REPO` of any public GitHub repository. CODEVERSE loads available releases, failed GitHub Actions runs and open issues labeled `bug`, `incident`, `regression`, `critical`, or `security`. It prepares a draft LinkedIn announcement for each recent release; **no content is posted automatically**. Errors link to GitHub rather than asserting a root cause. The initial previews are explicitly synthetic.

**n8n:** Import `n8n/social-drafts.json` and `n8n/enterprise-errors.json` into your own n8n instance (also available in the browser as downloads). Replace `OWNER/REPO` in each HTTP Request node with the actual public repository. Activate schedules only after reviewing and testing. The workflows emit reviewable draft records and normalized failures, respectively; they do not auto-publish social posts or message private recipients. To publish on LinkedIn, add your own authorized publishing connector and a human approval gate. For monitoring private repos use properly scoped server-side n8n credentials, not client-side secrets.

**Supabase social sources (from upload):** `integrations/social-sources/social_scraper.py` collects public GitHub organization repositories/releases and optionally Slack messages accessible to your own bot into `social_items`. Apply `integrations/social-sources/social_schema.sql`, set `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` as GitHub Actions secrets, and opt into `.github/workflows/social-sources.yml` by setting `ENABLE_SOCIAL_COLLECTOR=true` in Actions variables. Slack sources require `SLACK_BOT_TOKEN` secret and `SLACK_CHANNEL_IDS` variable. The public anon key may **only select GitHub rows**, not Slack messages. Be sure your Slack bot is authorized to access the channels and your organization permits retention and processing. Do not run the uploaded `daily.yml` directly: it references a missing `scraper.py`; the integrated workflow replaces that broken path.

**Operational caveats:** Public GitHub API requests can be rate-limited or partially unavailable, and public Actions endpoints may be disabled. Repository `pushed_at` is not proof of a commit by the account owner. A workflow failure or labeled issue is not proof of an enterprise incident. Scanning data requires internet access. No n8n, Supabase, or social network credentials are bundled.

## First 20 developers pilot

See `pilot/README.md` for voluntary recruitment, completion criteria, evaluation, a privacy-preserving CSV template and local reporting (`python -m pilot.metrics pilot/journeys.csv`). **No real users have been recruited or evaluated by this release.**
