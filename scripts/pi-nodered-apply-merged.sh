#!/bin/bash
# Pi에서 실행: 병합된 Node-RED export JSON을 Admin API(/<adminRoot>/flows)로 반영 (기존 flows 백업)
# - CronusFarm 기본: httpAdminRoot=/farm
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

# 본문은 export 그대로의 JSON 배열이므로 Admin API(/<adminRoot>/flows)에 그대로 POST 합니다.
# (httpAdminRoot가 바뀌면 여기 경로도 함께 바뀝니다.)
ADMIN_ROOT="${CRONUSFARM_ADMIN_ROOT:-/farm}"
URL="http://127.0.0.1:1880${ADMIN_ROOT}/flows"

# 재시작 직후(포트 열리기 전) 잠깐 실패할 수 있어 재시도합니다.
for i in $(seq 1 30); do
  if curl -sS -f -X POST "$URL" \
  -H 'Content-Type: application/json' \
  -d @"$MERGED" >/dev/null; then
    echo ""
    echo "Node-RED POST ${ADMIN_ROOT}/flows 완료 (배열 export)"
    exit 0
  fi
  sleep 1
done

echo "Node-RED POST 실패(재시도 30초 초과): $URL" >&2
exit 1
