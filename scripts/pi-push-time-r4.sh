#!/usr/bin/env bash
# Pi KST → R4 소프트 시계 (USB serial 우선, MQTT 폴백)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEVICE_ID="${CRONUSFARM_DEVICE_ID:-cronusfarm-01}"
API="${CRONUSFARM_R4_SERIAL_API_URL:-http://127.0.0.1:18767}"
HOST="${CRONUSFARM_MQTT_HOST:-127.0.0.1}"
PORT="${CRONUSFARM_MQTT_PORT:-1883}"
TOPIC="cronusfarm/${DEVICE_ID}/cmd"
PAYLOAD="rtc_local=$(date +%Y%m%d%H%M%S)"

if curl -fsS -m 5 -X POST "${API%/}/r4/cmd" \
  -H "Content-Type: application/json" \
  -d "{\"device_id\":\"${DEVICE_ID}\",\"payload\":\"${PAYLOAD}\"}" >/dev/null 2>&1; then
  echo "[ok] serial ${PAYLOAD}"
  exit 0
fi

if command -v mosquitto_pub >/dev/null 2>&1; then
  mosquitto_pub -h "$HOST" -p "$PORT" -t "$TOPIC" -m "$PAYLOAD" -q 1
  echo "[ok] mqtt ${TOPIC} <- ${PAYLOAD}"
  exit 0
fi

echo "[error] serial API + mosquitto_pub 모두 실패" >&2
exit 1
