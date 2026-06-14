#!/usr/bin/env bash
# R4 MQTT 복구 → RTC 동기 → force_all_auto → RTC 타이머 설치
set -eu
(set -o pipefail 2>/dev/null) && set -o pipefail || true

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEVICE_ID="${CRONUSFARM_DEVICE_ID:-cronusfarm-01}"
WAIT_ONLINE_SEC="${CRONUSFARM_WAIT_ONLINE_SEC:-180}"
SKIP_R4_RESET="${CRONUSFARM_SKIP_R4_RESET:-0}"

log() { echo "[$(date +%H:%M:%S)] $*"; }

log "=== [1/5] R4 소프트 리셋 ==="
if [[ "$SKIP_R4_RESET" == "1" ]]; then
  log "SKIP (CRONUSFARM_SKIP_R4_RESET=1) — 업로드 직후 등"
  sleep 15
elif [[ -f "$ROOT/scripts/pi-reset-r4.sh" ]]; then
  if bash "$ROOT/scripts/pi-reset-r4.sh"; then
    log "R4 리셋 완료"
  else
    log "WARN: R4 리셋 실패 — MQTT 대기 계속"
  fi
else
  log "WARN: pi-reset-r4.sh 없음"
fi

log "=== [2/5] MQTT·tele 대기 (최대 ${WAIT_ONLINE_SEC}s) ==="
TELE_MAX_STALE_SEC="${CRONUSFARM_RECOVER_TELE_MAX_STALE_SEC:-90}"
online=0
deadline=$(( $(date +%s) + WAIT_ONLINE_SEC ))
while [[ $(date +%s) -lt $deadline ]]; do
  api_json=""
  api_json=$(curl -fsS -m 4 \
    "http://127.0.0.1:18766/api/time/status?device_id=${DEVICE_ID}" 2>/dev/null || true)
  if [[ -n "$api_json" ]]; then
  tele_stale=$(printf '%s' "$api_json" | python3 -c \
    "import sys,json; d=json.load(sys.stdin); print(int(d.get('tele_stale_sec') or 99999))" 2>/dev/null \
    || echo 99999)
  r4_on=$(printf '%s' "$api_json" | python3 -c \
    "import sys,json; d=json.load(sys.stdin); print('1' if d.get('r4_online') else '0')" 2>/dev/null \
    || echo 0)
  last_st=$(printf '%s' "$api_json" | python3 -c \
    "import sys,json; d=json.load(sys.stdin); print((d.get('last_status') or '').strip())" 2>/dev/null \
    || echo "")
  if [[ "$r4_on" == "1" && "$tele_stale" -lt "$TELE_MAX_STALE_SEC" ]]; then
    online=1
    log "api r4_online=true tele_stale=${tele_stale}s status=${last_st:-?}"
    break
  fi
  fi
  if timeout 12 mosquitto_sub -h 127.0.0.1 -p 1883 \
    -t "cronusfarm/${DEVICE_ID}/tele" -C 1 -W 10 >/dev/null 2>&1; then
    online=1
    log "mqtt tele 수신 OK"
    break
  fi
  st=$(timeout 3 mosquitto_sub -h 127.0.0.1 -p 1883 \
    -t "cronusfarm/${DEVICE_ID}/status" -C 1 -W 2 2>/dev/null || true)
  log "대기… status=${st:-none} tele_stale=${tele_stale:-?}s (retain online만으로는 통과 안 함)"
  sleep 5
done
if [[ "$online" != 1 ]]; then
  log "ERROR: R4 tele 없음/오래됨 — WiFi·MQTT·secrets.h·전원 확인 후 wifi_recover 재시도"
fi

log "=== [3/5] RTC 동기 ==="
bash "$ROOT/scripts/pi-mqtt-publish-rtc-to-r4.sh"
sleep 2
curl -fsS -m 15 -X POST "http://127.0.0.1:18766/api/rtc/sync_to_device" \
  -H 'Content-Type: application/json' \
  -d "{\"device_id\":\"${DEVICE_ID}\"}" || true
echo ""

log "=== [4/5] force_all_auto ==="
curl -fsS -m 120 \
  "http://127.0.0.1:18766/api/device/force_all_auto?device_id=${DEVICE_ID}" || true
echo ""

log "=== [5/5] RTC 5분 타이머 ==="
sudo bash "$ROOT/scripts/pi-install-mqtt-rtc-r4-timer.sh"

log "=== 최종 상태 ==="
curl -fsS -m 8 "http://127.0.0.1:18766/api/time/status?device_id=${DEVICE_ID}" \
  | python3 -m json.tool 2>/dev/null || true
timeout 5 mosquitto_sub -h 127.0.0.1 -p 1883 \
  -t "cronusfarm/${DEVICE_ID}/status" -C 1 -W 4 2>/dev/null || echo "status: timeout"
