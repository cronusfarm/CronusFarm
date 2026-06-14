#!/bin/bash
# Pi: MQTT 감시·장시간 offline 시 USB WiFi 프로비저닝 자동 복구
set -eu
ROOT="${HOME}/CronusFarm"
UNIT_SRC="$ROOT/deploy/systemd/cronusfarm-mqtt-watch.service"
UNIT_DST="/etc/systemd/system/cronusfarm-mqtt-watch.service"

if [[ ! -f "$UNIT_SRC" ]]; then
  echo "ERROR: 없음 $UNIT_SRC" >&2
  exit 1
fi

sudo cp -f "$UNIT_SRC" "$UNIT_DST"
sudo systemctl daemon-reload
sudo systemctl enable cronusfarm-mqtt-watch.service
sudo systemctl restart cronusfarm-mqtt-watch.service
systemctl is-active cronusfarm-mqtt-watch.service || true
echo "OK pi-enable-mqtt-watch.sh"
