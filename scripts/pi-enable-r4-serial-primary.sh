#!/usr/bin/env bash
# USB serial primary 활성화 (빠른 전환)
set -eu
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
bash "$ROOT/scripts/pi-install-r4-serial-primary.sh"
echo "펌웨어 secrets.h 에 CRONUSFARM_MQTT_ENABLE 0 후 pi-upload-r4.sh 실행 권장"
