#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
echo 'CODEVERSE local setup — no remote database changes'
PYTHON=${PYTHON:-python3}
if ! command -v "$PYTHON" >/dev/null 2>&1; then echo 'Python 3 not found'; exit 1; fi
if ! command -v node >/dev/null 2>&1; then echo 'Node.js missing (recommended >=22)'; exit 1; fi
NODE_MAJOR=$(node -p 'Number(process.versions.node.split(".")[0])')
if ((NODE_MAJOR<22)); then echo 'Node.js 22+ required for the recommended Vite setup'; exit 1; fi
"$PYTHON" -m venv .venv
. .venv/bin/activate
python -m pip install -r services/api/requirements.txt pytest
npm install
python tools/codeverse.py doctor
python tools/codeverse.py test
cat <<'EOF'

Run API (terminal 1):
  source .venv/bin/activate
  uvicorn services.api.main:app --host 127.0.0.1 --port 8000

Run 3D city (terminal 2):
  npm run dev -- --host 127.0.0.1 --port 3000

Visit http://127.0.0.1:3000 and http://127.0.0.1:8000/studio
For release readiness: python tools/codeverse.py status --with-tests
EOF
