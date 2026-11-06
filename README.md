# CODEVERSE Glass 2.1

A GitHub career workspace with glass repository stacks, a seven-step student profile, explainable skill coverage, repository recommendations, job tracking and a visual automation canvas.

**Start with [START_GLASS.md](START_GLASS.md).** Complete configuration and deployment instructions are in [docs/GLASS_DEPLOYMENT.md](docs/GLASS_DEPLOYMENT.md).

- Height represents default-branch commit counts; footprint represents GitHub stars.
- Visitor-only signup; privileged roles are operator-provisioned.
- 305 technologies and 58 curated reference repositories, also seeded into PostgreSQL.
- Real GitHub/Gmail operations require your OAuth configuration. Python executes only through the separate isolated worker.
- Original source, datasets, Grafana security monitoring and earlier career tools are preserved. See [docs/MERGE_MANIFEST.json](docs/MERGE_MANIFEST.json).

## Local development

Use Node >=22.12 and Python >=3.11.

```sh
npm ci
python3.10 -m venv .venv
.venv/bin/pip install -r services/api/requirements.txt pytest
# Start frontend and API together:
npm run dev
```

## Production

Apply migrations, configure Supabase GitHub OAuth and fill `.env.deploy`, then:

```sh
docker compose --env-file .env.deploy up --build -d
```

The service binds to localhost:8000; place it behind your HTTPS reverse proxy. Read the deployment guide before activating optional Gmail/runner integrations. No service credentials are included.

## Validation

```sh
npm test
npm run build
.venv/bin/python -m pytest -q tests_python tests_ops
```

The screenshot uses clearly labeled illustrative stacks. Live integrations and Docker runtime activation require your environment and are not represented as verified by local tests.

See [the interface audit](docs/INTERFACE_AUDIT.md) and [requirements CSV](docs/interface-requirements-audit.csv) for the 2.1 fixes and activation boundaries.
