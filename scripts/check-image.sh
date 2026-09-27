#!/usr/bin/env bash
# Checks the API image is ready for AWS Lambda (the same image runs under
# docker compose and on Lambda via the Web Adapter). Needs the image built:
#   docker compose build api && scripts/check-image.sh
set -euo pipefail
cd "$(dirname "$0")/.."

pass() { printf '  \033[32mok\033[0m   %s\n' "$1"; }
fail() { printf '  \033[31mFAIL\033[0m %s\n' "$1"; exit 1; }

# The image compose built for the api service, run bare: no volume, no compose settings
IMAGE="${IMAGE:-$(docker compose config --images | grep -e '-api$' | head -1)}"
docker image inspect "$IMAGE" >/dev/null 2>&1 || fail "image $IMAGE not built (run: docker compose build api)"
run() { docker run --rm "$@"; }

echo "API image check (Lambda readiness) → $IMAGE"

[ "$(run "$IMAGE" whoami)" = appuser ] && pass "runs as appuser, not root" || fail "user"

run "$IMAGE" test -x /opt/extensions/lambda-adapter && pass "Lambda Web Adapter in /opt/extensions" \
  || fail "no /opt/extensions/lambda-adapter"

envs=$(run "$IMAGE" env)
for kv in AWS_LWA_PORT=5000 AWS_LWA_READINESS_CHECK_PATH=/api/health; do
  grep -qx "$kv" <<<"$envs" && pass "$kv" || fail "missing $kv"
done

found=$(run "$IMAGE" sh -c "find / -xdev \( -name '*.db' -o -name '.env' \) 2>/dev/null || true")
[ -z "$found" ] && pass "no .db or .env baked into the image" || fail "found: $found"

versions=$(run "$IMAGE" python -c "import gunicorn, boto3; print('gunicorn', gunicorn.__version__, 'boto3', boto3.__version__)") \
  && pass "$versions importable" || fail "gunicorn/boto3 missing"

# Fail closed: in production the dev key must stop the app from starting
out=$(run -e APP_ENV=production "$IMAGE" python -c "import app" 2>&1 || true)
grep -q "SECRET_KEY must be" <<<"$out" && pass "APP_ENV=production refuses the dev key" \
  || fail "production started with the dev key: $out"

key=$(python3 -c "import secrets; print(secrets.token_hex(32))")
run -e APP_ENV=production -e SECRET_KEY="$key" "$IMAGE" python -c "import app" \
  && pass "APP_ENV=production starts with a random 64-char key" || fail "production refused a strong key"

echo "All image checks passed."
