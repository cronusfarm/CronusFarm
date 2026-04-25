#!/bin/bash
# Pi에서 실행: 병합된 Node-RED export JSON을 POST /admin/flows 로 반영 (기존 flows 백업)
# 사용: ./pi-nodered-apply-merged.sh /path/to/merged-deploy.json

set -eu
MERGED="${1:?첫 인자: 병합된 flows JSON 경로}"
if [[ ! -f "$MERGED" ]]; then
  echo "파일 없음: $MERGED" >&2
  exit 1
fi

TS="$(date +%s)"
if [[ -f ~/.node-red/flows.json ]]; then
  cp ~/.node-red/flows.json ~/.node-red/flows.cronusfarm-backup."$TS".json
  echo "백업: ~/.node-red/flows.cronusfarm-backup.$TS.json"
fi

# 본문은 export 그대로의 JSON 배열이므로 Admin API(/admin/flows)에 그대로 POST 합니다.
curl -sS -f -X POST http://127.0.0.1:1880/admin/flows \
  -H 'Content-Type: application/json' \
  -d @"$MERGED"
echo ""
echo "Node-RED POST /admin/flows 완료 (배열 export)"
