#!/usr/bin/env bash
# secrets.h 에 HTTP tele 백업 상수가 없으면 추가 (기존 MQTT_HOST 기준)
set -euo pipefail
SECRETS="${1:-$HOME/CronusFarm/arduino/CronusFarm/secrets.h}"
if [[ ! -f "$SECRETS" ]]; then
  echo "secrets.h 없음: $SECRETS" >&2
  exit 1
fi
if grep -q 'BRIDGE_HTTP_HOST' "$SECRETS"; then
  echo "OK: BRIDGE_HTTP_* already in secrets.h"
  exit 0
fi
MQTT_IP=$(grep -E '^#define MQTT_HOST' "$SECRETS" | head -1 | sed -E 's/.*"([^"]+)".*/\1/')
MQTT_IP="${MQTT_IP:-192.168.60.222}"
cat >>"$SECRETS" <<EOF

// HTTP tele 백업 (MQTT 실패 시)
#define BRIDGE_HTTP_HOST "${MQTT_IP}"
#define BRIDGE_HTTP_PORT 80
#define BRIDGE_HTTP_PATH "/farm/cronusfarm-sqlite/ingest/tele"
#define CRONUS_HTTP_TELE_BACKUP 1
EOF
echo "OK: appended HTTP backup defines to $SECRETS"
