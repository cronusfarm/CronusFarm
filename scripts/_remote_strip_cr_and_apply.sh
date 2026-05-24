#!/usr/bin/env bash
set -euo pipefail
ROOT=/home/dooly/CronusFarm
for f in \
  "$ROOT/scripts/pi-mosquitto-apply-cronusfarm-conf.sh" \
  "$ROOT/scripts/pi-apply-nodered-cronusfarm-env.sh" \
  "$ROOT/scripts/pi-mqtt-stability-apply-all.sh"
do
  tr -d '\r' < "$f" > "$f.lf" && mv "$f.lf" "$f"
  chmod +x "$f"
done
if [ -f /tmp/cf-mqtt-sync/cronusfarm.conf ]; then
  mkdir -p "$ROOT/deploy/mosquitto/conf.d"
  tr -d '\r' < /tmp/cf-mqtt-sync/cronusfarm.conf > "$ROOT/deploy/mosquitto/conf.d/cronusfarm.conf"
fi
bash "$ROOT/scripts/pi-mqtt-stability-apply-all.sh"
