#!/usr/bin/env bash
# Pi에서 실행: SQLite 브리지·KV 저장 한 번에 자가진단
# 사용: bash ~/CronusFarm/scripts/pi-check-sqlite-kv.sh
set -euo pipefail
DB="${CRONUSFARM_SQLITE_PATH:-$HOME/.node-red/cronusfarm.sqlite}"
BR="${CRONUSFARM_SQLITE_BRIDGE_URL:-http://127.0.0.1:18766}"
echo "=== 1) health ==="
curl -sS "$BR/health" || { echo "FAIL: 브리지 안 뜸"; exit 1; }
echo ""
echo "=== 2) KV 테스트 INSERT (diag_kv_test=ok) ==="
code="$(curl -sS -o /dev/null -w '%{http_code}' -X POST "$BR/settings/kv" \
  -H 'Content-Type: application/json' \
  -d '{"device_id":"cronusfarm-01","key":"diag_kv_test","value":"ok"}')"
echo "HTTP $code (기대: 204)"
echo "=== 3) DB에서 확인 ==="
sqlite3 "$DB" "SELECT key,value,updated_at FROM settings_kv WHERE key='diag_kv_test';"
echo "=== 끝 (행이 나오면 브리지+DB OK. 대시보드만 안 되면 Node-RED 슬라이더→KV 노드 배선·Deploy 확인) ==="
