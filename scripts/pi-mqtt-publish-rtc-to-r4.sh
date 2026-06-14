#!/usr/bin/env bash
#
# Pi 로컬 시각 → cmd → R4 소프트웨어 시계 (CronusFarm.ino `rtc_local=` / `time_local=`)
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
exec bash "$ROOT/scripts/pi-push-time-r4.sh"
