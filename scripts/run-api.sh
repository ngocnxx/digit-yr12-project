#!/usr/bin/env bash
# Bare-metal API (Flask) on $API_PORT. Creates the venv + DB on first run.
#   API_PORT=5050 WEB_PORT=5500 scripts/run-api.sh
set -euo pipefail
cd "$(dirname "$0")/../back-end"

API_PORT="${API_PORT:-5050}"
WEB_PORT="${WEB_PORT:-5500}"
# Project targets Python 3.13; override with PYTHON=... if yours is named otherwise.
PYTHON="${PYTHON:-python3.13}"

[ -d .venv ] || "$PYTHON" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -r requirements.txt

export SECRET_KEY="${SECRET_KEY:-dev-insecure-change-me}"
export DATABASE_PATH="${DATABASE_PATH:-navigator.db}"
export CORS_ORIGIN="${CORS_ORIGIN:-http://127.0.0.1:${WEB_PORT}}"

python -c "import db; db.init_db()"
echo "API → http://127.0.0.1:${API_PORT}  (CORS allows ${CORS_ORIGIN})"
exec python -m flask --app app run --debug --port "${API_PORT}"
