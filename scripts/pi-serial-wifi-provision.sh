#!/usr/bin/env bash
# Pi USB → R4 시리얼 WiFi 프로비저닝 (CronusFarm.ino wifi_set / wifi_clear)
#
# 사용:
#   bash ~/CronusFarm/scripts/pi-serial-wifi-provision.sh
#   bash ... --clear
#   CRONUSFARM_R4_SERIAL=/dev/ttyACM1 bash ...
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec python3 "$ROOT/scripts/pi-serial-wifi-provision.py" "$@"
