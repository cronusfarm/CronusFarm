#!/bin/bash
# cmd retain 제거 + 전 채널 AUTO + 스케줄 MQTT 동기화 (Node-RED UI 피드백 루프 회피용)
set -euo pipefail

DEVICE="${1:-cronusfarm-01}"
BRIDGE_URL="${CRONUSFARM_SQLITE_BRIDGE_URL:-http://127.0.0.1:18766}"
HOST="${CRONUSFARM_MQTT_HOST:-127.0.0.1}"
PORT="${CRONUSFARM_MQTT_PORT:-1883}"
TOPIC="cronusfarm/${DEVICE}/cmd"

echo "[force-auto] device=$DEVICE"

if command -v mosquitto_pub >/dev/null 2>&1; then
  echo "[force-auto] clear cmd retain"
  mosquitto_pub -h "$HOST" -p "$PORT" -t "$TOPIC" -r -n || true
  RTC=$(date +%Y%m%d%H%M%S)
  mosquitto_pub -h "$HOST" -p "$PORT" -t "$TOPIC" -m "rtc_local=${RTC}"
fi

echo "[force-auto] bridge API force_all_auto"
curl -fsS -m 120 "${BRIDGE_URL}/api/device/force_all_auto?device_id=${DEVICE}" || {
  echo "[force-auto] WARN: bridge API failed — mosquitto only" >&2
  if command -v mosquitto_pub >/dev/null 2>&1; then
    for ch in led_a1 led_a2 led_b1 led_b2 pump_a1 pump_a2 pump_b1 pump_b2 \
      fan_a1 fan_a2 fan_b1 fan_b2 pump_c1 pump_c2 pump_d1 pump_d2; do
      mosquitto_pub -h "$HOST" -p "$PORT" -t "$TOPIC" -m "auto_${ch}=1"
      sleep 0.08
    done
  fi
}

sleep 3
echo "[force-auto] tele sample:"
timeout 6 mosquitto_sub -h "$HOST" -p "$PORT" -t "cronusfarm/${DEVICE}/tele" -C 1 -W 6 || true

echo "[force-auto] done"
