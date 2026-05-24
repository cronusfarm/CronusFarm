#!/usr/bin/env bash
set -euo pipefail
ROOT=/home/dooly/CronusFarm
SRC=/tmp/cf-mqtt-sync
cp "$SRC/cronusfarm_mqtt_watch.py" "$SRC/cronusfarm_mqtt_wifi_recover.py" "$ROOT/scripts/"
cp "$SRC/pi-apply-nodered-cronusfarm-env.sh" "$SRC/pi-install-mqtt-watch.sh" "$ROOT/scripts/"
cp "$SRC/cronusfarm-mqtt-watch.service" "$ROOT/deploy/systemd/"
for f in "$ROOT/scripts/cronusfarm_mqtt_watch.py" "$ROOT/scripts/cronusfarm_mqtt_wifi_recover.py" \
  "$ROOT/scripts/pi-apply-nodered-cronusfarm-env.sh" "$ROOT/scripts/pi-install-mqtt-watch.sh"; do
  tr -d '\r' < "$f" > "$f.lf" && mv "$f.lf" "$f"
done
chmod +x "$ROOT/scripts/cronusfarm_mqtt_watch.py" "$ROOT/scripts/cronusfarm_mqtt_wifi_recover.py" \
  "$ROOT/scripts/pi-install-mqtt-watch.sh"
bash "$ROOT/scripts/pi-apply-nodered-cronusfarm-env.sh"
bash "$ROOT/scripts/pi-install-mqtt-watch.sh"
