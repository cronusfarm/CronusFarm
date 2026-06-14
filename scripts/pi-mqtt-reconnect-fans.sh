#!/bin/bash
# MQTT 복구 + Fan OFF + RTC 동기 (tele 끊김·잘못된 RTC로 Fan ON 유지 시)
set -eu
ROOT="${HOME}/CronusFarm"
DEVICE="${CRONUSFARM_DEVICE_ID:-cronusfarm-01}"
BRIDGE="${CRONUSFARM_SQLITE_BRIDGE_URL:-http://127.0.0.1:18766}"
HOST="${CRONUSFARM_MQTT_HOST:-127.0.0.1}"
PORT="${CRONUSFARM_MQTT_PORT:-1883}"

log() { echo "[$(date +%H:%M:%S)] $*"; }

log "=== mosquitto ==="
sudo systemctl restart mosquitto
sleep 1

log "=== Node-RED (MQTT 127.0.0.1 재연결) ==="
sudo systemctl restart nodered
sleep 8

if [[ -f "$ROOT/scripts/pi-recover-r4-mqtt-rtc.sh" ]]; then
  log "=== R4 MQTT·RTC 복구 ==="
  bash "$ROOT/scripts/pi-recover-r4-mqtt-rtc.sh" || true
fi

log "=== Fan 4채널 수동 OFF (MQTT) ==="
for ch in fan_a1 fan_a2 fan_b1 fan_b2; do
  curl -fsS -m 8 -X POST "$BRIDGE/api/channel-action" \
    -H 'Content-Type: application/json' \
    -d "{\"device_id\":\"$DEVICE\",\"channel\":\"$ch\",\"action\":\"off\"}" \
    && log "  $ch off OK" || log "  WARN $ch"
  sleep 0.3
done

log "=== RTC 재동기 ==="
curl -fsS -m 15 -X POST "$BRIDGE/api/rtc/sync_to_device" \
  -H 'Content-Type: application/json' \
  -d "{\"device_id\":\"$DEVICE\"}" || true

log "=== tele 확인 (10s) ==="
timeout 10 mosquitto_sub -h "$HOST" -p "$PORT" -t "cronusfarm/${DEVICE}/tele" -C 1 -W 10 | head -c 400 || true
echo ""
log "=== 상태 ==="
curl -fsS -m 8 "$BRIDGE/api/time/status?device_id=$DEVICE" | python3 -m json.tool 2>/dev/null || true
log "완료"
