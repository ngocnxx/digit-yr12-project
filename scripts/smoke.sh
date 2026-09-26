#!/usr/bin/env bash
# API smoke test — drives the whole F1 flow over HTTP and checks status codes.
# Works against bare-metal or Docker; point it with API_BASE.
#   API_BASE=http://127.0.0.1:5050 scripts/smoke.sh
set -euo pipefail

API_BASE="${API_BASE:-http://127.0.0.1:5050}"
EMAIL="smoke+$(date +%s)@test.nz"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
pass() { printf '  \033[32mok\033[0m   %s\n' "$1"; }
fail() { printf '  \033[31mFAIL\033[0m %s\n' "$1"; exit 1; }

echo "Smoke test → $API_BASE"

code=$(curl -s -o /dev/null -w '%{http_code}' "$API_BASE/api/health")
[ "$code" = 200 ] && pass "health 200" || fail "health $code"

curl -s -X POST "$API_BASE/api/auth/signup" -H 'Content-Type: application/json' \
  -d "{\"name\":\"Smoke\",\"email\":\"$EMAIL\",\"password\":\"secret-pass\",\"yearLevel\":12}" > "$TMP/signup.json"
TOKEN=$(python3 -c "import json;print(json.load(open('$TMP/signup.json'))['token'])")
[ -n "$TOKEN" ] && pass "signup → token" || fail "signup"
AUTH=(-H "Authorization: Bearer $TOKEN")

curl -s -X POST "$API_BASE/api/subjects" "${AUTH[@]}" -H 'Content-Type: application/json' \
  -d '{"name":"Biology","emoji":"B","colour":"#10B981"}' > "$TMP/subject.json"
SID=$(python3 -c "import json;print(json.load(open('$TMP/subject.json'))['subject']['id'])")
[ -n "$SID" ] && pass "create subject (id=$SID)" || fail "create subject"

code=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$API_BASE/api/topics" "${AUTH[@]}" \
  -H 'Content-Type: application/json' \
  -d "{\"subjectId\":$SID,\"name\":\"Photosynthesis\",\"standardNumber\":\"AS 91156\"}")
[ "$code" = 201 ] && pass "create topic 201" || fail "create topic $code"

code=$(curl -s -o /dev/null -w '%{http_code}' -X PUT "$API_BASE/api/user/onboarding" "${AUTH[@]}")
[ "$code" = 200 ] && pass "complete onboarding 200" || fail "onboarding $code"

curl -s "$API_BASE/api/subjects" "${AUTH[@]}" > "$TMP/list.json"
N=$(python3 -c "import json;d=json.load(open('$TMP/list.json'));print(len(d['subjects'][0]['topics']))")
[ "$N" = 1 ] && pass "list subjects → 1 topic" || fail "list subjects (topics=$N)"

# Negative paths
code=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$API_BASE/api/subjects" "${AUTH[@]}" \
  -H 'Content-Type: application/json' -d '{"name":"Biology"}')
[ "$code" = 400 ] && pass "duplicate subject 400" || fail "duplicate subject $code"

code=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$API_BASE/api/auth/login" \
  -H 'Content-Type: application/json' -d "{\"email\":\"$EMAIL\",\"password\":\"wrong\"}")
[ "$code" = 401 ] && pass "bad login 401" || fail "bad login $code"

code=$(curl -s -o /dev/null -w '%{http_code}' "$API_BASE/api/subjects")
[ "$code" = 401 ] && pass "no-token 401" || fail "no-token $code"

echo "All smoke checks passed."
