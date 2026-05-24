#!/usr/bin/env bash
# R3 패널(Arduino Uno) 소프트 리셋만 — compile/upload 없음
#
# 사용:
#   ./pi-reset-r3-soft.sh
#   ./pi-reset-r3-soft.sh /dev/ttyACM0
#   ./pi-reset-r3-soft.sh /dev/serial/by-id/usb-Arduino__www.arduino.cc__...
#
set -euo pipefail

PORT_HINT="${1:-}"
FQBN="arduino:avr:uno"
WAIT_SEC="${CRONUSFARM_RESET_WAIT_SEC:-8}"

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
  p="$(arduino-cli board list 2>/dev/null | grep -F "$FQBN" | head -n 1 | sed -E 's/[[:space:]].*$//' || true)"
  if [[ -n "$p" ]]; then
    echo "$p"
    return 0
  fi

  if [[ -d /dev/serial/by-id ]]; then
    p="$(ls -1 /dev/serial/by-id/* 2>/dev/null | grep -E 'Arduino_Uno|Arduino__www\.arduino\.cc__Arduino_Uno' | grep -v 'UNO_WiFi_R4' | head -n 1 || true)"
    if [[ -n "$p" ]]; then
      readlink -f "$p"
      return 0
    fi
  fi

  # R4가 ACM1이면 패널은 보통 ACM0
  if [[ -e /dev/ttyACM0 ]]; then
    echo /dev/ttyACM0
    return 0
  fi
  p="$(ls -1 /dev/ttyACM* 2>/dev/null | grep -v ACM1 | head -n 1 || true)"
  echo "$p"
}

release_port() {
  local port="$1"
  [[ -n "$port" && -e "$port" ]] || return 0
  if command -v fuser >/dev/null 2>&1; then
    sudo -n fuser -k "$port" 2>/dev/null || fuser -k "$port" 2>/dev/null || true
    sleep 0.5
  fi
}

avr_dtr_reset() {
  local port="$1"
  if python3 -c "import serial" 2>/dev/null; then
    python3 - "$port" <<'PY'
import serial, sys, time
port = sys.argv[1]
ser = serial.Serial(port, 115200)
ser.dtr = False
time.sleep(0.05)
ser.dtr = True
time.sleep(0.05)
ser.close()
PY
    return 0
  fi
  stty -F "$port" 115200 cs8 -cstopb -parenb 2>/dev/null || true
  stty -F "$port" hupcl 2>/dev/null || true
}

if ! command -v arduino-cli >/dev/null 2>&1; then
  echo "arduino-cli 없음 (포트 탐지용)" >&2
  exit 1
fi

PRE="$(pick_r3_port "$PORT_HINT")"
if [[ -z "$PRE" || ! -e "$PRE" ]]; then
  echo "R3 패널 시리얼 포트를 찾지 못했습니다." >&2
  arduino-cli board list 2>/dev/null || true
  exit 2
fi

echo "R3 패널 소프트 리셋 (DTR, 업로드 없음)"
echo "PRE=$PRE"

release_port "$PRE"
avr_dtr_reset "$PRE"

echo "부팅 대기 ${WAIT_SEC}s…"
sleep "$WAIT_SEC"

arduino-cli board list 2>/dev/null | grep -F "$FQBN" || true
echo "완료: R3 패널 소프트 리셋 (펌웨어는 기존 플래시 그대로)"
