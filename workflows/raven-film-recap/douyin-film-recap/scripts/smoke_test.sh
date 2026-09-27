#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
python -m compileall -q src
PYTHONPATH=src python scripts/generate_schemas.py >/dev/null
PYTHONPATH=src pytest -q
printf 'Smoke test passed.\n'
