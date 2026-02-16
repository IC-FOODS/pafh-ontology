#!/usr/bin/env bash
set -euo pipefail

# Run FastAPI contract tests in an isolated container so host Python deps are irrelevant.
# Usage:
#   ./scripts/test_fastapi_contract.sh

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FASTAPI_DIR="${REPO_ROOT}/backend/fastapi"

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker is required but not found in PATH" >&2
  exit 1
fi

docker run --rm \
  -v "${FASTAPI_DIR}:/app" \
  -w /app \
  python:3.11-slim \
  sh -lc 'pip install --no-cache-dir -r requirements.txt >/tmp/pip.log && python -m unittest tests.test_capabilities_endpoint -v'
