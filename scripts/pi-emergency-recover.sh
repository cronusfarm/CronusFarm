#!/usr/bin/env bash
# R4 USB tele 끊김·모니터 offline 긴급 복구 (Pi에서 실행)
set -eu
(set -o pipefail 2>/dev/null) && set -o pipefail || true
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
for f in "$ROOT"/scripts/*.sh; do tr -d '\r' <"$f" >"$f.lf" && mv "$f.lf" "$f"; chmod +x "$f"; done

log() { echo "[$(date +%H:%M:%S)] $*"; }

log "=== MQTT tele 재발행 ON (모니터용) ==="
sudo mkdir -p /etc/cronusfarm
sudo sed -i 's/CRONUSFARM_INGEST_REPUBLISH_MQTT=0/CRONUSFARM_INGEST_REPUBLISH_MQTT=1/' /etc/cronusfarm/r4-serial.env 2>/dev/null || true
if [[ -f /etc/systemd/system/cronusfarm-sqlite-bridge.service.d/30-r4-serial-cmd.conf ]]; then
  sudo sed -i 's/CRONUSFARM_INGEST_REPUBLISH_MQTT=0/CRONUSFARM_INGEST_REPUBLISH_MQTT=1/' \
    /etc/systemd/system/cronusfarm-sqlite-bridge.service.d/30-r4-serial-cmd.conf || true
fi
sudo systemctl restart cronusfarm-sqlite-bridge.service

log "=== R4 펌웨어 업로드 ==="
bash "$ROOT/scripts/pi-upload-r4.sh"

log "=== 부팅 120s (시리얼 tele) ==="
sleep 120
sudo systemctl restart cronusfarm-r4-serial.service
sleep 5

log "=== RTC ==="
CRONUSFARM_R4_CMD_TRANSPORT=serial bash "$ROOT/scripts/pi-mqtt-publish-rtc-to-r4.sh" || true

log "=== 상태 ==="
curl -fsS "http://127.0.0.1:18766/api/time/status?device_id=cronusfarm-01" || true
echo
journalctl -u cronusfarm-r4-serial -n 8 --no-pager
log "DONE"
