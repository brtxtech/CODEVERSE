# Start CODEVERSE Glass

1. Use Node **22.12+**. Run `npm ci` and `npm run build`.
2. Copy `.env.deploy.example` to `.env.deploy` and fill your Supabase and domain settings.
3. Apply all `supabase/migrations` in order and enable GitHub OAuth in Supabase.
4. Run `docker compose --env-file .env.deploy up --build -d`.
5. Open through your HTTPS reverse proxy. The app binds to localhost port 8000.

Read **docs/GLASS_DEPLOYMENT.md** for OAuth callbacks, visitor-only signup, privileged role provisioning, Gmail, the separate isolated Python runner, and the live acceptance checklist. Optional services fail explicitly until configured. No credentials or default passwords are included.

The new default page is `index.html`. All original features and datasets remain in the archive. `docs/MERGE_MANIFEST.json` explains the merge; `preserved-release-candidate/` contains differing older source versions.

Release 2.1 adds profile drafts/editing, evidence and learning progress, company CSV import/editing, ranked offers, reusable automation inventories and persisted output files. Read `docs/INTERFACE_AUDIT.md` and `docs/interface-requirements-audit.csv`. After installing Python requirements into `.venv`, `npm run dev` starts both API and frontend.
