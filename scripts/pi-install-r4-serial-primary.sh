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
Environment=CRONUSFARM_INGEST_REPUBLISH_MQTT=0
EOF

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
