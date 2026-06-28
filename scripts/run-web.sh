#!/usr/bin/env bash
# Bare-metal static SPA on $WEB_PORT. No backend required to serve it.
#   WEB_PORT=5500 scripts/run-web.sh
set -euo pipefail
cd "$(dirname "$0")/../front-end"

WEB_PORT="${WEB_PORT:-5500}"

# If something is already serving this port, don't crash with a Python traceback.
# Report it and exit cleanly — for `task web:open` the browser still opens to the
# already-running server, which is usually what you wanted anyway.
if lsof -nP -iTCP:"${WEB_PORT}" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "A server is already running on port ${WEB_PORT} — reusing it."
  echo "  → open   http://127.0.0.1:${WEB_PORT}/"
  echo "  → or stop it:   lsof -ti tcp:${WEB_PORT} | xargs kill"
  exit 0
fi

echo "Web → http://127.0.0.1:${WEB_PORT}"
exec python3 -m http.server "${WEB_PORT}"
