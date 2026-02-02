#!/usr/bin/env bash
set -euo pipefail

ENABLED=${1:-true}

curl -s -X POST http://localhost:5002/chaos/crash \
  -H "Content-Type: application/json" \
  -d "{\"enabled\": ${ENABLED}}" | python -m json.tool