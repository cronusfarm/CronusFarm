#!/usr/bin/env bash
# R4 USB 시리얼 primary 설치 (MQTT farm 채널은 선택 비활성)
set -eu
(set -o pipefail 2>/dev/null) && set -o pipefail || true

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_DIR="/etc/cronusfarm"
ENV_FILE="$ENV_DIR/r4-serial.env"
BRIDGE_DROPIN="/etc/systemd/system/cronusfarm-sqlite-bridge.service.d"
SERIAL_UNIT="cronusfarm-r4-serial.service"

log() { echo "[install-serial] $*"; }

SECRETS="$ROOT/arduino/CronusFarm/secrets.h"
if [[ -f "$SECRETS" ]]; then
  if grep -q 'CRONUSFARM_MQTT_ENABLE' "$SECRETS"; then
    sed -i 's/^#define CRONUSFARM_MQTT_ENABLE.*/#define CRONUSFARM_MQTT_ENABLE 0/' "$SECRETS" || true
    log "secrets.h: CRONUSFARM_MQTT_ENABLE 0"
  else
    printf '\n#define CRONUSFARM_MQTT_ENABLE 0\n' >>"$SECRETS"
    log "secrets.h: CRONUSFARM_MQTT_ENABLE 0 추가"
  fi
  bash "$ROOT/scripts/pi-ensure-secrets-http-backup.sh" "$SECRETS" 2>/dev/null || true
else
  log "WARN: secrets.h 없음 — example 복사 후 값 채우기"
fi

sudo mkdir -p "$ENV_DIR" "$BRIDGE_DROPIN"
if [[ ! -f "$ENV_FILE" ]]; then
  sudo cp "$ROOT/deploy/env/r4-serial.env.example" "$ENV_FILE"
  log "생성: $ENV_FILE (포트 수정 가능)"
fi

sudo cp "$ROOT/deploy/systemd/cronusfarm-r4-serial.service" \
  "/etc/systemd/system/$SERIAL_UNIT"
sudo tee "$BRIDGE_DROPIN/30-r4-serial-cmd.conf" >/dev/null <<EOF
[Service]
Environment=CRONUSFARM_R4_CMD_TRANSPORT=serial
Environment=CRONUSFARM_CMD_MQTT=0
Environment=CRONUSFARM_INGEST_REPUBLISH_MQTT=1
EOF
if grep -q '^CRONUSFARM_INGEST_REPUBLISH_MQTT=' "$ENV_FILE" 2>/dev/null; then
  sudo sed -i 's/^CRONUSFARM_INGEST_REPUBLISH_MQTT=.*/CRONUSFARM_INGEST_REPUBLISH_MQTT=1/' "$ENV_FILE"
else
  echo 'CRONUSFARM_INGEST_REPUBLISH_MQTT=1' | sudo tee -a "$ENV_FILE" >/dev/null
fi

sudo systemctl daemon-reload
sudo systemctl enable "$SERIAL_UNIT"
sudo systemctl restart cronusfarm-sqlite-bridge.service 2>/dev/null || true
sudo systemctl restart "$SERIAL_UNIT"

if systemctl is-active --quiet cronusfarm-mqtt-watch.service 2>/dev/null; then
  log "mqtt-watch 중지 (USB primary)"
  sudo systemctl stop cronusfarm-mqtt-watch.service || true
  sudo systemctl disable cronusfarm-mqtt-watch.service 2>/dev/null || true
fi

log "완료 — health: curl -s http://127.0.0.1:18767/health"
