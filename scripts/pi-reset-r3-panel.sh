#!/usr/bin/env bash
# R3 패널(2004) 펌웨어 재업로드 = 소프트 리셋
set -euo pipefail
ROOT="${CRONUS_ROOT:-$HOME/CronusFarm}"
export FQBN=arduino:avr:uno
exec bash "$ROOT/scripts/pi-arduino-build.sh" "$ROOT/arduino/CronusFarmPanel" /dev/ttyACM0
