#!/bin/bash
# 개발·점검: 전 채널 수동 ON (ui_<ch>=1) — 일회성 릴레이 테스트
set -euo pipefail

DEVICE="${1:-cronusfarm-01}"
BRIDGE_URL="${CRONUSFARM_SQLITE_BRIDGE_URL:-http://127.0.0.1:18766}"
HOST="${CRONUSFARM_MQTT_HOST:-127.0.0.1}"
PORT="${CRONUSFARM_MQTT_PORT:-1883}"

echo "[force-on] device=$DEVICE"
curl -fsS -m 30 "${BRIDGE_URL}/api/device/force_all_on?device_id=${DEVICE}" | head -c 500
echo

sleep 2
echo "[force-on] tele (S: 출력 확인):"
timeout 8 mosquitto_sub -h "$HOST" -p "$PORT" -t "cronusfarm/${DEVICE}/tele" -C 1 -W 8 || true
echo
echo "[force-on] done — 60분 후 홀드 만료·스케줄 복귀 가능. AUTO 복귀: pi-mqtt-force-all-auto.sh"
