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
# FQBN 예: arduino:renesas_uno:unor4wifi | arduino:avr:uno → 앞 두 토큰으로 코어 패키지 설치
CORE_REF="$(echo "$FQBN" | cut -d: -f1,2)"
if [[ -z "$CORE_REF" || "$CORE_REF" == "$FQBN" || "$CORE_REF" != *:* ]]; then
  echo "FQBN 형식 오류: $FQBN (예: arduino:avr:uno 또는 arduino:renesas_uno:unor4wifi)" >&2
  exit 1
fi
arduino-cli core install "$CORE_REF"
if [[ "$FQBN" == *"renesas"* ]]; then
  arduino-cli lib install "ArduinoMqttClient"
fi
# UNO R3 패널(CronusFarmPanel) — SD 카드 라이브러리
if [[ "$FQBN" == *"avr"* ]]; then
  arduino-cli lib install "SD"
fi

if [[ -z "$PORT" ]]; then
  PORT="$(arduino-cli board list | awk '/ttyACM/{print $1; exit}' || true)"
fi
if [[ -z "$PORT" ]]; then
  PORT="/dev/ttyACM0"
fi
echo "업로드 포트: $PORT"

arduino-cli compile -j 4 --fqbn "$FQBN" "$SKETCH_DIR"

# 업로드 직전: screen/minicom 등이 ttyACM 을 잡고 있으면 1200bps 터치 실패 → 점유 프로세스 종료
if [[ -e "$PORT" ]] && command -v fuser >/dev/null 2>&1; then
  echo "시리얼 점유 해제 시도: $PORT"
  sudo -n fuser -k "$PORT" 2>/dev/null || fuser -k "$PORT" 2>/dev/null || true
  sleep 1
fi

arduino-cli upload -p "$PORT" --fqbn "$FQBN" "$SKETCH_DIR"
echo "완료: compile + upload"
