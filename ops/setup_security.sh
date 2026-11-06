#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if ! command -v docker >/dev/null 2>&1; then echo "Docker CLI not found; install Docker Desktop or Docker Engine." >&2; exit 1; fi
if [ ! -f .env.security ]; then cp .env.security.example .env.security; echo 'Created .env.security — set your real Supabase keys and Grafana password first.'; exit 1; fi
if grep -q 'your-project\|your_server_only\|replace-with' .env.security; then echo 'Please edit .env.security: placeholder secrets remain.' >&2; exit 1; fi
mkdir -p ops/secrets
if [ ! -f ops/secrets/metrics_token ]; then python3 -c 'import secrets;print(secrets.token_urlsafe(48))' > ops/secrets/metrics_token; fi
chmod 600 ops/secrets/metrics_token .env.security
docker compose --env-file .env.security -f ops/compose.security.yml up -d --build
printf '\nCODEVERSE portal: http://127.0.0.1:8000/secure\nGrafana: http://127.0.0.1:3000 (credentials from .env.security)\nPrometheus: http://127.0.0.1:9090\n'
