#!/bin/bash
# Start the lab dashboard locally on port 8080 with demo credentials.
# Lab mode: local object store under ./data, policy publish without MDM.
set -euo pipefail
cd "$(dirname "$0")"

PORT="${PORT:-8080}"
export LAB_MODE=1
export OBJECT_STORE_MODE=local
export DATA_DIR="${DATA_DIR:-./data}"
export INGEST_TOKEN="${INGEST_TOKEN:-lab-ingest-token}"
export DASHBOARD_USER="${DASHBOARD_USER:-governance}"
export DASHBOARD_PASSWORD="${DASHBOARD_PASSWORD:-lab}"
DEFAULT_BUDGETS='{"teams":{"Platform":100,"Field Apps":100},"default_person":50,"period":"month"}'
export LAB_BUDGETS="${LAB_BUDGETS:-$DEFAULT_BUDGETS}"

if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
  .venv/bin/pip install -q -r requirements.txt
fi
if [ ! -f frontend/dist/index.html ]; then
  npm --prefix frontend ci --no-audit --no-fund
  npm --prefix frontend run build
fi
mkdir -p "${DATA_DIR}"

echo "Lab dashboard: http://localhost:${PORT}/  (user ${DASHBOARD_USER}, password ${DASHBOARD_PASSWORD})"
echo "Hook ingest:   POST http://localhost:${PORT}/api/v1/hooks  (Bearer ${INGEST_TOKEN})"
echo "Seed data:     .venv/bin/python scripts/seed-lab.py   (or LAB_SEED=lab|scale ./run-local.sh)"
# LAB_SEED=lab seeds the small four-user lab; LAB_SEED=scale seeds 60 users and 400 tickets.
if [ -n "${LAB_SEED:-}" ]; then
  (sleep 3; BASE_URL="http://127.0.0.1:${PORT}" INGEST_TOKEN="${INGEST_TOKEN}" .venv/bin/python "scripts/seed-${LAB_SEED}.py" >/dev/null 2>&1) &
fi
exec .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port "${PORT}"
