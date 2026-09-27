#!/usr/bin/env bash
# Web smoke test — the nginx container on both of its ports, and CORS on the API.
#   :5500  the page for split-origin dev (API on :5050)
#   :8080  the "edge", shaped like CloudFront (one origin, production headers)
# Run it against the Docker stack (task up):
#   scripts/smoke-web.sh
set -euo pipefail

WEB="${WEB_BASE:-http://127.0.0.1:${WEB_PORT:-5500}}"
EDGE="${EDGE_BASE:-http://127.0.0.1:${EDGE_PORT:-8080}}"
API="${API_BASE:-http://127.0.0.1:${API_PORT:-5050}}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
pass() { printf '  \033[32mok\033[0m   %s\n' "$1"; }
fail() { printf '  \033[31mFAIL\033[0m %s\n' "$1"; exit 1; }
# header NAME FILE -> the header's value (case-insensitive name, CR stripped)
header() { grep -i "^$1:" "$2" | head -1 | cut -d' ' -f2- | tr -d '\r'; }

echo "Web smoke test → page $WEB, edge $EDGE, api $API"

# --- :5500, the page -------------------------------------------------------
code=$(curl -s -D "$TMP/h" -o "$TMP/b" -w '%{http_code}' "$WEB/")
[ "$code" = 200 ] && grep -q 'js/main.js' "$TMP/b" && pass "page / 200 (index.html)" || fail "page / $code"
[ "$(header Cache-Control "$TMP/h")" = "no-cache" ] && pass "page Cache-Control: no-cache" \
  || fail "page Cache-Control: $(header Cache-Control "$TMP/h")"

curl -s -D "$TMP/h" -o /dev/null "$WEB/js/main.js"
case "$(header Content-Type "$TMP/h")" in
  *javascript*) pass "js/main.js served as JavaScript" ;;
  *) fail "js/main.js Content-Type: $(header Content-Type "$TMP/h")" ;;
esac

curl -s -o "$TMP/b" "$WEB/no/such/page"
grep -q 'js/main.js' "$TMP/b" && pass "unknown path falls back to index.html" || fail "SPA fallback"

code=$(curl -s -o /dev/null -w '%{http_code}' "$WEB/api/health")
[ "$code" = 200 ] && pass "page port forwards /api/health (Codespaces path)" || fail "page /api/health $code"

# --- CORS on the API (split origin) ---------------------------------------
preflight() {
  curl -s -D - -o /dev/null -X OPTIONS "$API/api/subjects" \
    -H "Origin: $1" -H 'Access-Control-Request-Method: GET' \
    -H 'Access-Control-Request-Headers: authorization' | tr -d '\r' \
    | grep -i '^access-control-allow-origin:' | cut -d' ' -f2-
}
for origin in "http://127.0.0.1:5500" "http://localhost:5500"; do
  [ "$(preflight "$origin")" = "$origin" ] && pass "CORS preflight allows $origin" \
    || fail "CORS preflight for $origin"
done
[ -z "$(preflight "http://evil.example")" ] && pass "CORS preflight refuses http://evil.example" \
  || fail "CORS allowed http://evil.example"

# --- :8080, the edge (like CloudFront) ------------------------------------
code=$(curl -s -D "$TMP/h" -o /dev/null -w '%{http_code}' "$EDGE/")
[ "$code" = 200 ] && pass "edge / 200" || fail "edge / $code"
[ "$(header X-Content-Type-Options "$TMP/h")" = "nosniff" ] && [ "$(header X-Frame-Options "$TMP/h")" = "DENY" ] \
  && pass "edge nosniff + frame DENY" || fail "edge security headers"

# The CSP must carry the hash of the one inline <script> in the index.html on disk
want=$(python3 - "$ROOT/front-end/index.html" <<'EOF'
import base64, hashlib, re, sys
html = open(sys.argv[1], encoding="utf-8").read()
script = re.search(r"(?s)<script>(.*?)</script>", html).group(1)
print("sha256-" + base64.b64encode(hashlib.sha256(script.encode("utf-8")).digest()).decode())
EOF
)
csp=$(header Content-Security-Policy "$TMP/h")
case "$csp" in
  *"connect-src 'self'"*"'$want'"* | *"'$want'"*"connect-src 'self'"*) pass "edge CSP has connect-src 'self' and $want" ;;
  *) fail "edge CSP is '$csp' (wanted $want)" ;;
esac

code=$(curl -s -o /dev/null -w '%{http_code}' "$EDGE/no/such/file.js")
[ "$code" = 403 ] && pass "edge missing file 403 (like S3 via OAC)" || fail "edge missing file $code"

code=$(curl -s -o "$TMP/b" -w '%{http_code}' "$EDGE/api/health")
[ "$code" = 200 ] && grep -q '"ok"' "$TMP/b" && pass "edge /api/health 200, same origin" || fail "edge /api/health $code"

# A body just over Flask's 3 MiB limit must reach Flask (JSON 413), not stop at nginx (HTML 413)
python3 -c "print('{\"email\":\"x\",\"password\":\"' + 'a' * 3200000 + '\"}')" > "$TMP/big.json"
code=$(curl -s -D "$TMP/h" -o "$TMP/b" -w '%{http_code}' -X POST "$EDGE/api/auth/login" \
  -H 'Content-Type: application/json' --data-binary "@$TMP/big.json")
case "$code $(header Content-Type "$TMP/h")" in
  "413 application/json"*) pass "3.2 MB body reaches Flask: JSON 413" ;;
  *) fail "big body: $code $(header Content-Type "$TMP/h")" ;;
esac

echo "All web smoke checks passed."
