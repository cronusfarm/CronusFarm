#!/usr/bin/env bash
# USB serial primary 복구: 데몬·tele·RTC·force_all_auto
set -eu
(set -o pipefail 2>/dev/null) && set -o pipefail || true

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEVICE_ID="${CRONUSFARM_DEVICE_ID:-cronusfarm-01}"
WAIT_SEC="${CRONUSFARM_WAIT_ONLINE_SEC:-120}"
TELE_MAX_STALE="${CRONUSFARM_RECOVER_TELE_MAX_STALE_SEC:-90}"

log() { echo "[$(date +%H:%M:%S)] $*"; }

log "=== MQTT tele 재발행 ON (모니터) ==="
sudo mkdir -p /etc/cronusfarm
if [[ -f /etc/cronusfarm/r4-serial.env ]]; then
  sudo sed -i 's/^CRONUSFARM_INGEST_REPUBLISH_MQTT=.*/CRONUSFARM_INGEST_REPUBLISH_MQTT=1/' \
    /etc/cronusfarm/r4-serial.env 2>/dev/null || true
fi
if [[ -f /etc/systemd/system/cronusfarm-sqlite-bridge.service.d/30-r4-serial-cmd.conf ]]; then
  sudo sed -i 's/^CRONUSFARM_INGEST_REPUBLISH_MQTT=.*/CRONUSFARM_INGEST_REPUBLISH_MQTT=1/' \
    /etc/systemd/system/cronusfarm-sqlite-bridge.service.d/30-r4-serial-cmd.conf 2>/dev/null || true
fi
sudo systemctl restart cronusfarm-sqlite-bridge.service 2>/dev/null || true

log "=== serial daemon 확인 ==="
if ! curl -fsS -m 3 http://127.0.0.1:18767/health >/dev/null 2>&1; then
  log "serial API 없음 — install 실행"
  bash "$ROOT/scripts/pi-install-r4-serial-primary.sh"
fi

log "=== R4 reboot cmd (펌웨어 지원 시) ==="
curl -sf -m 8 -X POST "http://127.0.0.1:18767/r4/cmd" \
  -H 'Content-Type: application/json' \
  -d '{"payload":"reboot=1"}' >/dev/null 2>&1 || true
sleep 12

SKIP_R4_RESET="${CRONUSFARM_SKIP_R4_RESET:-0}"
if [[ "$SKIP_R4_RESET" != "1" && -f "$ROOT/scripts/pi-reset-r4.sh" ]]; then
  log "=== R4 소프트 리셋 ==="
  bash "$ROOT/scripts/pi-reset-r4.sh" || log "WARN 리셋 실패"
  sleep 20
else
  sleep 5
fi

log "=== tele 대기 (브리지 API, 최대 ${WAIT_SEC}s) ==="
online=0
deadline=$(( $(date +%s) + WAIT_SEC ))
while [[ $(date +%s) -lt $deadline ]]; do
  api_json=$(curl -fsS -m 4 \
    "http://127.0.0.1:18766/api/time/status?device_id=${DEVICE_ID}" 2>/dev/null || true)
  if [[ -n "$api_json" ]]; then
    tele_stale=$(printf '%s' "$api_json" | python3 -c \
      "import sys,json; d=json.load(sys.stdin); print(int(d.get('tele_stale_sec') or 99999))" 2>/dev/null \
      || echo 99999)
    r4_on=$(printf '%s' "$api_json" | python3 -c \
      "import sys,json; d=json.load(sys.stdin); print('1' if d.get('r4_online') else '0')" 2>/dev/null \
      || echo 0)
    if [[ "$r4_on" == "1" && "$tele_stale" -lt "$TELE_MAX_STALE" ]]; then
      online=1
      log "OK tele_stale=${tele_stale}s"
      break
    fi
    log "대기… r4_online=$r4_on tele_stale=${tele_stale}s"
  fi
  sleep 5
done

if [[ "$online" != "1" ]]; then
  log "FAIL tele 미수신 — journalctl -u cronusfarm-r4-serial"
  exit 1
fi

if test -f "$ROOT/scripts/pi-mqtt-publish-rtc-to-r4.sh"; then
  log "=== RTC 동기 ==="
  CRONUSFARM_R4_CMD_TRANSPORT=serial bash "$ROOT/scripts/pi-mqtt-publish-rtc-to-r4.sh" || true
fi

if test -f "$ROOT/scripts/pi-mqtt-force-all-auto.sh"; then
  log "=== force_all_auto ==="
  CRONUSFARM_R4_CMD_TRANSPORT=serial bash "$ROOT/scripts/pi-mqtt-force-all-auto.sh" || true
fi

if test -f "$ROOT/scripts/pi-sync-schedules-serial.sh"; then
  log "=== DB → R4 SCHED_JSON (serial) ==="
  bash "$ROOT/scripts/pi-sync-schedules-serial.sh" || log "WARN SCHED sync 실패"
fi

log "DONE"
