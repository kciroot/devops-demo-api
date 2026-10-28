#!/usr/bin/env bash
# Smoke test: exercises the real API after a deployment.
# Usage: scripts/smoke_test.sh [base_url]   (default http://localhost:8000)
set -euo pipefail

BASE="${1:-http://localhost:8000}"
fail() { echo "FAIL: $*" >&2; exit 1; }

echo "Smoke test against $BASE"

for i in $(seq 1 30); do
  curl -fsS "$BASE/ready" >/dev/null 2>&1 && break
  [ "$i" -eq 30 ] && fail "API not ready after 30 s"
  sleep 1
done
echo "ok  /ready"

curl -fsS "$BASE/health" | grep -q '"status":"ok"' || fail "/health"
echo "ok  /health"

created=$(curl -fsS -X POST "$BASE/api/v1/tasks" \
  -H 'Content-Type: application/json' \
  -d '{"title":"smoke test","description":"created by the pipeline"}')
id=$(echo "$created" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
echo "ok  POST   /api/v1/tasks -> id $id"

curl -fsS "$BASE/api/v1/tasks/$id" | grep -q '"smoke test"' || fail "GET task"
echo "ok  GET    /api/v1/tasks/$id"

curl -fsS -X PUT "$BASE/api/v1/tasks/$id" -H 'Content-Type: application/json' \
  -d '{"done":true}' | grep -q '"done":true' || fail "PUT task"
echo "ok  PUT    /api/v1/tasks/$id"

code=$(curl -s -o /dev/null -w '%{http_code}' -X DELETE "$BASE/api/v1/tasks/$id")
[ "$code" = "204" ] || fail "DELETE returned $code"
echo "ok  DELETE /api/v1/tasks/$id"

curl -fsS "$BASE/metrics" | grep -q 'http_requests_total' || fail "/metrics"
echo "ok  /metrics"

echo "Smoke test passed"
