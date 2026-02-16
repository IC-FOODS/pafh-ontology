#!/usr/bin/env bash
#
# smoke_caddy_routes.sh
# Quick end-to-end proxy routing checks for Caddy in production compose mode.
#
# Usage:
#   ./scripts/smoke_caddy_routes.sh
#   BASE_URL=https://knowbrow.example.com ./scripts/smoke_caddy_routes.sh
#
# Notes:
# - Defaults to BASE_URL=https://localhost and uses curl -k for local self-signed certs.
# - Assumes docker compose production stack is already running with Caddy enabled.

set -euo pipefail

BASE_URL="${BASE_URL:-https://localhost}"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

PASS=0
FAIL=0

request() {
  local method="$1"
  local path="$2"
  local outfile="$3"
  local statusfile="$4"
  curl -k -sS -X "$method" -o "$outfile" -w "%{http_code}" "${BASE_URL}${path}" > "$statusfile"
}

in_list() {
  local value="$1"
  shift
  for item in "$@"; do
    if [ "$value" = "$item" ]; then
      return 0
    fi
  done
  return 1
}

check_status_in() {
  local label="$1"
  local method="$2"
  local path="$3"
  shift 3
  local ok_statuses=("$@")
  local body="$TMP_DIR/${label}.body"
  local codef="$TMP_DIR/${label}.code"
  request "$method" "$path" "$body" "$codef"
  local code
  code="$(cat "$codef")"
  if in_list "$code" "${ok_statuses[@]}"; then
    echo "PASS ${label}: ${method} ${path} -> ${code}"
    PASS=$((PASS + 1))
  else
    echo "FAIL ${label}: ${method} ${path} -> ${code} (expected: ${ok_statuses[*]})"
    echo "Body preview: $(head -c 140 "$body" | tr '\n' ' ')"
    FAIL=$((FAIL + 1))
  fi
}

check_body_contains() {
  local label="$1"
  local needle="$2"
  local body="$TMP_DIR/${label}.body"
  if grep -q "$needle" "$body"; then
    echo "PASS ${label}: body contains '${needle}'"
    PASS=$((PASS + 1))
  else
    echo "FAIL ${label}: body missing '${needle}'"
    echo "Body preview: $(head -c 220 "$body" | tr '\n' ' ')"
    FAIL=$((FAIL + 1))
  fi
}

check_body_not_contains() {
  local label="$1"
  local needle="$2"
  local body="$TMP_DIR/${label}.body"
  if grep -q "$needle" "$body"; then
    echo "FAIL ${label}: body unexpectedly contains '${needle}'"
    echo "Body preview: $(head -c 220 "$body" | tr '\n' ' ')"
    FAIL=$((FAIL + 1))
  else
    echo "PASS ${label}: body does not contain '${needle}'"
    PASS=$((PASS + 1))
  fi
}

echo "Caddy route smoke test against ${BASE_URL}"
echo

# Django-routed paths (should not fall through to Caddy fallback)
check_status_in "admin_root" "GET" "/admin" 200 301 302 303
check_body_not_contains "admin_root" "KnowBrow API"

check_status_in "cms_root" "GET" "/cms" 200 301 302 303
check_body_not_contains "cms_root" "KnowBrow API"

# FastAPI-routed paths
check_status_in "health" "GET" "/health" 200
check_body_contains "health" "\"status\""
check_body_contains "health" "healthy"

check_status_in "docs_blocked" "GET" "/docs" 404
check_status_in "openapi_blocked" "GET" "/openapi.json" 404

# Internal endpoints must be blocked at proxy
check_status_in "internal_root_blocked" "GET" "/internal" 404
check_status_in "internal_query_blocked" "POST" "/internal/query" 404

echo
echo "Summary: PASS=${PASS} FAIL=${FAIL}"
if [ "$FAIL" -ne 0 ]; then
  exit 1
fi
