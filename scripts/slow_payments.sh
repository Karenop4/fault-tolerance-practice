#!/usr/bin/env bash
set -euo pipefail

SECONDS=${1:-20}

curl -s -X POST http://localhost:5003/chaos/latency \
  -H "Content-Type: application/json" \
  -d "{\"seconds\": ${SECONDS}}" | python -m json.tool