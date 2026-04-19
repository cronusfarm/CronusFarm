#!/bin/bash
# 라즈베리파이에서 직접 실행: 의존성 확인 후 컴파일·업로드
# 사용: ./pi-arduino-build.sh [SKETCH_DIR] [PORT]
# 예: ./pi-arduino-build.sh /home/dooly/CronusFarm/arduino/CronusFarm /dev/ttyACM0

set -euo pipefail

FQBN="${FQBN:-arduino:renesas_uno:unor4wifi}"
if [[ -n "${1:-}" ]]; then
  SKETCH_DIR="$1"
else
  SKETCH_DIR="$(cd "$(dirname "$0")/../arduino/CronusFarm" && pwd)"
fi
PORT="${2:-}"

if ! command -v arduino-cli >/dev/null 2>&1; then
  echo "arduino-cli가 없습니다. 설치: curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | sh" >&2
  exit 1
fi

arduino-cli version
arduino-cli core update-index
arduino-cli core install arduino:renesas_uno
arduino-cli lib install "ArduinoMqttClient"

if [[ -z "$PORT" ]]; then
  PORT="$(arduino-cli board list | awk '/ttyACM/{print $1; exit}' || true)"
fi
if [[ -z "$PORT" ]]; then
  PORT="/dev/ttyACM0"
fi
echo "업로드 포트: $PORT"

arduino-cli compile -j 4 --fqbn "$FQBN" "$SKETCH_DIR"
arduino-cli upload -p "$PORT" --fqbn "$FQBN" "$SKETCH_DIR"
echo "완료: compile + upload"
