#!/bin/bash
# Pi 셸용: Windows 의 upcode.ps1 과 동일 역할(이 저장소에서 compile+upload)
# 사용: ~/CronusFarm/scripts/upcode.sh
#        ~/CronusFarm/scripts/upcode.sh /dev/ttyACM0
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SKETCH="$ROOT/arduino/CronusFarm"
BUILD="$ROOT/scripts/pi-arduino-build.sh"
export FQBN="${FQBN:-arduino:renesas_uno:unor4wifi}"
if [[ ! -f "$BUILD" ]]; then
  echo "없음: $BUILD (CronusFarm 클론 경로 확인)" >&2
  exit 1
fi
if [[ ! -d "$SKETCH" ]]; then
  echo "없음: $SKETCH" >&2
  exit 1
fi
exec bash "$BUILD" "$SKETCH" "${1:-}"
