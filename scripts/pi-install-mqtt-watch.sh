#!/usr/bin/env bash
# Pi: MQTT 감시 systemd 설치·기동
set -euo pipefail
ROOT="${CRONUSFARM_ROOT:-$HOME/CronusFarm}"
UNIT_SRC="$ROOT/deploy/systemd/cronusfarm-mqtt-watch.service"
UNIT_DST=/etc/systemd/system/cronusfarm-mqtt-watch.service

if [[ ! -f "$ROOT/scripts/cronusfarm_mqtt_watch.py" ]]; then
  echo "missing $ROOT/scripts/cronusfarm_mqtt_watch.py"
  exit 1
fi
chmod +x "$ROOT/scripts/cronusfarm_mqtt_watch.py" \
  "$ROOT/scripts/cronusfarm_mqtt_wifi_recover.py" 2>/dev/null || true

if [[ -f "$UNIT_SRC" ]]; then
  sudo cp "$UNIT_SRC" "$UNIT_DST"
  sudo sed -i "s|/home/dooly/CronusFarm|$ROOT|g" "$UNIT_DST" 2>/dev/null || true
  sudo sed -i "s|/home/pi/CronusFarm|$ROOT|g" "$UNIT_DST" 2>/dev/null || true
fi

if [[ -f /etc/cronusfarm/nodered-telegram.env ]]; then
  sudo sed -i 's/\r$//' /etc/cronusfarm/nodered-telegram.env
else
  echo "WARN: /etc/cronusfarm/nodered-telegram.env 없음 — 텔레그램 알림 비활성"
  echo "  scripts/pi-install-nodered-telegram-env.sh 실행 후 재시작"
fi

sudo systemctl daemon-reload
sudo systemctl enable cronusfarm-mqtt-watch.service
sudo systemctl restart cronusfarm-mqtt-watch.service
systemctl is-active cronusfarm-mqtt-watch.service
journalctl -u cronusfarm-mqtt-watch.service -n 5 --no-pager
