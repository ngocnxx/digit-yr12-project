#!/usr/bin/env bash
# Smoke test for the "database in S3" mode: two API copies share one database
# object in a local fake S3 (moto), like two AWS Lambda copies would.
#   docker compose --profile s3 up --build -d
#   scripts/smoke-s3.sh
set -euo pipefail

A="${API_A:-http://127.0.0.1:5061}"
B="${API_B:-http://127.0.0.1:5062}"
PASSWORD="smoke-pass-2026"
EMAIL="s3smoke+$(date +%s)@test.nz"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
pass() { printf '  \033[32mok\033[0m   %s\n' "$1"; }
fail() { printf '  \033[31mFAIL\033[0m %s\n' "$1"; exit 1; }
json() { python3 -c "import json,sys; d=json.load(open('$1')); print($2)"; }

echo "S3 smoke test -> copy A $A, copy B $B"

for url in "$A" "$B"; do
  for _ in $(seq 1 30); do
    [ "$(curl -s -o /dev/null -w '%{http_code}' "$url/api/health")" = 200 ] && break
    sleep 1
  done
  [ "$(curl -s -o /dev/null -w '%{http_code}' "$url/api/health")" = 200 ] && pass "health 200 on $url" || fail "health on $url"
done

# A student signs up on copy A ...
curl -s -X POST "$A/api/auth/signup" -H 'Content-Type: application/json' \
  -d "{\"name\":\"S3 Smoke\",\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\",\"yearLevel\":12}" > "$TMP/signup.json"
TOKEN=$(json "$TMP/signup.json" "d['token']")
[ -n "$TOKEN" ] && pass "sign up on A" || fail "sign up on A"
AUTH=(-H "Authorization: Bearer $TOKEN")

# ... and copy B can see them straight away (it downloads the new version)
code=$(curl -s -o /dev/null -w '%{http_code}' "$B/api/auth/me" "${AUTH[@]}")
[ "$code" = 200 ] && pass "copy B sees the new student" || fail "copy B /me $code"

curl -s -X POST "$A/api/subjects" "${AUTH[@]}" -H 'Content-Type: application/json' \
  -d '{"name":"Biology"}' > "$TMP/subject.json"
SID=$(json "$TMP/subject.json" "d['subject']['id']")
curl -s -X POST "$B/api/topics" "${AUTH[@]}" -H 'Content-Type: application/json' \
  -d "{\"subjectId\":$SID,\"name\":\"Photosynthesis\"}" > "$TMP/topic.json"
TID=$(json "$TMP/topic.json" "d['topic']['id']")
[ -n "$TID" ] && pass "subject on A, topic on B" || fail "subject/topic"

# 20 reviews at the same time, split across both copies. Every one must be saved.
for i in $(seq 1 20); do
  if [ $((i % 2)) = 0 ]; then url="$A"; else url="$B"; fi
  curl -s -o /dev/null -w '%{http_code}\n' -X POST "$url/api/log-review" "${AUTH[@]}" \
    -H 'Content-Type: application/json' -d "{\"topicId\":$TID}" > "$TMP/review-$i.code" &
done
wait
ok=$(cat "$TMP"/review-*.code | grep -c '^201$' || true)
[ "$ok" = 20 ] && pass "20 parallel reviews all saved (201)" || fail "only $ok of 20 reviews returned 201: $(cat "$TMP"/review-*.code | sort | uniq -c | tr '\n' ' ')"

curl -s "$A/api/subjects" "${AUTH[@]}" > "$TMP/list.json"
count=$(json "$TMP/list.json" "d['subjects'][0]['topics'][0]['reviewCount']")
rows=$(json "$TMP/list.json" "len(d['subjects'][0]['topics'][0]['reviews'])")
[ "$count" = 20 ] && [ "$rows" = 20 ] && pass "reviewCount 20 and 20 review rows (none lost)" \
  || fail "reviewCount=$count rows=$rows (expected 20 and 20)"

# 10 identical subjects at the same time: exactly one may be created
for i in $(seq 1 10); do
  if [ $((i % 2)) = 0 ]; then url="$A"; else url="$B"; fi
  curl -s -o /dev/null -w '%{http_code}\n' -X POST "$url/api/subjects" "${AUTH[@]}" \
    -H 'Content-Type: application/json' -d '{"name":"Chemistry"}' > "$TMP/subject-$i.code" &
done
wait
created=$(cat "$TMP"/subject-*.code | grep -c '^201$' || true)
dupes=$(cat "$TMP"/subject-*.code | grep -c '^400$' || true)
[ "$created" = 1 ] && [ "$dupes" = 9 ] && pass "10 identical subjects: one 201, nine 400" \
  || fail "identical subjects: created=$created duplicates=$dupes"

echo "All S3 smoke checks passed."
