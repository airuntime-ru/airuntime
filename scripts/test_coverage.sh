#!/usr/bin/env bash
# Runs the backend test suite with coverage. Use this before every deploy/merge - see
# docs/testing-workflow.md for the full process (fixing failures, deciding what new tests to
# add based on the coverage gaps this prints).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Run from backend/ (not the repo root) so pydantic-settings doesn't pick up the repo root
# .env file, which holds frontend-only NEXT_PUBLIC_* vars that Settings rejects as unknown.
cd "$ROOT_DIR/backend"

pytest -c ../pytest.ini ../tests \
  --cov=src \
  --cov-report=term-missing \
  --cov-report=html \
  "$@"

echo ""
echo "==> HTML coverage report: $ROOT_DIR/backend/htmlcov/index.html"
