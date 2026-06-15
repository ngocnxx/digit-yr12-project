#!/usr/bin/env bash
# Bare-metal static SPA on $WEB_PORT. No backend required to serve it.
#   WEB_PORT=5500 scripts/run-web.sh
set -euo pipefail
cd "$(dirname "$0")/../front-end"

WEB_PORT="${WEB_PORT:-5500}"
echo "Web → http://127.0.0.1:${WEB_PORT}"
exec python3 -m http.server "${WEB_PORT}"
