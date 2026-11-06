# START HERE — CODEVERSE Secure Grafana Release

**Entry point:** `http://127.0.0.1:8000/secure` (after configuration).

This release preserves the earlier Vite/Three.js Codeverse source but adds a separately secured FastAPI-hosted portal. The old demo sliders and user-switching UI do not grant roles and are disabled in `CODEVERSE_SECURE_MODE=1`.

## Quick start

1. Create a Supabase project, configure **asymmetric JWT signing**, enable email auth and desired Google/GitHub providers.
2. Apply Supabase migrations, including `supabase/migrations/20261101000000_codeverse_security.sql`.
3. From `codeverse`, run `cp .env.security.example .env.security` and edit Supabase keys, issuer, Grafana administrator password and public URL.
4. Add `http://localhost:8000/secure` to Supabase Auth redirect allowlist. Configure TOTP MFA in Supabase before promoting security admins.
5. Run `./ops/setup_security.sh` (Docker Compose required).
6. Open CODEVERSE at `http://127.0.0.1:8000/secure`; use the registration form to select **Developer** or **Recruiter**. Administrator account promotion is privileged SQL only.
7. Open Grafana at `http://127.0.0.1:3000/d/codeverse-security` with the **separate Grafana administrator credentials** configured in `.env.security`.

See `README_SECURITY.md` for complete documentation, account permissions, limitations, MFA, metrics and production security gates. See `SECURITY_AUDIT.md` for the four role scenarios.

**Do not put `SUPABASE_SERVICE_ROLE_KEY` in browser code or public CI.** It stays server-side only. Do not publish the old Vite demo as if it were the authenticated portal.

**This archive is not already deployed:** Supabase credentials, migrations, OAuth provider setup, Grafana Docker boot and alert evaluation have to be configured in your environment. There are no included real user records or fake security events.
