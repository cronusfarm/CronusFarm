#!/usr/bin/env bash
#
# Pi 로컬 시각 → MQTT cmd → R4 RV3028 RTC (CronusFarm.ino `rtc_local=`)
# - Pi 타임존/ntp가 맞으면 R4 패널 날짜·시간이 Pi와 동일해짐
#
# 사용:
#   export CRONUSFARM_DEVICE_ID=cronusfarm-01   # 선택, 기본 cronusfarm-01
#   bash ./pi-mqtt-publish-rtc-to-r4.sh
#
# cron 예 (5분마다):
#   */5 * * * * /home/dooly/CronusFarm/scripts/pi-mqtt-publish-rtc-to-r4.sh
#

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

DEVICE_ID="${CRONUSFARM_DEVICE_ID:-cronusfarm-01}"
HOST="${CRONUSFARM_MQTT_HOST:-127.0.0.1}"
PORT="${CRONUSFARM_MQTT_PORT:-1883}"
TOPIC="cronusfarm/${DEVICE_ID}/cmd"
PAYLOAD="rtc_local=$(date +%Y%m%d%H%M%S)"

if ! command -v mosquitto_pub >/dev/null 2>&1; then
  echo "[error] mosquitto_pub 없음. apt install mosquitto-clients" >&2
  exit 1
fi

mosquitto_pub -h "$HOST" -p "$PORT" -t "$TOPIC" -m "$PAYLOAD" -q 1
echo "[ok] $TOPIC <- $PAYLOAD"
