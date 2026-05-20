#!/usr/bin/env bash
set -euo pipefail
curl -s -m 90 -X POST http://127.0.0.1:11434/api/generate \
  -H 'Content-Type: application/json' \
  -d '{"model":"gemma:2b","prompt":"한국어 한 문장: 서울 천호동 농장 상태","stream":false,"options":{"num_predict":60}}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('response','').strip()[:300])"
