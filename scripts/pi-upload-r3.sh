#!/bin/bash
# Pi에서 실행: UNO R3(패널) 업로드
# 사용:
#   ./pi-upload-r3.sh [/path/to/arduino/CronusFarmPanel] [/dev/ttyACM? 또는 /dev/serial/by-id/...]
set -euo pipefail

SKETCH_DIR="${1:-/home/dooly/CronusFarm/arduino/CronusFarmPanel}"
PORT_HINT="${2:-}"
FQBN="arduino:avr:uno"

if ! command -v arduino-cli >/dev/null 2>&1; then
  echo "arduino-cli 없음" >&2
  exit 1
fi

if [[ ! -d "$SKETCH_DIR" ]]; then
  echo "스케치 폴더 없음: $SKETCH_DIR" >&2
  exit 2
fi

pick_r3_port() {
  local want="${1:-}"
  if [[ -n "$want" ]]; then
    if [[ -L "$want" ]]; then
      readlink -f "$want"
      return 0
    fi
    echo "$want"
    return 0
  fi

  local p
  p="$(arduino-cli board list 2>/dev/null | grep -F "$FQBN" | head -n 1 | sed -E 's/[[:space:]].*$//')"
  if [[ -n "$p" ]]; then
    echo "$p"
    return 0
  fi

  if [[ -d /dev/serial/by-id ]]; then
    p="$(ls -1 /dev/serial/by-id/* 2>/dev/null | grep -Ei 'arduino|uno|usb-arduino' | head -n 1)"
    if [[ -n "$p" ]]; then
      readlink -f "$p"
      return 0
    fi
  fi

  p="$(ls -1 /dev/ttyACM* /dev/ttyUSB* 2>/dev/null | head -n 1)"
  echo "$p"
}

echo "SKETCH_DIR=$SKETCH_DIR"
echo "PORT_HINT=$PORT_HINT"

PORT="$(pick_r3_port "$PORT_HINT")"
if [[ -z "$PORT" || ! -e "$PORT" ]]; then
  echo "R3 포트를 찾지 못했습니다." >&2
  arduino-cli board list || true
  exit 3
fi
echo "PORT=$PORT"

arduino-cli core update-index >/dev/null
arduino-cli core install "arduino:avr" >/dev/null

OUT="/tmp/cf_r3_build"
rm -rf "$OUT"
mkdir -p "$OUT"

arduino-cli compile --fqbn "$FQBN" --output-dir "$OUT" "$SKETCH_DIR"
arduino-cli upload -p "$PORT" --fqbn "$FQBN" "$SKETCH_DIR"

echo "DONE"

