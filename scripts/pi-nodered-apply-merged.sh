#!/bin/bash
# Pi에서 실행: 병합된 Node-RED export JSON을 userDir flows.json 으로 반영 후 서비스 재시작
# - Admin API POST(/admin/flows)는 대용량·역프록시에서 502가 잦아 기본에서는 쓰지 않음
# - 핫 리로드만 필요하면: CRONUSFARM_NR_DEPLOY=api ./pi-nodered-apply-merged.sh ...
# - CronusFarm 기본: httpAdminRoot=/admin
# 사용: ./pi-nodered-apply-merged.sh /path/to/merged-deploy.json

set -eu
MERGED="${1:?첫 인자: 병합된 flows JSON 경로}"
if [[ ! -f "$MERGED" ]]; then
  echo "파일 없음: $MERGED" >&2
  exit 1
fi

TS="$(date +%s)"
NR_HOME="${HOME}/.node-red"
mkdir -p "$NR_HOME"
if [[ -f "${NR_HOME}/flows.json" ]]; then
  cp "${NR_HOME}/flows.json" "${NR_HOME}/flows.cronusfarm-backup.${TS}.json"
  echo "백업: ${NR_HOME}/flows.cronusfarm-backup.${TS}.json"
fi

deploy_via_api() {
  local ADMIN_ROOT="${CRONUSFARM_ADMIN_ROOT:-/admin}"
  pick_base() {
    if [[ -n "${CRONUSFARM_NODERED_PORT:-}" ]]; then
      echo "http://127.0.0.1:${CRONUSFARM_NODERED_PORT}"
      return
    fi
    tcp_open() {
      local port="$1"
      timeout 1 bash -c "true </dev/tcp/127.0.0.1/${port}" 2>/dev/null
    }
    for try in 1882 1880; do
      if tcp_open "$try"; then
        echo "http://127.0.0.1:${try}"
        return
      fi
    done
    echo "http://127.0.0.1:1880"
  }
  local BASE URL
  BASE="$(pick_base)"
  URL="${BASE}${ADMIN_ROOT}/flows"
  echo "Node-RED flows POST (api mode) -> $URL" >&2
  local i
  for i in $(seq 1 30); do
    if curl -sS -f --max-time 120 -X POST "$URL" \
      -H 'Content-Type: application/json' \
      -d @"$MERGED" >/dev/null 2>&1; then
      echo "Node-RED POST ${ADMIN_ROOT}/flows OK"
      return 0
    fi
    sleep 1
  done
  return 1
}

MODE="${CRONUSFARM_NR_DEPLOY:-json}"
case "$MODE" in
  api)
    if deploy_via_api; then
      exit 0
    fi
    echo "WARN: Admin POST 실패 -> flows.json + restart 로 대체" >&2
    ;;
  json|auto|*)
    ;;
esac

install -m 644 "$MERGED" "${NR_HOME}/flows.json"
if command -v systemctl >/dev/null 2>&1; then
  sudo -n systemctl restart nodered.service 2>/dev/null || true
fi
echo "OK: flows.json 반영 + nodered 재시작 (POST 생략, 502 회피). /ui 로 확인하세요." >&2
exit 0
