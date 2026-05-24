#!/usr/bin/env bash
# MQTT farm 채널로 롤백 (USB 데몬 중지, 브리지 cmd→mosquitto_pub)
set -eu
(set -o pipefail 2>/dev/null) && set -o pipefail || true

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BRIDGE_DROPIN="/etc/systemd/system/cronusfarm-sqlite-bridge.service.d/30-r4-serial-cmd.conf"
SERIAL_UNIT="cronusfarm-r4-serial.service"

echo "[rollback-mqtt] serial daemon 중지"
sudo systemctl stop "$SERIAL_UNIT" 2>/dev/null || true
sudo systemctl disable "$SERIAL_UNIT" 2>/dev/null || true
sudo rm -f /run/cronusfarm/r4-upload.lock
sudo rm -f "$BRIDGE_DROPIN"
sudo systemctl daemon-reload
sudo systemctl restart cronusfarm-sqlite-bridge.service 2>/dev/null || true

if [[ -f /etc/systemd/system/cronusfarm-mqtt-watch.service ]]; then
  sudo systemctl enable cronusfarm-mqtt-watch.service 2>/dev/null || true
  sudo systemctl start cronusfarm-mqtt-watch.service 2>/dev/null || true
fi

echo "[rollback-mqtt] 펌웨어 secrets.h: CRONUSFARM_MQTT_ENABLE 1 후 pi-upload-r4.sh"
echo "[rollback-mqtt] tele 확인: timeout 12 mosquitto_sub -h 127.0.0.1 -t cronusfarm/cronusfarm-01/tele -C 1 -W 10"
