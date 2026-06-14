#!/usr/bin/env bash
# 초기 스케줄표(cronusfarm_schedule_defaults.py) → DB 강제 덮어쓰기 + SCHED_JSON + 전 채널 AUTO
set -euo pipefail

DEVICE="${1:-cronusfarm-01}"
BRIDGE="${CRONUSFARM_SQLITE_BRIDGE_URL:-http://127.0.0.1:18766}"
HOST="${CRONUSFARM_MQTT_HOST:-127.0.0.1}"
PORT="${CRONUSFARM_MQTT_PORT:-1883}"

echo "=== [1/2] seed_defaults (force=true) → DB + MQTT SCHED_JSON ==="
curl -fsS -m 120 -X POST "${BRIDGE}/api/schedule/seed_defaults" \
  -H 'Content-Type: application/json' \
  -d "{\"device_id\":\"${DEVICE}\",\"force\":true}"
echo

echo "=== [2/2] force_all_auto → retain 정리 + FORCE_AUTO_ALL + builtin ==="
curl -fsS -m 120 "${BRIDGE}/api/device/force_all_auto?device_id=${DEVICE}"
echo

sleep 2
echo "=== tele (A=자동, S=출력) ==="
timeout 8 mosquitto_sub -h "$HOST" -p "$PORT" -t "cronusfarm/${DEVICE}/tele" -C 1 -W 8 2>/dev/null | head -c 400 || true
echo
echo "OK: 초기 스케줄표 강제 적용 완료"
