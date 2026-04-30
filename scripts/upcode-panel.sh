#!/bin/bash
# Pi 셸용: UNO R3 패널(CronusFarmPanel) compile+upload — upcode.sh 와 동일 흐름, 보드만 AVR Uno
# 사용: ~/CronusFarm/scripts/upcode-panel.sh
#       ~/CronusFarm/scripts/upcode-panel.sh /dev/ttyACM1
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SKETCH="$ROOT/arduino/CronusFarmPanel"
BUILD="$ROOT/scripts/pi-arduino-build.sh"
# Trigorilla(Mega2560) 기본. R3 패널: FQBN=arduino:avr:uno
export FQBN="${FQBN:-arduino:avr:mega:cpu=atmega2560}"
if [[ ! -f "$BUILD" ]]; then
  echo "없음: $BUILD (CronusFarm 클론 경로 확인)" >&2
  exit 1
fi
if [[ ! -d "$SKETCH" ]]; then
  echo "없음: $SKETCH" >&2
  exit 1
fi
exec bash "$BUILD" "$SKETCH" "${1:-}"
